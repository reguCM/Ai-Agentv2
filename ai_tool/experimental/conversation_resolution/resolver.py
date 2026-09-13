"""Conversation resolution and follow-up handling (experimental PoC)."""
from __future__ import annotations

import re
import uuid
from typing import Any, Callable

from ai_tool.experimental.conversation_resolution.candidate_builder import (
    build_candidates_from_sources,
    choose_presentation_mode,
    classify_candidate_relation,
    difference_note,
)
from ai_tool.experimental.conversation_resolution.models import (
    ConversationState,
    FollowUpIntent,
    UserFacingPresentation,
)
from ai_tool.experimental.conversation_resolution.presenter import (
    build_presentation,
    format_source_navigation,
)
from ai_tool.experimental.evidence_context.packager import EvidenceSource
from ai_tool.web_tool_success_class_accuracy_evaluation import ExpectedFact

ChatFn = Callable[..., Any]


def resolution_system_prompt() -> str:
    return """
あなたはWeb Evidenceを材料に、ユーザーとの会話を行うアシスタントです（評価PoC）。

ルール:
- 通常は自然な一つの回答を優先する。
- 情報源の定義・年度が異なる場合のみ、候補を分けて説明してよい。
- 同一条件で矛盾する数値がある場合、勝手に一方を正解と決めない。
- Evidenceにない情報を捏造しない。
- 出典は必要なときだけ簡潔に触れる。URLの羅列は避ける。
""".strip()


def parse_follow_up_intent(user_message: str) -> FollowUpIntent:
    m = user_message.strip()
    if re.search(r"Aの方を採用|Aを採用|候補A|A側", m, re.I):
        return "ADOPT_A"
    if re.search(r"Bの方を採用|Bを採用|候補B|B側", m, re.I):
        return "ADOPT_B"
    if re.search(r"比較|違い|差", m):
        return "COMPARE"
    if re.search(r"元ページ|出典|ソース|URL|見せて|確認", m):
        return "SHOW_SOURCE"
    if re.search(r"両方|両方見", m):
        return "SHOW_BOTH"
    if m:
        return "CONTINUE"
    return "UNKNOWN"


def proxy_llm_response(state: ConversationState, *, difference: str) -> str:
    """Deterministic conversation proxy for offline PoC (not LLM Judge)."""
    cands = state.candidates
    if state.presentation_mode == "SINGLE" and cands:
        return f"{cands[0].claim}（出典: {cands[0].source_title}）"
    if state.presentation_mode == "MERGED" and cands:
        return f"複数ソースによれば、{cands[0].claim}"
    if state.presentation_mode in ("MULTI", "UNRESOLVED"):
        return "情報源によって時点や定義が異なります。詳細は候補をご確認ください。"
    return "確認できた範囲でお答えします。"


def call_resolution_llm(
    state: ConversationState,
    *,
    user_message: str,
    chat_fn: ChatFn | None,
    model: str,
    envelope: dict[str, Any],
) -> tuple[str, float | None]:
    if chat_fn is None:
        return proxy_llm_response(state, difference=envelope.get("difference_note") or ""), None

    import time

    ctx = {
        "candidates": envelope.get("candidates"),
        "relation": envelope.get("relation"),
        "presentation_mode": envelope.get("presentation_mode"),
        "difference_note": envelope.get("difference_note"),
    }
    messages = [
        {"role": "system", "content": resolution_system_prompt()},
        {
            "role": "user",
            "content": (
                f"USER_REQUEST: {state.user_request}\n"
                f"RESOLUTION_CONTEXT:\n{ctx}\n\n"
                f"USER_MESSAGE: {user_message}\n"
                "Evidenceに基づき会話的に回答してください。"
            ),
        },
    ]
    started = time.perf_counter()
    resp = chat_fn(messages=messages, model=model)
    latency = round((time.perf_counter() - started) * 1000, 1)
    text = getattr(getattr(resp, "message", None), "content", None) or ""
    return text.strip(), latency


def initialize_conversation(
    sources: list[EvidenceSource],
    *,
    user_request: str,
    topic: str = "",
    expected_facts: list[ExpectedFact] | None = None,
) -> tuple[ConversationState, dict[str, Any]]:
    candidates = build_candidates_from_sources(sources, topic=topic, expected_facts=expected_facts)
    relation = classify_candidate_relation(candidates)
    mode = choose_presentation_mode(relation)
    diff = difference_note(candidates, relation)
    envelope = {
        "candidates": [c.to_dict() for c in candidates],
        "relation": relation,
        "presentation_mode": mode,
        "difference_note": diff,
        "user_request": user_request,
    }
    state = ConversationState(
        session_id=str(uuid.uuid4())[:8],
        user_request=user_request,
        candidates=candidates,
        presentation_mode=mode,
        relation=relation,
        turn=0,
    )
    return state, envelope


def resolve_initial_turn(
    state: ConversationState,
    envelope: dict[str, Any],
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    llm_body, latency = call_resolution_llm(
        state,
        user_message=state.user_request,
        chat_fn=chat_fn if llm_enabled else None,
        model=model,
        envelope=envelope,
    )
    presentation = build_presentation(state, llm_body=llm_body, difference_note=envelope.get("difference_note") or "")
    state.turn = 1
    return {
        "turn": 1,
        "llm_body": llm_body,
        "latency_ms": latency,
        "presentation": presentation.to_dict(),
        "presentation_mode": state.presentation_mode,
        "relation": state.relation,
    }


def handle_follow_up(
    state: ConversationState,
    envelope: dict[str, Any],
    user_message: str,
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    intent = parse_follow_up_intent(user_message)
    response_type = "conversation"
    navigation: str | None = None
    selected = state.selected_candidate_id

    if intent == "ADOPT_A" and state.candidates:
        selected = state.candidates[0].candidate_id
        state.selected_candidate_id = selected
        response_type = "user_decision"
        body = f"了解しました。{state.candidates[0].label}（{state.candidates[0].source_title}）の情報を基準に続けます。"
    elif intent == "ADOPT_B" and len(state.candidates) >= 2:
        selected = state.candidates[1].candidate_id
        state.selected_candidate_id = selected
        response_type = "user_decision"
        c = state.candidates[1]
        body = f"了解しました。{c.label}（{c.source_title}）の情報を基準に続けます。"
    elif intent == "SHOW_SOURCE":
        target = next((c for c in state.candidates if c.candidate_id == selected), None)
        if not target:
            target = state.candidates[0] if state.candidates else None
        if target:
            navigation = format_source_navigation(target)
            body = navigation
            response_type = "source_navigation"
        else:
            body = "参照可能な出典がありません。"
    elif intent == "SHOW_BOTH":
        body = "\n\n".join(format_source_navigation(c) for c in state.candidates)
        response_type = "source_navigation"
    elif intent == "COMPARE":
        body = envelope.get("difference_note") or "候補間の差異は整理中です。"
        for c in state.candidates:
            body += f"\n{c.label}: {c.claim}"
        response_type = "comparison"
    else:
        llm_body, latency = call_resolution_llm(
            state,
            user_message=user_message,
            chat_fn=chat_fn if llm_enabled else None,
            model=model,
            envelope=envelope,
        )
        body = llm_body
        latency = latency
        return {
            "turn": state.turn + 1,
            "intent": intent,
            "response_type": response_type,
            "body": body,
            "selected_candidate_id": state.selected_candidate_id,
            "latency_ms": latency,
        }

    state.turn += 1
    return {
        "turn": state.turn,
        "intent": intent,
        "response_type": response_type,
        "body": body,
        "selected_candidate_id": state.selected_candidate_id,
        "source_navigation": navigation,
    }
