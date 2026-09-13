"""TDA Follow-up intents (experimental PoC — wraps conversation_resolution)."""
from __future__ import annotations

import re
from typing import Any, Callable, Literal

from ai_tool.experimental.conversation_resolution.models import ConversationState
from ai_tool.experimental.conversation_resolution.resolver import (
    handle_follow_up,
    parse_follow_up_intent,
)
from ai_tool.experimental.development_assistance.technology_candidate import TechnologyCandidate

TDAFollowUpIntent = Literal[
    "RESEARCH_MORE",
    "SELECT_CANDIDATE",
    "COMPARE_CANDIDATES",
    "BUILD_CUSTOM",
    "DEFER",
    "SHOW_SOURCE",
    "CONTINUE",
    "UNKNOWN",
]

ChatFn = Callable[..., Any]


def parse_tda_follow_up_intent(user_message: str) -> TDAFollowUpIntent:
    m = user_message.strip()
    if re.search(r"もっと調べ|追加調査|さらに調査|research more|dig deeper", m, re.I):
        return "RESEARCH_MORE"
    if re.search(r"自作|custom build|スクラッチ|一から", m, re.I):
        return "BUILD_CUSTOM"
    if re.search(r"保留|あとで|defer|後で", m, re.I):
        return "DEFER"
    if re.search(r"比較|違い|compare", m, re.I):
        return "COMPARE_CANDIDATES"
    if re.search(r"採用|使いたい|使う|select|adopt|Aを|Bを|Cを", m, re.I):
        return "SELECT_CANDIDATE"
    if re.search(r"出典|ソース|URL|元ページ", m, re.I):
        return "SHOW_SOURCE"

    base = parse_follow_up_intent(m)
    if base in ("ADOPT_A", "ADOPT_B"):
        return "SELECT_CANDIDATE"
    if base == "COMPARE":
        return "COMPARE_CANDIDATES"
    if base == "SHOW_SOURCE":
        return "SHOW_SOURCE"
    if m:
        return "CONTINUE"
    return "UNKNOWN"


def handle_tda_follow_up(
    state: ConversationState,
    envelope: dict[str, Any],
    user_message: str,
    tech_candidates: list[TechnologyCandidate],
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    intent = parse_tda_follow_up_intent(user_message)

    if intent == "BUILD_CUSTOM":
        custom = next((c for c in tech_candidates if c.type == "Custom Build"), None)
        state.selected_candidate_id = custom.candidate_id if custom else "CUSTOM"
        state.turn += 1
        return {
            "turn": state.turn,
            "intent": intent,
            "response_type": "user_decision",
            "body": "了解しました。Custom Build（自作）を開発方針として保持します。Tool実装には接続しません。",
            "selected_candidate_id": state.selected_candidate_id,
            "development_decision": "CUSTOM_BUILD",
        }

    if intent == "DEFER":
        state.turn += 1
        return {
            "turn": state.turn,
            "intent": intent,
            "response_type": "defer",
            "body": "了解しました。判断は保留として記録します。",
            "selected_candidate_id": state.selected_candidate_id,
            "development_decision": "DEFERRED",
        }

    if intent == "RESEARCH_MORE":
        state.turn += 1
        target = state.selected_candidate_id or (
            tech_candidates[0].candidate_id if tech_candidates else None
        )
        return {
            "turn": state.turn,
            "intent": intent,
            "response_type": "research_request",
            "body": f"追加調査を要求しました。対象候補: {target or '未選択'}",
            "selected_candidate_id": state.selected_candidate_id,
            "research_more_target": target,
            "needs_targeted_research": True,
        }

    if intent == "SELECT_CANDIDATE":
        letter = re.search(r"([ABC])を|([ABC])にして", user_message, re.I)
        if letter and tech_candidates:
            pick = (letter.group(1) or letter.group(2) or "").upper()
            target_id = f"TC{pick}"
            match = next((c for c in tech_candidates if c.candidate_id == target_id), None)
            if match:
                state.selected_candidate_id = match.candidate_id
                state.turn += 1
                return {
                    "turn": state.turn,
                    "intent": intent,
                    "response_type": "user_decision",
                    "body": f"了解しました。以降は {match.name} ({match.candidate_id}) を前提にTool仕様を組み立てます。",
                    "selected_candidate_id": state.selected_candidate_id,
                    "development_decision": state.selected_candidate_id,
                }
        # Delegate to resolver ADOPT patterns
        fu = handle_follow_up(
            state, envelope, user_message, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled
        )
        fu["intent"] = intent
        fu["development_decision"] = fu.get("selected_candidate_id")
        return fu

    if intent == "COMPARE_CANDIDATES":
        fu = handle_follow_up(
            state, envelope, user_message, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled
        )
        fu["intent"] = intent
        return fu

    if intent == "SHOW_SOURCE":
        fu = handle_follow_up(
            state, envelope, user_message, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled
        )
        fu["intent"] = intent
        return fu

    fu = handle_follow_up(
        state, envelope, user_message, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled
    )
    fu["intent"] = intent
    return fu
