"""
Phase 6: Memory Judge LLM。

規則が作った候補イベント（最大 8）から、今の open_questions に必要な 0〜3 件を選ぶ。
History 全件は読まない。失敗時は Phase 5 rule bundle にフォールバック。
"""

from __future__ import annotations

import json
import os
from typing import Any

from tools.ai.state.memory_recall import (
    MODE_FRESH,
    MODE_RELATED,
    MODE_REPEATING,
    MODE_ESCALATION,
    prior_failures_from_events,
)
from tools.ai.state.retrieve import get_event, preview_events

MEMORY_JUDGE_CANDIDATE_LIMIT = 8
MEMORY_JUDGE_SELECT_LIMIT = 3


def memory_judge_enabled() -> bool:
    """既定 OFF。AI_AGENT_MEMORY_JUDGE=1 で有効。"""
    return os.environ.get("AI_AGENT_MEMORY_JUDGE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _candidate_pool_from_bundle(bundle, state):
    """規則 bundle の recalled + History からスコア上位を最大 8 件。"""
    history = getattr(state, "research_history", None)
    previews = list((bundle or {}).get("recalled_events") or [])
    # policy_trace.scores があればそれで補完
    scores = list(((bundle or {}).get("policy_trace") or {}).get("scores") or [])
    by_id = {p.get("id"): p for p in previews if p.get("id")}
    for item in scores:
        eid = item.get("id")
        if eid and eid not in by_id:
            event = get_event(history, eid)
            if event:
                by_id[eid] = preview_events([event])[0]
    pool = list(by_id.values())[:MEMORY_JUDGE_CANDIDATE_LIMIT]
    return pool


def build_memory_judge_materials(state, rule_bundle):
    open_qs = list((rule_bundle or {}).get("open_questions") or [])
    usable = list((rule_bundle or {}).get("usable_findings") or [])[:5]
    candidates = _candidate_pool_from_bundle(rule_bundle, state)
    return {
        "goal_task": getattr(state, "task", "") or "",
        "open_questions": open_qs,
        "usable_summary": [
            item.get("summary") or item.get("finding") or item
            if isinstance(item, dict)
            else item
            for item in usable
        ],
        "candidate_events": candidates,
        "suggested_mode": (rule_bundle or {}).get("mode") or MODE_RELATED,
        "rules": [
            "Select 0 to 3 event ids from candidate_events that help answer open_questions.",
            "For a new problem prefer mode=fresh and selected_event_ids=[].",
            "For repeating failures keep mode=repeating and select the most relevant failures.",
            "Do not invent event ids.",
        ],
    }


def normalize_memory_judgment(payload, *, fallback_bundle):
    """不正 JSON 時は rule bundle を返す。"""
    if not isinstance(payload, dict):
        return None
    mode = str(payload.get("mode") or "").strip().lower()
    if mode not in (MODE_FRESH, MODE_RELATED, MODE_REPEATING, MODE_ESCALATION):
        mode = (fallback_bundle or {}).get("mode") or MODE_RELATED
    selected = payload.get("selected_event_ids") or []
    if isinstance(selected, str):
        selected = [selected]
    selected = [str(x).strip() for x in selected if str(x).strip()]
    selected = selected[:MEMORY_JUDGE_SELECT_LIMIT]
    return {
        "mode": mode,
        "selected_event_ids": selected,
        "omit_reason": str(payload.get("omit_reason") or "").strip(),
        "hint": str(payload.get("hint") or "").strip(),
    }


def apply_judgment_to_bundle(state, rule_bundle, judgment):
    """Memory Judge 出力で rule bundle を上書き。不正時は rule のまま。"""
    if not judgment:
        out = dict(rule_bundle or {})
        trace = dict(out.get("policy_trace") or {})
        trace["memory_judge"] = "fallback_invalid"
        out["policy_trace"] = trace
        return out
    history = getattr(state, "research_history", None)
    events = []
    for eid in judgment.get("selected_event_ids") or []:
        event = get_event(history, eid)
        if event:
            events.append(event)
    # fresh で空選択は許容
    if judgment.get("mode") == MODE_FRESH and not events:
        events = []
    elif not events and (rule_bundle or {}).get("recalled_events"):
        # 選択が解決できない → rule 維持
        out = dict(rule_bundle or {})
        trace = dict(out.get("policy_trace") or {})
        trace["memory_judge"] = "fallback_unresolved_ids"
        out["policy_trace"] = trace
        return out
    previews = preview_events(events)
    out = dict(rule_bundle or {})
    out["mode"] = judgment["mode"]
    out["recalled_events"] = previews
    out["prior_failures"] = prior_failures_from_events(state, events)
    if judgment.get("hint"):
        out["repeating_hint"] = judgment["hint"]
    trace = dict(out.get("policy_trace") or {})
    trace["memory_judge"] = "applied"
    trace["memory_judge_omit_reason"] = judgment.get("omit_reason")
    trace["recalled_event_count"] = len(previews)
    out["policy_trace"] = trace
    return out


def _extract_json_object(text):
    text = str(text or "")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def run_memory_judge_llm(materials, *, chat_fn=None, model=None):
    """
    LLM 呼び出し。chat_fn 未指定時は tools.system.llm.chat を使う。
    戻り値: (judgment_dict | None, raw_text, error)
    """
    prompt = (
        "Return ONLY one JSON object with keys: "
        "mode, selected_event_ids, omit_reason, hint.\n"
        + json.dumps(materials, ensure_ascii=False)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Memory Judge. Select which past failure events "
                "belong in the next research prompt. Output JSON only."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    try:
        if chat_fn is None:
            from tools.system.config import get_llm_profile
            from tools.system.llm import chat

            profile = get_llm_profile()
            model = model or profile.get("model")
            response = chat(model=model, messages=messages)
            text = response.message.content
        else:
            text = chat_fn(messages)
        payload = _extract_json_object(text)
        return payload, text, None
    except Exception as exc:
        return None, "", str(exc)


def apply_memory_judge(state, rule_bundle, *, chat_fn=None, model=None):
    """
    Memory Judge を適用。失敗時は rule_bundle をそのまま返す。
    """
    if not memory_judge_enabled():
        return rule_bundle
    materials = build_memory_judge_materials(state, rule_bundle)
    payload, _text, error = run_memory_judge_llm(
        materials, chat_fn=chat_fn, model=model
    )
    if error or payload is None:
        out = dict(rule_bundle or {})
        trace = dict(out.get("policy_trace") or {})
        trace["memory_judge"] = f"fallback_error:{error or 'no_json'}"
        out["policy_trace"] = trace
        return out
    judgment = normalize_memory_judgment(payload, fallback_bundle=rule_bundle)
    return apply_judgment_to_bundle(state, rule_bundle, judgment)
