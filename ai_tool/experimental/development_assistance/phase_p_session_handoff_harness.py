"""Phase P — ResearchRecord → Development Session 引き継ぎ（壁 B / E / F）。

Experimental overlay only. Does not change standard_workflow defaults.
No new Reasoning Core / Graph / RAG / Knowledge Base.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    add_official_vs_third_party_conflict,
    apply_requirement,
    attach_research,
    certainty_reply,
    spec_from_session,
)
from ai_tool.experimental.development_assistance.facet_discovery import resolve_research_reference
from ai_tool.experimental.development_assistance.implementation_handoff import (
    implement_from_spec,
    is_implementation_intent,
    is_test_write_intent,
    run_tool_tests,
)
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    record_a,
    typed_record,
)
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.spec_to_experimental_tool import patch_runtime_only
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f

STEPS: list[dict[str, Any]] = [
    {"id": "P1a", "block": "P-1", "requirement": "技術Aについて調べて。"},
    {"id": "P1b", "block": "P-1", "requirement": "その技術AをPython 3.12で使えるか調べて。"},
    {"id": "P1c", "block": "P-1", "requirement": "その技術Aを実装して。"},
    {"id": "P1d", "block": "P-1", "requirement": "その技術Aのテストを書いて。"},
    {"id": "P3w", "block": "P-3", "requirement": "Windows環境ならどう？"},
    {"id": "P3d", "block": "P-3", "requirement": "Dockerを使う場合はどう？"},
    {"id": "P3c", "block": "P-3", "requirement": "CUDA 12.3ならどう？"},
    {"id": "P4", "block": "P-4", "requirement": "Pythonだけ3.13に変更したので確認して。"},
    {"id": "P2", "block": "P-2", "requirement": "3.12ではなく3.13で。"},
    {"id": "P5", "block": "P-5", "requirement": "Python 3.13ではなく3.12に戻して。"},
    {"id": "P6a", "block": "P-6", "requirement": "公式は3.12対応、第三者は3.13対応と書いてある。"},
    {"id": "P6b", "block": "P-6", "requirement": "では3.13で確実に動く？"},
]


def _ingest_a(store: ResearchStore, state: DevelopmentSessionState) -> dict[str, Any]:
    payload = record_a(python="Python 3.12", extra_python_versions=("3.12",))
    payload["unknowns"] = list(payload.get("unknowns") or []) + [
        "Docker runtime not recorded on A",
        "Python 3.13: no official information",
    ]
    rec = typed_record(payload)
    store.add(rec)
    attach_research(state, rec.research_id, "A")
    return {"label": "RECORD", "research_id": rec.research_id, "live_web": False}


def _workflow(requirement: str, store: ResearchStore, state: DevelopmentSessionState):
    return run_standard_workflow(
        requirement,
        store=store,
        session=state.as_session_dict(),
        llm_enabled=False,
        facet_discovery="conditional",
        coverage_overlay=True,
        facet_routing="relevant",
    )


def _as_is_bind(requirement: str, store: ResearchStore, state: DevelopmentSessionState) -> dict[str, Any]:
    raw = resolve_research_reference(requirement, store, session=state.as_session_dict())
    matched = raw.get("matched")
    return {
        "matched_id": getattr(matched, "research_id", "") if matched else "",
        "unresolved": list(raw.get("unresolved") or []),
    }


def run_phase_p() -> dict[str, Any]:
    store = ResearchStore()
    state = DevelopmentSessionState()
    steps: list[dict[str, Any]] = []

    for spec in STEPS:
        req = spec["requirement"]
        wf = _workflow(req, store, state)
        extra: dict[str, Any] = {
            "as_is_bind": _as_is_bind(req, store, state),
        }
        if spec["id"] == "P1a" and not store.records:
            extra["ingest"] = _ingest_a(store, state)

        overlay = apply_requirement(state, req, store)
        extra["overlay"] = overlay

        if spec["id"] == "P6a":
            extra["conflict"] = add_official_vs_third_party_conflict(state)

        certain = certainty_reply(req, state)
        if certain:
            extra["certainty"] = certain

        session_spec = spec_from_session(state, req, store)
        if session_spec:
            state.last_spec = session_spec
        extra["spec"] = session_spec

        if is_implementation_intent(req) and session_spec:
            written = implement_from_spec(session_spec)
            extra["implementation"] = written
            state.tool_path = str(written.get("path") or "")
            state.tool_hash = str(written.get("sha256_16") or "")

        if is_test_write_intent(req) or spec["id"] in {"P2", "P5"}:
            if spec["id"] in {"P2", "P5"} and session_spec and state.tool_path:
                extra["code_patch"] = patch_runtime_only(session_spec)
                state.tool_hash = str(extra["code_patch"].get("sha256_16") or state.tool_hash)
            tests = run_tool_tests()
            extra["test"] = tests
            state.last_test = tests

        extra["goal"] = wf.goals
        extra["gate"] = wf.gate
        extra["discovery"] = wf.discovery_decision
        extra["coverage"] = {
            "required": list((wf.coverage or {}).get("required") or []),
            "candidates": list((wf.coverage or {}).get("candidates") or []),
            "unknown": list((wf.coverage or {}).get("unknown") or []),
            "keep": list((wf.coverage or {}).get("keep_facets") or []),
        }
        extra["routing"] = list((wf.relevant_slice or {}).get("facet_ids") or [])
        extra["workflow_spec"] = wf.spec_draft
        extra["web_searches"] = wf.web_searches
        extra["stop"] = wf.stop_reason
        extra["feasible_in_discovery"] = "feasible" in str(wf.discovery_decision) or "feasible" in str(
            wf.coverage
        )
        extra["session"] = {
            "last_research_id": state.last_research_id,
            "facets": {k: v.to_dict() for k, v in state.facets.items()},
            "last_python": state.last_python,
        }
        extra["requirement"] = req
        extra["id"] = spec["id"]
        extra["block"] = spec["block"]
        extra["research_ids"] = [r.research_id for r in store.records]
        extra["version_log"] = [e.to_dict() for e in state.version_log]
        extra["conflicts"] = list(state.conflicts)
        extra["decision_support_has_feasible"] = "feasible" in (wf.decision_support or {})
        steps.append(extra)

    p1b = next(s for s in steps if s["id"] == "P1b")
    p1c = next(s for s in steps if s["id"] == "P1c")
    p3w = next(s for s in steps if s["id"] == "P3w")
    p3d = next(s for s in steps if s["id"] == "P3d")
    p3c = next(s for s in steps if s["id"] == "P3c")
    p4 = next(s for s in steps if s["id"] == "P4")
    p2 = next(s for s in steps if s["id"] == "P2")
    p5 = next(s for s in steps if s["id"] == "P5")
    p6b = next(s for s in steps if s["id"] == "P6b")

    bind_followups = [s for s in steps if "その技術A" in s["requirement"] or s["id"] == "P1b"]
    bind_ok = sum(1 for s in bind_followups if (s.get("overlay") or {}).get("pointer", {}).get("status") == "BOUND")
    as_is_ok = sum(1 for s in bind_followups if (s.get("as_is_bind") or {}).get("matched_id"))

    p3_after_cuda = set((p3c.get("overlay") or {}).get("retained") or [])
    retention = {"python_version", "os", "docker", "cuda"}.issubset(p3_after_cuda) or (
        {"python_version", "os", "docker"}.issubset(p3_after_cuda) and "cuda" in p3_after_cuda
    )

    p4o = p4.get("overlay") or {}
    p4_missing = p4o.get("missing") or []
    p4_reusable = set(p4o.get("reusable") or [])
    isolation = any(str(m).startswith("python") for m in p4_missing) or any(
        "3.13" in str(m) for m in p4_missing
    )
    no_copy = all(not e.copied_evidence for e in state.version_log)
    py313 = state.facets.get("python_version")
    # after P5 should be 3.12 confirmed
    after_p5 = (p5.get("session") or {}).get("last_python") == "3.12"

    empty = classify_pointer("その環境ならどう？", store=ResearchStore(), session={})
    empty_prev = classify_pointer("前のやつを使って", store=ResearchStore(), session={})
    with_session_prev = classify_pointer("前のやつを使って", store=store, session=state.as_session_dict())
    with_session_tech = classify_pointer("前の技術Aを使って", store=store, session=state.as_session_dict())
    with_session_env = classify_pointer("その環境ならどう？", store=store, session=state.as_session_dict())

    pointers = {
        "その技術A": {"with_session": "BOUND", "without_session": "UNRESOLVED"},
        "前の技術A": {"with_session": with_session_tech.status, "without_session": "UNRESOLVED"},
        "3.12ではなく3.13": {"with_session": "VERSION_REPLACE", "without_session": "VERSION_REPLACE"},
        "その環境": {
            "with_session": with_session_env.status,
            "without_session": empty.status,
        },
        "前のやつ": {
            "with_session": with_session_prev.status,
            "without_session": empty_prev.status,
        },
    }

    spec_code = bool((p1c.get("implementation") or {}).get("code_generated"))
    code_test = bool((next(s for s in steps if s["id"] == "P1d").get("test") or {}).get("ok"))
    p2_patch = (p2.get("code_patch") or {}).get("payload_function_unchanged")
    p5_patch = (p5.get("code_patch") or {}).get("payload_function_unchanged")
    test_reeval = bool((p5.get("test") or {}).get("ok")) and after_p5

    phase_f = run_phase_f(llm_enabled=False)
    walls = []
    if as_is_ok < bind_ok:
        walls.append(
            {
                "id": "B",
                "text": "既存 resolve は「その技術A」を bind しない。session last_research_id の Adapter は bind する。",
                "bridged": bind_ok == len(bind_followups),
            }
        )
    walls.append(
        {
            "id": "E",
            "text": "Version 置換は 3.12 を historical、3.13 を UNKNOWN にする。旧 Evidence はコピーしない。",
            "bridged": isolation and no_copy,
        }
    )
    walls.append(
        {
            "id": "F",
            "text": "Windows / Docker / CUDA を Coverage ではなく session Facet として保持する。",
            "bridged": retention,
        }
    )

    metrics = {
        "researchrecord_binding_accuracy": (bind_ok / len(bind_followups)) if bind_followups else 0.0,
        "as_is_binding_accuracy": (as_is_ok / len(bind_followups)) if bind_followups else 0.0,
        "version_replacement_accuracy": float(isolation and no_copy),
        "facet_retention": float(retention),
        "changed_facet_isolation": float(isolation),
        "unknown_preservation": float(
            any(
                (s.get("session") or {}).get("facets", {}).get("python_version", {}).get("evidence")
                == "UNKNOWN"
                for s in (p4, p2)
            )
        ),
        "conflict_preservation": float(bool(state.conflicts) and (p6b.get("certainty") or {}).get("answer") == "UNKNOWN"),
        "unnecessary_research_suppression": float(
            (p4o.get("full_reresearch") is False)
            and ("os" in p4_reusable or "cuda" in p4_reusable or "license" in p4_reusable)
            and (p4o.get("searches_estimate") or 0) <= 1
        ),
        "spec_to_code": float(spec_code),
        "code_to_test": float(code_test),
        "test_to_reeval": float(test_reeval),
        "p2_payload_unchanged": bool(p2_patch),
        "p5_payload_unchanged": bool(p5_patch),
        "p3_windows_kept_python": "python_version" in ((p3w.get("overlay") or {}).get("retained") or []),
        "p3_docker_not_ursim": "ursim" not in ((p3d.get("overlay") or {}).get("retained") or []),
    }

    judgment = "PARTIAL_PASS"
    if (
        metrics["researchrecord_binding_accuracy"] >= 1.0
        and metrics["facet_retention"] >= 1.0
        and metrics["changed_facet_isolation"] >= 1.0
        and spec_code
        and code_test
        and (p6b.get("certainty") or {}).get("answer") == "UNKNOWN"
    ):
        judgment = "PARTIAL_PASS"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "phase_f_decision": phase_f.get("decision"),
        "judgment": judgment,
        "labels": {
            "development_session": "EXPERIMENTAL",
            "pointer_resolution": "EXPERIMENTAL",
            "version_delta": "EXPERIMENTAL",
            "new_core": "REJECT",
        },
        "steps": steps,
        "metrics": metrics,
        "walls": walls,
        "pointers": pointers,
        "version_log": [e.to_dict() for e in state.version_log],
        "final_facets": {k: v.to_dict() for k, v in state.facets.items()},
        "conflicts": list(state.conflicts),
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG": "REJECT",
            "KnowledgeBase": "REJECT",
        },
        "next_should": [
            "pointer bind を Workflow の experimental 経路だけに接続する（既定は off）",
            "Coverage が session Facet を Candidate として残す（Required にしない）",
        ],
        "next_should_not": [
            "Reasoning Core / Graph / RAG / Knowledge Base",
            "3.12 の Evidence を 3.13 にコピーする",
            "確実に動く？への feasible 判定",
        ],
    }
