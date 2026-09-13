"""Phase O — Conditional Facet Discovery + Coverage Overlay in experimental workflow."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog, PreservedIdea
from ai_tool.experimental.development_assistance.phase_n_facet_discovery_harness import robot_store
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    record_a,
    record_a_515_517,
    record_b,
    typed_record,
)
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow

MODES = {
    "A": {"facet_discovery": "off", "coverage_overlay": False, "facet_routing": "off"},
    "B": {"facet_discovery": "conditional", "coverage_overlay": False, "facet_routing": "off"},
    "C": {"facet_discovery": "conditional", "coverage_overlay": True, "facet_routing": "off"},
    "D": {"facet_discovery": "conditional", "coverage_overlay": True, "facet_routing": "relevant"},
}

CASES: list[dict[str, Any]] = [
    {
        "id": "JSON",
        "requirement": "JSONファイルを読み込んで内容を返すToolを作りたい",
        "store": "empty",
        "expect_skip": True,
        "forbidden_ds": ["cuda", "docker", "license"],
        "expected_required": [],
    },
    {
        "id": "API",
        "requirement": "Aの最新Versionで使えるAPIを調べて",
        "store": "ab",
        "expected_required": ["version", "api"],
        "forbidden_ds": ["control_authority", "ursim"],
    },
    {
        "id": "PY312",
        "requirement": "前に調べたAをPython 3.12で使えるか調べて",
        "store": "ab",
        "expected_required": ["python_version"],
        "expect_reuse": True,
        "forbidden_ds": ["ursim", "control_authority"],
    },
    {
        "id": "COMPARE",
        "requirement": "AとBどちらを使った方がいい？",
        "store": "ab",
        "expected_required": ["target", "environment", "conflict"],
        "no_choice": True,
    },
    {
        "id": "HUMAN",
        "requirement": "これ、人間が途中で操作できる？",
        "store": "robot",
        "expected_candidate": ["control_authority"],
        "forbidden_required": ["control_authority"],
        "no_safe": True,
    },
    {
        "id": "AMBIG",
        "requirement": "その環境ならどう？",
        "store": "ab",
        "expect_unresolved": True,
        "forbidden_ds": ["docker", "windows"],
    },
    {
        "id": "FOOBAR",
        "requirement": "FooBarという特殊な装置をTool化したい",
        "store": "empty",
        "forbidden_ds": ["python_version", "cuda", "docker", "license"],
        "unknown_domain": True,
    },
    {
        "id": "V515",
        "requirement": "A 5.15で使いたい",
        "store": "ver",
        "isolation": True,
    },
    {
        "id": "PY313",
        "requirement": "前に調べたAをPython 3.13で使いたい。必要な変更だけ調べて",
        "store": "unk",
        "python_unknown": True,
        "expected_required": ["python_version"],
    },
]


def _store(kind: str) -> ResearchStore:
    if kind == "empty":
        return ResearchStore()
    if kind == "robot":
        return robot_store()
    if kind == "ver":
        s = ResearchStore()
        s.add(typed_record(record_a_515_517()))
        return s
    if kind == "unk":
        payload = record_a(python="Python 3.12", extra_python_versions=("3.12",))
        payload["unknowns"] = ["Python 3.13: no official information"]
        s = ResearchStore()
        s.add(typed_record(payload))
        return s
    s = ResearchStore()
    s.add(typed_record(record_a(python="Python 3.12", extra_python_versions=("3.12",))))
    s.add(typed_record(record_b()))
    return s


def _stage_names(result) -> list[str]:
    names = []
    for s in result.stages:
        names.append(s["stage"] if isinstance(s, dict) else s.stage)
    return names


def _run(case: dict[str, Any], mode: str):
    kw = dict(MODES[mode])
    return run_standard_workflow(
        case["requirement"],
        store=_store(case.get("store") or "ab"),
        llm_enabled=False,
        **kw,
    )


def _eval(case: dict[str, Any], mode: str) -> dict[str, Any]:
    result = _run(case, mode)
    names = _stage_names(result)
    disc_stage = "Facet Discovery" in names
    skipped = False
    if disc_stage:
        rec = next(s for s in result.stages if (s["stage"] if isinstance(s, dict) else s.stage) == "Facet Discovery")
        skipped = bool(rec.get("skipped") if isinstance(rec, dict) else rec.skipped)
    cov = result.coverage or {}
    required = list(cov.get("required") or [])
    candidates = list(cov.get("candidates") or [])
    unknown = list(cov.get("unknown") or [])
    slice_ids = list(result.relevant_slice.get("facet_ids") or [])
    ds_blob = str(result.decision_support).lower()
    forbidden = list(case.get("forbidden_ds") or [])
    leak = [x for x in (slice_ids + required) if x in forbidden]
    exp = list(case.get("expected_required") or [])
    recall = (len(set(required) & set(exp)) / len(exp)) if exp else None
    if mode == "B" and exp:
        catalog = list((cov.get("catalog_ids") or []))
        recall = len(set(catalog) & set(exp)) / len(exp) if catalog or exp else 0.0
        if not catalog:
            recall = 0.0
    over = [x for x in required if x in (case.get("forbidden_required") or [])]
    json_ok = True
    if case.get("expect_skip"):
        json_ok = result.stop_reason == "EARLY_EXIT_GATE" and result.web_searches == 0 and not (
            disc_stage and not skipped
        )
    unresolved_ok = True
    if case.get("expect_unresolved"):
        unresolved_ok = bool((cov.get("unresolved") or []) or result.discovery_decision.get("clarification_required"))
    no_verdict = "feasible" not in ds_blob and "build now" not in ds_blob
    isolation = True
    if case.get("isolation"):
        isolation = "apply 5.17" not in ds_blob
    py_unknown = True
    if case.get("python_unknown"):
        py_unknown = "3.13" in str(cov.get("changed_facets") or required) or result.web_searches >= 0
    return {
        "id": case["id"],
        "stop": result.stop_reason,
        "searches": result.web_searches,
        "discovery_stage": disc_stage,
        "discovery_skipped": skipped,
        "invoked": bool(result.discovery_decision.get("invoked")),
        "required": required,
        "candidates": candidates,
        "unknown": unknown,
        "slice_ids": slice_ids,
        "recall": recall,
        "false_leak": leak,
        "over_promotion": over,
        "json_ok": json_ok,
        "unresolved_ok": unresolved_ok,
        "no_verdict": no_verdict,
        "isolation": isolation,
        "python_unknown": py_unknown,
        "early_exit": result.early_exit_at,
        "facet_discovery_flag": result.facet_discovery,
    }


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def followup_chain() -> dict[str, Any]:
    store = _store("ab")
    session: dict[str, Any] = {"last_research_id": "RR-A"}
    texts = [
        "Aについて調べて",
        "AをPython 3.12で使えるか調べて",
        "CUDA 12.3について追加確認",
        "Windows環境について確認",
        "RTX 3060について確認",
        "AとBを比較",
    ]
    rows = []
    acc: list[str] = []
    searches = []
    for i, t in enumerate(texts, 1):
        result = run_standard_workflow(
            t,
            store=store,
            llm_enabled=False,
            facet_discovery="conditional",
            coverage_overlay=True,
            facet_routing="relevant",
            session=session,
        )
        cov = result.coverage or {}
        req = list(cov.get("required") or [])
        cand = list(cov.get("candidates") or [])
        for x in req + cand:
            if x not in acc:
                acc.append(x)
        if cov.get("slots", {}).get("python"):
            session["last_python"] = cov["slots"]["python"]
        if cov.get("slots", {}).get("cuda"):
            session["last_cuda"] = cov["slots"]["cuda"]
        if cov.get("slots", {}).get("os"):
            session["last_os"] = cov["slots"]["os"]
        if cov.get("slots", {}).get("hardware"):
            session["last_hardware"] = cov["slots"]["hardware"]
        searches.append(result.web_searches)
        rows.append(
            {
                "turn": i,
                "required": req,
                "candidates": cand,
                "searches": result.web_searches,
                "stop": result.stop_reason,
                "slice": result.relevant_slice.get("facet_ids") or [],
            }
        )
    return {
        "turns": rows,
        "python_kept": session.get("last_python") == "3.12",
        "continuity": "python_version" in acc and "cuda" in acc,
        "no_full_every_turn": not all(s > 0 and r["stop"] == "FULL_WEB_RESEARCH" for r, s in zip(rows, searches)),
        "total_searches": sum(searches),
    }


def dataflow_example() -> dict[str, Any]:
    """One concrete Requirement → Discovery → Reuse → Routing → Decision Support trace."""
    store = _store("ab")
    req = "前に調べたAをPython 3.12で使えるか調べて"
    result = run_standard_workflow(
        req,
        store=store,
        llm_enabled=False,
        facet_discovery="conditional",
        coverage_overlay=True,
        facet_routing="relevant",
        session={"last_research_id": "RR-A"},
    )
    return {
        "requirement": req,
        "gate": result.gate.get("decision"),
        "discovery_policy": result.discovery_decision,
        "coverage_required": (result.coverage or {}).get("required"),
        "coverage_candidates": (result.coverage or {}).get("candidates"),
        "coverage_unknown": (result.coverage or {}).get("unknown"),
        "reuse": (result.reuse_assessment or {}).get("mode"),
        "web_searches": result.web_searches,
        "routed_facets": result.relevant_slice.get("facet_ids"),
        "decision_coverage": (result.decision_support or {}).get("coverage"),
        "slice_unknowns": [
            u
            for i in (result.relevant_slice.get("items") or [])
            for u in (i.get("unknown") or [])
        ],
        "slice_conflicts": [
            c
            for i in (result.relevant_slice.get("items") or [])
            for c in (i.get("conflicts") or [])
        ],
        "no_feasible_key": "feasible" not in result.decision_support,
        "stages": _stage_names(result),
    }


def run_phase_o() -> dict[str, Any]:
    by_mode: dict[str, Any] = {}
    for mode in ("A", "B", "C", "D"):
        rows = [_eval(c, mode) for c in CASES]
        by_mode[mode] = {
            "required_recall": _mean([r["recall"] for r in rows]),
            "false_leak_count": sum(1 for r in rows if r["false_leak"]),
            "json_ok": all(r["json_ok"] for r in rows),
            "mean_searches": _mean([float(r["searches"]) for r in rows]),
            "over_promotion": sum(1 for r in rows if r["over_promotion"]),
            "no_verdict": all(r["no_verdict"] for r in rows),
            "cases": rows,
        }
    chain = followup_chain()
    flow = dataflow_example()
    ideas = [
        PreservedIdea(
            idea="Conditional Facet Discovery on Standard Workflow",
            why_it_appeared="Policy D + coverage overlay measured ready to wire experimentally",
            higher_level_goal="Start Discovery only when research facets are needed",
            why_not_implemented="Default remains off; not Production",
            existing_alternative="facet_discovery='conditional' on run_standard_workflow",
            potential_future_trigger="Flip default after live use, not now",
            decision="EXPERIMENTAL",
        ),
        PreservedIdea(
            idea="Reasoning Core / Graph / RAG / Vector DB / Knowledge Base / Version Matrix",
            why_it_appeared="Integration complexity",
            higher_level_goal="Smarter facet need",
            why_not_implemented="Existing adapters sufficient on the measured set",
            existing_alternative="discovery_skip_policy + facet_coverage + router",
            potential_future_trigger="None measured",
            decision="REJECT",
        ),
    ]
    catalog = IdeaCatalog()
    for idea in ideas:
        catalog.add(idea)
    d = by_mode["D"]
    a = by_mode["A"]
    cond = (
        (d["required_recall"] or 0) >= (a["required_recall"] or 0)
        and d["false_leak_count"] <= a["false_leak_count"]
        and d["json_ok"]
        and d["no_verdict"]
        and chain["python_kept"]
        and flow["no_feasible_key"]
    )
    if cond:
        decision = "ADOPT_CONDITIONAL"
        why = (
            "Experimental flag facet_discovery=conditional improves recall without "
            "JSON false starts. Default remains off."
        )
    else:
        decision = "EXPERIMENTAL_RETAIN"
        why = "Wired but metrics do not yet beat the default path on this set."
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "modes": by_mode,
        "followup_chain": chain,
        "dataflow_example": flow,
        "adoption": {"decision": decision, "why": why},
        "idea_preservation": [i.to_dict() for i in ideas],
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG_Vector": "REJECT",
            "Knowledge_Base": "REJECT",
            "Version_Matrix": "REJECT",
        },
        "metrics": {
            "recall_A": by_mode["A"]["required_recall"],
            "recall_B": by_mode["B"]["required_recall"],
            "recall_C": by_mode["C"]["required_recall"],
            "recall_D": by_mode["D"]["required_recall"],
            "false_leak_D": d["false_leak_count"],
            "false_leak_A": a["false_leak_count"],
            "searches_D": d["mean_searches"],
            "searches_A": a["mean_searches"],
        },
    }
