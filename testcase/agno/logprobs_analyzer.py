#!/usr/bin/env python3
"""
logprobs_analyzer.py — 分析 LLM 回答的確定性與資訊熵

使用 vLLM / OpenAI-compatible API 的 logprobs 參數，
計算每個 token 的資訊熵(Information Entropy)，評估 LLM 回答的信心程度。

用法:
    # 基本問答 (使用 .env 設定)
    python logprobs_analyzer.py "什麼是量子計算？"

    # 指定模型端點
    python logprobs_analyzer.py --api-base http://10.130.10.2:30013/v1 "解釋機器學習"

    # 顯示每個 token 的詳細資訊
    python logprobs_analyzer.py -v "Python 的 GIL 是什麼？"

    # 只看高不確定性 token (熵 > 閾值)
    python logprobs_analyzer.py --threshold 1.5 "比較 React 和 Vue"

    # JSON 輸出 (適合程式處理)
    python logprobs_analyzer.py --json "什麼是 Docker？"

    # 搭配 Agno MCP 工具使用：先搜尋文件再分析信心
    python logprobs_analyzer.py --system "根據以下內容回答：..." "文件中提到的關鍵結論是什麼？"
"""

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# 載入 .env
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

try:
    from openai import OpenAI
except ImportError:
    print("需要安裝 openai: pip install openai", file=sys.stderr)
    sys.exit(1)


# ─── 資料結構 ───────────────────────────────────────────────

@dataclass
class TokenInfo:
    """單一 token 的 logprobs 資訊"""
    token: str
    logprob: float          # log probability (自然對數)
    probability: float      # 機率 (0~1)
    entropy: float          # 該位置的資訊熵 (bits)
    top_alternatives: list = field(default_factory=list)  # [(token, prob), ...]


@dataclass
class AnalysisResult:
    """完整回答的分析結果"""
    answer: str
    total_tokens: int
    avg_entropy: float              # 平均資訊熵 (bits)
    max_entropy: float              # 最大資訊熵
    min_entropy: float              # 最小資訊熵
    confidence_score: float         # 信心分數 (0~100)
    high_uncertainty_tokens: list   # 高不確定性 token 列表
    tokens: list                    # 所有 TokenInfo
    model: str = ""


# ─── 核心計算 ───────────────────────────────────────────────

def calc_entropy(top_logprobs: list[dict]) -> float:
    """
    計算 token 位置的 Shannon Entropy (bits)

    H = -Σ p_i * log2(p_i)

    - H ≈ 0: 模型非常確定 (一個選項機率接近 1)
    - H > 2: 模型不太確定 (多個選項機率相近)
    - H > 3: 模型很不確定
    """
    if not top_logprobs:
        return 0.0

    entropy = 0.0
    for item in top_logprobs:
        logp = item.get("logprob", item) if isinstance(item, dict) else item.logprob
        p = math.exp(logp)
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def entropy_to_confidence(avg_entropy: float, max_entropy_cap: float = 4.0) -> float:
    """
    將平均資訊熵轉換為 0~100 的信心分數

    - 熵 0 → 信心 100 (完全確定)
    - 熵 ≥ max_entropy_cap → 信心 0 (完全不確定)
    """
    score = max(0.0, 1.0 - avg_entropy / max_entropy_cap) * 100
    return round(score, 1)


# ─── API 呼叫 ───────────────────────────────────────────────

