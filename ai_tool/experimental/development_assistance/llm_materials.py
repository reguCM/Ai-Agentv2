"""LLM に渡す材料。機械的 bind / diff / select のあとだけ。全記憶は渡さない。"""
from __future__ import annotations

from typing import Any

from ai_tool.experimental.development_assistance.memory_slice import compare_llm_payloads
from ai_tool.experimental.development_assistance.research_record import ResearchStore

FORBIDDEN_LLM_KEYS = frozenset(
    {
        "dump_all",
        "all_records",
        "search_memory",
        "feasible",
        "safe",
        "correct",
        "executable",
        "build",
    }
)

LLM_TASK = (
    "この材料から Development Spec を作成せよ。"
    "記憶から必要情報を探すな。未選択の Record を使うな。"
    "Unknown を Confirmed にするな。Conflict を一つの正解にまとめるな。"
    "確実に動く / 安全 / 実行可能 とは書くな。"
)


def build_llm_materials(
    *,
    requirement: str,
    store: ResearchStore,
    bound_research_id: str,
    bound_label: str,
    session_facets: dict[str, dict[str, Any]],
    missing: list[str],
    reusable: list[str],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """選択済み Facet だけを LLM 入力にする。dump_all は含めない。"""
    cmp_ = compare_llm_payloads(
        store,
        bound_research_id=bound_research_id,
        session_facet_ids=list(session_facets.keys()),
        missing_facet_ids=[m.split(":")[0] for m in missing],
    )
    rec = next((r for r in store.records if r.research_id == bound_research_id), None)
    selected_ids = list(cmp_["selected_ids"])
    evidence: list[dict[str, str]] = []
    if rec:
        wanted = set(selected_ids)
        for f in rec.facet_records or []:
            fid = str(f.get("facet_id") or "")
            if fid not in wanted:
                continue
            ev = f.get("evidence") or []
            evidence.append({"facet_id": fid, "evidence": str(ev[0] if ev else ""), "record": bound_research_id})
    py = session_facets.get("python_version") or {}
    os_ = session_facets.get("os") or {}
    cuda = session_facets.get("cuda") or {}
    unknown = [
        f"{k}:{v.get('value')}"
        for k, v in session_facets.items()
        if v.get("evidence") in {"UNKNOWN", "MISSING"}
    ]
    materials = {
        "task": LLM_TASK,
        "requirement": requirement,
        "target": bound_label or bound_research_id,
        "bound_research_id": bound_research_id,
        "needed_facets": selected_ids,
        "evidence": evidence,
        "unknown": unknown,
        "conflict": list(conflicts),
        "version": {"python": py.get("value"), "python_status": py.get("evidence")},
        "environment": {"os": os_.get("value"), "cuda": cuda.get("value")},
        "reused_facets": list(reusable),
        "research_required_facets": list(missing),
        "llm_facet_count": cmp_["llm_slice_facet_count"],
        "all_memory_facet_count": cmp_["all_memory_facet_count"],
        "contamination": cmp_["cross_record_contamination"],
        "selected_record_ids": [bound_research_id] if bound_research_id else [],
        "dump_all_included": False,
        "search_memory_instruction": False,
    }
    leak = [k for k in FORBIDDEN_LLM_KEYS if k in materials]
    materials["forbidden_keys_in_payload"] = leak
    return materials


def audit_llm_role(materials: dict[str, Any], spec: dict[str, Any] | None, *, code_proposal: bool) -> dict[str, Any]:
    """LLM がやってよいこと / 禁止をログする。実 LLM は呼ばない。"""
    blob = str(spec or {})
    allowed = {
        "organize_selected_evidence": True,
        "generate_spec": spec is not None,
        "code_proposal": code_proposal,
        "test_proposal": code_proposal,
        "revise_from_test": True,
    }
    py_slot = ((spec or {}).get("version") or {}).get("python") if isinstance((spec or {}).get("version"), dict) else None
    py_status = str((py_slot or {}).get("status") or "") if isinstance(py_slot, dict) else ""
    unknown_313 = any("3.13" in str(u) for u in (materials.get("unknown") or []))
    forbidden_done = {
        "search_all_memory": bool(materials.get("dump_all_included") or materials.get("search_memory_instruction")),
        "copy_version_evidence": bool((spec or {}).get("copied_from_old_python")),
        "promote_unknown": unknown_313 and py_status == "confirmed",
        "merge_conflict": any(c.get("winner") for c in (materials.get("conflict") or [])),
        "claim_certain": any(w in blob for w in ("確実に動く", "feasible")) or ("safe" in (spec or {})) or ("correct" in (spec or {})),
        "safety_verdict": "safe" in (spec or {}),
        "use_unselected_record": False,
    }
    selected = set(materials.get("selected_record_ids") or [])
    for row in materials.get("evidence") or []:
        if row.get("record") and row["record"] not in selected:
            forbidden_done["use_unselected_record"] = True
    return {
        "allowed": allowed,
        "forbidden_done": forbidden_done,
        "pass": not any(forbidden_done.values()) and not materials.get("forbidden_keys_in_payload"),
        "input_facet_count": materials.get("llm_facet_count"),
        "task": materials.get("task"),
    }
