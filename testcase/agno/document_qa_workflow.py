"""
Document QA Workflow — Agno Agent + MCP + LiteLLM

自動化文件問答測試流程:
  Phase 1: 透過 MCP 列出文件目錄
  Phase 2: 提取文字、生成問題、建立摘要
  Phase 3: 建立文件摘要 Markdown 表格
  Phase 4: Agno Agent 逐一問答並記錄 tool calling
  Phase 5: 輸出帶時間戳的 QA 結果 Markdown

使用方式:
    # 1. 啟動 MCP Docker HTTP server
    docker compose -f docker-compose.http.yaml up -d

    # 2. 安裝依賴
    pip install -r testcase/agno/requirements.txt

    # 3. 設定環境變數
    export LITELLM_MODEL="openai/your-model"
    export LITELLM_API_BASE="http://localhost:8000/v1"
    export LITELLM_API_KEY="sk-xxx"
    export MCP_URL="http://localhost:30003/mcp"

    # 4. 執行
    python testcase/agno/document_qa_workflow.py
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
# Configuration
# ============================================================

MCP_URL = os.getenv("MCP_URL", "http://localhost:30003/mcp")
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "openai/your-model-name")
LITELLM_API_BASE = os.getenv("LITELLM_API_BASE", "http://localhost:8000/v1")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-placeholder")
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "32000"))
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "")  # relative path within /data/documents
QA_RESULTS_DIR = Path(__file__).parent / "qa_results"

# Supported document extensions for filtering
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".epub", ".odt",
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".pptx", ".xlsx", ".zip", ".tar", ".gz",
}


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ============================================================
# Phase 1: Discover Documents
# ============================================================

async def phase1_discover_documents(mcp_tools) -> list[dict]:
    """List all documents via MCP rga_list_documents tool."""
    log("Phase 1: Discovering documents...")

    result = await mcp_tools.call("rga_list_documents", {
        "path": DOCUMENTS_PATH,
        "recursive": True,
    })

    data = json.loads(result) if isinstance(result, str) else result

    documents = []
    _collect_files(data.get("entries", []), DOCUMENTS_PATH, documents)

    log(f"  Found {len(documents)} files")
    for doc in documents:
        log(f"    - {doc['file_path']} ({doc.get('size_human', '?')})")

    return documents


def _collect_files(entries: list, parent_path: str, out: list):
    """Recursively collect file entries from list_documents response."""
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

async def phase2_extract_and_generate(mcp_tools, documents: list[dict]) -> list[dict]:
    """For each document, extract text, generate questions, create summary."""
    log("Phase 2: Extracting text and generating questions...")

    enriched = []
    for i, doc in enumerate(documents):
        file_path = doc["file_path"]
        log(f"  [{i+1}/{len(documents)}] Processing: {file_path}")

        # Extract text via MCP
        try:
            extract_result = await mcp_tools.call("rga_extract_text", {
                "file_id": file_path,
                "max_tokens": MAX_CONTEXT_TOKENS,
            })
            extract_data = json.loads(extract_result) if isinstance(extract_result, str) else extract_result
        except Exception as e:
            log(f"    [ERROR] Extract failed: {e}")
            enriched.append({**doc, "error": str(e), "questions": [], "summary": ""})
            continue

        extracted_text = extract_data.get("extracted_text", "")
        token_stats = extract_data.get("token_stats", {})
        token_count = token_stats.get("estimated_tokens", len(extracted_text) // 4)
        truncated = token_stats.get("truncated", False)

        if not extracted_text.strip():
            log(f"    [SKIP] No text extracted")
            enriched.append({**doc, "extracted_text": "", "questions": [], "summary": "", "token_count": 0})
            continue

        fits_context = token_count <= MAX_CONTEXT_TOKENS
        log(f"    Tokens: ~{token_count}, fits context: {fits_context}, truncated: {truncated}")

        # Generate questions via LiteLLM
        questions = await _generate_questions(extracted_text, file_path)
        log(f"    Generated {len(questions)} questions")

        # Generate summary via LiteLLM
        summary = await _generate_summary(extracted_text, file_path)
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


async def _generate_questions(text: str, file_path: str) -> list[str]:
    """Use LiteLLM to generate 5-10 questions about the document."""
    # Truncate text for prompt if very long
    prompt_text = text[:12000] if len(text) > 12000 else text

    try:
        response = litellm.completion(
            model=LITELLM_MODEL,
            api_base=LITELLM_API_BASE,
            api_key=LITELLM_API_KEY,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a document analyst. Given a document, generate 5-10 specific questions "
                        "that can be answered from the content. Return ONLY a JSON array of question strings, "
                        "no other text. Example: [\"What is the main topic?\", \"Who is the author?\"]"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Document path: {file_path}\n\n---\n\n{prompt_text}",
                },
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        # Parse JSON array from response (handle markdown code blocks)
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


async def _generate_summary(text: str, file_path: str) -> str:
    """Use LiteLLM to create a refined summary of the document."""
    prompt_text = text[:12000] if len(text) > 12000 else text

    try:
        response = litellm.completion(
            model=LITELLM_MODEL,
            api_base=LITELLM_API_BASE,
            api_key=LITELLM_API_KEY,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a document summarizer. Provide a concise summary of the document "
                        "in 2-3 sentences. Focus on the key topics, purpose, and main content."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Document path: {file_path}\n\n---\n\n{prompt_text}",
                },
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log(f"    [ERROR] Summary generation failed: {e}")
    return ""


# ============================================================
# Phase 3: Build Document Summary Table
# ============================================================

def phase3_build_summary_table(enriched_docs: list[dict]) -> str:
    """Create markdown table summarizing all documents."""
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
    print("\n" + table + "\n")
    return table


# ============================================================
# Phase 4: Agent Q&A Testing
# ============================================================

async def phase4_agent_qa(mcp_tools, enriched_docs: list[dict]) -> list[dict]:
    """Run Agno Agent to answer each question, recording tool calls and results."""
    from agno.agent import Agent
    from agno.models.litellm import LiteLLM

    log("Phase 4: Running Agent Q&A...")

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

            # Run with summary context
            result_with_summary = await _run_agent_question(
                mcp_tools, q, file_path, summary,
                model_id=LITELLM_MODEL,
                api_base=LITELLM_API_BASE,
                api_key=LITELLM_API_KEY,
            )

            # Run without summary context
            result_without_summary = await _run_agent_question(
                mcp_tools, q, file_path, "",
                model_id=LITELLM_MODEL,
                api_base=LITELLM_API_BASE,
                api_key=LITELLM_API_KEY,
            )

            qa_results.append({
                "doc_file": file_path,
                "question": q,
                "with_summary": result_with_summary,
                "without_summary": result_without_summary,
            })

    return qa_results


async def _run_agent_question(
    mcp_tools,
    question: str,
    file_path: str,
    summary: str,
    model_id: str,
    api_base: str,
    api_key: str,
) -> dict:
    """Run a single question through the Agno agent, capturing tool calls and answer."""
    from agno.agent import Agent
    from agno.models.litellm import LiteLLM

    instructions = [
        "You have access to rga MCP tools for document search and text extraction.",
        "Use rga_list_documents to discover files and directories.",
        "Use rga_search_content to find specific content by keyword.",
        "Use rga_extract_text to read full file content.",
        "Be concise and accurate in your answers.",
    ]
    if summary:
        instructions.append(
            f"Relevant document: '{file_path}'. Summary: {summary}"
        )

    agent = Agent(
        name="Document QA Agent",
        model=LiteLLM(id=model_id, api_base=api_base, api_key=api_key),
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

        # Extract answer text
        if run_response and run_response.content:
            answer = run_response.content

        # Extract tool call information from messages
        if run_response and hasattr(run_response, "messages"):
            for msg in run_response.messages or []:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name if hasattr(tc, "function") else str(tc)
                        fn_args = tc.function.arguments if hasattr(tc, "function") else ""
                        tool_calls_log.append(f"{fn_name}")
                        # Check if the agent found the correct file
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

def phase5_record_results(
    enriched_docs: list[dict],
    summary_table: str,
    qa_results: list[dict],
) -> str:
    """Save timestamped QA results as markdown."""
    log("Phase 5: Recording results...")

    QA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    filename = f"qa_{now.strftime('%Y%m%d_%H%M%S')}.md"
    filepath = QA_RESULTS_DIR / filename

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

    # Tool usage stats
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

    # Build markdown
    md_parts = [
        f"# Document QA Test Results",
        f"",
        f"- **Date**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Model**: {LITELLM_MODEL}",
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
        # Heuristic: summary helped if with-summary found file but without didn't,
        # or with-summary was faster
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
    log(f"  MCP URL:    {MCP_URL}")
    log(f"  LLM Model:  {LITELLM_MODEL}")
    log(f"  API Base:   {LITELLM_API_BASE}")
    log(f"  Max Tokens: {MAX_CONTEXT_TOKENS}")
    log(f"  Doc Path:   {DOCUMENTS_PATH or '(root)'}")
    log("")

    # Connect to MCP via HTTP
    mcp_tools = MCPTools(transport="streamable-http", url=MCP_URL)

    try:
        await mcp_tools.connect()
        log("MCP connected successfully")

        # Verify tools are available
        tools = mcp_tools.functions
        tool_names = list(tools.keys()) if isinstance(tools, dict) else [t.name for t in tools]
        log(f"Available tools: {tool_names}")

        # Phase 1
        documents = await phase1_discover_documents(mcp_tools)
        if not documents:
            log("[WARN] No documents found. Check that files are mounted in /data/documents.")
            return

        # Phase 2
        enriched_docs = await phase2_extract_and_generate(mcp_tools, documents)
        docs_with_questions = [d for d in enriched_docs if d.get("questions")]
        if not docs_with_questions:
            log("[WARN] No questions generated for any document. Check LLM configuration.")
            return

        # Phase 3
        summary_table = phase3_build_summary_table(enriched_docs)

        # Phase 4
        qa_results = await phase4_agent_qa(mcp_tools, enriched_docs)

        # Phase 5
        result_path = phase5_record_results(enriched_docs, summary_table, qa_results)
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
