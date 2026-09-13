"""
Phase 4 / 4.1: 明示的 Context 枠配分 + 常時 reserved headroom。

正式化後の通常経路:
  live allocation ON（AI_AGENT_CONTEXT_ALLOC_LIVE=0 で legacy 送信に戻す）
  計測は既定 ON（AI_AGENT_CONTEXT_ALLOC_SHADOW=0 でオフ）

現行の圧縮（web.py / research_judge.py）は互換層として維持し、
その上で Retriever ベースの slim materials を組み立てる。

allocation（論理カテゴリ）と transport（1 message 送信）は分離する。
複数 message / 複数 turn は未実装（将来 adapter 側で選択可能）。
"""

from __future__ import annotations

import copy
import os
from typing import Any

from tools.ai.llm.adapter import (
    dumps_json,
    render_contract_items,
    render_materials,
    render_state,
)
from tools.ai.llm.context_budget import (
    estimate_messages_chars,
    prompt_budget_chars,
)
from tools.ai.prompts.create import (
    RESEARCH_JUDGE_CONTRACT,
    RESEARCH_JUDGE_JSON_SHAPE,
    WEB_CANDIDATE_CONTRACT,
    WEB_CANDIDATE_JSON_SHAPE,
)
from tools.ai.prompts.state import STATE_CONTRACT
from tools.ai.state.retrieve import (
    preview_events,
    retrieve_failures_for_open_questions,
)
from tools.ai.state.memory_recall import (
    apply_recall_limit,
    build_recall_bundle,
    empty_recall_bundle,
    memory_recall_enabled,
)
from tools.ai.state.task_state import snapshot_state
from tools.ai.tool_builder.web import (
    compact_judge_reason_for_candidate,
    compact_prior_failures_for_candidate,
    compact_search_results_for_candidate,
)
from tools.system.config import get_llm_profile

RESERVED_HEADROOM_CHARS = 800

BUILDER_WEB = "build_web_candidate_messages"
BUILDER_JUDGE = "build_research_judge_messages"

# 中核カテゴリ（最後まで保護）
CORE_WEB_CATEGORIES = frozenset(
    {"system", "goal", "current_state", "open_questions", "usable_findings"}
)
CORE_JUDGE_CATEGORIES = frozenset(
    {"system", "goal_state", "usable_findings", "current_state", "open_questions"}
)

ALLOCATION_PROFILES = {
    BUILDER_WEB: {
        "sections": {
            "system": 1200,
            "goal": 200,
            "current_state": 800,
            "open_questions": 400,
            "recent_events": 600,
            "summary": 400,
            "action_local": 1200,
            "safety": 300,
        },
        "headroom": RESERVED_HEADROOM_CHARS,
    },
    BUILDER_JUDGE: {
        "sections": {
            "system": 1500,
            "goal_state": 1200,
            "summary": 600,
            "escalation_evidence": 800,
        },
        "headroom": RESERVED_HEADROOM_CHARS,
    },
}

WEB_GOAL_KEYS = ("subject", "items", "followup_questions")
WEB_ACTION_LOCAL_KEYS = ("search_results", "inventory", "search_keywords")
WEB_RECENT_KEYS = ("prior_failures", "recent_events")
WEB_SAFETY_KEYS = (
    "rules",
    "rejected_commands",
    "exploration_hints",
    "route_hints",
    "environment",
    "empty_search",
)
WEB_SUMMARY_KEYS = ("judge_reason",)

JUDGE_GOAL_STATE_KEYS = ("target_request", "output")
JUDGE_ESCALATION_KEYS = ("unresolved", "insufficient_findings", "insufficient_summary")
JUDGE_SUMMARY_KEYS = ("judging_hints",)
JUDGE_USABLE_KEYS = ("usable_findings",)

