"""Phase 1 Cognitive State — generate / update / visualize only.

Does NOT call Diagnostic Selector, Tools, GPT, or auto-fix.
Sidecar to TaskState: unresolved questions can sync from open_questions.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any


PHASE = "cognitive_phase1"
SCHEMA_VERSION = "0.1"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def empty_cognitive_state(
    *,
    goal: str = "",
    intent: str = "",
    session_id: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    """Create a minimal Cognitive State document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "session_id": session_id or _new_id("cog"),
        "created_at": _now(),
        "updated_at": _now(),
        "human_review": {
            "status": "pending_human_review",
            "confirmed_at": None,
            "reviewer": None,
            "note": "",
        },
        "goal": str(goal or "").strip(),
        "intent": str(intent or "").strip(),
        "claims": [],
        "hypotheses": [],
        "concepts": [],
        "evidence": [],
        "unresolved_questions": [],
        "confidence": {
            "overall": "unknown",
            "notes": "Phase 1: confidence is recorded only; not used for Selector or escalation.",
            "do_not_use_as_selector_signal": True,
        },
        "links": {
            "task_state_task": str(goal or "").strip(),
            "open_questions_synced": False,
        },
        "audit": [],
        "meta": {
            "source": source,
            "selector_invoked": False,
            "tool_execution_invoked": False,
            "auto_fix_allowed": False,
        },
    }


