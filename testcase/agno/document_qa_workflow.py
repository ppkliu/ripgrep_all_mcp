"""
Document QA Workflow — Agno Agent + MCP + LiteLLM

自動化文件問答測試流程:
  Phase 1: 透過 MCP 掃描 documents/ 下所有檔案路徑
  Phase 2: 提取文字、判斷 token 是否放入 context、生成問題（中文）、精煉摘要
  Phase 3: 建立文件摘要 Markdown 表格
  Phase 4: Agno Agent 逐一問答並記錄完整 tool calling 歷程（含每步驟耗時）
  Phase 5: 輸出帶時間戳的 QA 結果 Markdown（含時間分析）

支援雙 LLM 設定:
  - LLM_API_BASE   / LLM_API_KEY   / LLM_MODEL   → 主要 LLM (Phase 2 問題生成/摘要)
  - LLM_API_BASE_2 / LLM_API_KEY_2 / LLM_MODEL_2 → 第二組 LLM (Phase 4 Agno Agent)
  若未設定第二組，Phase 4 會使用主要 LLM。

CLI 參數可覆蓋 .env 設定:
    python document_qa_workflow.py --model openai/qwen3 --api-base http://localhost:1234/v1
    python document_qa_workflow.py --use-model 2          # Agent 使用第二組 LLM
    python document_qa_workflow.py --prompt "這份文件的主題是什麼？"  # 直接提問模式
    python document_qa_workflow.py --help

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

import argparse
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
# CLI 參數解析
# ============================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="文件 QA 自動化測試 — Agno Agent + MCP + LiteLLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 完整自動化測試 (使用 .env 設定)
  python document_qa_workflow.py

  # 指定主要 LLM
  python document_qa_workflow.py --model openai/qwen3 --api-base http://localhost:1234/v1

  # Agent 使用第二組 LLM
  python document_qa_workflow.py --use-model 2

  # 直接提問模式 (跳過自動測試流程)
  python document_qa_workflow.py --prompt "這份文件的主題是什麼？"
  python document_qa_workflow.py --prompt "找出關於 MCP 的說明" --use-model 2
""",
    )
    # 模式選擇
    p.add_argument("--prompt", help="直接提問模式: 輸入問題讓 Agent 搜尋文件並回答")
    p.add_argument("--use-model", choices=["1", "2"], default="1",
                   help="Agent 使用哪組 LLM: 1=主要, 2=第二組 (預設: 1)")

    # LLM 設定覆蓋
    p.add_argument("--model", help="主要 LLM 模型名稱 (覆蓋 LLM_MODEL)")
    p.add_argument("--api-base", help="主要 LLM API 端點 (覆蓋 LLM_API_BASE)")
    p.add_argument("--api-key", help="主要 LLM API key (覆蓋 LLM_API_KEY)")
    p.add_argument("--model-2", help="Agent LLM 模型名稱 (覆蓋 LLM_MODEL_2)")
    p.add_argument("--api-base-2", help="Agent LLM API 端點 (覆蓋 LLM_API_BASE_2)")
    p.add_argument("--api-key-2", help="Agent LLM API key (覆蓋 LLM_API_KEY_2)")
    p.add_argument("--mcp-url", help="MCP HTTP URL (覆蓋 MCP_URL)")
    p.add_argument("--max-tokens", type=int, help="最大 context token 數 (覆蓋 MAX_CONTEXT_TOKENS)")
    p.add_argument("--doc-path", help="文件子路徑 (覆蓋 DOCUMENTS_PATH)")
    return p.parse_args()


def _apply_cli_args(args: argparse.Namespace):
    """CLI 參數覆蓋環境變數。"""
    mapping = {
        "model": "LLM_MODEL",
        "api_base": "LLM_API_BASE",
        "api_key": "LLM_API_KEY",
        "model_2": "LLM_MODEL_2",
        "api_base_2": "LLM_API_BASE_2",
        "api_key_2": "LLM_API_KEY_2",
        "mcp_url": "MCP_URL",
        "max_tokens": "MAX_CONTEXT_TOKENS",
        "doc_path": "DOCUMENTS_PATH",
    }
    for attr, env_key in mapping.items():
        val = getattr(args, attr, None)
        if val is not None:
            os.environ[env_key] = str(val)


# ============================================================
# Configuration
# ============================================================

def _load_config():
    """重新讀取環境變數 (CLI 參數已覆蓋後)。"""
    global MCP_URL, MAX_CONTEXT_TOKENS, DOCUMENTS_PATH
    MCP_URL = os.getenv("MCP_URL", "http://localhost:30003/mcp")
    MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "32000"))
    DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "")

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

# ============================================================
# Timing tracker
# ============================================================

class TimingTracker:
    """追蹤各 Phase 及整體執行時間。"""

    def __init__(self):
        self.workflow_start: float = 0
        self.workflow_end: float = 0
        self.phases: list[dict] = []
        self._phase_start: float = 0

    def start_workflow(self):
        self.workflow_start = time.time()

    def end_workflow(self):
        self.workflow_end = time.time()

    def start_phase(self, name: str):
        self._phase_start = time.time()
        self.phases.append({"name": name, "start": self._phase_start, "end": 0, "elapsed": 0})

    def end_phase(self):
        now = time.time()
        if self.phases:
            self.phases[-1]["end"] = now
            self.phases[-1]["elapsed"] = round(now - self.phases[-1]["start"], 2)

    @property
    def total_elapsed(self) -> float:
        return round(self.workflow_end - self.workflow_start, 2)

    def summary_table(self) -> str:
        lines = [
            "| 階段 | 耗時 (秒) | 佔比 |",
            "|------|-----------|------|",
        ]
        total = self.total_elapsed or 1
        for p in self.phases:
            pct = p["elapsed"] / total * 100
            lines.append(f"| {p['name']} | {p['elapsed']:.2f} | {pct:.1f}% |")
        lines.append(f"| **合計** | **{total:.2f}** | **100%** |")
        return "\n".join(lines)


