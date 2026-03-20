#!/usr/bin/env python3
"""
agno_logprobs_qa.py — Agno Agent + Logprobs 確定性分析

結合 MCP 文件工具 (rga-mcp-server) 與 logprobs 分析，
讓 Agent 回答文件問題後自動評估回答的信心程度。

用法:
    # 搜尋文件並分析回答信心
    python agno_logprobs_qa.py "文件中提到的主要結論是什麼？"

    # 指定搜尋關鍵字後提問
    python agno_logprobs_qa.py --search "API rate limit" "rate limit 的設定值是多少？"

    # 從特定文件提問
    python agno_logprobs_qa.py --file "report.pdf" "第三章的重點是什麼？"

    # 調整信心閾值
    python agno_logprobs_qa.py --threshold 1.5 "解釋系統架構"
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# 載入 .env
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from logprobs_analyzer import analyze, print_report, print_json, entropy_label

try:
    from agno.agent import Agent
    from agno.models.litellm import LiteLLM
    from agno.tools.mcp import MCPTools
except ImportError:
    print("需要安裝: pip install agno litellm mcp", file=sys.stderr)
    sys.exit(1)


async def get_document_context(
    mcp_url: str,
    search_pattern: str = "",
    file_id: str = "",
    max_tokens: int = 4000,
) -> str:
    """
    透過 MCP 工具取得文件內容作為上下文
    """
    async with MCPTools(
        transport="streamable-http",
        url=mcp_url,
    ) as mcp_tools:
        agent = Agent(
            name="Context Fetcher",
            model=LiteLLM(
                id=os.environ.get("LLM_MODEL", ""),
                api_base=os.environ.get("LLM_API_BASE", "http://localhost:8000/v1"),
                api_key=os.environ.get("LLM_API_KEY", "no-key"),
            ),
            tools=[mcp_tools],
            instructions=(
                "你是文件檢索助手。請使用提供的工具取得文件內容，"
                "只回傳原始文件內容，不要加入自己的分析。"
            ),
            markdown=False,
        )

        if file_id:
            query = f"請提取文件 '{file_id}' 的完整文字內容"
        elif search_pattern:
            query = f"請搜尋包含 '{search_pattern}' 的文件內容"
        else:
            query = "請列出所有可用的文件"

        response = await agent.arun(query, stream=False)
        return response.content or ""


async def qa_with_confidence(
    question: str,
    context: str = "",
    search_pattern: str = "",
    file_id: str = "",
    mcp_url: str = "",
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    threshold: float = 2.0,
    verbose: bool = False,
    json_output: bool = False,
):
    """
    主流程：取得文件上下文 → 用 logprobs 分析回答信心
    """
    mcp_url = mcp_url or os.environ.get("MCP_URL", "http://localhost:30003/mcp")
    api_base = api_base or os.environ.get("LLM_API_BASE", "http://localhost:8000/v1")
    api_key = api_key or os.environ.get("LLM_API_KEY", "no-key")
    model = model or os.environ.get("LLM_MODEL", "")

    # Step 1: 取得文件上下文 (如果有指定)
    if not context and (search_pattern or file_id):
        print("[Step 1] 透過 MCP 取得文件內容...", file=sys.stderr)
        context = await get_document_context(
            mcp_url=mcp_url,
            search_pattern=search_pattern,
            file_id=file_id,
        )
        print(f"[Step 1] 取得 {len(context)} 字元的上下文", file=sys.stderr)

    # Step 2: 建構 system prompt
    system = ""
    if context:
        system = (
            "請根據以下文件內容回答問題。如果文件中沒有相關資訊，請明確說明。\n\n"
            f"=== 文件內容 ===\n{context[:8000]}\n=== 文件內容結束 ==="
        )

    # Step 3: 用 logprobs 分析
    print("[Step 2] 呼叫 LLM 並分析 logprobs...", file=sys.stderr)
    result = analyze(
        prompt=question,
        system=system,
        api_base=api_base,
        api_key=api_key,
        model=model,
        threshold=threshold,
    )

    # Step 4: 輸出結果
    if json_output:
        out = {
            "question": question,
            "has_context": bool(context),
            "context_length": len(context),
            "model": result.model,
            "confidence_score": result.confidence_score,
            "avg_entropy": result.avg_entropy,
            "entropy_label": entropy_label(result.avg_entropy),
            "answer": result.answer,
            "high_uncertainty_count": len(result.high_uncertainty_tokens),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if context:
            print(f"\n文件上下文: {len(context)} 字元")
        print_report(result, verbose=verbose)


def main():
    parser = argparse.ArgumentParser(
        description="Agno Agent + Logprobs 文件問答信心分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  %(prog)s "文件中的主要結論是什麼？"
  %(prog)s --search "API" "API 的使用方式？"
  %(prog)s --file "report.pdf" "第三章重點？"
  %(prog)s --json --search "config" "設定值是多少？"
        """,
    )
    parser.add_argument("question", help="要問的問題")
    parser.add_argument("--search", default="", help="先搜尋文件中的關鍵字")
    parser.add_argument("--file", default="", help="指定文件 ID")
    parser.add_argument("--context", default="", help="直接提供上下文文字")
    parser.add_argument("--mcp-url", default="", help="MCP server URL")
    parser.add_argument("--api-base", default="", help="LLM API 端點")
    parser.add_argument("--api-key", default="", help="LLM API Key")
    parser.add_argument("--model", "-m", default="", help="模型名稱")
    parser.add_argument("--threshold", type=float, default=2.0, help="高不確定性閾值")
    parser.add_argument("--verbose", "-v", action="store_true", help="顯示 token 詳細")
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON 輸出")

    args = parser.parse_args()

    asyncio.run(qa_with_confidence(
        question=args.question,
        context=args.context,
        search_pattern=args.search,
        file_id=args.file,
        mcp_url=args.mcp_url,
        api_base=args.api_base,
        api_key=args.api_key,
        model=args.model,
        threshold=args.threshold,
        verbose=args.verbose,
        json_output=args.json_output,
    ))


if __name__ == "__main__":
    main()
