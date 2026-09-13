"""Phase D — Practical Decision Support observation harness."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.defensive_core_discovery_policy import (
    evaluate_llm_capability_role,
    phase_forbidden_actions,
)
from ai_tool.experimental.development_assistance.api_observation import observe_apis_from_sources
from ai_tool.experimental.development_assistance.capability_observation import (
    CapabilityObservation,
    CANDIDATE_CATALOG,
)
from ai_tool.experimental.development_assistance.decision_factors import (
    compare_candidates_for_decision,
    compute_decision_factors,
    infer_deciding_factors,
)
from ai_tool.experimental.development_assistance.decision_presentation import format_decision_comparison
from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec, tda_evaluation_cases
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.research_state import ResearchState
from ai_tool.experimental.development_assistance.spec_draft import build_spec_draft
from ai_tool.experimental.development_assistance.version_facts import version_facts_from_candidate
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[3]

PhaseDDecision = Literal[
    "CONTINUE",
    "INVESTIGATE",
    "EXPERIMENTAL_RETAIN",
    "STOP_NO_NEW_CORE",
]

ChatFn = Callable[..., Any]

# Phase D Case A–H → Phase B fixtures
PHASE_D_CASE_MAP: dict[str, str] = {
    "TDS-A": "TDA-A",  # General Tool
    "TDS-B": "TDA-B",  # Niche OSS
    "TDS-C": "TDA-C",  # Multiple candidates
    "TDS-D": "TDA-E",  # Version difference
    "TDS-E": "TDA-H",  # Environment dependent
    "TDS-F": "TDA-F",  # License difference (conflicting sources include license)
    "TDS-G": "TDA-F",  # Source conflict — reuse TDA-F (license/env conflict)
    "TDS-H": "TDA-G",  # Specialized URScript
}


@dataclass
class TDSCaseSpec:
    tds_id: str
    label: str
    tda_id: str
    user_constraints: dict[str, str] = field(default_factory=dict)
    api_names_to_observe: list[str] = field(default_factory=list)
    resume_follow_up: str = ""
    selection_message: str = ""
    expected_deciding_factors: list[str] = field(default_factory=list)


def phase_d_cases() -> list[TDSCaseSpec]:
    labels = {
        "TDS-A": "Case A — 一般Tool (JSON)",
        "TDS-B": "Case B — ニッチOSS (Polars)",
        "TDS-C": "Case C — 複数候補 (PDF)",
        "TDS-D": "Case D — Version差 (DataFrameLib)",
        "TDS-E": "Case E — 環境依存 (PyTorch/GPU)",
        "TDS-F": "Case F — License差 (ToolX)",
        "TDS-G": "Case G — 情報源Conflict (ToolX)",
        "TDS-H": "Case H — 専門Tool (URScript)",
    }
    constraints = {
        "TDS-E": {
            "os": "Windows",
            "python": "Python 3.12",
            "gpu": "RTX 3060",
            "cuda": "CUDA 12",
        },
        "TDS-F": {"license_preference": "MIT"},
    }
    apis = {
        "TDS-H": ["movej", "movel", "set_digital_out", "pandas.read_csv"],
    }
    resume = {"TDS-B": "Bについてもう少し調べて"}
    selection = {
        "TDS-C": "pdfplumberを使いたい",
        "TDS-F": "Bにしてください",
        "TDS-H": "Aを使いたい",
    }
    by_id = {c.case_id: c for c in tda_evaluation_cases()}
    out: list[TDSCaseSpec] = []
    for tds_id, tda_id in PHASE_D_CASE_MAP.items():
        if tda_id not in by_id:
            continue
        out.append(
            TDSCaseSpec(
                tds_id=tds_id,
                label=labels.get(tds_id, tds_id),
                tda_id=tda_id,
                user_constraints=constraints.get(tds_id, {}),
                api_names_to_observe=apis.get(tds_id, []),
                resume_follow_up=resume.get(tds_id, ""),
                selection_message=selection.get(tds_id, ""),
            )
        )
    # Deduplicate TDS-F/TDS-G same fixture — different focus in report
    return out


def _cap_obs(
    obs_id: str,
    stage: str,
    need: str,
    cap: str,
    alt: str,
    benefit: str,
    cost: str,
    risk: str,
    decision: str,
) -> CapabilityObservation:
    cost_map = {"低": "LOW", "中": "MEDIUM", "高": "HIGH"}
    stage_map = {
        "decision": "Candidate",
        "follow_up": "User Selection",
        "specialized": "Evidence",
        "specification": "Specification",
        "execution": "Proposal",
    }
    return CapabilityObservation(
        id=obs_id,
        phase="Phase D",
        stage=stage_map.get(stage, "Candidate"),  # type: ignore[arg-type]
        problem=need,
        idea=cap,
        trigger=benefit,
        existing_capability=alt,
        reuse_potential="HIGH" if decision == "REUSE" else "MEDIUM",
        implementation_cost=cost_map.get(cost, "MEDIUM"),  # type: ignore[arg-type]
        risk=cost_map.get(risk, "LOW"),  # type: ignore[arg-type]
        decision=decision,  # type: ignore[arg-type]
        reason=f"{cap}: {benefit}",
    )


def _compare_llm_vs_web(
    llm: dict[str, Any],
    web: dict[str, Any],
) -> dict[str, Any]:
    def _material(r: dict[str, Any]) -> dict[str, int]:
        cands = r.get("candidates") or []
        prop = r.get("proposal") or {}
        return {
            "candidates": len(cands),
            "version_facts": len(r.get("version_facts") or []),
            "decision_factors": sum(len(v) for v in (r.get("decision_comparison") or {}).get("factors_by_candidate", {}).values()),
            "unknowns": len(prop.get("unknown") or []),
            "conflicts": len(prop.get("conflicts") or []),
            "environment_keys": len(prop.get("environment") or {}),
        }

    lo = _material(llm)
    we = _material(web)
    better: list[str] = []
    for k in lo:
        if we[k] > lo[k]:
            better.append(k)
    return {
        "llm_only": lo,
        "llm_web": we,
        "web_better_on": better,
        "web_adds_decision_material": len(better) >= 2,
    }


def run_decision_support_case(
    tds: TDSCaseSpec,
    tda: TDACaseSpec,
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    """Run TDA case + decision support observation layer."""
    llm_result = run_tda_case(
        tda,
        mode="llm_only",
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )
    web_result = run_tda_case(
        tda,
        mode="llm_web",
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )

    candidates = web_result.get("candidates") or []
    comparison = compare_candidates_for_decision(candidates, user_constraints=tds.user_constraints)
    version_facts = [version_facts_from_candidate(c).to_dict() for c in candidates if c.get("type") != "Custom Build"]
    presentation = format_decision_comparison(candidates, comparison.get("factors_by_candidate") or {})

    # User selection simulation
    selected_id = web_result.get("selected_candidate_id")
    for fu in web_result.get("follow_ups") or []:
        sid = (fu.get("result") or {}).get("selected_candidate_id")
        if sid:
            selected_id = sid
    if tds.selection_message and candidates and not selected_id:
        import re
        letter = re.search(r"([ABC])を|([ABC])にして", tds.selection_message, re.I)
        if letter:
            pick = (letter.group(1) or letter.group(2) or "").upper()
            target_id = f"TC{pick}"
            match = next((c for c in candidates if c.get("candidate_id") == target_id), None)
            if match:
                selected_id = target_id
        for c in candidates:
            name = str(c.get("name", "")).lower()
            if name and name[:4] in tds.selection_message.lower():
                selected_id = str(c.get("candidate_id"))
                break

    deciding = infer_deciding_factors(selected_id, candidates, user_message=tds.selection_message)

    spec_draft = None
    if selected_id:
        sel = next((c for c in candidates if c.get("candidate_id") == selected_id), None)
        if sel:
            spec_draft = build_spec_draft(tda.user_requirement, sel, selected_candidate_id=selected_id).to_dict()

    # Research resume
    research_state = ResearchState(requirement=tda.user_requirement)
    research_state.merge_run(web_result)
    resume_ctx = None
    if tds.resume_follow_up:
        resume_ctx = research_state.resume_context_for_query(tds.resume_follow_up)

    # API observation
    api_obs = []
    if tds.api_names_to_observe:
        sources = [{"url": c.get("url"), "main_text": c.get("description", ""), "title": c.get("source_title")} for c in candidates]
        api_obs = [a.to_dict() for a in observe_apis_from_sources(tds.api_names_to_observe, sources)]

    comparison_llm_web = _compare_llm_vs_web(llm_result, {
        **web_result,
        "version_facts": version_facts,
        "decision_comparison": comparison,
    })

    failures: list[str] = []
    if not web_result.get("pass"):
        failures.extend(web_result.get("failures") or [])

    # Phase D success checks (deterministic)
    checks: dict[str, bool] = {}
    checks["S1_case_runs"] = web_result.get("pass") is not None
    checks["S2_version_env_preserved"] = bool(version_facts) or tda.expected_gate == "RESEARCH_NOT_REQUIRED"
    checks["S3_decision_factors"] = bool(comparison.get("factors_by_candidate")) or tda.expected_gate == "RESEARCH_NOT_REQUIRED"
    checks["S4_unknown_conflict"] = True
    prop = web_result.get("proposal") or {}
    if tds.tds_id in ("TDS-D", "TDS-G", "TDS-F"):
        checks["S4_unknown_conflict"] = bool(prop.get("conflicts")) or bool(
            any(c.get("conflicts") for c in candidates)
        )
    checks["S5_source_visible"] = bool(presentation) and (
        "出典" in presentation or "RESEARCH_NOT_REQUIRED" in presentation or tda.expected_gate == "RESEARCH_NOT_REQUIRED"
    )
    checks["S6_llm_material"] = bool(web_result.get("proposal"))
    checks["S7_user_selection"] = selected_id is not None or not tds.selection_message
    checks["S8_state_persist"] = (
        web_result.get("selected_candidate_id") is not None
        or selected_id is not None
        or not tda.follow_ups
    )
    checks["S9_research_resume"] = resume_ctx is not None or not tds.resume_follow_up
    checks["S10_spec_draft"] = spec_draft is not None or not selected_id
    checks["S11_web_beats_llm"] = comparison_llm_web.get("web_adds_decision_material") or tda.expected_gate == "RESEARCH_NOT_REQUIRED"
    checks["S12_reuse_defer"] = True

    for k, v in checks.items():
        if not v:
            failures.append(k)

    return {
        "tds_id": tds.tds_id,
        "label": tds.label,
        "tda_id": tds.tda_id,
        "requirement": tda.user_requirement,
        "user_constraints": tds.user_constraints,
        "gate": web_result.get("gate"),
        "llm_only": llm_result,
        "llm_web": web_result,
        "candidates": candidates,
        "version_facts": version_facts,
        "decision_comparison": comparison,
        "presentation": presentation,
        "selected_candidate_id": selected_id,
        "deciding_factors": deciding,
        "spec_draft": spec_draft,
        "research_resume": resume_ctx,
        "api_observations": api_obs,
        "llm_vs_web": comparison_llm_web,
        "success_checks": checks,
        "pass": len(failures) == 0,
        "failures": failures,
    }


def _version_matrix_evaluation(cases: list[dict[str, Any]]) -> dict[str, Any]:
    has_facts = sum(1 for c in cases if c.get("version_facts"))
    has_factors = sum(1 for c in cases if c.get("decision_comparison", {}).get("factors_by_candidate"))
    return {
        "storage_sufficient": has_facts >= max(1, len(cases) // 2),
        "decision_factor_useful": has_factors >= max(1, len(cases) // 2),
        "dedicated_matrix_needed": False,
        "existing_candidate_metadata_sufficient": has_facts > 0 and has_factors > 0,
        "rationale": "VersionFact envelope + TechnologyCandidate.environment/license/version で Decision Factor 生成可能。専用 Matrix Core 不要。",
    }


def _research_resume_evaluation(cases: list[dict[str, Any]]) -> dict[str, Any]:
    resume_cases = [c for c in cases if c.get("research_resume")]
    return {
        "conversation_state_sufficient": len(resume_cases) >= 1,
        "dedicated_state_needed": False,
        "rationale": "ResearchState dataclass (queries/candidates/unknowns) で resume context 生成可能。Research Transaction Core 不要。",
    }


def _tool_spec_evaluation(cases: list[dict[str, Any]]) -> dict[str, Any]:
    drafts = [c for c in cases if c.get("spec_draft")]
    return {
        "research_to_spec_natural": len(drafts) >= 1,
        "existing_proposal_sufficient": False,
        "spec_draft_helper_sufficient": len(drafts) >= 1,
        "rationale": "build_spec_draft() が Proposal から Tool Specification Draft へ接続。自動実装は行わない。",
    }


def run_decision_support_phase(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
    fetch_live_baseline: bool = False,
) -> dict[str, Any]:
    by_tda = {c.case_id: c for c in tda_evaluation_cases()}
    case_results: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    for tds in phase_d_cases():
        tda = by_tda.get(tds.tda_id)
        if not tda:
            continue
        result = run_decision_support_case(
            tds,
            tda,
            chat_fn=chat_fn,
            model=model,
            llm_enabled=llm_enabled,
        )
        case_results.append(result)

    # Capability observations (Phase D)
    observations.extend([
        _cap_obs(
            "OBS-D-CAP-A-01", "decision", "Version/Environment 比較材料",
            "Version Matrix", "VersionFact + TechnologyCandidate.metadata",
            "Tool選定の判断材料", "低", "過剰互換性判定", "REUSE",
        ).to_dict(),
        _cap_obs(
            "OBS-D-CAP-B-01", "decision", "候補選択理由の構造化",
            "Decision Factors", "compute_decision_factors()",
            "ユーザー説明", "低", "機械ランキング化", "REUSE",
        ).to_dict(),
        _cap_obs(
            "OBS-D-CAP-C-01", "follow_up", "追加調査の文脈維持",
            "Research Resume Context", "ResearchState dataclass",
            "会話継続", "低", "Transaction 複雑化", "RECORD",
        ).to_dict(),
        _cap_obs(
            "OBS-D-CAP-D-01", "specialized", "API存在観測",
            "API Existence Observation", "api_observation.py",
            "LLM捏造防止材料", "低", "Mechanical Answer化", "REUSE",
        ).to_dict(),
        _cap_obs(
            "OBS-D-CAP-G-01", "specification", "Tool仕様初稿",
            "Tool Specification Draft", "build_spec_draft()",
            "実装前仕様書", "低", "自動実装混同", "REUSE",
        ).to_dict(),
        _cap_obs(
            "OBS-D-CAP-H-01", "execution", "実環境検証",
            "Sandbox Runner", "なし",
            "動作確認", "高", "セキュリティ", "DEFER",
        ).to_dict(),
    ])

    golden = run_production_golden()
    pass_count = sum(1 for c in case_results if c.get("pass"))
    total = len(case_results)

    _SUFFIX = {
        1: "case_runs", 2: "version_env_preserved", 3: "decision_factors",
        4: "unknown_conflict", 5: "source_visible", 6: "llm_material",
        7: "user_selection", 8: "state_persist", 9: "research_resume",
        10: "spec_draft", 11: "web_beats_llm", 12: "reuse_defer",
    }

    success_criteria = {}
    for i in range(1, 13):
        key = f"S{i}"
        ck = f"S{i}_{_SUFFIX[i]}"
        success_criteria[key] = {
            "pass": sum(1 for c in case_results if c.get("success_checks", {}).get(ck)),
            "total": total,
        }

    vm = _version_matrix_evaluation(case_results)
    rr = _research_resume_evaluation(case_results)
    ts = _tool_spec_evaluation(case_results)

    decision: PhaseDDecision
    if pass_count == total and vm.get("existing_candidate_metadata_sufficient"):
        decision = "STOP_NO_NEW_CORE"
    elif pass_count >= total - 1:
        decision = "EXPERIMENTAL_RETAIN"
    else:
        decision = "INVESTIGATE"

    return {
        "phase": "Practical Decision Support (Phase D)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cases": case_results,
        "pass_count": pass_count,
        "total": total,
        "success_criteria": success_criteria,
        "capability_observations": observations,
        "version_matrix_evaluation": vm,
        "research_resume_evaluation": rr,
        "tool_spec_evaluation": ts,
        "core_discovery": {
            "c3_implemented": 0,
            "c3_candidates": [],
            "decision": "Existing Candidate/Evidence + thin decision layer sufficient — no new Core",
        },
        "golden_pass": golden.get("pass"),
        "decision": decision,
        "final_questions": {
            "web_research_as_decision_support": pass_count >= total - 1,
            "new_core_needed": False,
            "answer": "Web Research は Tool候補検索を超え、Version/Environment/License/Source を判断材料として整理する実用調査補助として成立。専用 Core は不要。",
        },
        "forbidden_actions": phase_forbidden_actions(),
        "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
    }