def snapshot_cognitive(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(state)


def _append_audit(
    state: dict[str, Any],
    *,
    action: str,
    reason_code: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    note: str = "",
) -> None:
    state.setdefault("audit", []).append(
        {
            "id": _new_id("aud"),
            "at": _now(),
            "action": action,
            "reason_code": reason_code,
            "note": note,
            "before_excerpt": _excerpt(before),
            "after_excerpt": _excerpt(after),
        }
    )
    state["updated_at"] = _now()
    # Re-open human review after substantive changes
    if action not in ("confirm", "render"):
        hr = state.setdefault("human_review", {})
        if hr.get("status") == "confirmed":
            hr["status"] = "pending_human_review"
            hr["confirmed_at"] = None


def _excerpt(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state:
        return None
    return {
        "goal": state.get("goal"),
        "intent": state.get("intent"),
        "claims_n": len(state.get("claims") or []),
        "hypotheses_n": len(state.get("hypotheses") or []),
        "unresolved_n": len(state.get("unresolved_questions") or []),
        "evidence_n": len(state.get("evidence") or []),
        "human_review": (state.get("human_review") or {}).get("status"),
    }


def set_goal(state: dict[str, Any], goal: str, *, reason_code: str = "set_goal", note: str = "") -> dict[str, Any]:
    before = snapshot_cognitive(state)
    state["goal"] = str(goal or "").strip()
    state.setdefault("links", {})["task_state_task"] = state["goal"]
    _append_audit(state, action="set_goal", reason_code=reason_code, before=before, after=state, note=note)
    return state


def set_intent(state: dict[str, Any], intent: str, *, reason_code: str = "set_intent", note: str = "") -> dict[str, Any]:
    before = snapshot_cognitive(state)
    state["intent"] = str(intent or "").strip()
    _append_audit(state, action="set_intent", reason_code=reason_code, before=before, after=state, note=note)
    return state


def add_claim(
    state: dict[str, Any],
    text: str,
    *,
    status: str = "proposed",
    reason_code: str = "add_claim",
    note: str = "",
) -> str:
    before = snapshot_cognitive(state)
    cid = _new_id("clm")
    state.setdefault("claims", []).append(
        {
            "id": cid,
            "text": str(text or "").strip()[:500],
            "status": status,
            "created_at": _now(),
        }
    )
    _append_audit(state, action="add_claim", reason_code=reason_code, before=before, after=state, note=note)
    return cid


def add_hypothesis(
    state: dict[str, Any],
    text: str,
    *,
    status: str = "open",
    reason_code: str = "add_hypothesis",
    note: str = "",
) -> str:
    before = snapshot_cognitive(state)
    hid = _new_id("hyp")
    state.setdefault("hypotheses", []).append(
        {
            "id": hid,
            "text": str(text or "").strip()[:500],
            "status": status,  # open | supported | rejected | unknown
            "created_at": _now(),
        }
    )
    _append_audit(state, action="add_hypothesis", reason_code=reason_code, before=before, after=state, note=note)
    return hid


def update_hypothesis_status(
    state: dict[str, Any],
    hypothesis_id: str,
    status: str,
    *,
    reason_code: str = "update_hypothesis",
    note: str = "",
) -> bool:
    before = snapshot_cognitive(state)
    for item in state.get("hypotheses") or []:
        if item.get("id") == hypothesis_id:
            item["status"] = status
            item["updated_at"] = _now()
            _append_audit(
                state, action="update_hypothesis", reason_code=reason_code, before=before, after=state, note=note
            )
            return True
    return False


def add_evidence(
    state: dict[str, Any],
    summary: str,
    *,
    kind: str = "note",
    ref: str = "",
    reason_code: str = "add_evidence",
    note: str = "",
) -> str:
    before = snapshot_cognitive(state)
    eid = _new_id("ev")
    state.setdefault("evidence", []).append(
        {
            "id": eid,
            "kind": kind,
            "summary": str(summary or "").strip()[:500],
            "ref": ref,
            "created_at": _now(),
        }
    )
    _append_audit(state, action="add_evidence", reason_code=reason_code, before=before, after=state, note=note)
    return eid


def add_unresolved(
    state: dict[str, Any],
    text: str,
    *,
    question_id: str | None = None,
    reason_code: str = "add_unresolved",
    note: str = "",
) -> str:
    before = snapshot_cognitive(state)
    text = str(text or "").strip()[:200]
    if not text:
        return ""
    for item in state.get("unresolved_questions") or []:
        if item.get("status") == "open" and item.get("text", "").lower() == text.lower():
            return item["id"]
    qid = question_id or _new_id("uq")
    state.setdefault("unresolved_questions", []).append(
        {
            "id": qid,
            "text": text,
            "status": "open",
            "created_at": _now(),
        }
    )
    _append_audit(state, action="add_unresolved", reason_code=reason_code, before=before, after=state, note=note)
    return qid


def resolve_unresolved(
    state: dict[str, Any],
    question_id: str,
    *,
    reason_code: str = "resolve_unresolved",
    note: str = "",
) -> bool:
    before = snapshot_cognitive(state)
    for item in state.get("unresolved_questions") or []:
        if item.get("id") == question_id and item.get("status") == "open":
            item["status"] = "resolved"
            item["resolved_at"] = _now()
            _append_audit(
                state, action="resolve_unresolved", reason_code=reason_code, before=before, after=state, note=note
            )
            return True
    return False


def set_confidence_notes(
    state: dict[str, Any],
    overall: str,
    notes: str = "",
    *,
    reason_code: str = "set_confidence",
) -> dict[str, Any]:
    before = snapshot_cognitive(state)
    state["confidence"] = {
        "overall": overall,
        "notes": notes or state.get("confidence", {}).get("notes", ""),
        "do_not_use_as_selector_signal": True,
    }
    _append_audit(state, action="set_confidence", reason_code=reason_code, before=before, after=state, note=notes)
    return state


def sync_unresolved_from_task_state(state: dict[str, Any], task_state: Any) -> int:
    """Copy open_questions from TaskState into unresolved_questions (ids preserved when possible)."""
    before = snapshot_cognitive(state)
    oqs = []
    if task_state is None:
        return 0
    if hasattr(task_state, "open_questions"):
        oqs = list(task_state.open_questions or [])
    elif isinstance(task_state, dict):
        oqs = list(task_state.get("open_questions") or [])
    added = 0
    existing_texts = {
        (i.get("text") or "").lower()
        for i in state.get("unresolved_questions") or []
        if i.get("status") == "open"
    }
    for q in oqs:
        if not isinstance(q, dict):
            continue
        if q.get("status") and q.get("status") != "open":
            continue
        text = str(q.get("text") or "").strip()
        if not text or text.lower() in existing_texts:
            continue
        state.setdefault("unresolved_questions", []).append(
            {
                "id": q.get("id") or _new_id("uq"),
                "text": text[:200],
                "status": "open",
                "from_task_state": True,
                "created_at": _now(),
            }
        )
        existing_texts.add(text.lower())
        added += 1
    if hasattr(task_state, "task") and task_state.task and not state.get("goal"):
        state["goal"] = str(task_state.task)
    state.setdefault("links", {})["open_questions_synced"] = True
    if added:
        _append_audit(
            state,
            action="sync_open_questions",
            reason_code="sync_from_task_state",
            before=before,
            after=state,
            note=f"added={added}",
        )
    return added


def confirm_human_review(
    state: dict[str, Any],
    *,
    reviewer: str = "",
    note: str = "",
) -> dict[str, Any]:
    before = snapshot_cognitive(state)
    state["human_review"] = {
        "status": "confirmed",
        "confirmed_at": _now(),
        "reviewer": reviewer or "human",
        "note": note,
    }
    _append_audit(state, action="confirm", reason_code="human_confirm", before=before, after=state, note=note)
    return state


def render_cognitive_markdown(state: dict[str, Any]) -> str:
    """Human-readable visualization for Phase 1 review."""
    hr = state.get("human_review") or {}
    conf = state.get("confidence") or {}
    meta = state.get("meta") or {}
    lines = [
        "# Cognitive State (Phase 1)",
        "",
        f"- session_id: `{state.get('session_id')}`",
        f"- updated_at: {state.get('updated_at')}",
        f"- human_review: **{hr.get('status')}**",
        f"- selector_invoked: `{meta.get('selector_invoked')}`",
        f"- tool_execution_invoked: `{meta.get('tool_execution_invoked')}`",
        f"- auto_fix_allowed: `{meta.get('auto_fix_allowed')}`",
        "",
        "## Goal",
        "",
        state.get("goal") or "_(empty)_",
        "",
        "## Intent",
        "",
        state.get("intent") or "_(empty)_",
        "",
        "## Claims",
        "",
    ]
    claims = state.get("claims") or []
    if not claims:
        lines.append("_(none)_")
    else:
        for c in claims:
            lines.append(f"- [{c.get('status')}] `{c.get('id')}`: {c.get('text')}")
    lines.extend(["", "## Hypotheses", ""])
    hyps = state.get("hypotheses") or []
    if not hyps:
        lines.append("_(none)_")
    else:
        for h in hyps:
            lines.append(f"- [{h.get('status')}] `{h.get('id')}`: {h.get('text')}")
    lines.extend(["", "## Evidence", ""])
    evs = state.get("evidence") or []
    if not evs:
        lines.append("_(none)_")
    else:
        for e in evs:
            ref = f" (ref: {e.get('ref')})" if e.get("ref") else ""
            lines.append(f"- [{e.get('kind')}] `{e.get('id')}`: {e.get('summary')}{ref}")
    lines.extend(["", "## Unresolved Questions", ""])
    uqs = state.get("unresolved_questions") or []
    open_u = [u for u in uqs if u.get("status") == "open"]
    if not open_u:
        lines.append("_(none open)_")
    else:
        for u in open_u:
            lines.append(f"- `{u.get('id')}`: {u.get('text')}")
    lines.extend(
        [
            "",
            "## Confidence (record only)",
            "",
            f"- overall: {conf.get('overall')}",
            f"- notes: {conf.get('notes')}",
            f"- do_not_use_as_selector_signal: {conf.get('do_not_use_as_selector_signal')}",
            "",
            "## Audit (recent)",
            "",
        ]
    )
    audits = list(state.get("audit") or [])[-10:]
    if not audits:
        lines.append("_(none)_")
    else:
        for a in audits:
            lines.append(
                f"- {a.get('at')} `{a.get('action')}` reason={a.get('reason_code')} {a.get('note') or ''}"
            )
    lines.extend(
        [
            "",
            "---",
            "",
            "Phase 1: Selector / Tool execution / auto-fix are **not** connected.",
            "",
        ]
    )
    return "\n".join(lines)


def init_from_user_request(user_request: str, *, source: str = "clarity") -> dict[str, Any]:
    state = empty_cognitive_state(goal=user_request, source=source)
    state["intent"] = "clarify_and_track_understanding"
    _append_audit(
        state,
        action="init",
        reason_code="init_from_user_request",
        before=None,
        after=state,
        note="Phase 1 initialization",
    )
    return state