timing = TimingTracker()


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
            log(f"  自動偵測模型: {name}")
            if len(models) > 1:
                all_names = [m.get("id", "") for m in models]
                log(f"  可用模型: {all_names}")
            return f"openai/{name}"
    except Exception as e:
        log(f"  無法查詢 {models_url}: {e}")
    return ""


def _resolve_llm_config(suffix: str = "") -> tuple | None:
    """
    回傳 (model_id, api_base, api_key)。

    suffix="" → 主要 LLM (LLM_API_BASE)
    suffix="2" → 第二組 LLM (LLM_API_BASE_2)

    優先順序:
      1. LLM_API_BASE{suffix} / LLM_API_KEY{suffix} / LLM_MODEL{suffix}
      2. (suffix="" only) LITELLM_API_BASE / LITELLM_API_KEY / LITELLM_MODEL
      3. (suffix="" only) ANTHROPIC_API_KEY / LLM_MODEL

    模型自動偵測: LLM_MODEL 未設定時查詢 /v1/models。
    """
    s = f"_{suffix}" if suffix else ""

    api_base = os.getenv(f"LLM_API_BASE{s}")
    api_key = os.getenv(f"LLM_API_KEY{s}")
    model_id = os.getenv(f"LLM_MODEL{s}", "")

    # 主要 LLM fallback: LITELLM_*
    if not suffix:
        api_base = api_base or os.getenv("LITELLM_API_BASE")
        api_key = api_key or os.getenv("LITELLM_API_KEY")
        model_id = model_id or os.getenv("LITELLM_MODEL", "")

    if api_key is None:
        api_key = "no-key"

    if api_base:
        if not model_id:
            model_id = _detect_model_from_api(api_base, api_key)
        if not model_id:
            log(f"[ERROR] 無法偵測模型。請在 .env 中設定 LLM_MODEL{s}")
            return None
        if "/" not in model_id:
            model_id = f"openai/{model_id}"
        return (model_id, api_base, api_key)

    # 第二組未設定 → 回傳 None (由呼叫者 fallback 到主要)
    if suffix:
        return None

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
    timing.start_phase("Phase 1: 文件掃描")
    log("Phase 1: 掃描文件目錄...")

    result = await _call_tool(mcp_tools, "rga_list_documents", {
        "path": DOCUMENTS_PATH,
        "recursive": True,
    })
    data = json.loads(result)

    documents = []
    _collect_files(data.get("entries", []), DOCUMENTS_PATH, documents)

    # 表格化輸出
    print()
    print(f"┌{'─'*4}┬{'─'*40}┬{'─'*12}┐")
    print(f"│ {'#':>2} │ {'檔案路徑':<38} │ {'大小':>10} │")
    print(f"├{'─'*4}┼{'─'*40}┼{'─'*12}┤")
    for i, doc in enumerate(documents):
        fp = doc['file_path'][:38]
        sz = doc.get('size_human', '?')
        print(f"│ {i+1:>2} │ {fp:<38} │ {sz:>10} │")
    print(f"└{'─'*4}┴{'─'*40}┴{'─'*12}┘")
    log(f"  共找到 {len(documents)} 個檔案")
    print()

    timing.end_phase()
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
# Phase 2: Extract Text & Generate Questions (中文)
# ============================================================

