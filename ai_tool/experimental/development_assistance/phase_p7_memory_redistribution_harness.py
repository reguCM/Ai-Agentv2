"""Phase P-7〜P-12 — 記憶増量と機械的な再配分。Core ではない。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    apply_requirement,
    seed_from_record,
)
from ai_tool.experimental.development_assistance.memory_slice import (
    compare_llm_payloads,
    dump_all_for_llm,
    iter_memory_facets,
)
from ai_tool.experimental.development_assistance.phase_p7_memory_fixtures import (
    multi_record_store,
    overlap_store,
)
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f

FOREIGN = {"ursim", "ros", "nodejs", "control_authority", "dashboard", "docker"}


def _item_pass(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_phase_p7_p12() -> dict[str, Any]:
    store = multi_record_store()
    state = DevelopmentSessionState()
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    seed_from_record(state, rec_a)

    dumped = dump_all_for_llm(store)
    p7 = {
        "record_ids": [r.research_id for r in store.records],
        "record_count": len(store.records),
        "all_memory_facet_count": dumped["facet_count"],
        "distributed": True,
        "not_one_giant_record": len(store.records) >= 5,
    }

    # P-8 pointers
    p8_ok = classify_pointer(
        "その技術Aについて調べて。",
        store=store,
        session=state.as_session_dict(),
    )
    p8_cont = classify_pointer(
        "前に調べた技術Aについて続けて。",
        store=store,
        session=state.as_session_dict(),
    )
    p8_no_session = classify_pointer(
        "その技術Aについて調べて。",
        store=store,
        session={},
    )
    state_b = DevelopmentSessionState()
    rec_b = next(r for r in store.records if r.research_id == "RR-B")
    seed_from_record(state_b, rec_b)
    p8_wrong_session = classify_pointer(
        "その技術Aについて調べて。",
        store=store,
        session=state_b.as_session_dict(),
    )
    p8 = {
        "with_session_a": p8_ok.to_dict(),
        "continue_a": p8_cont.to_dict(),
        "without_session": p8_no_session.to_dict(),
        "session_is_b": p8_wrong_session.to_dict(),
        "no_mix": p8_ok.bound_research_id == "RR-A" and p8_ok.status == "BOUND",
        "unresolved_without_id": p8_no_session.status == "UNRESOLVED",
        "unresolved_when_session_is_b": p8_wrong_session.status == "UNRESOLVED",
    }

    # P-9 one facet change
    p9_req = "Python 3.13で使えるか調べて。"
    p9_overlay = apply_requirement(state, p9_req, store)
    py = state.facets["python_version"]
    retained = set(p9_overlay["retained"])
    p9_foreign = sorted(FOREIGN & retained)
    p9_compare = compare_llm_payloads(
        store,
        bound_research_id="RR-A",
        session_facet_ids=list(state.facets.keys()),
        missing_facet_ids=["python_version"],
        expected_ids=["python_version", "os", "cuda", "license"],
    )
    wf_p9 = run_standard_workflow(
        p9_req,
        store=store,
        session=state.as_session_dict(),
        llm_enabled=False,
        facet_discovery="conditional",
        coverage_overlay=True,
        facet_routing="relevant",
    )
    p9 = {
        "python": py.to_dict(),
        "copied": py.copied_from_old,
        "kept_os": state.facets.get("os") and state.facets["os"].value == "windows",
        "kept_cuda": state.facets.get("cuda") and state.facets["cuda"].value == "12.3",
        "kept_license": state.facets.get("license") and state.facets["license"].value == "Y",
        "missing": p9_overlay["missing"],
        "reusable": p9_overlay["reusable"],
        "foreign_added": p9_foreign,
        "searches_estimate": p9_overlay["searches_estimate"],
        "full_reresearch": p9_overlay["full_reresearch"],
        "history_has_312": any(h.get("value") == "3.12" for h in state.history),
        "workflow_routing": list((wf_p9.relevant_slice or {}).get("facet_ids") or []),
        "workflow_web_searches": wf_p9.web_searches,
        "compare": p9_compare,
    }

    # P-10 CUDA only
    py_before = state.facets["python_version"].to_dict()
    p10_overlay = apply_requirement(state, "CUDAは12.4の環境で。", store)
    p10 = {
        "python_kept": state.facets["python_version"].to_dict(),
        "python_not_reset": (
            state.facets["python_version"].value == py_before["value"]
            and state.facets["python_version"].evidence == py_before["evidence"]
        ),
        "cuda": state.facets["cuda"].to_dict(),
        "copied_cuda": state.facets["cuda"].copied_from_old,
        "kept_os": state.facets["os"].value == "windows",
        "kept_license": state.facets["license"].value == "Y",
        "missing": p10_overlay["missing"],
        "reusable": p10_overlay["reusable"],
        "searches_estimate": p10_overlay["searches_estimate"],
        "full_reresearch": p10_overlay["full_reresearch"],
    }
    p10_compare = compare_llm_payloads(
        store,
        bound_research_id="RR-A",
        session_facet_ids=list(state.facets.keys()),
        missing_facet_ids=["cuda"],
        expected_ids=["python_version", "os", "cuda", "license"],
    )
    p10["compare"] = p10_compare

    # P-11 restore python 3.12
    p11_overlay = apply_requirement(state, "Pythonは3.12に戻して。", store)
    p11 = {
        "python": state.facets["python_version"].to_dict(),
        "cuda_still": state.facets["cuda"].to_dict(),
        "missing": p11_overlay["missing"],
        "reusable": p11_overlay["reusable"],
        "history": list(state.history),
    }

    # P-12 already in compare; also default-off workflow
    wf_off = run_standard_workflow(
        p9_req,
        store=store,
        llm_enabled=False,
    )

    # Overlap
    ostore = overlap_store()
    unique = classify_pointer("WindowsでPython 3.12の方", store=ostore, session={})
    ambiguous = classify_pointer("Windowsの方", store=ostore, session={})
    overlap = {
        "unique": unique.to_dict(),
        "ambiguous": ambiguous.to_dict(),
        "unique_ok": unique.status == "BOUND" and unique.bound_research_id == "RR-WA",
        "ambiguous_unresolved": ambiguous.status == "UNRESOLVED",
    }

    items = {
        "P-7": _item_pass(p7["not_one_giant_record"] and p7["all_memory_facet_count"] > 8),
        "P-8": _item_pass(
            p8["no_mix"] and p8["unresolved_without_id"] and p8["unresolved_when_session_is_b"]
        ),
        "P-9": _item_pass(
            py.value == "3.13"
            and py.evidence == "UNKNOWN"
            and not py.copied_from_old
            and p9["kept_os"]
            and p9["kept_cuda"]
            and p9["kept_license"]
            and not p9_foreign
            and p9_overlay["searches_estimate"] == 1
        ),
        "P-10": _item_pass(
            p10["python_not_reset"]
            and state.facets["cuda"].value == "12.4"
            and state.facets["cuda"].evidence == "UNKNOWN"
            and not state.facets["cuda"].copied_from_old
            and p10["kept_os"]
            and p10["kept_license"]
            and p10_overlay["searches_estimate"] == 1
            and not p10_overlay["full_reresearch"]
        ),
        "P-11": _item_pass(
            state.facets["python_version"].value == "3.12"
            and state.facets["python_version"].evidence == "confirmed"
            and state.facets["cuda"].value == "12.4"
        ),
        "P-12": _item_pass(
            p9_compare["llm_slice_facet_count"] < p9_compare["all_memory_facet_count"]
            and p9_compare["cross_record_contamination"] == 0
            and p9_compare["irrelevant_suppression"] == 1.0
        ),
        "overlap_unique": _item_pass(overlap["unique_ok"]),
        "overlap_ambiguous": _item_pass(overlap["ambiguous_unresolved"]),
    }
    fails = [k for k, v in items.items() if v == "FAIL"]
    judgment = "PASS"
    if fails:
        judgment = "PARTIAL_PASS" if len(fails) <= 2 else "FAIL"
    if p9_compare["cross_record_contamination"] > 0 or p9_foreign:
        judgment = "FAIL"

    phase_f = run_phase_f(llm_enabled=False)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "phase_f_decision": phase_f.get("decision"),
        "judgment": judgment,
        "item_results": items,
        "p7": p7,
        "p8": p8,
        "p9": p9,
        "p10": p10,
        "p11": p11,
        "p12": {
            "all_memory_facet_count": p9_compare["all_memory_facet_count"],
            "llm_dump_all_facet_count": p9_compare["llm_dump_all_facet_count"],
            "llm_slice_facet_count": p9_compare["llm_slice_facet_count"],
            "reduction": p9_compare["reduction"],
            "relevant_facet_recall": p9_compare["relevant_facet_recall"],
            "irrelevant_suppression": p9_compare["irrelevant_suppression"],
            "cross_record_contamination": p9_compare["cross_record_contamination"],
            "research_search_count": wf_p9.web_searches,
            "default_workflow_discovery": wf_off.facet_discovery,
            "design_candidate": p9_compare["design_note"],
            "core_now": "REJECT",
        },
        "overlap": overlap,
        "metrics": {
            "all_memory_facet_count": dumped["facet_count"],
            "selected_facet_count": p9_compare["llm_slice_facet_count"],
            "llm_facet_count": p9_compare["llm_slice_facet_count"],
            "research_again_facet_count": p9_overlay["searches_estimate"],
            "reuse_facet_count": len(p9_overlay["reusable"]),
            "foreign_added": p9_foreign,
            "version_isolation": py.evidence == "UNKNOWN" and not py.copied_from_old,
            "unknown_preservation": True,
            "conflict_preservation": bool(rec_a.conflicts),
        },
        "final_facets": {k: v.to_dict() for k, v in state.facets.items()},
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG": "REJECT",
            "KnowledgeBase": "REJECT",
            "memory_slice_as_core": "REJECT_NOW",
        },
        "memory_rows": iter_memory_facets(store),
    }