def query_with_logprobs(
    prompt: str,
    system: str = "",
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    top_logprobs: int = 5,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> tuple[str, list[TokenInfo], str]:
    """
    呼叫 LLM API 並取得 logprobs

    Returns: (answer_text, token_infos, model_name)
    """
    api_base = api_base or os.environ.get("LLM_API_BASE", "http://localhost:8000/v1")
    api_key = api_key or os.environ.get("LLM_API_KEY", "no-key")
    model = model or os.environ.get("LLM_MODEL", "")

    client = OpenAI(base_url=api_base, api_key=api_key)

    # 自動偵測模型
    if not model:
        models = client.models.list()
        if models.data:
            model = models.data[0].id
            print(f"[自動偵測模型] {model}", file=sys.stderr)
        else:
            print("錯誤：無法偵測模型，請用 --model 指定", file=sys.stderr)
            sys.exit(1)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        logprobs=True,
        top_logprobs=top_logprobs,
    )

    choice = response.choices[0]
    answer = choice.message.content or ""

    token_infos = []
    if choice.logprobs and choice.logprobs.content:
        for item in choice.logprobs.content:
            # top_logprobs 中包含該位置的 top-k 候選 token
            top_alts = []
            item_entropy = 0.0

            if hasattr(item, "top_logprobs") and item.top_logprobs:
                for alt in item.top_logprobs:
                    p = math.exp(alt.logprob)
                    top_alts.append((alt.token, round(p, 4)))
                    if p > 0:
                        item_entropy -= p * math.log2(p)

            token_infos.append(TokenInfo(
                token=item.token,
                logprob=round(item.logprob, 4),
                probability=round(math.exp(item.logprob), 4),
                entropy=round(item_entropy, 4),
                top_alternatives=top_alts,
            ))

    return answer, token_infos, response.model or model