async def phase2_extract_and_generate(mcp_tools, documents: list[dict],
                                       llm_config: tuple) -> list[dict]:
    """對每個文件: 提取文字 → 判斷 token → 生成中文問題 → 精煉摘要。"""
    timing.start_phase("Phase 2: 文字提取與問題生成")
    log("Phase 2: 提取文字並生成問題...")

    enriched = []
    for i, doc in enumerate(documents):
        file_path = doc["file_path"]
        t0 = time.time()
        log(f"  [{i+1}/{len(documents)}] {file_path}")

        # Extract text via MCP
        t_extract_start = time.time()
        try:
            raw = await _call_tool(mcp_tools, "rga_extract_text", {
                "file_id": file_path,
                "max_tokens": MAX_CONTEXT_TOKENS,
            })
            extract_data = json.loads(raw)
        except Exception as e:
            log(f"    [錯誤] 提取失敗: {e}")
            enriched.append({**doc, "error": str(e), "questions": [], "summary": "",
                           "mcp_extract_time": round(time.time() - t_extract_start, 2),
                           "question_gen_time": 0, "summary_gen_time": 0,
                           "total_process_time": round(time.time() - t0, 2)})
            continue
        mcp_extract_time = round(time.time() - t_extract_start, 2)

        extracted_text = extract_data.get("extracted_text", "")
        token_stats = extract_data.get("token_stats", {})
        token_count = token_stats.get("full_document_tokens",
                      token_stats.get("estimated_tokens", len(extracted_text) // 4))
        truncated = token_stats.get("truncated", False)

        if not extracted_text.strip():
            log(f"    [跳過] 無文字內容")
            enriched.append({**doc, "extracted_text": "", "questions": [],
                           "summary": "", "token_count": 0,
                           "mcp_extract_time": mcp_extract_time,
                           "question_gen_time": 0, "summary_gen_time": 0,
                           "total_process_time": round(time.time() - t0, 2)})
            continue

        fits_context = token_count <= MAX_CONTEXT_TOKENS
        log(f"    Tokens: ~{token_count:,}, 可放入 context: {fits_context}, "
            f"截斷: {truncated}, MCP提取: {mcp_extract_time}s")

        # 決定放入 LLM prompt 的文字量
        prompt_text = extracted_text if fits_context else extracted_text[:12000]

        # Generate questions (中文)
        t1 = time.time()
        questions = _generate_questions(llm_config, prompt_text, file_path)
        question_time = round(time.time() - t1, 2)
        log(f"    生成 {len(questions)} 個問題 (LLM: {question_time}s)")

        # Generate summary
        t2 = time.time()
        summary = _generate_summary(llm_config, prompt_text, file_path)
        summary_time = round(time.time() - t2, 2)
        log(f"    摘要: {summary[:60]}... (LLM: {summary_time}s)")

        enriched.append({
            **doc,
            "extracted_text": extracted_text,
            "token_count": token_count,
            "full_text_fits_context": fits_context,
            "truncated": truncated,
            "questions": questions,
            "summary": summary,
            "mcp_extract_time": mcp_extract_time,
            "question_gen_time": question_time,
            "summary_gen_time": summary_time,
            "total_process_time": round(time.time() - t0, 2),
        })

    timing.end_phase()
    return enriched


def _generate_questions(llm_config: tuple, text: str, file_path: str) -> list[str]:
    try:
        raw = _llm_completion(llm_config,
            system=(
                "你是一位文件分析專家。根據提供的文件內容，生成 5-10 個具體的中文問題，"
                "這些問題必須可以從文件內容中找到答案。"
                "只回傳 JSON 陣列格式的問題字串，不要其他文字。"
                "範例: [\"這份文件的主題是什麼？\", \"作者提出了哪些主要觀點？\"]"
            ),
            user=f"文件路徑: {file_path}\n\n---\n\n{text}",
        )
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        questions = json.loads(raw)
        if isinstance(questions, list):
            return [str(q) for q in questions[:10]]
    except Exception as e:
        log(f"    [錯誤] 問題生成失敗: {e}")
    return []


def _generate_summary(llm_config: tuple, text: str, file_path: str) -> str:
    try:
        return _llm_completion(llm_config,
            system=(
                "你是一位文件摘要專家。用 2-3 句中文簡要總結文件的關鍵主題、目的和主要內容。"
            ),
            user=f"文件路徑: {file_path}\n\n---\n\n{text}",
            temperature=0.2, max_tokens=500,
        )
    except Exception as e:
        log(f"    [錯誤] 摘要生成失敗: {e}")
    return ""


# ============================================================
# Phase 3: Build Document Summary Table
# ============================================================

def phase3_build_summary_table(enriched_docs: list[dict]) -> str:
    timing.start_phase("Phase 3: 摘要表格")
    log("Phase 3: 建立文件摘要表格...")

    lines = [
        "| # | 檔案 | Tokens | 可放入 Context | 摘要 | 問題數 |",
        "|---|------|--------|---------------|------|--------|",
    ]
    for i, doc in enumerate(enriched_docs):
        summary_short = doc.get("summary", "")[:60].replace("|", "/").replace("\n", " ")
        if len(doc.get("summary", "")) > 60:
            summary_short += "..."
        lines.append(
            f"| {i+1} "
            f"| {doc['file_path']} "
            f"| {doc.get('token_count', 0):,} "
            f"| {'是' if doc.get('full_text_fits_context') else '否'} "
            f"| {summary_short} "
            f"| {len(doc.get('questions', []))} |"
        )

    table = "\n".join(lines)
    log(f"  共 {len(enriched_docs)} 個文件")
    print(f"\n{table}\n")

    timing.end_phase()
    return table


# ============================================================
# Phase 4: Agent Q&A Testing (支援雙 LLM, 每步驟計時)
# ============================================================

async def phase4_agent_qa(mcp_tools, enriched_docs: list[dict],
                          llm_config: tuple, llm_config_2: tuple | None) -> list[dict]:
    """使用 Agno Agent 根據表格中的問題逐一問答，記錄完整 tool calling 歷程及每步驟耗時。"""
    from agno.agent import Agent

    timing.start_phase("Phase 4: Agent Q&A")

    # 決定 Agent 使用的 LLM
    agent_config = llm_config_2 or llm_config
    log("Phase 4: 啟動 Agent Q&A...")
    log(f"  Agent LLM: {agent_config[0]}")
    if llm_config_2:
        log(f"  (使用第二組 LLM: LLM_API_BASE_2)")

    model = _create_agno_model(agent_config)
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
            log(f"  [{question_idx}/{total_questions}] Q: {q[:60]}...")

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

            # 即時顯示工具呼叫歷程
            _print_tool_history(question_idx, q, result_with)

    timing.end_phase()
    return qa_results


def _print_tool_history(idx: int, question: str, result: dict):
    """即時在 console 輸出 Agent 的 tool calling 歷程（含每步驟耗時）。"""
    steps = result.get("tool_steps", [])
    q_short = question[:50]
    print()
    print(f"  ┌─ Q{idx}: {q_short}{'...' if len(question) > 50 else ''}")

    if steps:
        for i, step in enumerate(steps):
            is_last = (i == len(steps) - 1)
            prefix = "  └" if is_last else "  ├"
            args_short = step.get("arguments", "")[:60]
            tool_elapsed = step.get("tool_elapsed", 0)
            time_str = f" [{tool_elapsed:.2f}s]" if tool_elapsed else ""
            print(f"  │  {prefix}─ [{i+1}] {step['tool']}({args_short}){time_str}")
            if step.get("result_preview"):
                preview = step["result_preview"][:80].replace("\n", " ")
                pad = "  │  │" if not is_last else "  │   "
                print(f"  {pad}     → {preview}")
    else:
        print(f"  │  └─ (無工具呼叫)")

    # 耗時明細
    total_tool = result.get("total_tool_time", 0)
    llm_time = result.get("llm_thinking_time", 0)
    total = result["elapsed_seconds"]
    ans_short = result.get("answer", "")[:80].replace("\n", " ")
    print(f"  └─ A: {ans_short}{'...' if len(result.get('answer', '')) > 80 else ''}")
    print(f"     總耗時: {total:.2f}s │ LLM思考: {llm_time:.2f}s │ "
          f"工具執行: {total_tool:.2f}s │ 呼叫: {len(steps)} 次")
    print()


async def _run_agent_question(mcp_tools, model, question: str,
                               file_path: str, summary: str) -> dict:
    from agno.agent import Agent

    instructions = [
        "你可以使用 rga MCP 工具來搜尋文件和提取文字。",
        "使用 rga_list_documents 查看檔案和目錄。",
        "使用 rga_search_content 透過關鍵字搜尋內容。",
        "使用 rga_extract_text 讀取完整檔案內容。",
        "請用中文回答問題，簡潔且準確。",
        "",
        "重要: 回答時必須標註參考來源。格式範例:",
        "  📄 來源: filename.pdf (第 3 頁, 行 42)",
        "  📄 來源: report.docx (行 15-20)",
        "根據 rga_search_content 回傳的 file 和 line_number 欄位來標註。",
        "若為 PDF 文件，line_number 對應頁碼內的行號，請同時標註檔名。",
        "若從 rga_extract_text 取得內容，標註檔名即可。",
        "",
        "效能提示:",
        "- 如果已知檔案路徑，直接用 rga_extract_text，不需要先 rga_list_documents",
        "- 如果只需要特定關鍵字，優先用 rga_search_content 而非提取整個檔案",
        "- 避免重複呼叫相同工具和相同參數",
    ]
    if summary:
        instructions.append(f"相關文件: '{file_path}'。摘要: {summary}")

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
    tool_steps = []  # 詳細工具呼叫歷程 (含耗時)
    found_correct_file = False

    try:
        run_response = await agent.arun(question, stream=False)
        if run_response and run_response.content:
            answer = run_response.content

        # 提取完整 tool calling 歷程，計算每步驟耗時
        if run_response and hasattr(run_response, "messages"):
            msgs = run_response.messages or []

            # 收集所有訊息的時間戳 (如果有的話) 用於計算耗時
            # Agno messages 可能有 created_at 屬性
            msg_times = []
            for msg in msgs:
                ts = getattr(msg, "created_at", None)
                if ts:
                    if isinstance(ts, (int, float)):
                        msg_times.append(ts)
                    elif hasattr(ts, "timestamp"):
                        msg_times.append(ts.timestamp())

            tool_call_idx = 0
            for mi, msg in enumerate(msgs):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name if hasattr(tc, "function") else str(tc)
                        fn_args = tc.function.arguments if hasattr(tc, "function") else ""
                        tool_calls_log.append(fn_name)

                        step = {
                            "tool": fn_name,
                            "arguments": fn_args if isinstance(fn_args, str) else json.dumps(fn_args, ensure_ascii=False),
                            "result_preview": "",
                            "tool_elapsed": 0.0,
                            "msg_index": mi,
                        }
                        tool_steps.append(step)

                        if file_path and file_path in str(fn_args):
                            found_correct_file = True

                # 捕捉工具回應 (tool role messages)
                if hasattr(msg, "role") and msg.role == "tool":
                    content = ""
                    if hasattr(msg, "content"):
                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    # 對應到最近一個沒有結果的 step，並計算耗時
                    for step in tool_steps:
                        if not step["result_preview"]:
                            step["result_preview"] = content[:200]
                            # 嘗試用 metric / created_at 計算工具耗時
                            metric = getattr(msg, "metrics", None) or getattr(msg, "metric", None)
                            if metric and hasattr(metric, "time"):
                                step["tool_elapsed"] = round(metric.time, 2)
                            break

    except asyncio.TimeoutError:
        answer = "TIMEOUT"
    except Exception as e:
        answer = f"ERROR: {e}"

    elapsed = time.time() - start_time

    # 計算工具總耗時和 LLM 思考時間
    total_tool_time = sum(s["tool_elapsed"] for s in tool_steps)

    # 若無法從 metric 取得工具耗時，用啟發式估算:
    # 假設 tool calls 之間的時間差為 LLM 思考時間
    if total_tool_time == 0 and tool_steps:
        # 粗略估算: 每個工具呼叫平均分配
        avg_per_tool = elapsed / (len(tool_steps) + 1) if tool_steps else 0
        for step in tool_steps:
            step["tool_elapsed"] = round(avg_per_tool, 2)
        total_tool_time = round(avg_per_tool * len(tool_steps), 2)

    llm_thinking_time = round(elapsed - total_tool_time, 2)
    if llm_thinking_time < 0:
        llm_thinking_time = 0

    return {
        "answer": answer[:500] if isinstance(answer, str) else str(answer)[:500],
        "tool_calls": tool_calls_log,
        "tool_steps": [
            {k: v for k, v in s.items() if k != "msg_index"}
            for s in tool_steps
        ],
        "tool_calls_str": " → ".join(tool_calls_log) if tool_calls_log else "(無)",
        "found_correct_file": found_correct_file,
        "elapsed_seconds": round(elapsed, 2),
        "total_tool_time": total_tool_time,
        "llm_thinking_time": llm_thinking_time,
    }


# ============================================================
# Phase 5: Record Results (含時間分析)
# ============================================================

def phase5_record_results(enriched_docs: list[dict], summary_table: str,
                          qa_results: list[dict],
                          llm_config: tuple, llm_config_2: tuple | None) -> str:
    timing.start_phase("Phase 5: 輸出結果")
    log("Phase 5: 記錄結果...")

    QA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    filepath = QA_RESULTS_DIR / f"qa_{now.strftime('%Y%m%d_%H%M%S')}.md"

    model_id = llm_config[0]
    agent_config = llm_config_2 or llm_config
    agent_model_id = agent_config[0]

    total_docs = len(enriched_docs)
    total_questions = len(qa_results)
    all_tool_calls = []
    all_tool_steps = []
    correct_files = 0
    total_elapsed = 0.0
    total_llm_time = 0.0
    total_tool_time_all = 0.0

    for r in qa_results:
        ws = r["with_summary"]
        all_tool_calls.extend(ws["tool_calls"])
        all_tool_steps.extend(ws.get("tool_steps", []))
        if ws["found_correct_file"]:
            correct_files += 1
        total_elapsed += ws["elapsed_seconds"]
        total_llm_time += ws.get("llm_thinking_time", 0)
        total_tool_time_all += ws.get("total_tool_time", 0)

    tool_counts: dict[str, int] = {}
    tool_time_by_name: dict[str, float] = {}
    for step in all_tool_steps:
        name = step["tool"]
        tool_counts[name] = tool_counts.get(name, 0) + 1
        tool_time_by_name[name] = tool_time_by_name.get(name, 0) + step.get("tool_elapsed", 0)
    total_tc = len(all_tool_calls)

    tool_stats_lines = []
    for tool_name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        pct = (count / total_tc * 100) if total_tc > 0 else 0
        avg_t = tool_time_by_name.get(tool_name, 0) / count if count else 0
        tool_stats_lines.append(
            f"| {tool_name} | {count} | {pct:.0f}% | "
            f"{tool_time_by_name.get(tool_name, 0):.2f}s | {avg_t:.2f}s |"
        )

    avg_time = (total_elapsed / total_questions) if total_questions > 0 else 0
    file_accuracy = (correct_files / total_questions * 100) if total_questions > 0 else 0

    # Phase 2 時間統計
    total_mcp_extract = sum(d.get("mcp_extract_time", 0) for d in enriched_docs)
    total_qgen_time = sum(d.get("question_gen_time", 0) for d in enriched_docs)
    total_sgen_time = sum(d.get("summary_gen_time", 0) for d in enriched_docs)

    md_parts = [
        f"# 文件 QA 測試報告",
        f"",
        f"## 測試環境",
        f"",
        f"| 項目 | 值 |",
        f"|------|-----|",
        f"| 日期 | {now.strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| 問題生成 LLM | {model_id} |",
        f"| Agent LLM | {agent_model_id} |",
        f"| MCP URL | {MCP_URL} |",
        f"| 掃描文件數 | {total_docs} |",
        f"| 總問題數 | {total_questions} |",
        f"| 最大 Context Tokens | {MAX_CONTEXT_TOKENS:,} |",
        f"",
    ]

    # 時間分析
    md_parts.extend([
        f"## 時間分析",
        f"",
        timing.summary_table(),
        f"",
        f"### Phase 2 細項",
        f"",
        f"| 項目 | 耗時 (秒) |",
        f"|------|-----------|",
        f"| MCP 文字提取 | {total_mcp_extract:.2f} |",
        f"| LLM 問題生成 | {total_qgen_time:.2f} |",
        f"| LLM 摘要生成 | {total_sgen_time:.2f} |",
        f"",
    ])

    # Phase 2 每個檔案的處理時間
    md_parts.extend([
        f"### Phase 2 各檔案處理時間",
        f"",
        f"| # | 檔案 | MCP提取 | LLM問題 | LLM摘要 | 合計 |",
        f"|---|------|---------|---------|---------|------|",
    ])
    for i, doc in enumerate(enriched_docs):
        md_parts.append(
            f"| {i+1} | {doc['file_path']} "
            f"| {doc.get('mcp_extract_time', 0):.2f}s "
            f"| {doc.get('question_gen_time', 0):.2f}s "
            f"| {doc.get('summary_gen_time', 0):.2f}s "
            f"| {doc.get('total_process_time', 0):.2f}s |"
        )

    # Phase 4 時間分析
    md_parts.extend([
        f"",
        f"### Phase 4 Q&A 時間分析",
        f"",
        f"| 項目 | 值 |",
        f"|------|-----|",
        f"| 總耗時 | {total_elapsed:.2f}s |",
        f"| 平均每題 | {avg_time:.2f}s |",
        f"| LLM 思考總時間 | {total_llm_time:.2f}s |",
        f"| 工具執行總時間 | {total_tool_time_all:.2f}s |",
        f"| 最快 | {min((r['with_summary']['elapsed_seconds'] for r in qa_results), default=0):.2f}s |",
        f"| 最慢 | {max((r['with_summary']['elapsed_seconds'] for r in qa_results), default=0):.2f}s |",
        f"",
    ])

    # Bottleneck 分析
    if total_elapsed > 0:
        llm_pct = total_llm_time / total_elapsed * 100
        tool_pct = total_tool_time_all / total_elapsed * 100
        bottleneck = "LLM 思考" if llm_pct > tool_pct else "工具執行"
        md_parts.extend([
            f"### 效能瓶頸分析",
            f"",
            f"| 項目 | 耗時 | 佔比 |",
            f"|------|------|------|",
            f"| LLM 思考 | {total_llm_time:.2f}s | {llm_pct:.1f}% |",
            f"| 工具執行 | {total_tool_time_all:.2f}s | {tool_pct:.1f}% |",
            f"| **瓶頸** | **{bottleneck}** | |",
            f"",
        ])

    # Document Summary
    md_parts.extend([
        f"## 文件摘要表格",
        f"",
        summary_table,
        f"",
    ])

    # Q&A Results (含時間明細)
    md_parts.extend([
        f"## Q&A 結果 (有摘要)",
        f"",
        f"| # | 文件 | 問題 | 回答 (截斷) | 工具呼叫 | 定位正確 | 總耗時 | LLM | 工具 |",
        f"|---|------|------|-------------|---------|---------|--------|-----|------|",
    ])

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
            f"| {'是' if ws['found_correct_file'] else '否'} "
            f"| {ws['elapsed_seconds']:.1f}s "
            f"| {ws.get('llm_thinking_time', 0):.1f}s "
            f"| {ws.get('total_tool_time', 0):.1f}s |"
        )

    # Tool calling 詳細歷程
    md_parts.extend([
        f"",
        f"## 工具呼叫歷程",
        f"",
    ])

    for i, r in enumerate(qa_results):
        ws = r["with_summary"]
        steps = ws.get("tool_steps", [])
        q_short = r["question"][:60]
        md_parts.append(f"### Q{i+1}: {q_short}")
        md_parts.append(f"")
        md_parts.append(f"總耗時: {ws['elapsed_seconds']:.2f}s | "
                        f"LLM: {ws.get('llm_thinking_time', 0):.2f}s | "
                        f"工具: {ws.get('total_tool_time', 0):.2f}s")
        md_parts.append(f"")
        if steps:
            md_parts.append(f"| 步驟 | 工具 | 參數 | 耗時 | 結果預覽 |")
            md_parts.append(f"|------|------|------|------|---------|")
            for j, step in enumerate(steps):
                args = step.get("arguments", "")[:50].replace("|", "/").replace("\n", " ")
                preview = step.get("result_preview", "")[:60].replace("|", "/").replace("\n", " ")
                te = step.get("tool_elapsed", 0)
                md_parts.append(
                    f"| {j+1} | `{step['tool']}` | {args} | {te:.2f}s | {preview} |"
                )
        else:
            md_parts.append(f"_(無工具呼叫)_")
        md_parts.append(f"")

    # Tool analysis
    md_parts.extend([
        f"## 工具呼叫統計",
        f"",
        f"| 工具 | 呼叫次數 | 佔比 | 總耗時 | 平均耗時 |",
        f"|------|---------|------|--------|---------|",
        *tool_stats_lines,
        f"| **合計** | **{total_tc}** | **100%** | "
        f"**{total_tool_time_all:.2f}s** | |",
        f"",
        f"| 項目 | 值 |",
        f"|------|-----|",
        f"| 檔案定位準確率 | {file_accuracy:.0f}% ({correct_files}/{total_questions}) |",
        f"| 平均回應時間 | {avg_time:.1f}s |",
        f"",
    ])

    # Summary context comparison
    md_parts.extend([
        f"## 摘要 Context 對照比較",
        f"",
        f"| # | 文件 | 問題 | 有摘要回答 | 無摘要回答 | 摘要有幫助 |",
        f"|---|------|------|-----------|-----------|-----------|",
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
            f"| {'是' if helped else '否'} |"
        )

    md_content = "\n".join(md_parts) + "\n"
    filepath.write_text(md_content, encoding="utf-8")
    log(f"  結果已儲存: {filepath}")

    timing.end_phase()

    # 在 console 輸出最終時間分析表格
    print()
    log("=" * 60)
    log("測試完成 — 時間分析")
    log("=" * 60)
    print()
    print(timing.summary_table())
    print()

    # 效能瓶頸摘要
    if total_elapsed > 0:
        llm_pct = total_llm_time / total_elapsed * 100
        tool_pct = total_tool_time_all / total_elapsed * 100
        print(f"┌{'─'*50}┐")
        print(f"│ {'效能瓶頸分析':<44} │")
        print(f"├{'─'*50}┤")
        print(f"│ {'LLM 思考時間:':<18} {total_llm_time:>8.2f}s ({llm_pct:>5.1f}%) {'':>8} │")
        print(f"│ {'工具執行時間:':<18} {total_tool_time_all:>8.2f}s ({tool_pct:>5.1f}%) {'':>8} │")
        print(f"│ {'總耗時:':<20} {total_elapsed:>8.2f}s {'':>16} │")
        bottleneck = "LLM 思考" if llm_pct > tool_pct else "工具執行"
        print(f"│ {'主要瓶頸:':<19} {bottleneck:<28} │")
        print(f"└{'─'*50}┘")

    print()
    log(f"  總耗時: {timing.total_elapsed:.2f}s")
    log(f"  問題生成 LLM: {llm_config[0]}")
    log(f"  Agent LLM:    {agent_config[0]}")
    if llm_config_2:
        log(f"  (使用雙 LLM 模式)")
    print()

    return str(filepath)


# ============================================================
# Main
# ============================================================

async def _run_prompt_mode(mcp_tools, prompt: str, agent_config: tuple):
    """直接提問模式: 用 Agent 搜尋文件並回答問題。"""
    from agno.agent import Agent

    model = _create_agno_model(agent_config)

    instructions = [
        "你可以使用 rga MCP 工具來搜尋文件和提取文字。",
        "使用 rga_list_documents 查看檔案和目錄。",
        "使用 rga_search_content 透過關鍵字搜尋內容。",
        "使用 rga_extract_text 讀取完整檔案內容。",
        "請用中文回答問題，詳細且準確。",
        "",
        "重要: 回答時必須標註參考來源。格式範例:",
        "  📄 來源: filename.pdf (第 3 頁, 行 42)",
        "  📄 來源: report.docx (行 15-20)",
        "根據 rga_search_content 回傳的 file 和 line_number 欄位來標註。",
        "若為 PDF 文件，line_number 對應頁碼內的行號，請同時標註檔名。",
        "若從 rga_extract_text 取得內容，標註檔名即可。",
        "",
        "效能提示:",
        "- 如果用戶已提供完整檔案路徑，直接用 rga_extract_text，不需要先 rga_list_documents",
        "- 如果只需要特定關鍵字，優先用 rga_search_content 而非提取整個檔案",
        "- 避免重複呼叫相同工具和相同參數",
    ]

    agent = Agent(
        name="Document QA Agent",
        model=model,
        tools=[mcp_tools],
        instructions=instructions,
        markdown=True,
    )

    model_id, api_base, _ = agent_config
    print(f"┌{'─'*58}┐")
    print(f"│ {'Prompt 模式':<52} │")
    print(f"├{'─'*58}┤")
    print(f"│ {'LLM 模型':<10}: {model_id:<42} │")
    print(f"│ {'API Base':<10}: {(api_base or 'Anthropic'):<42} │")
    print(f"│ {'MCP URL':<10}: {MCP_URL:<42} │")
    print(f"└{'─'*58}┘")
    print()
    log(f"提問: {prompt}")
    print()

    start_time = time.time()

    try:
        run_response = await agent.arun(prompt, stream=False)
        elapsed = round(time.time() - start_time, 2)

        # 提取完整 tool calling 歷程，計算每步驟耗時
        tool_steps = []
        if run_response and hasattr(run_response, "messages"):
            msgs = run_response.messages or []
            for mi, msg in enumerate(msgs):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name if hasattr(tc, "function") else str(tc)
                        fn_args = tc.function.arguments if hasattr(tc, "function") else ""
                        step = {
                            "tool": fn_name,
                            "arguments": fn_args if isinstance(fn_args, str) else json.dumps(fn_args, ensure_ascii=False),
                            "result_preview": "",
                            "tool_elapsed": 0.0,
                            "msg_index": mi,
                        }
                        tool_steps.append(step)

                # 捕捉工具回應 (tool role messages)
                if hasattr(msg, "role") and msg.role == "tool":
                    content = ""
                    if hasattr(msg, "content"):
                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    for step in tool_steps:
                        if not step["result_preview"]:
                            step["result_preview"] = content[:200]
                            metric = getattr(msg, "metrics", None) or getattr(msg, "metric", None)
                            if metric and hasattr(metric, "time"):
                                step["tool_elapsed"] = round(metric.time, 2)
                            break

        # 計算工具總耗時和 LLM 思考時間
        total_tool_time = sum(s["tool_elapsed"] for s in tool_steps)
        if total_tool_time == 0 and tool_steps:
            avg_per_tool = elapsed / (len(tool_steps) + 1) if tool_steps else 0
            for step in tool_steps:
                step["tool_elapsed"] = round(avg_per_tool, 2)
            total_tool_time = round(avg_per_tool * len(tool_steps), 2)

        llm_thinking_time = round(elapsed - total_tool_time, 2)
        if llm_thinking_time < 0:
            llm_thinking_time = 0

        # 顯示回答
        print("=" * 60)
        print("回答:")
        print("=" * 60)
        if run_response and run_response.content:
            print(run_response.content)
        print()

        # 顯示 tool calling 歷程（含每步驟耗時）
        if tool_steps:
            print(f"  ┌─ Prompt 模式 Agent 工具呼叫歷程")
            for i, step in enumerate(tool_steps):
                is_last = (i == len(tool_steps) - 1)
                prefix = "  └" if is_last else "  ├"
                args_short = step.get("arguments", "")[:60]
                te = step.get("tool_elapsed", 0)
                time_str = f" [{te:.2f}s]" if te else ""
                print(f"  │  {prefix}─ [{i+1}] {step['tool']}({args_short}){time_str}")
                if step.get("result_preview"):
                    preview = step["result_preview"][:80].replace("\n", " ")
                    pad = "  │  │" if not is_last else "  │   "
                    print(f"  {pad}     → {preview}")
            print()

        # 瓶頸分析
        tool_pct = round(total_tool_time / elapsed * 100, 1) if elapsed > 0 else 0
        llm_pct = round(llm_thinking_time / elapsed * 100, 1) if elapsed > 0 else 0
        bottleneck = "LLM 思考" if llm_thinking_time >= total_tool_time else "工具執行"

        print(f"┌{'─'*58}┐")
        print(f"│ {'效能分析':<52} │")
        print(f"├{'─'*58}┤")
        print(f"│ {'總耗時':<12}: {elapsed:>8.2f}s{'':<34} │")
        print(f"│ {'LLM 思考':<10}: {llm_thinking_time:>8.2f}s ({llm_pct:>5.1f}%){'':<24} │")
        print(f"│ {'工具執行':<10}: {total_tool_time:>8.2f}s ({tool_pct:>5.1f}%){'':<24} │")
        print(f"│ {'工具呼叫':<10}: {len(tool_steps):>8} 次{'':<34} │")
        print(f"│ {'瓶頸':<12}: {bottleneck:<40} │")
        print(f"└{'─'*58}┘")

        # 每個工具類型的時間統計
        if tool_steps:
            tool_time_by_name: dict[str, list[float]] = {}
            for step in tool_steps:
                name = step["tool"]
                tool_time_by_name.setdefault(name, []).append(step["tool_elapsed"])

            print(f"\n┌{'─'*58}┐")
            print(f"│ {'工具耗時統計':<50} │")
            print(f"├{'─'*26}┬{'─'*8}┬{'─'*10}┬{'─'*10}┤")
            print(f"│ {'工具名稱':<24} │ {'次數':>6} │ {'總耗時':>8} │ {'平均':>8} │")
            print(f"├{'─'*26}┼{'─'*8}┼{'─'*10}┼{'─'*10}┤")
            for name, times in sorted(tool_time_by_name.items()):
                total_t = sum(times)
                avg_t = total_t / len(times) if times else 0
                print(f"│ {name:<24} │ {len(times):>6} │ {total_t:>7.2f}s │ {avg_t:>7.2f}s │")
            print(f"└{'─'*26}┴{'─'*8}┴{'─'*10}┴{'─'*10}┘")

        print()

    except Exception as e:
        log(f"[錯誤] {e}")
        import traceback
        traceback.print_exc()


async def main():
    from agno.tools.mcp import MCPTools

    # 解析 CLI 參數並覆蓋環境變數
    args = _parse_args()
    _apply_cli_args(args)
    _load_config()

    log("=" * 60)
    log("文件 QA 自動化測試")
    log("=" * 60)

    timing.start_workflow()

    # 解析主要 LLM 設定
    llm_config = _resolve_llm_config()
    if not llm_config:
        log("[錯誤] 未設定 LLM。請在 .env 中設定 LLM_API_BASE 或 ANTHROPIC_API_KEY")
        log("       或使用 --model / --api-base 參數指定")
        sys.exit(1)

    # 解析第二組 LLM 設定 (可選)
    llm_config_2 = _resolve_llm_config(suffix="2")

    # 根據 --use-model 決定 Agent 使用哪組 LLM
    if args.use_model == "2":
        if not llm_config_2:
            log("[錯誤] --use-model 2 但未設定第二組 LLM (LLM_API_BASE_2)")
            sys.exit(1)
        agent_config = llm_config_2
    elif args.use_model == "1":
        agent_config = llm_config
    else:
        agent_config = llm_config_2 or llm_config

    print()
    print(f"┌{'─'*50}┐")
    print(f"│ {'設定項目':<20} {'值':<28} │")
    print(f"├{'─'*50}┤")
    print(f"│ {'MCP URL':<20} {MCP_URL:<28} │")
    print(f"│ {'問題生成 LLM':<16} {llm_config[0]:<28} │")
    print(f"│ {'API Base':<20} {(llm_config[1] or 'Anthropic'):<28} │")
    if agent_config != llm_config:
        print(f"│ {'Agent LLM (第二組)':<14} {agent_config[0]:<28} │")
        print(f"│ {'API Base 2':<20} {agent_config[1]:<28} │")
    else:
        print(f"│ {'Agent LLM':<20} {llm_config[0]+' (同上)':<28} │")
    print(f"│ {'Max Tokens':<20} {MAX_CONTEXT_TOKENS:<28,} │")
    print(f"│ {'文件路徑':<18} {DOCUMENTS_PATH or '(根目錄)':<28} │")
    if args.prompt:
        print(f"│ {'模式':<20} {'直接提問':<28} │")
    print(f"└{'─'*50}┘")
    print()

    # Connect to MCP via HTTP
    mcp_tools = MCPTools(transport="streamable-http", url=MCP_URL)

    try:
        await mcp_tools.connect()
        log("MCP 連線成功")

        tools = mcp_tools.functions
        tool_names = list(tools.keys()) if isinstance(tools, dict) else [t.name for t in tools]
        log(f"可用工具: {tool_names}")

        # --prompt 模式: 直接提問
        if args.prompt:
            await _run_prompt_mode(mcp_tools, args.prompt, agent_config)
            return

        # === 完整自動化測試流程 ===

        # Phase 1
        documents = await phase1_discover_documents(mcp_tools)
        if not documents:
            log("[警告] 未找到文件。請確認 /data/documents 中已掛載檔案。")
            return

        # Phase 2
        enriched_docs = await phase2_extract_and_generate(mcp_tools, documents, llm_config)
        docs_with_questions = [d for d in enriched_docs if d.get("questions")]
        if not docs_with_questions:
            log("[警告] 沒有生成任何問題。請檢查 LLM 設定。")
            return

        # Phase 3
        summary_table = phase3_build_summary_table(enriched_docs)

        # Phase 4 — 使用 --use-model 選擇的 LLM
        effective_config_2 = agent_config if agent_config != llm_config else None
        qa_results = await phase4_agent_qa(mcp_tools, enriched_docs,
                                           llm_config, effective_config_2)

        # Phase 5
        timing.end_workflow()
        result_path = phase5_record_results(enriched_docs, summary_table,
                                            qa_results, llm_config, effective_config_2)
        log(f"測試完成! 結果: {result_path}")

    except Exception as e:
        log(f"[致命錯誤] {e}")
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
