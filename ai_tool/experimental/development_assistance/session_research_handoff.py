"""Session research bind — Experimental adapter, not a Knowledge Core.

Conversational pointers such as 「その技術A」do not match existing
resolve_research_reference patterns (those expect 「前に調べたA」or
a requirement starting with 「Aを」). Reuse then reports no_reuse and
Tool Spec is empty even though a ResearchRecord is in the session store.

This adapter binds only when session already has last_research_id or the
store has exactly one record. It does not guess a technology.
"""
from __future__ import annotations

import re
from typing import Any

from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore
from ai_tool.experimental.development_assistance.spec_draft import build_spec_draft

_POINTER = re.compile(
    r"その技術A|技術A|そのAを|そのAに|ある技術A|前回|前の結果|作ったTool|作成したTool",
    re.I,
)


def bind_last_research(
    requirement: str,
    store: ResearchStore,
    session: dict[str, Any],
) -> dict[str, Any]:
    """Bind a follow-up to session research. Never invent a record."""
    rid = str(session.get("last_research_id") or "")
    rec: ResearchRecord | None = None
    if rid:
        rec = next((r for r in store.records if r.research_id == rid), None)
    if rec is None and len(store.records) == 1:
        rec = store.records[0]
        rid = rec.research_id
    pointer = bool(_POINTER.search(requirement))
    bound = rec is not None and (pointer or bool(session.get("last_research_id")))
    return {
        "bound": bound,
        "research_id": rid if bound else "",
        "pointer_in_text": pointer,
        "guessed": False,
        "reason": (
            "session last_research_id or single store record"
            if bound
            else "no bind without session target or unique store record"
        ),
    }


def recover_spec_if_missing(
    requirement: str,
    *,
    spec: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    store: ResearchStore,
    session: dict[str, Any],
) -> dict[str, Any]:
    """If workflow produced no spec, copy candidates from bound ResearchRecord.

    RECORD: this is a handoff, not new research. EXPERIMENTAL.
    """
    if spec and candidates:
        return {
            "recovered": False,
            "spec": spec,
            "candidates": candidates,
            "reason": "workflow already produced spec",
        }
    bind = bind_last_research(requirement, store, session)
    rec = next((r for r in store.records if r.research_id == bind.get("research_id")), None)
    if not rec or not rec.technology_candidates:
        return {
            "recovered": False,
            "spec": spec,
            "candidates": candidates,
            "reason": "no bound ResearchRecord with candidates",
            "bind": bind,
        }
    cand = list(rec.technology_candidates)
    draft = build_spec_draft(requirement, cand[0]).to_dict()
    draft["provenance_note"] = (
        "Draft recovered from session ResearchRecord — not execution-verified"
    )
    return {
        "recovered": True,
        "spec": draft,
        "candidates": cand,
        "reason": "workflow spec empty; session ResearchRecord used",
        "bind": bind,
        "label": "EXPERIMENTAL",
    }
