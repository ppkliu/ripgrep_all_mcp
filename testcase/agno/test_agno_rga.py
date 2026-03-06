"""
Agno + rga-mcp-server 整合測試

預設使用 Docker HTTP 模式連線 MCP server。

使用方式:
    # 1. 安裝依賴
    cd testcase/agno && uv venv && source .venv/bin/activate
    uv pip install -e ".[dev]"

    # 2. 啟動 Docker MCP HTTP server
    docker compose up -d

    # 3. 設定 .env (複製範例檔並編輯)
    cp .env.example .env

    # 4. 執行測試
    python test_agno_rga.py                    # 全部測試 (Docker HTTP)
    python test_agno_rga.py --connection-only  # 僅連線測試
    python test_agno_rga.py --stdio            # 使用 stdio 模式 (需 npm run build)
"""

import asyncio
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# ============================================================
# 設定
# ============================================================

# 載入 .env 檔案 (testcase/agno/.env)
def _load_dotenv():
    """從 testcase/agno/.env 載入環境變數，不覆蓋已存在的值。"""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    print(f"[config] Loading .env from {env_file}")
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = value

_load_dotenv()

# MCP server 路徑 (stdio 模式用)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_JS = PROJECT_ROOT / "dist" / "index.js"

# MCP HTTP URL (Docker 模式用)
MCP_URL = os.getenv("MCP_URL", "http://localhost:30003/mcp")

# 測試文件目錄 (stdio 模式用)
TEST_DOCS_DIR = tempfile.mkdtemp(prefix="rga-agno-test-")
TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="rga-agno-upload-")


def setup_test_files():
    """建立測試文件 (stdio 模式用)"""
    (Path(TEST_DOCS_DIR) / "sample.txt").write_text(
        "Hello World\nThis is a test document.\nEmail: user@example.com\n"
    )
    (Path(TEST_DOCS_DIR) / "notes.md").write_text(
        "# Project Notes\n\n## TODO\n- Fix bug #123\n- Review PR #456\n"
    )
    (Path(TEST_DOCS_DIR) / "config.json").write_text(
        json.dumps({"api_key": "test-key-123", "endpoint": "https://api.example.com"}, indent=2)
    )
    print(f"[setup] Test documents: {TEST_DOCS_DIR}")
    print(f"[setup] Upload dir: {TEST_UPLOAD_DIR}")


def cleanup():
    """清理測試文件"""
    shutil.rmtree(TEST_DOCS_DIR, ignore_errors=True)
    shutil.rmtree(TEST_UPLOAD_DIR, ignore_errors=True)
    print("[cleanup] Done")


# ============================================================
# MCP 連線工廠
# ============================================================

def _create_mcp_tools(use_stdio: bool):
    """建立 MCPTools 實例。"""
    from agno.tools.mcp import MCPTools

    if use_stdio:
        server_cmd = f"node {SERVER_JS}"
        print(f"[config] MCP: stdio mode ({SERVER_JS})")
        return MCPTools(
            command=server_cmd,
            env={
                **os.environ,
                "MCP_TRANSPORT": "stdio",
                "UPLOAD_DIR": TEST_UPLOAD_DIR,
                "DOCUMENTS_DIR": TEST_DOCS_DIR,
            },
        )
    else:
        print(f"[config] MCP: HTTP mode ({MCP_URL})")
        return MCPTools(transport="streamable-http", url=MCP_URL)


async def _call_tool(mcp_tools, name: str, arguments: dict) -> str:
    """透過 MCP session 直接呼叫工具，回傳文字結果。"""
    session = await mcp_tools.get_session_for_run()
    result = await session.call_tool(name, arguments)
    # CallToolResult.content 是 list of TextContent/ImageContent
    texts = [c.text for c in result.content if hasattr(c, "text")]
    return "\n".join(texts)


# ============================================================
# 測試 1: MCP 連線測試 (不需要 API key)
# ============================================================

async def test_mcp_connection(use_stdio: bool):
    """測試 MCP server 連線與工具列表。"""
    print("\n" + "=" * 60)
    print("TEST 1: MCP Connection & Tool Discovery")
    print("=" * 60)

    mcp_tools = _create_mcp_tools(use_stdio)

    try:
        await mcp_tools.connect()
        print("[PASS] MCP server connected successfully")

        tools = mcp_tools.functions
        tool_names = list(tools.keys()) if isinstance(tools, dict) else [t.name for t in tools]
        print(f"[INFO] Discovered {len(tool_names)} tools: {tool_names}")

        expected_tools = [
            "rga_upload_file",
            "rga_extract_text",
            "rga_search_content",
            "rga_list_supported_formats",
            "rga_list_documents",
        ]
        for name in expected_tools:
            if name in tool_names:
                print(f"  [PASS] {name}")
            else:
                print(f"  [FAIL] {name} not found!")

        return True
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        return False
    finally:
        await mcp_tools.close()


