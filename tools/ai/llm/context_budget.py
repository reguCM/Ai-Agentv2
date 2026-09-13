"""LLM プロンプトの context 予算見積もり（profile の context_limit / num_predict 準拠）。"""

from tools.system.config import get_llm_profile

# 出力予約・システムオーバーヘッド用。profile 値ではなく固定マージン。
SAFETY_MARGIN_TOKENS = 128
# Phase 4: 常時空ける headroom（chars）。7680 上限まで詰め込まない。
DEFAULT_HEADROOM_CHARS = 800
# 送信前の概算用（厳密な tokenizer は使わない）。
CHARS_PER_TOKEN = 4


def prompt_budget_tokens(profile=None):
    """入力側に使える token 概算。context_limit - num_predict - margin。"""
    profile = profile or get_llm_profile()
    context_limit = int(profile.get("context_limit") or 0)
    if context_limit <= 0:
        return None
    num_predict = int(profile.get("num_predict") or 0)
    budget = context_limit - num_predict - SAFETY_MARGIN_TOKENS
    return max(budget, 0)


def prompt_budget_chars(profile=None):
    tokens = prompt_budget_tokens(profile)
    if tokens is None:
        return None
    return tokens * CHARS_PER_TOKEN


def effective_prompt_budget_chars(profile=None, *, headroom=DEFAULT_HEADROOM_CHARS):
    """headroom を差し引いた送信上限 chars。"""
    budget = prompt_budget_chars(profile)
    if budget is None:
        return None
    return max(int(budget) - int(headroom), 0)


def estimate_messages_chars(messages):
    total = 0
    breakdown = {}
    for message in messages or []:
        role = str((message or {}).get("role") or "unknown")
        content = str((message or {}).get("content") or "")
        chars = len(content)
        total += chars
        breakdown[role] = breakdown.get(role, 0) + chars
    return total, breakdown


def check_context_budget(
    messages,
    profile=None,
    *,
    builder_name=None,
    reserve_headroom=False,
    headroom=DEFAULT_HEADROOM_CHARS,
):
    """
    予算超過時は context_overflow 用 dict を返す。
    予算未設定（context_limit なし）または超過なしなら None。

    reserve_headroom=True のとき effective budget（上限 - headroom）で判定する。
    """
    profile = profile or get_llm_profile()
    budget_chars = prompt_budget_chars(profile)
    if budget_chars is None:
        return None
    effective_budget = (
        effective_prompt_budget_chars(profile, headroom=headroom)
        if reserve_headroom
        else budget_chars
    )
    estimated, breakdown = estimate_messages_chars(messages)
    if estimated <= effective_budget:
        return None
    return {
        "kind": "context_overflow",
        "estimated_chars": estimated,
        "budget_chars": budget_chars,
        "effective_budget_chars": effective_budget,
        "headroom_chars": headroom if reserve_headroom else 0,
        "context_limit": int(profile.get("context_limit") or 0),
        "num_predict": int(profile.get("num_predict") or 0),
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "breakdown": breakdown,
        "builder": builder_name,
    }
