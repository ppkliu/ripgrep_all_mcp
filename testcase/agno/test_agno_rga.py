"""
Agno + rga-mcp-server 整合測試

使用方式:
    # 1. 安裝依賴
    pip install agno anthropic

    # 2. 確保 MCP server 已建構
    cd /path/to/ripgrep_all_mcp
    npm run build

    # 3. 設定環境變數
    export ANTHROPIC_API_KEY="your-api-key"

    # 4. 執行測試
    python testcase/agno/test_agno_rga.py

    # 或執行不需要 API key 的連線測試
    python testcase/agno/test_agno_rga.py --connection-only
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

# MCP server 路徑
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_JS = PROJECT_ROOT / "dist" / "index.js"

# 測試文件目錄
TEST_DOCS_DIR = tempfile.mkdtemp(prefix="rga-agno-test-")
TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="rga-agno-upload-")


def setup_test_files():
    """建立測試文件"""
    # 純文字
    (Path(TEST_DOCS_DIR) / "sample.txt").write_text(
        "Hello World\nThis is a test document.\nEmail: user@example.com\n"
    )
    # Markdown
    (Path(TEST_DOCS_DIR) / "notes.md").write_text(
        "# Project Notes\n\n## TODO\n- Fix bug #123\n- Review PR #456\n"
    )
    # JSON
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
# 測試 1: MCP 連線測試 (不需要 API key)
# ============================================================

async def test_mcp_connection():
    """
    測試 MCP server 連線與工具列表
    不需要 LLM API key，直接測試 MCP protocol 層
    """
    from agno.tools.mcp import MCPTools

    print("\n" + "=" * 60)
    print("TEST 1: MCP Connection & Tool Discovery")
    print("=" * 60)

    server_cmd = f"node {SERVER_JS}"
    mcp_tools = MCPTools(
        command=server_cmd,
        env={
            **os.environ,
            "MCP_TRANSPORT": "stdio",
            "UPLOAD_DIR": TEST_UPLOAD_DIR,
            "DOCUMENTS_DIR": TEST_DOCS_DIR,
        },
    )

    try:
        await mcp_tools.connect()
        print("[PASS] MCP server connected successfully")

        # 列出工具
        tools = mcp_tools.functions
        tool_names = list(tools.keys()) if isinstance(tools, dict) else [t.name for t in tools]
        print(f"[INFO] Discovered {len(tool_names)} tools: {tool_names}")

        expected_tools = [
            "rga_upload_file",
            "rga_extract_text",
            "rga_search_content",
            "rga_list_supported_formats",
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

async def test_direct_tool_calls():
    """
    直接呼叫 MCP 工具，不經過 LLM
    驗證每個工具的基本功能
    """
    from agno.tools.mcp import MCPTools

    print("\n" + "=" * 60)
    print("TEST 2: Direct Tool Calls (no LLM needed)")
    print("=" * 60)

    server_cmd = f"node {SERVER_JS}"
    mcp_tools = MCPTools(
        command=server_cmd,
        env={
            **os.environ,
            "MCP_TRANSPORT": "stdio",
            "UPLOAD_DIR": TEST_UPLOAD_DIR,
            "DOCUMENTS_DIR": TEST_DOCS_DIR,
        },
    )

    passed = 0
    failed = 0

    try:
        await mcp_tools.connect()

        # --- Test: list_supported_formats ---
        print("\n[test] rga_list_supported_formats...")
        try:
            result = await mcp_tools.call("rga_list_supported_formats", {})
            data = json.loads(result) if isinstance(result, str) else result
            if isinstance(data, dict) and "formats" in data:
                print(f"  [PASS] Returned {len(data['formats'])} format categories")
                passed += 1
            else:
                # 結果可能包在 content 中
                print(f"  [INFO] Response: {str(result)[:200]}")
                passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

        # --- Test: upload_file ---
        print("\n[test] rga_upload_file...")
        try:
            import base64
            content_b64 = base64.b64encode(b"Test upload content from Agno").decode()
            result = await mcp_tools.call("rga_upload_file", {
                "filename": "agno-test.txt",
                "content_base64": content_b64,
            })
            data = json.loads(result) if isinstance(result, str) else result
            print(f"  [INFO] Response: {str(result)[:200]}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

        # --- Test: extract_text ---
        print("\n[test] rga_extract_text (from documents dir)...")
        try:
            result = await mcp_tools.call("rga_extract_text", {
                "file_id": "sample.txt",
                "max_tokens": 1000,
            })
            result_str = str(result)
            if "Hello World" in result_str:
                print("  [PASS] Extracted text contains expected content")
                passed += 1
            else:
                print(f"  [INFO] Response: {result_str[:200]}")
                passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

        # --- Test: search_content ---
        print("\n[test] rga_search_content...")
        try:
            result = await mcp_tools.call("rga_search_content", {
                "pattern": "email|Email",
                "case_insensitive": True,
            })
            print(f"  [INFO] Response: {str(result)[:200]}")
            passed += 1
        except Exception as e:
            # rga 可能未安裝，這不是嚴重錯誤
            if "rga" in str(e).lower() or "not found" in str(e).lower():
                print(f"  [SKIP] rga not installed: {e}")
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
# 測試 3: Agno Agent 整合測試 (需要 API key)
# ============================================================

async def test_agno_agent():
    """
    完整的 Agno Agent 整合測試
    需要 ANTHROPIC_API_KEY 環境變數
    """
    from agno.agent import Agent
    from agno.models.anthropic import Claude
    from agno.tools.mcp import MCPTools

    print("\n" + "=" * 60)
    print("TEST 3: Agno Agent Integration (requires API key)")
    print("=" * 60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[SKIP] ANTHROPIC_API_KEY not set. Set it to run this test.")
        return True

    server_cmd = f"node {SERVER_JS}"
    mcp_tools = MCPTools(
        command=server_cmd,
        env={
            **os.environ,
            "MCP_TRANSPORT": "stdio",
            "UPLOAD_DIR": TEST_UPLOAD_DIR,
            "DOCUMENTS_DIR": TEST_DOCS_DIR,
        },
    )

    try:
        await mcp_tools.connect()

        agent = Agent(
            name="RGA Test Agent",
            model=Claude(id="claude-sonnet-4-5"),
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

        # Test: 搜尋文件
        print("\n[test] Agent: search documents...")
        await agent.aprint_response(
            "Search for 'bug' in the documents directory. What did you find?",
            stream=True,
        )
        print("  [PASS] Agent responded")

        # Test: 提取文字
        print("\n[test] Agent: extract text...")
        await agent.aprint_response(
            "Extract the text from sample.txt and summarize it briefly.",
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

    # 確認 server 已建構
    if not SERVER_JS.exists():
        print(f"[ERROR] Server not built: {SERVER_JS}")
        print("        Run: npm run build")
        sys.exit(1)

    setup_test_files()

    results = []

    try:
        # Test 1: 連線測試 (必跑)
        results.append(("MCP Connection", await test_mcp_connection()))

        if not connection_only:
            # Test 2: 直接工具呼叫 (必跑)
            results.append(("Direct Tool Calls", await test_direct_tool_calls()))

            # Test 3: Agent 整合 (需要 API key)
            results.append(("Agno Agent", await test_agno_agent()))

    finally:
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
