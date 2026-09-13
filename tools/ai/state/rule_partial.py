"""Rule-based Partial Judge。Verify 結果から機械的に StatePatch / escalation を作る。"""

from tools.ai.state.open_questions import (
    compact_unresolved_for_state,
    question_text_from_finding,
)
from tools.ai.state.retrieve import event_preview, retrieve_events_for_question
from tools.ai.state.state_patch import apply_state_patches
from tools.ai.tool_builder.research_result import command_key


def _finding_summary(finding, *, limit=120):
    text = str((finding or {}).get("finding") or (finding or {}).get("question") or "").strip()
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def build_rule_patches_from_verify(round_research, *, history, round_num=None):
    """
    Verify 済み pack から StatePatch リストと event id を生成する。
    History へ finding を先に記録し、patch に event 参照を付ける。
    """
    patches = []
    event_ids = []
    round_research = round_research or {}

    for item in round_research.get("unresolved") or []:
        if not isinstance(item, dict):
            continue
        event_id = history.record_finding(
            item, event_type="verify_fail", round_num=round_num
        )
        event_ids.append(event_id)
        text = question_text_from_finding(item)
        if text:
            patches.append(
                {
                    "op": "add_open_question",
                    "text": text,
                    "event_id": event_id,
                }
            )
        command, args = command_key(item)
        if command:
            patches.append(
                {
                    "op": "ban_action",
                    "command": command,
                    "args": list(args),
                    "event_id": event_id,
                    "reason": "verify_fail",
                }
            )

    for item in round_research.get("usable_findings") or []:
        if not isinstance(item, dict):
            continue
        event_id = history.record_finding(
            item, event_type="verify_ok", round_num=round_num
        )
        event_ids.append(event_id)
        patches.append(
            {
                "op": "add_usable",
                "finding_ref": event_id,
                "summary": _finding_summary(item),
                "source": "rule_partial",
            }
        )

    return patches, event_ids


def decide_escalation(round_research, *, state, event_ids, applied_patches):
    """
    規則で判断できない / ゴール整合が必要な場合に escalation 情報を返す。

    Phase 2:
    - Partial LLM は未実装 → 必要時は via=partial_llm_unavailable で Global へ
    - 現行 Global Judge は常時併用するため、routine フラグで将来の間引きを準備
    """
    round_research = round_research or {}
    usable = [x for x in (round_research.get("usable_findings") or []) if isinstance(x, dict)]
    unresolved = [x for x in (round_research.get("unresolved") or []) if isinstance(x, dict)]
    reference = [
        x for x in (round_research.get("reference_findings") or []) if isinstance(x, dict)
    ]
    open_ids = [
        q.get("id")
        for q in (getattr(state, "open_questions", None) or [])
        if q.get("status") == "open" and q.get("id")
    ]

    history = getattr(state, "research_history", None)
    evidence = []
    if history is not None:
        for eid in (event_ids or [])[-5:]:
            for event in history.events:
                if event.get("id") == eid:
                    evidence.append(event_preview(event))
                    break

    base = {
        "related_event_ids": list(event_ids or [])[-5:],
        "related_question_ids": open_ids[:5],
        "evidence_preview": evidence,
        "applied_patch_ops": [
            p.get("op") for p in (applied_patches or []) if isinstance(p, dict)
        ],
    }

    if reference and not usable and not unresolved:
        return {
            **base,
            "level": "global_judge",
            "via": "partial_llm_unavailable",
            "reason": "ambiguous_reference_only",
            "needs_partial_llm": True,
            "routine": False,
        }

    if usable:
        return {
            **base,
            "level": "global_judge",
            "via": "rule_partial",
            "reason": "usable_needs_goal_check",
            "needs_partial_llm": False,
            "routine": False,
        }

    if unresolved:
        return {
            **base,
            "level": "global_judge",
            "via": "rule_partial",
            "reason": "verify_fail_open_questions_updated",
            "needs_partial_llm": False,
            "routine": True,
        }

    return {
        **base,
        "level": "global_judge",
        "via": "rule_partial",
        "reason": "empty_round_needs_review",
        "needs_partial_llm": False,
        "routine": False,
    }


def apply_rule_partial(state, round_research, *, round_num=None):
    """
    Verify 後に規則ベース Partial を適用する。

    - research dict は変更しない
    - History に finding を記録し StatePatch を適用
    - 既存 Global Judge は呼び出し側が継続する（二重運用）
    """
    history = state.research_history
    patches, event_ids = build_rule_patches_from_verify(
        round_research, history=history, round_num=round_num
    )
    applied = apply_state_patches(state, patches, history=history)
    state.unresolved = compact_unresolved_for_state(state.open_questions)
    escalation = decide_escalation(
        round_research,
        state=state,
        event_ids=event_ids,
        applied_patches=applied,
    )
    return {
        "applied": applied,
        "event_ids": event_ids,
        "escalation": escalation,
        "needs_partial_llm": bool((escalation or {}).get("needs_partial_llm")),
        "needs_global_judge": True,
        "findings_recorded": True,
    }


def retrieve_escalation_evidence(state, escalation, *, limit=3):
    """escalation の related_question から History 断片を補完する。"""
    escalation = dict(escalation or {})
    previews = list(escalation.get("evidence_preview") or [])
    if len(previews) >= limit:
        return escalation
    for qid in escalation.get("related_question_ids") or []:
        for event in retrieve_events_for_question(state, qid, limit=1):
            preview = event_preview(event)
            if preview.get("id") and preview["id"] not in {
                item.get("id") for item in previews
            }:
                previews.append(preview)
            if len(previews) >= limit:
                break
        if len(previews) >= limit:
            break
    escalation["evidence_preview"] = previews[:limit]
    return escalation