# 重要度ベース削減（補助→件数→action-local）。中核は触らない。
REDUCTION_STEPS = (
    {
        "label": "baseline",
        "recent_limit": 3,
        "search_limit": 3,
        "insufficient_keep": 5,
        "omit_route_hints": False,
        "omit_exploration_hints": False,
        "drop_judge_reason": False,
        "trim_rejected": False,
    },
    {
        "label": "omit_hints",
        "recent_limit": 3,
        "search_limit": 3,
        "insufficient_keep": 5,
        "omit_route_hints": True,
        "omit_exploration_hints": "unless_empty_search",
        "drop_judge_reason": False,
        "trim_rejected": False,
    },
    {
        "label": "reduce_recent",
        "recent_limit": 2,
        "search_limit": 3,
        "insufficient_keep": 3,
        "omit_route_hints": True,
        "omit_exploration_hints": "unless_empty_search",
        "drop_judge_reason": True,
        "trim_rejected": False,
    },
    {
        "label": "reduce_retrieve",
        "recent_limit": 1,
        "search_limit": 2,
        "insufficient_keep": 2,
        "omit_route_hints": True,
        "omit_exploration_hints": True,
        "drop_judge_reason": True,
        "trim_rejected": True,
    },
    {
        "label": "minimal_action_local",
        "recent_limit": 1,
        "search_limit": 1,
        "insufficient_keep": 1,
        "omit_route_hints": True,
        "omit_exploration_hints": True,
        "drop_judge_reason": True,
        "trim_rejected": True,
    },
)

_shadow_collector: list[dict[str, Any]] | None = None


