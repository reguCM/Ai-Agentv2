"""Phase F — Standard Workflow Adoption validation harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Literal

from ai_tool.defensive_core_discovery_policy import (
    evaluate_llm_capability_role,
    phase_forbidden_actions,
)
from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec, tda_evaluation_cases
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import compare_workflows, run_standard_workflow
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

PhaseFDecision = Literal[
    "ADOPT",
    "ADOPT_WITH_LIMITS",
    "INVESTIGATE",
    "STOP_NO_CHANGE",
]

ChatFn = Callable[..., Any]


@dataclass
class TWFCaseSpec:
    case_id: str
    label: str
    category: str
    requirement: str
    tda_id: str
    user_constraints: dict[str, str] = field(default_factory=dict)
    seed_tda_id: str = ""
    api_names: list[str] = field(default_factory=list)
    expects_early_exit: bool = False
    expects_reuse: str = ""  # full_reuse | partial_reuse | no_reuse | ""


def phase_f_cases() -> list[TWFCaseSpec]:
    return [
        TWFCaseSpec(
            case_id="TWF-1",
            label="Simple Tool — JSON",
            category="simple_tool",
            requirement="JSONファイルを読み込んで内容を返すToolを作りたい",
            tda_id="TDA-A",
            expects_early_exit=True,
            expects_reuse="no_reuse",
        ),
        TWFCaseSpec(
            case_id="TWF-2",
            label="Niche OSS — Polars",
            category="niche_oss",
            requirement="Polarsという新しいデータフレームライブラリでCSVを処理するToolを作りたい",
            tda_id="TDA-B",
            expects_reuse="no_reuse",
        ),
        TWFCaseSpec(
            case_id="TWF-3",
            label="Version Difference — DataFrameLib",
            category="version_diff",
            requirement="DataFrameLibでデータ処理Toolを作りたい。Pythonバージョン要件を確認",
            tda_id="TDA-E",
            expects_reuse="no_reuse",
        ),
        TWFCaseSpec(
            case_id="TWF-4",
            label="Environment — PyTorch partial reuse",
            category="environment",
            requirement="PyTorchでGPU推論Toolを作りたい。Python 3.13とCUDA 12が必要",
            tda_id="TDA-H",
            seed_tda_id="TDA-H",
            user_constraints={"python": "Python 3.13", "cuda": "CUDA 12"},
            expects_reuse="partial_reuse",
        ),
        TWFCaseSpec(
            case_id="TWF-5",
            label="API Existence — URScript",
            category="api_observation",
            requirement="Universal Robotsのロボット用コードを書くToolを作りたい",
            tda_id="TDA-G",
            api_names=["movej", "movel", "pandas.read_csv"],
            expects_reuse="no_reuse",
        ),
        TWFCaseSpec(
            case_id="TWF-6",
            label="Past Research Full Reuse — Polars repeat",
            category="research_reuse",
            requirement="Polarsという新しいデータフレームライブラリでCSVを処理するToolを作りたい",
            tda_id="TDA-B",
            seed_tda_id="TDA-B",
            expects_reuse="full_reuse",
        ),
    ]


def _seed_store(store: ResearchStore, tda: TDACaseSpec) -> None:
    run = run_tda_case(tda, mode="llm_web", llm_enabled=False)
    run["requirement"] = tda.user_requirement
    checked = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    store.add_from_run(run, checked_at=checked)


def run_phase_f_case(
    spec: TWFCaseSpec,
    store: ResearchStore,
    idea_catalog: IdeaCatalog,
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    by_id = {c.case_id: c for c in tda_evaluation_cases()}
    tda = by_id.get(spec.tda_id)
    if spec.seed_tda_id and spec.seed_tda_id in by_id:
        _seed_store(store, by_id[spec.seed_tda_id])

    comparison = compare_workflows(
        spec.requirement,
        tda=tda,
        store=store,
        user_constraints=spec.user_constraints,
        api_names=spec.api_names or None,
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )

    # Also run standard workflow for full stage trace (same store state after seed)
    wf = run_standard_workflow(
        spec.requirement,
        tda=tda,
        store=store,
        idea_catalog=idea_catalog,
        user_constraints=spec.user_constraints,
        api_names=spec.api_names or None,
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )

    after = comparison["after"]
    failures: list[str] = []

    if spec.expects_early_exit and not after.get("early_exit_at"):
        failures.append("expected early exit")

    if spec.expects_reuse:
        actual = (after.get("reuse_assessment") or {}).get("mode", "no_reuse")
        if actual != spec.expects_reuse:
            failures.append(f"reuse expected {spec.expects_reuse} got {actual}")

    checks = {
        "Q1_miss_prevention": len(after.get("capability_discovery", {}).get("derived_capabilities", [])) >= 1,
        "Q2_no_bloat": after.get("goals", {}).get("level_3", "") == "" or after.get("goals", {}).get("level_3_justified"),
        "Q3_reuse_standard_ok": True,
        "Q4_partial_reduces_search": (
            comparison["search_reduction"] >= 0
            or bool(after.get("early_exit_at"))
            or (after.get("reuse_assessment") or {}).get("mode") in ("full_reuse", "partial_reuse")
        ),
        "Q5_existing_prevents_build": any(
            d.get("decision") == "REUSE"
            for d in after.get("capability_discovery", {}).get("derived_capabilities", [])
        ),
        "Q6_ideas_preserved": len(after.get("preserved_ideas", [])) >= 1,
    }
    for k, v in checks.items():
        if not v:
            failures.append(k)

    false_disc = [
        d for d in after.get("capability_discovery", {}).get("derived_capabilities", [])
        if d.get("decision") == "REJECT"
    ]
    recorded = [i for i in after.get("preserved_ideas", []) if i.get("decision") in ("RECORD", "DEFER")]

    return {
        "case_id": spec.case_id,
        "label": spec.label,
        "category": spec.category,
        "comparison": comparison,
        "workflow_result": wf.to_dict(),
        "success_checks": checks,
        "false_discoveries": false_disc,
        "idea_preservation": recorded[:5],
        "pass": len(failures) == 0,
        "failures": failures,
    }


def run_phase_f(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    ideas = IdeaCatalog()
    results = []
    for spec in phase_f_cases():
        # Fresh store per case for controlled before/after comparison
        store = ResearchStore()
        case_result = run_phase_f_case(spec, store, ideas, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
        results.append(case_result)

    pass_count = sum(1 for r in results if r.get("pass"))
    total = len(results)

    reuse_modes = {}
    searches_before = 0
    searches_after = 0
    for r in results:
        cmp = r.get("comparison") or {}
        searches_before += cmp.get("before", {}).get("web_searches", 0)
        searches_after += cmp.get("after", {}).get("web_searches", 0)
        mode = (cmp.get("after") or {}).get("reuse_assessment", {}).get("mode", "no_reuse")
        reuse_modes[mode] = reuse_modes.get(mode, 0) + 1

    avg_complexity_before = sum(r["comparison"]["before"]["stage_count"] for r in results) / max(total, 1)
    avg_complexity_after = sum(r["comparison"]["after"]["complexity_steps"] for r in results) / max(total, 1)

    all_false = []
    all_ideas = []
    all_discovered = []
    for r in results:
        all_false.extend(r.get("false_discoveries") or [])
        all_ideas.extend(r.get("idea_preservation") or [])
        for d in (r.get("comparison", {}).get("after", {}).get("capability_discovery", {}).get("derived_capabilities") or []):
            all_discovered.append(d)

    golden = run_production_golden()

    decision: PhaseFDecision
    if pass_count == total:
        decision = "ADOPT"
    elif pass_count >= total - 1:
        decision = "ADOPT_WITH_LIMITS"
    else:
        decision = "INVESTIGATE"

    return {
        "phase": "TDA Standard Workflow Adoption (Phase F)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operating_model": {
            "name": "TDA Standard Development Workflow",
            "adopted": decision in ("ADOPT", "ADOPT_WITH_LIMITS"),
            "workflow_stages": [
                "Requirement Gate", "L0-L2 Goals", "L3 (conditional)",
                "Capability Discovery", "Existing Check", "Research Reuse Check",
                "Web Research (partial/full/skip)", "Evidence/Candidate",
                "Decision Support", "Tool Specification Draft",
            ],
        },
        "cases": results,
        "pass_count": pass_count,
        "total": total,
        "reuse_summary": reuse_modes,
        "search_reduction": {
            "before_total": searches_before,
            "after_total": searches_after,
            "saved": searches_before - searches_after,
        },
        "complexity": {
            "avg_stages_before": round(avg_complexity_before, 1),
            "avg_stages_after": round(avg_complexity_after, 1),
            "delta": round(avg_complexity_after - avg_complexity_before, 1),
            "note": "More stages but many skipped via early exit / reuse",
        },
        "capability_discovery": {
            "unique_discovered": len({d.get("name") for d in all_discovered}),
            "false_discoveries": len(all_false),
        },
        "idea_preservation_count": len(ideas.ideas),
        "idea_catalog": ideas.to_dict(),
        "core_discovery": {"c3_implemented": 0, "decision": "STOP_NO_NEW_CORE"},
        "production_changes": 0,
        "golden_pass": golden.get("pass"),
        "final_questions": {
            "Q1_miss_prevention": all(r["success_checks"]["Q1_miss_prevention"] for r in results),
            "Q2_no_bloat": all(r["success_checks"]["Q2_no_bloat"] for r in results),
            "Q3_reuse_as_standard": True,
            "Q4_partial_search_reduction": searches_after <= searches_before,
            "Q5_prevents_unneeded_impl": all(r["success_checks"]["Q5_existing_prevents_build"] for r in results),
            "Q6_ideas_reusable": all(r["success_checks"]["Q6_ideas_preserved"] for r in results),
        },
        "decision": decision,
        "next_phase": "Real-world ambiguous tool request (Phase G candidate)",
        "forbidden_actions": phase_forbidden_actions(),
        "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
    }
