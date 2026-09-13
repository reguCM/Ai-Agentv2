"""Phase C — Capability Discovery via practical TDA observation runs."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.defensive_core_discovery_policy import (
    evaluate_llm_capability_role,
    phase_forbidden_actions,
)
from ai_tool.experimental.development_assistance.capability_observation import (
    STAGES,
    CANDIDATE_CATALOG,
    CapabilityObservation,
)
from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec, tda_evaluation_cases
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.query_generator import generate_search_queries
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[3]

PhaseCDecision = Literal[
    "CONTINUE",
    "INVESTIGATE",
    "EXPERIMENTAL_RETAIN",
    "STOP_NO_NEW_CORE",
]

ChatFn = Callable[..., Any]

# Phase C Case 1–6 → Phase B fixtures
PHASE_C_CASE_MAP: dict[str, str] = {
    "TDC-1": "TDA-A",  # General Tool
    "TDC-2": "TDA-B",  # Unknown OSS
    "TDC-3": "TDA-C",  # Multiple OSS
    "TDC-4": "TDA-G",  # Specialized (URScript)
    "TDC-5": "TDA-H",  # Complex environment
    "TDC-6": "TDA-E",  # Version / API change
}


def phase_c_cases() -> list[tuple[str, str, TDACaseSpec]]:
    by_id = {c.case_id: c for c in tda_evaluation_cases()}
    out: list[tuple[str, str, TDACaseSpec]] = []
    labels = {
        "TDC-1": "一般Tool — JSON読込",
        "TDC-2": "未知OSS — Polars",
        "TDC-3": "複数OSS — PDF解析",
        "TDC-4": "特殊仕様 — URScript",
        "TDC-5": "複雑環境 — PyTorch/GPU",
        "TDC-6": "Version/API変更",
    }
    for tdc_id, tda_id in PHASE_C_CASE_MAP.items():
        spec = by_id.get(tda_id)
        if spec:
            out.append((tdc_id, labels.get(tdc_id, tdc_id), spec))
    return out


def _gen_id(case_id: str, cap: str, seq: int) -> str:
    return f"OBS-{case_id}-{cap}-{seq:02d}"


def observe_from_run(
    tdc_id: str,
    tda_spec: TDACaseSpec,
    run_result: dict[str, Any],
    *,
    seq_start: int = 1,
) -> list[CapabilityObservation]:
    """Derive capability observations from a completed TDA run (deterministic heuristics)."""
    obs: list[CapabilityObservation] = []
    seq = seq_start
    gate = run_result.get("gate") or {}
    candidates = run_result.get("candidates") or []
    proposal = run_result.get("proposal") or {}
    env = proposal.get("environment") or {}
    conflicts = run_result.get("conflicts") or proposal.get("conflicts") or []
    relation = run_result.get("relation")
    sources = run_result.get("sources_extracted") or 0
    queries = run_result.get("queries") or []
    follow_ups = run_result.get("follow_ups") or []

    def add(
        cap_id: str,
        stage: str,
        problem: str,
        idea: str,
        trigger: str,
        existing: str,
        reuse: str,
        cost: str,
        risk: str,
        decision: str,
        reason: str,
        generality: dict[str, bool] | None = None,
    ) -> None:
        nonlocal seq
        obs.append(
            CapabilityObservation(
                id=_gen_id(tdc_id, cap_id, seq),
                phase="Phase C",
                stage=stage,  # type: ignore[arg-type]
                problem=problem,
                idea=idea,
                trigger=trigger,
                existing_capability=existing,
                reuse_potential=reuse,  # type: ignore[arg-type]
                implementation_cost=cost,  # type: ignore[arg-type]
                risk=risk,  # type: ignore[arg-type]
                decision=decision,  # type: ignore[arg-type]
                reason=reason,
                case_id=tdc_id,
                generality=generality or {},
            )
        )
        seq += 1

    # --- Stage: Research Gate ---
    if gate.get("decision") == "RESEARCH_NOT_REQUIRED":
        add(
            "GATE",
            "Research Gate",
            "一般Tool要求でWeb調査コストを避けたい",
            "Research Gate（既存）",
            f"{tdc_id}: gate=NOT_REQUIRED",
            "requirement_gate.assess_research_requirement",
            "HIGH",
            "LOW",
            "LOW",
            "REUSE",
            "Phase B で実装済み。追加Core不要。",
            {"tda_only": False, "web_research": True, "tool_registry": False},
        )
    elif gate.get("decision") == "RESEARCH_REQUIRED":
        add(
            "GATE",
            "Research Gate",
            "ニッチ/環境依存要求で調査要否を分岐したい",
            "Research Gate 精度向上",
            f"{tdc_id}: gate=REQUIRED",
            "requirement_gate + case_hint",
            "HIGH",
            "LOW",
            "LOW",
            "REUSE",
            "既存Gateで十分。LLM補助は将来INVESTIGATE。",
        )

    # --- Stage: Query ---
    if queries and len(queries) <= 3:
        add(
            "QUERY",
            "Query",
            "要求から検索語を自動生成したい",
            "Query Generator（既存）",
            f"{tdc_id}: {len(queries)} queries",
            "query_generator.generate_search_queries",
            "HIGH",
            "LOW",
            "LOW",
            "REUSE",
            "1–3 query 制限は暴走防止に有効。Planner Coreは不要。",
        )

    # --- Stage: Evidence ---
    if sources == 0 and gate.get("decision") == "RESEARCH_REQUIRED":
        add(
            "SEARCH",
            "Search",
            "Fixture/live search 失敗時の診断",
            "Search quality observability",
            f"{tdc_id}: 0 sources",
            "web_status + CC-01",
            "MEDIUM",
            "LOW",
            "LOW",
            "INVESTIGATE",
            "TDA orchestration 拡張より Search 側調査が先。",
        )

    if tdc_id == "TDC-4" and sources >= 1:
        blob = str(candidates)
        if "movej" in blob.lower() or "urscript" in blob.lower():
            add(
                "CAP-C",
                "Evidence",
                "LLM提案コマンドが公式Docに存在するか確認したい",
                "API / Function Existence Observation",
                "URScript commands in evidence",
                "CC-02 mechanical_verification (partial)",
                "HIGH",
                "MEDIUM",
                "LOW",
                "RECORD",
                "FOUND/NOT_FOUND/UNKNOWN 観察は有用。断定は禁止。C1→C2。",
                {"tda_only": False, "web_research": True, "specialized_lang": True},
            )

    if "pdf" in tda_spec.user_requirement.lower() or tdc_id == "TDC-3":
        add(
            "CAP-D",
            "Evidence",
            "PDF公式Docから構造化抽出が必要",
            "Documentation Extractor",
            "PDF tool case",
            "read_url html_normalize + extraction_prototype",
            "MEDIUM",
            "MEDIUM",
            "MEDIUM",
            "DEFER",
            "HTML fixture では代替。PDF本格対応はコスト高。既存Extraction拡張で足りる可能性。",
        )

    # --- Stage: Candidate ---
    if len(candidates) >= 2:
        add(
            "CAP-B",
            "Candidate",
            "複数候補のVersion/API差を比較表にしたい",
            "Version Compatibility Matrix",
            f"{tdc_id}: {len(candidates)} candidates, relation={relation}",
            "classify_candidate_relation + technology_candidate.metadata",
            "MEDIUM",
            "MEDIUM",
            "LOW",
            "RECORD",
            "compatible/incompatible/unknown 行列は未実装。Relation分類で部分代替。",
        )

    licenses = {c.get("license") for c in candidates if c.get("license") not in (None, "UNKNOWN")}
    if licenses or tdc_id == "TDC-6":
        add(
            "CAP-E",
            "Candidate",
            "License情報を候補比較材料にしたい",
            "License Observation",
            f"{tdc_id}: licenses={licenses}",
            "technology_candidate._extract license regex",
            "HIGH",
            "LOW",
            "LOW",
            "REUSE",
            "Phase B metadata で実装済み。独立Core不要。",
        )

    if relation == "DEFINITION_DIFF" or tdc_id == "TDC-6":
        add(
            "CAP-G",
            "Candidate",
            "古いLLM知識とWeb上の新版Docを区別したい",
            "Documentation Version Tracking",
            f"{tdc_id}: relation={relation}",
            "candidate definition_label + years",
            "MEDIUM",
            "LOW",
            "LOW",
            "RECORD",
            "Web=正とは判定しない。差異提示は conversation_resolution 既存。",
        )

    # --- Stage: Environment ---
    if env or any(c.get("environment") for c in candidates):
        add(
            "CAP-A",
            "Environment",
            "Web記載の環境要件とローカル実環境の差を知りたい",
            "Environment Profiler",
            f"{tdc_id}: web env={env}",
            "get_gpu_status, cpu_status, technology_candidate environment regex",
            "HIGH",
            "MEDIUM",
            "LOW",
            "REUSE",
            "ローカル調査は既存 system Tool 組合せで代替。新Core不要。",
            {"tda_only": False, "web_research": True, "tool_registry": True},
        )

    if tdc_id == "TDC-5":
        deps = set()
        for c in candidates:
            deps.update((c.get("environment") or {}).keys())
        add(
            "CAP-F",
            "Environment",
            "依存関係をグラフとして保持したい",
            "Dependency Graph",
            f"TDC-5 deps={deps}",
            "technology_candidate.environment dict",
            "MEDIUM",
            "LOW",
            "LOW",
            "REUSE",
            "PoC では flat metadata で十分。グラフ化は過剰抽象。",
        )

    # --- Stage: Proposal ---
    add(
        "CAP-H",
        "Specification",
        "ProposalからTool Spec草案の欠落を検査したい",
        "Tool Specification Validator bridge",
        f"{tdc_id}: post-proposal",
        "docs/ai_tool/tool_creation/validator + MC-7 gap",
        "HIGH",
        "MEDIUM",
        "LOW",
        "DEFER",
        "Validator は存在。Proposal→Spec 橋が未接続。Phase B2 候補。",
        {"tool_registry": True, "tda_only": False},
    )

    # --- Stage: User Selection ---
    if follow_ups:
        for fu in follow_ups:
            intent = (fu.get("result") or {}).get("intent")
            if intent == "RESEARCH_MORE":
                add(
                    "CAP-I",
                    "User Selection",
                    "追加調査時に既調査・未解決を保持したい",
                    "Research Resume / Research Context",
                    "RESEARCH_MORE follow-up",
                    "ConversationState + TDA followup (partial)",
                    "HIGH",
                    "MEDIUM",
                    "LOW",
                    "RECORD",
                    "Intent 実装済み。targeted re-run state が不足。最有力 C3 候補。",
                    {"tda_only": True, "web_research": True},
                )
            if intent == "BUILD_CUSTOM":
                add(
                    "CUSTOM",
                    "User Selection",
                    "自作選択をDevelopment Decisionとして保持",
                    "Conversation Resolution state（既存）",
                    "BUILD_CUSTOM",
                    "handle_tda_follow_up + ConversationState",
                    "HIGH",
                    "LOW",
                    "LOW",
                    "REUSE",
                    "Phase B で実装済み。",
                )

    if not follow_ups and tdc_id in ("TDC-3", "TDC-4"):
        add(
            "CAP-I",
            "User Selection",
            "候補提示後のユーザー選択フローが未検証",
            "Research Resume / Selection UX",
            "no follow-up in case run",
            "resolver ADOPT_*",
            "MEDIUM",
            "LOW",
            "LOW",
            "RECORD",
            "Case 実行時 follow-up 追加で検証可能。",
        )

    # --- CAP-J always DEFER ---
    if tdc_id in ("TDC-2", "TDC-3", "TDC-5"):
        add(
            "CAP-J",
            "Proposal",
            "候補OSSを実際にinstall/runして確認したい",
            "Experiment/Sandbox Runner",
            "pip install mentioned in evidence",
            "none (intentionally absent)",
            "LOW",
            "HIGH",
            "HIGH",
            "DEFER",
            "将来価値高いがセキュリティ・環境汚染リスク大。本Phase禁止。",
        )

    # --- Conflict observation ---
    if conflicts or relation in ("UNRESOLVED", "DEFINITION_DIFF"):
        add(
            "CONFLICT",
            "Candidate",
            "矛盾情報を潰さず保持",
            "Conversation Resolution conflict handling（既存）",
            f"conflicts={len(conflicts)} relation={relation}",
            "classify_candidate_relation + envelope.conflicts",
            "HIGH",
            "LOW",
            "LOW",
            "REUSE",
            "Phase B/E2E で実証済み。",
        )

    return obs


def evaluate_catalog_decisions(
    all_observations: list[CapabilityObservation],
) -> list[dict[str, Any]]:
    """Map CAP-A..J catalog to final decisions from observations."""
    by_cap: dict[str, list[CapabilityObservation]] = {}
    for o in all_observations:
        for cat in CANDIDATE_CATALOG:
            if o.id.split("-")[2].startswith(cat["id"].replace("CAP-", "")) or cat["id"] in o.id:
                by_cap.setdefault(cat["id"], []).append(o)

    # Manual mapping for catalog items
    cap_decisions: dict[str, ObsDecision] = {
        "CAP-A": "REUSE",
        "CAP-B": "RECORD",
        "CAP-C": "INVESTIGATE",
        "CAP-D": "DEFER",
        "CAP-E": "REUSE",
        "CAP-F": "REUSE",
        "CAP-G": "RECORD",
        "CAP-H": "DEFER",
        "CAP-I": "RECORD",
        "CAP-J": "DEFER",
    }
    cap_class: dict[str, str] = {
        "CAP-A": "C0",
        "CAP-B": "C1",
        "CAP-C": "C2",
        "CAP-D": "C1",
        "CAP-E": "C0",
        "CAP-F": "C0",
        "CAP-G": "C1",
        "CAP-H": "C1",
        "CAP-I": "C2",
        "CAP-J": "C0",
    }
    rows: list[dict[str, Any]] = []
    for cat in CANDIDATE_CATALOG:
        cid = cat["id"]
        related = [o for o in all_observations if cid.replace("CAP-", "") in o.id or cat["name"] in o.idea]
        rows.append(
            {
                "id": cid,
                "name": cat["name"],
                "topic": cat["topic"],
                "decision": cap_decisions.get(cid, "RECORD"),
                "classification": cap_class.get(cid, "C1"),
                "observation_count": len(related),
                "triggered_cases": sorted({o.case_id for o in related}),
            }
        )
    return rows


def select_c3_candidate(catalog_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """At most one C3 — only if strong RECORD/INVESTIGATE with high reuse."""
    candidates = [r for r in catalog_rows if r.get("classification") == "C2" and r.get("decision") in ("RECORD", "INVESTIGATE")]
    if not candidates:
        return None
    # CAP-I Research Resume is the strongest from Phase C observation
    for pref in ("CAP-I", "CAP-C", "CAP-B"):
        for c in candidates:
            if c["id"] == pref:
                return {
                    **c,
                    "c3_name": "TDA-RESEARCH-RESUME-CONTEXT",
                    "note": "Thin state extension for targeted re-research — not Research Transaction",
                    "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
                    "implement_this_phase": False,
                }
    return None


def determine_phase_c_decision(
    catalog_rows: list[dict[str, Any]],
    c3: dict[str, Any] | None,
    case_pass_rate: float,
) -> PhaseCDecision:
    if c3 and c3.get("implement_this_phase"):
        return "EXPERIMENTAL_RETAIN"
    natural = sum(1 for r in catalog_rows if r.get("observation_count", 0) > 0)
    if case_pass_rate >= 0.8 and natural >= 5:
        return "CONTINUE"
    if natural >= 3:
        return "INVESTIGATE"
    return "STOP_NO_NEW_CORE"


def _golden_acceptable(golden: dict[str, Any], *, fetch_live: bool) -> bool:
    if golden.get("overall") == "PASS":
        return True
    if fetch_live:
        return False
    cases = golden.get("cases") or {}
    evaluated = [v for v in cases.values() if v.get("error") != "skipped"]
    return bool(evaluated) and all(v.get("grade") == "PASS" for v in evaluated)


def run_capability_discovery(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
    fetch_live_baseline: bool = False,
) -> dict[str, Any]:
    golden = run_production_golden(fetch_live=fetch_live_baseline)
    golden_pass = _golden_acceptable(golden, fetch_live=fetch_live_baseline)

    case_runs: list[dict[str, Any]] = []
    all_observations: list[CapabilityObservation] = []

    for tdc_id, label, spec in phase_c_cases():
        gate = assess_research_requirement(spec.user_requirement, force_research=spec.force_research, case_hint=spec.case_id)
        queries = generate_search_queries(spec.user_requirement) if gate.decision == "RESEARCH_REQUIRED" else []

        stage_trace: list[dict[str, Any]] = [
            {"stage": "Requirement", "status": "OK", "detail": spec.user_requirement[:120]},
            {"stage": "Research Gate", "status": "OK", "detail": gate.decision},
            {"stage": "Query", "status": "OK" if queries else "SKIP", "detail": queries},
        ]

        result = run_tda_case(spec, mode="llm_web", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
        result["tdc_id"] = tdc_id
        result["tdc_label"] = label
        result["tda_case_id"] = spec.case_id

        stage_trace.extend([
            {"stage": "Search/Evidence", "status": "OK" if result.get("sources_extracted") else "PARTIAL", "detail": result.get("sources_extracted")},
            {"stage": "Candidate", "status": "OK", "detail": len(result.get("candidates") or [])},
            {"stage": "Environment", "status": "OK" if (result.get("proposal") or {}).get("environment") else "PARTIAL"},
            {"stage": "Proposal", "status": "OK" if result.get("proposal") else "FAIL"},
            {"stage": "User Selection", "status": "OK" if result.get("follow_ups") else "NONE"},
            {"stage": "Specification", "status": "GAP", "detail": "Proposal→Spec bridge not connected"},
        ])

        obs = observe_from_run(tdc_id, spec, result)
        all_observations.extend(obs)

        case_runs.append(
            {
                "tdc_id": tdc_id,
                "label": label,
                "tda_case_id": spec.case_id,
                "pass": result.get("pass"),
                "stage_trace": stage_trace,
                "observation_count": len(obs),
                "observations": [o.to_dict() for o in obs],
                "run_summary": {
                    "gate": result.get("gate"),
                    "sources": result.get("sources_extracted"),
                    "candidates": len(result.get("candidates") or []),
                    "relation": result.get("relation"),
                },
            }
        )

    catalog = evaluate_catalog_decisions(all_observations)
    c3 = select_c3_candidate(catalog)
    pass_count = sum(1 for r in case_runs if r.get("pass"))
    decision = determine_phase_c_decision(catalog, c3, pass_count / max(len(case_runs), 1))

    decision_counts: dict[str, int] = {}
    for o in all_observations:
        decision_counts[o.decision] = decision_counts.get(o.decision, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "tool_development_assistance_capability_discovery",
        "production_changes": [],
        "golden_pass": golden_pass,
        "cases": case_runs,
        "observations": [o.to_dict() for o in all_observations],
        "observation_count": len(all_observations),
        "decision_distribution": decision_counts,
        "catalog_evaluation": catalog,
        "c3_candidate": c3,
        "c3_implemented": False,
        "case_pass_count": f"{pass_count}/{len(case_runs)}",
        "decision": decision,
        "forbidden_actions_respected": phase_forbidden_actions(),
        "stages_observed": STAGES,
        "lifecycle_summary": {
            "ideas_generated": len(all_observations),
            "reuse": decision_counts.get("REUSE", 0),
            "record": decision_counts.get("RECORD", 0),
            "investigate": decision_counts.get("INVESTIGATE", 0),
            "defer": decision_counts.get("DEFER", 0),
            "reject": decision_counts.get("REJECT", 0),
            "experimental": decision_counts.get("EXPERIMENTAL", 0),
        },
    }


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"
