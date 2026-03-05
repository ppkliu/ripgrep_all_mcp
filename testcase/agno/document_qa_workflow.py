"""
Document QA Workflow — Agno Agent + MCP + LiteLLM

自動化文件問答測試流程:
  Phase 1: 透過 MCP 掃描 documents/ 下所有檔案路徑
  Phase 2: 提取文字、判斷 token 是否放入 context、生成問題、精煉摘要
  Phase 3: 建立文件摘要 Markdown 表格
  Phase 4: Agno Agent 逐一問答並記錄 tool calling
  Phase 5: 輸出帶時間戳的 QA 結果 Markdown

使用方式:
    # 1. 啟動 MCP Docker HTTP server
    docker compose -f docker-compose.http.yaml up -d

    # 2. 安裝依賴 + 設定 .env
    cd testcase/agno
    cp .env.example .env   # 編輯填入 LLM 設定
    uv pip install -e ".[dev]"

    # 3. 執行
    source .venv/bin/activate
    python document_qa_workflow.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import litellm

# ============================================================
# .env 載入
# ============================================================

def _load_dotenv():
    """從 testcase/agno/.env 載入環境變數，不覆蓋已存在的值。"""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = value

_load_dotenv()

# ============================================================
# Configuration
# ============================================================

MCP_URL = os.getenv("MCP_URL", "http://localhost:30003/mcp")
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "32000"))
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "")
QA_RESULTS_DIR = Path(__file__).parent / "qa_results"

# Supported document extensions
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".epub", ".odt",
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".pptx", ".xlsx", ".zip", ".tar", ".gz",
}


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ============================================================
# LLM 設定 (支援 LLM_* 和 LITELLM_* 環境變數)
# ============================================================

def _detect_model_from_api(api_base: str, api_key: str) -> str:
    """查詢 OpenAI-compatible API 的 /v1/models 端點，自動偵測模型。"""
    import httpx
    base = api_base.rstrip("/")
    models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
    try:
        resp = httpx.get(models_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        resp.raise_for_status()
        models = resp.json().get("data", [])
        if models:
            name = models[0].get("id", "")
            log(f"  Auto-detected model: {name}")
            if len(models) > 1:
                all_names = [m.get("id", "") for m in models]
                log(f"  Available models: {all_names}")
            return f"openai/{name}"
    except Exception as e:
        log(f"  Cannot query {models_url}: {e}")
    return ""


def _resolve_llm_config() -> tuple:
    """
    回傳 (model_id, api_base, api_key)。

    支援兩組環境變數 (優先順序):
      1. LLM_API_BASE / LLM_API_KEY / LLM_MODEL
      2. LITELLM_API_BASE / LITELLM_API_KEY / LITELLM_MODEL
      3. ANTHROPIC_API_KEY / LLM_MODEL

    模型自動偵測: LLM_MODEL 未設定時查詢 /v1/models。
    """
    # 統一讀取: LLM_* 優先，LITELLM_* 作為 fallback
    api_base = os.getenv("LLM_API_BASE") or os.getenv("LITELLM_API_BASE")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("LITELLM_API_KEY", "no-key")
    model_id = os.getenv("LLM_MODEL") or os.getenv("LITELLM_MODEL", "")

    if api_base:
        if not model_id:
            model_id = _detect_model_from_api(api_base, api_key)
        if not model_id:
            log("[ERROR] Cannot detect model. Set LLM_MODEL in .env")
            return None
        if "/" not in model_id:
            model_id = f"openai/{model_id}"
        return (model_id, api_base, api_key)

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        if not model_id:
            model_id = "claude-sonnet-4-5"
        return (model_id, None, anthropic_key)

    return None


def _create_agno_model(config: tuple):
    """建立 Agno model 實例。"""
    model_id, api_base, api_key = config
    if api_base:
        from agno.models.litellm import LiteLLM
        return LiteLLM(id=model_id, api_base=api_base, api_key=api_key)
    else:
        from agno.models.anthropic import Claude
        return Claude(id=model_id)


def _llm_completion(config: tuple, system: str, user: str,
                    temperature: float = 0.3, max_tokens: int = 2000) -> str:
    """直接呼叫 LLM completion (不經過 Agno)。"""
    model_id, api_base, api_key = config
    kwargs = {"model": model_id, "api_key": api_key,
              "max_tokens": max_tokens, "temperature": temperature}
    if api_base:
        kwargs["api_base"] = api_base
    resp = litellm.completion(messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], **kwargs)
    return resp.choices[0].message.content.strip()


# ============================================================
# MCP 工具呼叫
# ============================================================

async def _call_tool(mcp_tools, name: str, arguments: dict) -> str:
    """透過 MCP session 直接呼叫工具，回傳文字結果。"""
    session = await mcp_tools.get_session_for_run()
    result = await session.call_tool(name, arguments)
    texts = [c.text for c in result.content if hasattr(c, "text")]
    return "\n".join(texts)


# ============================================================
# Phase 1: Discover Documents
# ============================================================

async def phase1_discover_documents(mcp_tools) -> list[dict]:
    """透過 MCP rga_list_documents 遞迴掃描所有檔案。"""
    log("Phase 1: Discovering documents...")

    result = await _call_tool(mcp_tools, "rga_list_documents", {
        "path": DOCUMENTS_PATH,
        "recursive": True,
    })
    data = json.loads(result)

    documents = []
    _collect_files(data.get("entries", []), DOCUMENTS_PATH, documents)

    log(f"  Found {len(documents)} files")
    for doc in documents:
        log(f"    - {doc['file_path']} ({doc.get('size_human', '?')})")

    return documents


def _collect_files(entries: list, parent_path: str, out: list):
    for entry in entries:
        name = entry.get("name", "")
        entry_type = entry.get("type", "")
        if entry_type == "file":
            ext = Path(name).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                rel = f"{parent_path}/{name}" if parent_path else name
                out.append({
                    "file_path": rel,
                    "file_name": name,
                    "size": entry.get("size", 0),
                    "size_human": entry.get("size_human", ""),
                })
        elif entry_type == "directory":
            dir_name = name.rstrip("/")
            sub_path = f"{parent_path}/{dir_name}" if parent_path else dir_name
            if "children" in entry:
                _collect_files(entry["children"], sub_path, out)


# ============================================================
# Phase 2: Extract Text & Generate Questions
# ============================================================

async def phase2_extract_and_generate(mcp_tools, documents: list[dict],
                                       llm_config: tuple) -> list[dict]:
    """對每個文件: 提取文字 → 判斷 token → 生成問題 → 精煉摘要。"""
    log("Phase 2: Extracting text and generating questions...")

    enriched = []
    for i, doc in enumerate(documents):
        file_path = doc["file_path"]
        log(f"  [{i+1}/{len(documents)}] {file_path}")

        # Extract text via MCP
        try:
            raw = await _call_tool(mcp_tools, "rga_extract_text", {
                "file_id": file_path,
                "max_tokens": MAX_CONTEXT_TOKENS,
            })
            extract_data = json.loads(raw)
        except Exception as e:
            log(f"    [ERROR] Extract failed: {e}")
            enriched.append({**doc, "error": str(e), "questions": [], "summary": ""})
            continue

        extracted_text = extract_data.get("extracted_text", "")
        token_stats = extract_data.get("token_stats", {})
        token_count = token_stats.get("full_document_tokens",
                      token_stats.get("estimated_tokens", len(extracted_text) // 4))
        truncated = token_stats.get("truncated", False)

        if not extracted_text.strip():
            log(f"    [SKIP] No text extracted")
            enriched.append({**doc, "extracted_text": "", "questions": [],
                           "summary": "", "token_count": 0})
            continue

        fits_context = token_count <= MAX_CONTEXT_TOKENS
        log(f"    Tokens: ~{token_count:,}, fits context: {fits_context}, truncated: {truncated}")

        # 決定放入 LLM prompt 的文字量
        prompt_text = extracted_text if fits_context else extracted_text[:12000]

        # Generate questions
        questions = _generate_questions(llm_config, prompt_text, file_path)
        log(f"    Generated {len(questions)} questions")

        # Generate summary
        summary = _generate_summary(llm_config, prompt_text, file_path)
        log(f"    Summary: {summary[:80]}...")

        enriched.append({
            **doc,
            "extracted_text": extracted_text,
            "token_count": token_count,
            "full_text_fits_context": fits_context,
            "truncated": truncated,
            "questions": questions,
            "summary": summary,
        })

    return enriched


def _generate_questions(llm_config: tuple, text: str, file_path: str) -> list[str]:
    try:
        raw = _llm_completion(llm_config,
            system=(
                "You are a document analyst. Given a document, generate 5-10 specific questions "
                "that can be answered from the content. Return ONLY a JSON array of question strings. "
                "Example: [\"What is the main topic?\", \"Who is the author?\"]"
            ),
            user=f"Document: {file_path}\n\n---\n\n{text}",
        )
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        questions = json.loads(raw)
        if isinstance(questions, list):
            return [str(q) for q in questions[:10]]
    except Exception as e:
        log(f"    [ERROR] Question generation failed: {e}")
    return []


def _generate_summary(llm_config: tuple, text: str, file_path: str) -> str:
    try:
        return _llm_completion(llm_config,
            system=(
                "You are a document summarizer. Provide a concise summary "
                "in 2-3 sentences. Focus on the key topics, purpose, and main content."
            ),
            user=f"Document: {file_path}\n\n---\n\n{text}",
            temperature=0.2, max_tokens=500,
        )
    except Exception as e:
        log(f"    [ERROR] Summary generation failed: {e}")
    return ""


# ============================================================
# Phase 3: Build Document Summary Table
# ============================================================

def phase3_build_summary_table(enriched_docs: list[dict]) -> str:
    log("Phase 3: Building document summary table...")

    lines = [
        "| # | File | Tokens | Fits Context | Summary | Questions |",
        "|---|------|--------|--------------|---------|-----------|",
    ]
    for i, doc in enumerate(enriched_docs):
        summary_short = doc.get("summary", "")[:60].replace("|", "/").replace("\n", " ")
        if len(doc.get("summary", "")) > 60:
            summary_short += "..."
        lines.append(
            f"| {i+1} "
            f"| {doc['file_path']} "
            f"| {doc.get('token_count', 0):,} "
            f"| {'Yes' if doc.get('full_text_fits_context') else 'No'} "
            f"| {summary_short} "
            f"| {len(doc.get('questions', []))} |"
        )

    table = "\n".join(lines)
    log(f"  Table has {len(enriched_docs)} documents")
    print(f"\n{table}\n")
    return table


# ============================================================
# Phase 4: Agent Q&A Testing
# ============================================================

async def phase4_agent_qa(mcp_tools, enriched_docs: list[dict],
                          llm_config: tuple) -> list[dict]:
    """使用 Agno Agent 根據表格中的問題逐一問答。"""
    from agno.agent import Agent

    log("Phase 4: Running Agent Q&A...")

    model = _create_agno_model(llm_config)
    qa_results = []
    total_questions = sum(len(d.get("questions", [])) for d in enriched_docs)
    question_idx = 0

    for doc in enriched_docs:
        file_path = doc.get("file_path", "")
        summary = doc.get("summary", "")
        questions = doc.get("questions", [])

        if not questions:
            continue

        for q in questions:
            question_idx += 1
            log(f"  [{question_idx}/{total_questions}] Q: {q[:70]}...")

            # With summary context
            result_with = await _run_agent_question(
                mcp_tools, model, q, file_path, summary)

            # Without summary context
            result_without = await _run_agent_question(
                mcp_tools, model, q, file_path, "")

            qa_results.append({
                "doc_file": file_path,
                "question": q,
                "with_summary": result_with,
                "without_summary": result_without,
            })

    return qa_results


async def _run_agent_question(mcp_tools, model, question: str,
                               file_path: str, summary: str) -> dict:
    from agno.agent import Agent

    instructions = [
        "You have access to rga MCP tools for document search and text extraction.",
        "Use rga_list_documents to discover files and directories.",
        "Use rga_search_content to find specific content by keyword.",
        "Use rga_extract_text to read full file content.",
        "Be concise and accurate in your answers.",
    ]
    if summary:
        instructions.append(f"Relevant document: '{file_path}'. Summary: {summary}")

    agent = Agent(
        name="Document QA Agent",
        model=model,
        tools=[mcp_tools],
        instructions=instructions,
        markdown=False,
    )

    start_time = time.time()
    answer = ""
    tool_calls_log = []
    found_correct_file = False

    try:
        run_response = await agent.arun(question, stream=False)
        if run_response and run_response.content:
            answer = run_response.content
        if run_response and hasattr(run_response, "messages"):
            for msg in run_response.messages or []:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name if hasattr(tc, "function") else str(tc)
                        fn_args = tc.function.arguments if hasattr(tc, "function") else ""
                        tool_calls_log.append(fn_name)
                        if file_path and file_path in str(fn_args):
                            found_correct_file = True
    except asyncio.TimeoutError:
        answer = "TIMEOUT"
    except Exception as e:
        answer = f"ERROR: {e}"

    elapsed = time.time() - start_time

    return {
        "answer": answer[:500] if isinstance(answer, str) else str(answer)[:500],
        "tool_calls": tool_calls_log,
        "tool_calls_str": " → ".join(tool_calls_log) if tool_calls_log else "none",
        "found_correct_file": found_correct_file,
        "elapsed_seconds": round(elapsed, 2),
    }


# ============================================================
# Phase 5: Record Results
# ============================================================

def phase5_record_results(enriched_docs: list[dict], summary_table: str,
                          qa_results: list[dict], llm_config: tuple) -> str:
    log("Phase 5: Recording results...")

    QA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    filepath = QA_RESULTS_DIR / f"qa_{now.strftime('%Y%m%d_%H%M%S')}.md"

    model_id = llm_config[0]
    total_docs = len(enriched_docs)
    total_questions = len(qa_results)
    all_tool_calls = []
    correct_files = 0
    total_elapsed = 0.0

    for r in qa_results:
        ws = r["with_summary"]
        all_tool_calls.extend(ws["tool_calls"])
        if ws["found_correct_file"]:
            correct_files += 1
        total_elapsed += ws["elapsed_seconds"]

    tool_counts: dict[str, int] = {}
    for tc in all_tool_calls:
        tool_counts[tc] = tool_counts.get(tc, 0) + 1
    total_tc = len(all_tool_calls)
    tool_stats_lines = []
    for tool_name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        pct = (count / total_tc * 100) if total_tc > 0 else 0
        tool_stats_lines.append(f"- {tool_name}: {count} calls ({pct:.0f}%)")

    avg_time = (total_elapsed / total_questions) if total_questions > 0 else 0
    file_accuracy = (correct_files / total_questions * 100) if total_questions > 0 else 0

    md_parts = [
        f"# Document QA Test Results",
        f"",
        f"- **Date**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Model**: {model_id}",
        f"- **MCP URL**: {MCP_URL}",
        f"- **Documents scanned**: {total_docs}",
        f"- **Total questions**: {total_questions}",
        f"- **Max context tokens**: {MAX_CONTEXT_TOKENS:,}",
        f"",
        f"## Document Summary Table",
        f"",
        summary_table,
        f"",
        f"## Q&A Results (With Summary Context)",
        f"",
        f"| # | Document | Question | Answer (truncated) | Tools Called | Found File? | Time |",
        f"|---|----------|----------|--------------------|-------------|-------------|------|",
    ]

    for i, r in enumerate(qa_results):
        ws = r["with_summary"]
        answer_short = ws["answer"][:80].replace("|", "/").replace("\n", " ")
        if len(ws["answer"]) > 80:
            answer_short += "..."
        question_short = r["question"][:60].replace("|", "/")
        if len(r["question"]) > 60:
            question_short += "..."
        md_parts.append(
            f"| {i+1} "
            f"| {r['doc_file']} "
            f"| {question_short} "
            f"| {answer_short} "
            f"| {ws['tool_calls_str']} "
            f"| {'Yes' if ws['found_correct_file'] else 'No'} "
            f"| {ws['elapsed_seconds']:.1f}s |"
        )

    md_parts.extend([
        f"",
        f"## Tool Calling Analysis",
        f"",
        f"- **Total tool calls**: {total_tc}",
        *tool_stats_lines,
        f"- **File discovery accuracy**: {file_accuracy:.0f}% ({correct_files}/{total_questions})",
        f"- **Average response time**: {avg_time:.1f}s",
        f"",
        f"## Summary Context Comparison",
        f"",
        f"| # | Document | Question | With Summary | Without Summary | Summary Helped? |",
        f"|---|----------|----------|--------------|-----------------|-----------------|",
    ])

    for i, r in enumerate(qa_results):
        ws = r["with_summary"]
        wos = r["without_summary"]
        ws_short = ws["answer"][:50].replace("|", "/").replace("\n", " ")
        wos_short = wos["answer"][:50].replace("|", "/").replace("\n", " ")
        helped = (
            (ws["found_correct_file"] and not wos["found_correct_file"])
            or (ws["elapsed_seconds"] < wos["elapsed_seconds"] * 0.8)
        )
        question_short = r["question"][:40].replace("|", "/")
        md_parts.append(
            f"| {i+1} "
            f"| {r['doc_file']} "
            f"| {question_short} "
            f"| {ws_short} "
            f"| {wos_short} "
            f"| {'Yes' if helped else 'No'} |"
        )

    md_content = "\n".join(md_parts) + "\n"
    filepath.write_text(md_content, encoding="utf-8")
    log(f"  Results saved to: {filepath}")
    return str(filepath)


# ============================================================
# Main
# ============================================================

async def main():
    from agno.tools.mcp import MCPTools

    log("=" * 60)
    log("Document QA Workflow")
    log("=" * 60)

    # 解析 LLM 設定
    llm_config = _resolve_llm_config()
    if not llm_config:
        log("[ERROR] 未設定 LLM。請在 .env 中設定 LLM_API_BASE 或 ANTHROPIC_API_KEY")
        sys.exit(1)

    log(f"  MCP URL:    {MCP_URL}")
    log(f"  LLM Model:  {llm_config[0]}")
    log(f"  API Base:   {llm_config[1] or 'Anthropic'}")
    log(f"  Max Tokens: {MAX_CONTEXT_TOKENS:,}")
    log(f"  Doc Path:   {DOCUMENTS_PATH or '(root)'}")
    log("")

    # Connect to MCP via HTTP
    mcp_tools = MCPTools(transport="streamable-http", url=MCP_URL)

    try:
        await mcp_tools.connect()
        log("MCP connected successfully")

        tools = mcp_tools.functions
        tool_names = list(tools.keys()) if isinstance(tools, dict) else [t.name for t in tools]
        log(f"Available tools: {tool_names}")

        # Phase 1
        documents = await phase1_discover_documents(mcp_tools)
        if not documents:
            log("[WARN] No documents found. Check that files are mounted in /data/documents.")
            return

        # Phase 2
        enriched_docs = await phase2_extract_and_generate(mcp_tools, documents, llm_config)
        docs_with_questions = [d for d in enriched_docs if d.get("questions")]
        if not docs_with_questions:
            log("[WARN] No questions generated. Check LLM configuration.")
            return

        # Phase 3
        summary_table = phase3_build_summary_table(enriched_docs)

        # Phase 4
        qa_results = await phase4_agent_qa(mcp_tools, enriched_docs, llm_config)

        # Phase 5
        result_path = phase5_record_results(enriched_docs, summary_table,
                                            qa_results, llm_config)
        log(f"\nWorkflow complete! Results: {result_path}")

    except Exception as e:
        log(f"[FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            await mcp_tools.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