def analyze(
    prompt: str,
    system: str = "",
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    top_logprobs: int = 5,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    threshold: float = 2.0,
) -> AnalysisResult:
    """
    完整分析流程：呼叫 API → 計算熵 → 產出報告
    """
    answer, tokens, model_name = query_with_logprobs(
        prompt=prompt,
        system=system,
        api_base=api_base,
        api_key=api_key,
        model=model,
        top_logprobs=top_logprobs,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    if not tokens:
        return AnalysisResult(
            answer=answer,
            total_tokens=0,
            avg_entropy=0.0,
            max_entropy=0.0,
            min_entropy=0.0,
            confidence_score=100.0,
            high_uncertainty_tokens=[],
            tokens=[],
            model=model_name,
        )

    entropies = [t.entropy for t in tokens]
    avg_ent = sum(entropies) / len(entropies)

    high_unc = [
        {"token": t.token, "entropy": t.entropy, "alternatives": t.top_alternatives[:3]}
        for t in tokens if t.entropy > threshold
    ]

    return AnalysisResult(
        answer=answer,
        total_tokens=len(tokens),
        avg_entropy=round(avg_ent, 4),
        max_entropy=round(max(entropies), 4),
        min_entropy=round(min(entropies), 4),
        confidence_score=entropy_to_confidence(avg_ent),
        high_uncertainty_tokens=high_unc,
        tokens=tokens,
        model=model_name,
    )


# ─── 輸出格式 ───────────────────────────────────────────────

def confidence_bar(score: float) -> str:
    """視覺化信心分數"""
    filled = int(score / 5)
    bar = "█" * filled + "░" * (20 - filled)
    return f"[{bar}] {score}%"


def entropy_label(entropy: float) -> str:
    """資訊熵等級標籤"""
    if entropy < 0.5:
        return "非常確定"
    elif entropy < 1.0:
        return "確定"
    elif entropy < 2.0:
        return "略有不確定"
    elif entropy < 3.0:
        return "不確定"
    else:
        return "非常不確定"


def print_report(result: AnalysisResult, verbose: bool = False):
    """印出人類可讀的分析報告"""
    print("\n" + "=" * 60)
    print(f"  LLM 回答確定性分析")
    print("=" * 60)

    print(f"\n模型: {result.model}")
    print(f"Token 數: {result.total_tokens}")
    print(f"\n{'─' * 40}")
    print(f"  信心分數: {confidence_bar(result.confidence_score)}")
    print(f"  平均資訊熵: {result.avg_entropy:.4f} bits ({entropy_label(result.avg_entropy)})")
    print(f"  最大資訊熵: {result.max_entropy:.4f} bits")
    print(f"  最小資訊熵: {result.min_entropy:.4f} bits")
    print(f"{'─' * 40}")

    print(f"\n回答:")
    print(f"  {result.answer[:500]}{'...' if len(result.answer) > 500 else ''}")

    if result.high_uncertainty_tokens:
        print(f"\n高不確定性 Token ({len(result.high_uncertainty_tokens)} 個):")
        for i, t in enumerate(result.high_uncertainty_tokens[:10]):
            alts = ", ".join(f"'{a[0]}'={a[1]:.2%}" for a in t["alternatives"])
            print(f"  [{i+1}] '{t['token']}' 熵={t['entropy']:.2f} | 候選: {alts}")
        if len(result.high_uncertainty_tokens) > 10:
            print(f"  ... 還有 {len(result.high_uncertainty_tokens) - 10} 個")

    if verbose and result.tokens:
        print(f"\n所有 Token 詳細:")
        print(f"  {'Token':<20} {'機率':>8} {'熵':>8} {'等級':<12}")
        print(f"  {'─' * 52}")
        for t in result.tokens:
            tok_display = repr(t.token)[:18]
            print(f"  {tok_display:<20} {t.probability:>7.2%} {t.entropy:>7.4f} {entropy_label(t.entropy):<12}")

    print()


def print_json(result: AnalysisResult):
    """JSON 輸出"""
    out = {
        "model": result.model,
        "total_tokens": result.total_tokens,
        "confidence_score": result.confidence_score,
        "avg_entropy": result.avg_entropy,
        "max_entropy": result.max_entropy,
        "min_entropy": result.min_entropy,
        "entropy_label": entropy_label(result.avg_entropy),
        "answer": result.answer,
        "high_uncertainty_count": len(result.high_uncertainty_tokens),
        "high_uncertainty_tokens": result.high_uncertainty_tokens,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


# ─── CLI ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="分析 LLM 回答的確定性與資訊熵",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  %(prog)s "什麼是量子計算？"
  %(prog)s -v "Python 的 GIL 是什麼？"
  %(prog)s --threshold 1.5 "比較 React 和 Vue"
  %(prog)s --json "什麼是 Docker？"
  %(prog)s --api-base http://10.130.10.2:30010/v1 "解釋機器學習"
  %(prog)s --system "你是醫學專家" "什麼是高血壓？"

熵值參考:
  < 0.5  非常確定 (模型高度自信)
  0.5~1  確定 (正常回答)
  1~2    略有不確定 (可能有多種表達方式)
  2~3    不確定 (模型在多個答案間猶豫)
  > 3    非常不確定 (可能在胡說)
        """,
    )
    parser.add_argument("prompt", help="要問 LLM 的問題")
    parser.add_argument("--system", "-s", default="", help="System prompt")
    parser.add_argument("--api-base", default="", help="API 端點 (預設: $LLM_API_BASE)")
    parser.add_argument("--api-key", default="", help="API Key (預設: $LLM_API_KEY)")
    parser.add_argument("--model", "-m", default="", help="模型名稱 (預設: 自動偵測)")
    parser.add_argument("--top-logprobs", "-k", type=int, default=5, help="Top-K logprobs (預設: 5)")
    parser.add_argument("--max-tokens", type=int, default=1024, help="最大回覆 token 數 (預設: 1024)")
    parser.add_argument("--temperature", "-t", type=float, default=0.0, help="Temperature (預設: 0.0)")
    parser.add_argument("--threshold", type=float, default=2.0, help="高不確定性閾值 (預設: 2.0)")
    parser.add_argument("--verbose", "-v", action="store_true", help="顯示每個 token 詳細資訊")
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON 格式輸出")

    args = parser.parse_args()

    result = analyze(
        prompt=args.prompt,
        system=args.system,
        api_base=args.api_base,
        api_key=args.api_key,
        model=args.model,
        top_logprobs=args.top_logprobs,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        threshold=args.threshold,
    )

    if args.json_output:
        print_json(result)
    else:
        print_report(result, verbose=args.verbose)


if __name__ == "__main__":
    main()