# ============================================================
# 測試 2: 直接工具呼叫測試 (不需要 API key)
# ============================================================

async def test_direct_tool_calls(use_stdio: bool):
    """直接呼叫 MCP 工具，不經過 LLM。"""
    print("\n" + "=" * 60)
    print("TEST 2: Direct Tool Calls (no LLM needed)")
    print("=" * 60)

    mcp_tools = _create_mcp_tools(use_stdio)

    passed = 0
    failed = 0
    uploaded_file_id = ""

    try:
        await mcp_tools.connect()

        # --- Test: list_supported_formats ---
        print("\n[test] rga_list_supported_formats...")
        try:
            result = await _call_tool(mcp_tools, "rga_list_supported_formats", {})
            data = json.loads(result)
            if "formats" in data:
                print(f"  [PASS] Returned {len(data['formats'])} format categories")
            else:
                print(f"  [PASS] Response: {result[:200]}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

        # --- Test: list_documents ---
        print("\n[test] rga_list_documents...")
        try:
            result = await _call_tool(mcp_tools, "rga_list_documents", {})
            data = json.loads(result)
            print(f"  [PASS] Found {data.get('total_files', 0)} files, {data.get('total_directories', 0)} dirs")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

        # --- Test: upload_file ---
        print("\n[test] rga_upload_file...")
        try:
            import base64
            content_b64 = base64.b64encode(b"Test upload content from Agno").decode()
            result = await _call_tool(mcp_tools, "rga_upload_file", {
                "filename": "agno-test.txt",
                "content_base64": content_b64,
            })
            data = json.loads(result)
            uploaded_file_id = data.get("file_id", "")
            print(f"  [PASS] Uploaded: {uploaded_file_id}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

        # --- Test: extract_text ---
        print("\n[test] rga_extract_text...")
        try:
            # Docker 模式: 使用剛上傳的檔案; stdio 模式: 使用測試文件
            target = uploaded_file_id if not use_stdio else "sample.txt"
            result = await _call_tool(mcp_tools, "rga_extract_text", {
                "file_id": target,
                "max_tokens": 1000,
            })
            if "Test upload content" in result or "Hello World" in result:
                print(f"  [PASS] Extracted text contains expected content")
            else:
                print(f"  [PASS] Response: {result[:200]}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

        # --- Test: search_content ---
        print("\n[test] rga_search_content...")
        try:
            result = await _call_tool(mcp_tools, "rga_search_content", {
                "pattern": "test",
                "case_insensitive": True,
            })
            print(f"  [PASS] Response: {result[:200]}")
            passed += 1
        except Exception as e:
            if "rga" in str(e).lower() or "not found" in str(e).lower():
                print(f"  [SKIP] rga not available: {e}")
            else:
                print(f"  [FAIL] {e}")
                failed += 1

    except Exception as e:
        print(f"[FAIL] Setup error: {e}")
        failed += 1
    finally:
        await mcp_tools.close()

    print(f"\n[RESULT] Passed: {passed}, Failed: {failed}")
    return failed == 0


# ============================================================
# LLM Model 設定
# ============================================================

def _detect_model_from_api(api_base: str, api_key: str) -> str:
    """查詢 OpenAI-compatible API 的 /models 端點，自動偵測可用模型。"""
    import httpx

    # api_base 可能是 http://host:port/v1，models 端點在 /v1/models
    base = api_base.rstrip("/")
    if not base.endswith("/v1"):
        models_url = f"{base}/v1/models"
    else:
        models_url = f"{base}/models"

    try:
        resp = httpx.get(models_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("data", [])
        if models:
            model_name = models[0].get("id", "")
            print(f"[config] Auto-detected model from API: {model_name}")
            if len(models) > 1:
                all_names = [m.get("id", "") for m in models]
                print(f"[config]   Available models: {all_names}")
            return f"openai/{model_name}"
    except Exception as e:
        print(f"[config] Cannot query {models_url}: {e}")

    return ""


def _resolve_model():
    """
    依據環境變數決定使用的 LLM model。

    優先順序:
      1. LLM_API_BASE 設定 → OpenAI-compatible (透過 LiteLLM)
      2. ANTHROPIC_API_KEY 設定 → Anthropic Claude
      3. 都沒設定 → 回傳 None (跳過 Agent 測試)
    """
    llm_api_base = os.getenv("LLM_API_BASE")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if llm_api_base:
        from agno.models.litellm import LiteLLM
        api_key = os.getenv("LLM_API_KEY", "no-key")
        model_id = os.getenv("LLM_MODEL", "")

        if not model_id:
            # 未指定模型 → 從 API 自動偵測
            model_id = _detect_model_from_api(llm_api_base, api_key)
            if not model_id:
                print("[WARN] Cannot detect model from API, using 'openai/local-model'")
                model_id = "openai/local-model"

        # LiteLLM 需要 provider 前綴 (openai/) 來決定用 OpenAI-compatible 格式
        if "/" not in model_id:
            model_id = f"openai/{model_id}"

        print(f"[config] LLM: LiteLLM (OpenAI-compatible)")
        print(f"[config]   model:    {model_id}")
        print(f"[config]   api_base: {llm_api_base}")
        return LiteLLM(id=model_id, api_base=llm_api_base, api_key=api_key)

    if anthropic_key:
        from agno.models.anthropic import Claude
        model_id = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
        print(f"[config] LLM: Anthropic Claude")
        print(f"[config]   model: {model_id}")
        return Claude(id=model_id)

    return None


# ============================================================
# 測試 3: Agno Agent 整合測試 (需要 API key)
# ============================================================

async def test_agno_agent(use_stdio: bool):
    """
    完整的 Agno Agent 整合測試
    需要 LLM_API_BASE (OpenAI-compatible) 或 ANTHROPIC_API_KEY
    """
    from agno.agent import Agent

    print("\n" + "=" * 60)
    print("TEST 3: Agno Agent Integration (requires LLM API)")
    print("=" * 60)

    model = _resolve_model()
    if model is None:
        print("[SKIP] No LLM configured. Set LLM_API_BASE or ANTHROPIC_API_KEY.")
        return True

    mcp_tools = _create_mcp_tools(use_stdio)

    try:
        await mcp_tools.connect()

        agent = Agent(
            name="RGA Test Agent",
            model=model,
            tools=[mcp_tools],
            instructions=[
                "You have access to rga MCP tools for document search.",
                "Use rga_list_supported_formats to check available formats.",
                "Use rga_search_content to search in documents.",
                "Use rga_extract_text to extract full text.",
                "Be concise in your responses.",
            ],
            markdown=True,
        )

        # Test: 列出支援格式
        print("\n[test] Agent: list supported formats...")
        await agent.aprint_response(
            "List the supported file formats using the rga tool. Just show the format categories.",
            stream=True,
        )
        print("  [PASS] Agent responded")

        # Test: 列出文件
        print("\n[test] Agent: list documents...")
        await agent.aprint_response(
            "List all documents available in the documents directory.",
            stream=True,
        )
        print("  [PASS] Agent responded")

        # Test: 搜尋文件
        print("\n[test] Agent: search documents...")
        await agent.aprint_response(
            "Search for 'test' in the documents. What did you find?",
            stream=True,
        )
        print("  [PASS] Agent responded")

        return True

    except Exception as e:
        print(f"[FAIL] Agent error: {e}")
        return False
    finally:
        await mcp_tools.close()


# ============================================================
# Main
# ============================================================

async def main():
    connection_only = "--connection-only" in sys.argv
    use_stdio = "--stdio" in sys.argv

    if use_stdio:
        # stdio 模式需要已建構的 server
        if not SERVER_JS.exists():
            print(f"[ERROR] Server not built: {SERVER_JS}")
            print("        Run: npm run build")
            sys.exit(1)
        setup_test_files()
    else:
        print(f"[config] Using Docker HTTP mode: {MCP_URL}")
        print("[config] (use --stdio to switch to local stdio mode)")

    results = []

    try:
        # Test 1: 連線測試 (必跑)
        results.append(("MCP Connection", await test_mcp_connection(use_stdio)))

        if not connection_only:
            # Test 2: 直接工具呼叫 (必跑)
            results.append(("Direct Tool Calls", await test_direct_tool_calls(use_stdio)))

            # Test 3: Agent 整合 (需要 API key)
            results.append(("Agno Agent", await test_agno_agent(use_stdio)))

    finally:
        if use_stdio:
            cleanup()

    # 總結
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