def context_alloc_shadow_enabled() -> bool:
    return os.environ.get("AI_AGENT_CONTEXT_ALLOC_SHADOW", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def context_alloc_live_enabled() -> bool:
    """
    Phase 4 正式化以降: allocated prompt 送信が通常経路。
    オフにするときだけ AI_AGENT_CONTEXT_ALLOC_LIVE=0（legacy 圧縮のまま送信）。
    """
    raw = os.environ.get("AI_AGENT_CONTEXT_ALLOC_LIVE")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def init_context_budget_shadow() -> dict[str, Any]:
    global _shadow_collector
    _shadow_collector = []
    return {
        "mode": "live" if context_alloc_live_enabled() else "shadow",
        "shadow_enabled": context_alloc_shadow_enabled(),
        "headroom_chars": RESERVED_HEADROOM_CHARS,
        "calls": [],
        "summary": {},
    }


def _active_collector() -> list[dict[str, Any]] | None:
    return _shadow_collector


def record_context_budget_call(entry: dict[str, Any]) -> None:
    collector = _active_collector()
    if collector is not None:
        collector.append(entry)


def headroom_gate_ok(actual_headroom, *, reserved=RESERVED_HEADROOM_CHARS) -> bool:
    if actual_headroom is None:
        return False
    return int(actual_headroom) >= int(reserved)


def finalize_context_budget_shadow(summary: dict[str, Any]) -> dict[str, Any]:
    global _shadow_collector
    calls = list(summary.get("calls") or [])
    if not calls and _shadow_collector:
        calls = list(_shadow_collector)
    summary["calls"] = calls
    legacy_chars = [item.get("legacy_chars") or 0 for item in calls]
    allocated_chars = [item.get("allocated_chars") or 0 for item in calls]
    actual_headrooms = [
        item.get("actual_headroom")
        for item in calls
        if item.get("actual_headroom") is not None
    ]
    headroom_violations = [
        item
        for item in calls
        if not headroom_gate_ok(item.get("actual_headroom"))
    ]
    summary["summary"] = {
        "call_count": len(calls),
        "legacy_chars_total": sum(legacy_chars),
        "allocated_chars_total": sum(allocated_chars),
        "legacy_chars_max": max(legacy_chars) if legacy_chars else 0,
        "allocated_chars_max": max(allocated_chars) if allocated_chars else 0,
        "legacy_overflow_count": sum(
            1 for item in calls if item.get("legacy_overflow")
        ),
        "allocated_overflow_count": sum(
            1 for item in calls if item.get("allocated_overflow")
        ),
        "reserved_headroom": RESERVED_HEADROOM_CHARS,
        "actual_headroom_min": min(actual_headrooms) if actual_headrooms else None,
        "actual_headroom_max": max(actual_headrooms) if actual_headrooms else None,
        "headroom_gate_ok": len(headroom_violations) == 0 and bool(calls),
        "headroom_violation_count": len(headroom_violations),
        "reduction_applied_count": sum(
            1 for item in calls if (item.get("reduction_level") or 0) > 0
        ),
        "defer_count": sum(1 for item in calls if item.get("defer")),
    }
    _shadow_collector = None
    return summary


def effective_budget_chars(profile=None, *, headroom=RESERVED_HEADROOM_CHARS):
    budget = prompt_budget_chars(profile)
    if budget is None:
        return None
    return max(int(budget) - int(headroom), 0)


def _json_chars(value, profile=None) -> int:
    return len(dumps_json(value, profile))


def _question_text_for_event(state, event):
    event_id = str((event or {}).get("id") or "").strip()
    for question in getattr(state, "open_questions", None) or []:
        related = list(question.get("related_events") or [])
        if event_id and event_id in related:
            return str(question.get("text") or question.get("question") or "").strip()
    action = (event or {}).get("action") or {}
    command = str(action.get("command") or "").strip()
    return f"verify failure for {command}" if command else "verify failure"


def prior_failures_from_retriever(state, *, limit=3):
    """History Retriever から Web candidate 用 prior_failures を組み立てる。"""
    events = retrieve_failures_for_open_questions(
        state, limit_per_question=max(1, limit), total_limit=limit
    )
    previews = preview_events(events)
    failures = []
    for event, preview in zip(events, previews):
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        entry = {
            "question": _question_text_for_event(state, event),
            "finding": str(preview.get("type") or "verify_fail"),
            "error": str(preview.get("error_preview") or "").strip(),
        }
        command = str(preview.get("command") or action.get("command") or "").strip()
        if command:
            entry["command"] = command
        args = action.get("args")
        if args:
            entry["args"] = list(args)
        failures.append(entry)
    return failures, events


def compact_state_for_prompt(state, *, open_question_limit=8, finding_limit=5):
    payload = snapshot_state(state) or {}
    payload = copy.deepcopy(payload)
    open_questions = [
        item
        for item in (payload.get("open_questions") or [])
        if str(item.get("status") or "open") == "open"
    ][:open_question_limit]
    payload["open_questions"] = open_questions
    if open_questions:
        payload.pop("unresolved", None)
    selected = list(payload.get("selected_findings") or [])[:finding_limit]
    payload["selected_findings"] = selected
    banned = getattr(state, "banned_actions", None) or []
    if banned:
        payload["banned_actions"] = [
            {
                "command": item.get("command"),
                "reason": str(item.get("reason") or "")[:80],
            }
            for item in banned[:8]
            if isinstance(item, dict)
        ]
    return payload


def _summarize_insufficient_findings(items, *, keep=3):
    items = list(items or [])
    if len(items) <= keep:
        return items, None
    kept = items[:keep]
    summary = {
        "total": len(items),
        "shown": keep,
        "note": "Additional insufficient findings remain in History; only recent examples shown.",
    }
    return kept, summary


def _should_omit_exploration_hints(materials, policy) -> bool:
    if policy is True:
        return True
    if policy is False or policy is None:
        return False
    if policy == "unless_empty_search":
        return not bool(materials.get("empty_search"))
    return False


def _trim_rejected_commands(items, *, limit=6):
    trimmed = []
    for item in list(items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        entry = {}
        if item.get("command") not in (None, ""):
            entry["command"] = item.get("command")
        if "args" in item:
            entry["args"] = list(item.get("args") or [])
        trimmed.append(entry)
    return trimmed


def materials_for_prompt(materials):
    """Prompt に載せない内部メタを除去する。"""
    payload = copy.deepcopy(materials or {})
    payload.pop("_context_allocation", None)
    payload.pop("_allocation_categories", None)
    payload.pop("_recall_bundle", None)
    payload.pop("policy_trace", None)
    return payload


def _last_judge_reason_from_history(state):
    history = getattr(state, "research_history", None)
    if history is None:
        return ""
    for event in reversed(getattr(history, "events", None) or []):
        if event.get("type") != "judge":
            continue
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        reason = str((result or {}).get("reason") or "").strip()
        if reason:
            return reason
    return ""


def allocate_web_candidate_materials(materials, state, *, reduction=None):
    """
    Web candidate 用 slim materials。
    Phase 5: Memory Recall Policy が過去失敗を選ぶ。
    """
    reduction = reduction or REDUCTION_STEPS[0]
    base = copy.deepcopy(materials or {})
    omitted = []
    recent_limit = int(reduction.get("recent_limit") or 3)
    search_limit = int(reduction.get("search_limit") or 3)

    recall_bundle = empty_recall_bundle()
    if memory_recall_enabled() and state is not None:
        judge_reason = base.get("judge_reason") or _last_judge_reason_from_history(state)
        recall_bundle = build_recall_bundle(
            state,
            current_round=None,
            judge_reason=judge_reason,
            recent_limit=recent_limit,
        )
        recall_bundle = apply_recall_limit(recall_bundle, recent_limit=recent_limit)
        # Phase 6 Memory Judge（opt-in）
        try:
            from tools.ai.state.memory_judge import (
                apply_memory_judge,
                memory_judge_enabled,
            )

            if memory_judge_enabled():
                recall_bundle = apply_memory_judge(state, recall_bundle)
        except Exception:
            pass
        base["prior_failures"] = compact_prior_failures_for_candidate(
            recall_bundle.get("prior_failures") or [],
            base.get("rejected_commands") or recall_bundle.get("banned_digest"),
        )
        base["recent_events"] = list(recall_bundle.get("recalled_events") or [])
        if recall_bundle.get("banned_digest") and not base.get("rejected_commands"):
            base["rejected_commands"] = list(recall_bundle.get("banned_digest") or [])
        if recall_bundle.get("judge_summary"):
            base["judge_reason"] = recall_bundle["judge_summary"]
        elif reduction.get("drop_judge_reason"):
            base["judge_reason"] = ""
        if recall_bundle.get("repeating_hint"):
            hints = list(base.get("exploration_hints") or [])
            hint = recall_bundle["repeating_hint"]
            # pivot を先頭に。増量ではなく差し替え優先
            hints = [hint] + [h for h in hints if h != hint]
            base["exploration_hints"] = hints[:4]
        if recall_bundle.get("pivot_required"):
            base["pivot_required"] = True
            if recall_bundle.get("stuck_error_class"):
                base["stuck_error_class"] = recall_bundle["stuck_error_class"]
            if recall_bundle.get("stuck_family"):
                base["stuck_family"] = recall_bundle["stuck_family"]
        prior_source = "memory_recall"
        retrieved_count = len(base["recent_events"])
        base["_recall_bundle"] = {
            "mode": recall_bundle.get("mode"),
            "policy_trace": recall_bundle.get("policy_trace"),
        }
    else:
        retriever_failures, retrieved_events = prior_failures_from_retriever(
            state, limit=recent_limit
        )
        if retriever_failures:
            base["prior_failures"] = compact_prior_failures_for_candidate(
                retriever_failures, base.get("rejected_commands")
            )
            base["recent_events"] = preview_events(retrieved_events)
            prior_source = "retriever"
            retrieved_count = len(retrieved_events)
        else:
            legacy_prior = list(base.get("prior_failures") or [])[:recent_limit]
            base["prior_failures"] = compact_prior_failures_for_candidate(
                legacy_prior, base.get("rejected_commands")
            )
            base["recent_events"] = []
            prior_source = "legacy_trim"
            retrieved_count = 0

    base["search_results"] = compact_search_results_for_candidate(
        base.get("search_results"), limit=search_limit
    )

    if reduction.get("omit_route_hints"):
        if base.get("route_hints"):
            omitted.append("route_hints")
        base["route_hints"] = []

    if _should_omit_exploration_hints(base, reduction.get("omit_exploration_hints")):
        if base.get("exploration_hints"):
            omitted.append("exploration_hints")
        base["exploration_hints"] = []
    else:
        hints = list(base.get("exploration_hints") or [])
        if hints:
            base["exploration_hints"] = hints[:4]

    if memory_recall_enabled() and recall_bundle.get("judge_summary"):
        pass  # already set
    elif reduction.get("drop_judge_reason"):
        if base.get("judge_reason"):
            omitted.append("judge_reason")
        base["judge_reason"] = ""
    else:
        base["judge_reason"] = compact_judge_reason_for_candidate(
            base.get("judge_reason"), max_len=160
        )

    if reduction.get("trim_rejected"):
        before = len(base.get("rejected_commands") or [])
        base["rejected_commands"] = _trim_rejected_commands(
            base.get("rejected_commands"), limit=6
        )
        if before > len(base["rejected_commands"]):
            omitted.append("rejected_commands_extra")

    open_count = len(
        [
            q
            for q in (getattr(state, "open_questions", None) or [])
            if str(q.get("status") or "open") == "open"
        ]
    )
    meta = {
        "source": "allocated",
        "reduction_label": reduction.get("label"),
        "recent_limit": recent_limit,
        "search_limit": search_limit,
        "retrieve_count": retrieved_count,
        "prior_failures_count": len(base.get("prior_failures") or []),
        "search_results_count": len(base.get("search_results") or []),
        "prior_failures_source": prior_source,
        "recall_mode": recall_bundle.get("mode") if memory_recall_enabled() else None,
        "recalled_event_count": (
            (recall_bundle.get("policy_trace") or {}).get("recalled_event_count")
            if memory_recall_enabled()
            else retrieved_count
        ),
        "pivot_required": bool(recall_bundle.get("pivot_required"))
        if memory_recall_enabled()
        else False,
        "stuck_error_class": recall_bundle.get("stuck_error_class")
        if memory_recall_enabled()
        else None,
        "omitted_categories": omitted,
        "open_questions_count": open_count,
        "usable_findings_count": None,
    }
    base["_context_allocation"] = meta
    return base


def allocate_judge_materials(materials, state, *, reduction=None, escalation=True):
    """Global Judge 用 slim materials。usable_findings は保護する。"""
    reduction = reduction or REDUCTION_STEPS[0]
    base = copy.deepcopy(materials or {})
    omitted = []
    keep = int(reduction.get("insufficient_keep") or 5)
    insufficient = list(base.get("insufficient_findings") or [])
    trimmed, summary = _summarize_insufficient_findings(insufficient, keep=keep)
    if len(insufficient) > keep:
        omitted.append("insufficient_findings_extra")
    base["insufficient_findings"] = trimmed
    if summary:
        base["insufficient_summary"] = summary
    state_payload = compact_state_for_prompt(state)
    if state_payload.get("open_questions"):
        if "unresolved" in base:
            omitted.append("unresolved_duplicate")
        base.pop("unresolved", None)
    if memory_recall_enabled() and state is not None and escalation:
        recall_bundle = build_recall_bundle(
            state,
            escalation=True,
            recent_limit=int(reduction.get("recent_limit") or 5),
        )
        if recall_bundle.get("recalled_events"):
            base["recalled_events"] = recall_bundle["recalled_events"]
        base["_recall_bundle"] = {
            "mode": recall_bundle.get("mode"),
            "policy_trace": recall_bundle.get("policy_trace"),
        }
    if reduction.get("drop_judge_reason") and base.get("judging_hints"):
        hints = list(base.get("judging_hints") or [])
        if len(hints) > 3:
            base["judging_hints"] = hints[:3]
            omitted.append("judging_hints_extra")
    open_count = len(state_payload.get("open_questions") or [])
    usable_count = len(base.get("usable_findings") or [])
    meta = {
        "source": "allocated",
        "reduction_label": reduction.get("label"),
        "insufficient_keep": keep,
        "retrieve_count": len(base.get("recalled_events") or []),
        "omitted_categories": omitted,
        "unresolved_in_materials": "unresolved" in base,
        "open_questions_count": open_count,
        "usable_findings_count": usable_count,
        "recall_mode": (base.get("_recall_bundle") or {}).get("mode"),
        "recalled_event_count": len(base.get("recalled_events") or []),
    }
    base["_context_allocation"] = meta
    return base, state_payload


def _builder_contract(builder_name):
    if builder_name == BUILDER_WEB:
        return WEB_CANDIDATE_CONTRACT, WEB_CANDIDATE_JSON_SHAPE, []
    if builder_name == BUILDER_JUDGE:
        return RESEARCH_JUDGE_CONTRACT, RESEARCH_JUDGE_JSON_SHAPE, list(STATE_CONTRACT)
    return None, None, []


def _section_chars(mapping: dict[str, Any], keys, profile=None) -> int:
    payload = {key: mapping.get(key) for key in keys if key in mapping}
    if not payload:
        return 0
    return _json_chars(payload, profile)


def measure_prompt_sections(
    builder_name,
    materials,
    *,
    state=None,
    state_payload=None,
    extra=None,
    profile=None,
):
    profile = profile or get_llm_profile()
    contract, shape, state_contract = _builder_contract(builder_name)
    if contract is None:
        return {"total": 0, "sections": {}, "system": 0, "user": 0}
    prompt_materials = materials_for_prompt(materials)
    system_text = render_contract_items(
        contract, shape, profile, extra_items=state_contract or None
    )
    system_chars = len(system_text)
    state_text = ""
    if state is not None or state_payload is not None:
        state_text = render_state(
            state_payload if state_payload is not None else state, profile
        )
    materials_text = render_materials(prompt_materials, profile)
    extra_chars = len(str(extra or ""))
    sections = {}
    if builder_name == BUILDER_WEB:
        sections = {
            "system": system_chars,
            "goal": _section_chars(prompt_materials, WEB_GOAL_KEYS, profile),
            "current_state": len(state_text),
            "open_questions": _json_chars(
                (state_payload or snapshot_state(state) or {}).get("open_questions")
                or [],
                profile,
            ),
            "recent_events": _section_chars(prompt_materials, WEB_RECENT_KEYS, profile),
            "summary": _section_chars(prompt_materials, WEB_SUMMARY_KEYS, profile),
            "action_local": _section_chars(
                prompt_materials, WEB_ACTION_LOCAL_KEYS, profile
            ),
            "safety": _section_chars(prompt_materials, WEB_SAFETY_KEYS, profile),
            "extra": extra_chars,
        }
    elif builder_name == BUILDER_JUDGE:
        sections = {
            "system": system_chars,
            "goal_state": _section_chars(prompt_materials, JUDGE_GOAL_STATE_KEYS, profile)
            + len(state_text),
            "summary": _section_chars(prompt_materials, JUDGE_SUMMARY_KEYS, profile),
            "escalation_evidence": _section_chars(
                prompt_materials, JUDGE_ESCALATION_KEYS, profile
            ),
            "usable_findings": _section_chars(
                prompt_materials, JUDGE_USABLE_KEYS, profile
            ),
            "extra": extra_chars,
        }
    user_chars = len(
        "\n\n".join(
            part for part in (state_text, materials_text, str(extra or "")) if part
        )
    )
    total = system_chars + user_chars
    return {
        "total": total,
        "system": system_chars,
        "user": user_chars,
        "sections": sections,
        "materials": materials_text,
        "state": state_text,
    }


def build_allocation_categories(
    builder_name,
    materials,
    *,
    state_payload=None,
    sections=None,
    omitted=None,
):
    """
    論理カテゴリ構造。transport（1 message / 複数 message）とは独立。
    Phase 4.1 では単一 message に畳むだけ。
    """
    materials = materials or {}
    state_payload = state_payload or {}
    sections = sections or {}
    meta = materials.get("_context_allocation") or {}
    if builder_name == BUILDER_WEB:
        categories = {
            "system": {"chars": sections.get("system"), "core": True},
            "goal": {
                "chars": sections.get("goal"),
                "core": True,
                "keys": list(WEB_GOAL_KEYS),
            },
            "current_state": {"chars": sections.get("current_state"), "core": True},
            "open_questions": {
                "chars": sections.get("open_questions"),
                "core": True,
                "count": meta.get("open_questions_count"),
            },
            "recent_events": {
                "chars": sections.get("recent_events"),
                "core": False,
                "retrieve_count": meta.get("retrieve_count"),
            },
            "action_local": {
                "chars": sections.get("action_local"),
                "core": False,
                "search_results_count": meta.get("search_results_count"),
            },
            "safety": {"chars": sections.get("safety"), "core": False},
            "summary": {"chars": sections.get("summary"), "core": False},
        }
    else:
        categories = {
            "system": {"chars": sections.get("system"), "core": True},
            "goal_state": {"chars": sections.get("goal_state"), "core": True},
            "usable_findings": {
                "chars": sections.get("usable_findings"),
                "core": True,
                "count": meta.get("usable_findings_count"),
            },
            "escalation_evidence": {
                "chars": sections.get("escalation_evidence"),
                "core": False,
            },
            "summary": {"chars": sections.get("summary"), "core": False},
            "open_questions": {
                "chars": None,
                "core": True,
                "count": meta.get("open_questions_count"),
            },
        }
    return {
        "categories": categories,
        "omitted_categories": list(omitted or meta.get("omitted_categories") or []),
        "transport": "single_message",
        "core_protected": True,
    }


def _build_messages(
    builder, materials, *, state=None, state_payload=None, extra=None, profile=None
):
    use_state = state_payload if state_payload is not None else state
    return builder(
        materials_for_prompt(materials),
        extra=extra,
        state=use_state,
        profile=profile,
    )


def _estimate_messages(messages):
    total, breakdown = estimate_messages_chars(messages)
    return total, breakdown


def _actual_headroom(budget_total, allocated_chars):
    if budget_total is None:
        return None
    return int(budget_total) - int(allocated_chars)


def prepare_context_allocation_call(
    builder,
    materials,
    *,
    state=None,
    extra=None,
    profile=None,
):
    """
    legacy / allocated の両方を計測し、送信メッセージを決める。

    shadow（計測）: AI_AGENT_CONTEXT_ALLOC_SHADOW（既定 ON）
    live（送信）: Phase 4 正式化後は既定 ON。AI_AGENT_CONTEXT_ALLOC_LIVE=0 で legacy 送信。

    成功条件の主指標: actual_headroom = budget_total - allocated_chars >= 800
    """
    profile = profile or get_llm_profile()
    builder_name = getattr(builder, "__name__", str(builder))
    budget_total = prompt_budget_chars(profile)
    budget_effective = effective_budget_chars(profile)
    live = context_alloc_live_enabled()
    supports_allocation = builder_name in ALLOCATION_PROFILES

    legacy_messages = builder(materials, extra=extra, state=state)
    legacy_chars, legacy_breakdown = _estimate_messages(legacy_messages)
    legacy_overflow = budget_total is not None and legacy_chars > budget_total
    legacy_actual_headroom = _actual_headroom(budget_total, legacy_chars)

    allocated_materials = materials
    allocated_state_payload = None
    allocated_messages = legacy_messages
    allocated_sections = {}
    allocated_chars = legacy_chars
    allocated_breakdown = legacy_breakdown
    allocated_overflow = legacy_overflow
    reduction_level = 0
    reduction_label = None
    defer = False
    overflow_action = None
    allocation_bundle = None

    if supports_allocation:
        for level, step in enumerate(REDUCTION_STEPS):
            if builder_name == BUILDER_WEB:
                allocated_materials = allocate_web_candidate_materials(
                    materials, state, reduction=step
                )
                allocated_state_payload = compact_state_for_prompt(state)
            else:
                allocated_materials, allocated_state_payload = allocate_judge_materials(
                    materials, state, reduction=step
                )
            allocated_messages = _build_messages(
                builder,
                allocated_materials,
                state=state,
                state_payload=allocated_state_payload,
                extra=extra,
                profile=profile,
            )
            allocated_sections = measure_prompt_sections(
                builder_name,
                allocated_materials,
                state=state,
                state_payload=allocated_state_payload,
                extra=extra,
                profile=profile,
            )
            allocated_chars, allocated_breakdown = _estimate_messages(allocated_messages)
            actual_hr = _actual_headroom(budget_total, allocated_chars)
            allocated_overflow = not headroom_gate_ok(actual_hr)
            reduction_level = level
            reduction_label = step.get("label")
            allocation_bundle = build_allocation_categories(
                builder_name,
                allocated_materials,
                state_payload=allocated_state_payload,
                sections=allocated_sections.get("sections") or {},
            )
            if headroom_gate_ok(actual_hr):
                break
        else:
            allocated_chars, allocated_breakdown = _estimate_messages(allocated_messages)
            actual_hr = _actual_headroom(budget_total, allocated_chars)
            allocated_overflow = not headroom_gate_ok(actual_hr)
            defer = live and allocated_overflow
            overflow_action = "defer" if defer else "exhausted_reductions"
            reduction_level = len(REDUCTION_STEPS) - 1
    else:
        allocated_chars = legacy_chars
        allocated_breakdown = legacy_breakdown
        allocated_overflow = legacy_overflow

    actual_headroom = _actual_headroom(budget_total, allocated_chars)
    effective_slack = None
    if budget_effective is not None:
        effective_slack = budget_effective - allocated_chars

    send_messages = legacy_messages
    if live and supports_allocation and not defer:
        send_messages = allocated_messages
        overflow_action = "allocated" if reduction_level == 0 else "reduced"
    elif live and defer:
        send_messages = None

    meta = (allocated_materials or {}).get("_context_allocation") or {}
    measurement = {
        "builder": builder_name,
        "mode": "live" if live else "shadow",
        "budget_total": budget_total,
        "effective_budget": budget_effective,
        "reserved_headroom": RESERVED_HEADROOM_CHARS,
        "actual_headroom": actual_headroom,
        "effective_slack": effective_slack,
        "headroom_gate_ok": headroom_gate_ok(actual_headroom),
        "legacy_chars": legacy_chars,
        "allocated_chars": allocated_chars,
        "legacy_actual_headroom": legacy_actual_headroom,
        "legacy_overflow": legacy_overflow,
        "allocated_overflow": allocated_overflow if supports_allocation else legacy_overflow,
        "legacy_breakdown": legacy_breakdown,
        "allocated_breakdown": allocated_breakdown,
        "allocated_sections": allocated_sections.get("sections") or {},
        "category_usage": (allocation_bundle or {}).get("categories") or {},
        "omitted_categories": list(meta.get("omitted_categories") or []),
        "retrieve_count": meta.get("retrieve_count"),
        "usable_findings_count": meta.get("usable_findings_count"),
        "open_questions_count": meta.get("open_questions_count"),
        "recall_mode": meta.get("recall_mode"),
        "recalled_event_count": meta.get("recalled_event_count"),
        "reduction_level": reduction_level,
        "reduction_label": reduction_label,
        "defer": defer,
        "overflow_action": overflow_action,
        "allocation": allocation_bundle,
        "allocation_meta": meta,
        # 互換フィールド（Phase 4 初期）
        "budget_effective": budget_effective,
        "headroom_reserved": RESERVED_HEADROOM_CHARS,
        "allocated_headroom": actual_headroom,
        "legacy_headroom": legacy_actual_headroom,
    }

    if context_alloc_shadow_enabled() or live:
        record_context_budget_call(measurement)

    return {
        "messages": send_messages,
        "measurement": measurement,
        "allocated_materials": allocated_materials,
        "allocated_state_payload": allocated_state_payload,
        "allocation": allocation_bundle,
    }
