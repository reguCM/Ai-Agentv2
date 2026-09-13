"""Phase L — Requirement → relevant facet slice. Evaluation / orchestration only.

Does not add a Reasoning, Matrix, or Graph Core.
Mode A = existing RequirementFacets / Goal / Reuse / DecisionFactor.
Mode C = alias overlap against facet_records stored on the fixture (retrieve a slice).
"""
from __future__ import annotations

import json
import re
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.decision_factors import (
    DecisionFactor,
    compare_candidates_for_decision,
    compute_decision_factors,
)
from ai_tool.experimental.development_assistance.decision_presentation import format_decision_comparison
from ai_tool.experimental.development_assistance.goal_abstraction import discover_capabilities
from ai_tool.experimental.development_assistance.phase_l_relevant_facet_fixtures import (
    CASES,
    FACET_CATALOG,
    record_with_catalog,
)
from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import (
    assess_reuse,
    extract_requirement_facets,
    reuse_conversation_material,
)
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow

_TYPED = {f.name for f in fields(ResearchRecord)}


def existing_structure_audit() -> dict[str, Any]:
    rec = ResearchRecord(
        **{k: v for k, v in record_with_catalog().items() if k in _TYPED},
    )
    rf = extract_requirement_facets("人間がPolyScopeから操作を再開できるか")
    return {
        "requirement_facet_fields": [
            "technologies",
            "python",
            "cuda",
            "os",
            "license_preference",
            "topic_tokens",
        ],
        "requirement_facets_select_robot_ids": False,
        "requirement_facets_used_by": ["assess_reuse", "standard_workflow reuse check"],
        "facet_records_on_dataclass": "facet_records" in rec.to_dict(),
        "facet_records_on_fixture_json": True,
        "decision_factors_keys": ["version", "python_compatibility", "license", "official_source", "cuda"],
        "reuse_summary_emits": ["python", "cuda", "license", "source", "freshness", "unknowns as strings"],
        "reuse_summary_drops": [
            "control_authority",
            "operational_mode_source",
            "transport",
            "human_handoff",
            "facet_records",
        ],
        "harness_only_can_test": [
            "alias overlap against stored facet_records",
            "route evidence/unknown/conflict into DecisionFactor",
            "compare Mode A/B/C material packages without LLM truth judging",
        ],
        "cannot_without_helper": [
            "Standard Workflow will not select control_authority from a PolyScope handoff requirement",
            "reuse_conversation_material will not print TCP vs ownership",
        ],
    }


def _catalog_by_id() -> dict[str, dict[str, Any]]:
    return {str(f["facet_id"]): f for f in FACET_CATALOG}


def select_by_alias(requirement: str, catalog: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Retrieve stored facets whose aliases appear in the requirement. No inference."""
    from ai_tool.experimental.development_assistance.relevant_facet_router import select_relevant_facets

    selected = select_relevant_facets(requirement, catalog or FACET_CATALOG)
    return [
        {
            "facet_id": facet["facet_id"],
            "family": facet.get("family"),
            "matched_aliases": list(facet.get("matched_aliases") or []),
            "reason": (
                f"stored companion of {facet.get('pulled_with')}"
                if facet.get("pulled_with")
                else "requirement contains stored alias: " + ", ".join((facet.get("matched_aliases") or [])[:4])
            ),
            "evidence": list(facet.get("evidence") or []),
            "unknown": list(facet.get("unknown") or []),
            "conflicts": list(facet.get("conflicts") or []),
        }
        for facet in selected
    ]


def mode_a_existing(requirement: str, store: ResearchStore) -> dict[str, Any]:
    facets = extract_requirement_facets(requirement)
    goals = discover_capabilities(requirement)
    reuse = assess_reuse(facets, store)
    material = reuse_conversation_material(reuse, store)
    selected: list[str] = []
    if facets.python:
        selected.append("python_version")
    if facets.cuda:
        selected.append("cuda")
    if facets.os:
        selected.append("cpu")  # existing os field is not a robot facet
    if facets.license_preference:
        selected.append("license")
    for t in facets.technologies:
        tl = t.lower()
        if tl == "urscript":
            selected.append("urscript_api")
        elif tl in {"json", "pandas", "polars", "pytorch"}:
            selected.append("documentation_version")
    return {
        "mode": "A",
        "requirement_facets": facets.to_dict(),
        "goals": goals.goals.to_dict(),
        "derived": [d.name for d in goals.derived_capabilities],
        "reuse": reuse.to_dict(),
        "llm_material": material,
        "selected_ids": sorted(set(selected)),
        "notes": "Existing extractor only fills python/cuda/os/license/oss tech names.",
    }


def mode_b_full_record() -> dict[str, Any]:
    ids = [str(f["facet_id"]) for f in FACET_CATALOG]
    return {
        "mode": "B",
        "selected_ids": ids,
        "notes": "Entire facet catalog dumped; no requirement filtering.",
    }


def route_to_decision_factors(selected: list[dict[str, Any]], record: dict[str, Any]) -> list[DecisionFactor]:
    """Attach stored evidence/unknown/conflict. Does not decide YES/NO on the requirement."""
    factors: list[DecisionFactor] = []
    rec_conflicts = json.dumps(record.get("conflicts") or [], ensure_ascii=False).lower()
    rec_unknowns = json.dumps(record.get("unknowns") or [], ensure_ascii=False).lower()
    for item in selected:
        fid = str(item["facet_id"])
        unknowns = list(item.get("unknown") or [])
        conflicts = list(item.get("conflicts") or [])
        evidence = list(item.get("evidence") or [])
        if unknowns:
            status: str = "unknown"
            detail = "; ".join(unknowns)
        elif conflicts:
            status = "conflict"
            detail = "; ".join(str(c) for c in conflicts)
        elif evidence:
            status = "match"
            detail = "; ".join(str(e) for e in evidence[:3])
        else:
            status = "partial"
            detail = item.get("reason") or fid
        if fid in rec_unknowns and status != "conflict":
            status = "unknown"
            if not unknowns:
                detail = f"listed on ResearchRecord.unknowns ({fid})"
        if any(str(c).lower() in rec_conflicts for c in conflicts) or (
            fid.replace("_", " ") in rec_conflicts
        ):
            if status != "unknown":
                status = "conflict"
        factors.append(
            DecisionFactor(
                factor=fid,
                status=status,  # type: ignore[arg-type]
                detail=detail,
                candidate_id="RR-slice",
            )
        )
    return factors


def score_selection(
    case: dict[str, Any],
    selected_ids: list[str],
) -> dict[str, Any]:
    expected = list(case.get("expected") or [])
    irrelevant = list(case.get("irrelevant") or [])
    selected = set(selected_ids)
    exp = set(expected)
    irr = set(irrelevant)
    hit = selected & exp
    extra_ok = selected - exp - irr
    irr_hit = selected & irr
    recall = (len(hit) / len(exp)) if exp else None
    suppression = (1 - len(irr_hit) / len(irr)) if irr else 1.0
    not_primary = set(case.get("not_primary") or [])
    primary_leak = selected & not_primary
    return {
        "case_id": case["id"],
        "selected": sorted(selected),
        "expected_hit": sorted(hit),
        "expected_miss": sorted(exp - selected),
        "irrelevant_hit": sorted(irr_hit),
        "extra_not_penalized": sorted(extra_ok),
        "not_primary_selected": sorted(primary_leak),
        "recall": recall,
        "suppression": suppression,
        "why_expected": case.get("why_expected") or {},
    }


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def run_phase_l() -> dict[str, Any]:
    audit = existing_structure_audit()
    payload = record_with_catalog()
    typed = ResearchRecord(**{k: v for k, v in payload.items() if k in _TYPED})
    store = ResearchStore()
    store.add(typed)

    case_rows: list[dict[str, Any]] = []
    for case in CASES:
        req = case["requirement"]
        a = mode_a_existing(req, store)
        b = mode_b_full_record()
        c_sel = select_by_alias(req)
        c_ids = [x["facet_id"] for x in c_sel]
        factors = route_to_decision_factors(c_sel, payload)
        syn_candidate = {
            "candidate_id": "RR-slice",
            "name": "URSim 5.15.2 ResearchRecord slice",
            "type": "Vendor controller",
            "version": "5.15.2",
            "license": "UNKNOWN",
            "source_category": "Official Documentation",
            "source_title": "Phase J / L fixture",
            "url": "",
            "unknowns": [f.detail for f in factors if f.status == "unknown"],
            "conflicts": [{"note": f.detail} for f in factors if f.status == "conflict"],
        }
        presentation = format_decision_comparison(
            [syn_candidate],
            {"RR-slice": [f.to_dict() for f in factors]},
        )
        cand_factors = compute_decision_factors(payload["technology_candidates"][0])
        a_score = score_selection(case, a["selected_ids"])
        b_score = score_selection(case, b["selected_ids"])
        c_score = score_selection(case, c_ids)

        unknown_routed = [
            f.to_dict()
            for f in factors
            if f.status == "unknown" and f.factor in set(case.get("require_unknown") or [])
        ]
        conflict_routed = [f.to_dict() for f in factors if f.status == "conflict"]
        version_isolated = not (
            case["id"] in {"L4-D", "L7"} and any("5.17" in (f.detail or "") and f.status == "match" and f.factor == "permission_feature" for f in factors)
        )
        # Isolation = permission_feature arrived as conflict or unknown, not as match claiming 5.15 has 5.17
        if case["id"] in {"L4-D", "L7"}:
            perm = next((f for f in factors if f.factor == "permission_feature"), None)
            version_isolated = perm is None or perm.status in {"conflict", "unknown"}

        k9_conflict = False
        if case["id"] == "L9":
            blob = json.dumps([f.to_dict() for f in factors], ensure_ascii=False).lower()
            k9_conflict = "tcp disconnect" in blob or "transport-vs-authority" in blob or "does not clear" in blob

        reusable, missing = [], []
        if case["id"] == "L8":
            present = set(case.get("reuse_present_on_record") or [])
            reusable = sorted(set(c_ids) & present)
            missing = sorted(set(c_ids) - present)
            for fid in case.get("fresh_research_ok") or []:
                if fid not in c_ids:
                    missing.append(fid)
            missing = sorted(set(missing))

        case_rows.append(
            {
                "id": case["id"],
                "requirement": req,
                "mode_a": a_score,
                "mode_b": b_score,
                "mode_c": c_score,
                "mode_c_reasons": {x["facet_id"]: x["reason"] for x in c_sel},
                "factors": [f.to_dict() for f in factors],
                "existing_candidate_factors": [f.to_dict() for f in cand_factors],
                "presentation_excerpt": presentation[:800],
                "unknown_routed": unknown_routed,
                "conflict_routed": conflict_routed,
                "version_isolated": version_isolated,
                "k9_handoff_conflict_reached": k9_conflict,
                "l8_reusable": reusable,
                "l8_missing": missing,
                "workflow_a_derived": a["derived"],
                "workflow_a_reuse_mode": a["reuse"]["mode"],
                "workflow_a_material_has_authority": "control authority" in a["llm_material"].lower()
                or "operational mode" in a["llm_material"].lower(),
            }
        )

    def _agg(mode_key: str, field: str) -> float | None:
        return _mean([row[mode_key].get(field) for row in case_rows])

    l9 = next(r for r in case_rows if r["id"] == "L9")
    l3 = next(r for r in case_rows if r["id"] == "L3")
    l6 = next(r for r in case_rows if r["id"] == "L6")
    l7 = next(r for r in case_rows if r["id"] == "L7")
    l8 = next(r for r in case_rows if r["id"] == "L8")

    metrics = {
        "relevant_recall_mode_a": _agg("mode_a", "recall"),
        "relevant_recall_mode_b": _agg("mode_b", "recall"),
        "relevant_recall_mode_c": _agg("mode_c", "recall"),
        "irrelevant_suppression_mode_a": _agg("mode_a", "suppression"),
        "irrelevant_suppression_mode_b": _agg("mode_b", "suppression"),
        "irrelevant_suppression_mode_c": _agg("mode_c", "suppression"),
        "evidence_routing_mode_c": _mean(
            [1.0 if r["factors"] else 0.0 for r in case_rows]
        ),
        "unknown_routing_l6": 1.0 if l6["unknown_routed"] else 0.0,
        "conflict_routing_l7": 1.0 if l7["conflict_routed"] else 0.0,
        "version_isolation_l4d_l7": _mean(
            [1.0 if r["version_isolated"] else 0.0 for r in case_rows if r["id"] in {"L4-D", "L7"}]
        ),
        "reuse_routing_l8_reusable_n": len(l8["l8_reusable"]),
        "k9_min_facets_mode_c": len(set(l9["mode_c"]["expected_hit"])) / 5,
        "k9_conflict_reached": l9["k9_handoff_conflict_reached"],
        "decision_improvement_recall_c_minus_a": (
            None
            if _agg("mode_c", "recall") is None or _agg("mode_a", "recall") is None
            else _agg("mode_c", "recall") - _agg("mode_a", "recall")
        ),
        "l3_oss_suppression": l3["mode_c"]["suppression"],
    }

    mode_c_better_noise = (metrics["irrelevant_suppression_mode_c"] or 0) > (
        metrics["irrelevant_suppression_mode_b"] or 0
    )
    gate = {
        "RequirementFacets_as_robot_selector": "REJECT",
        "ResearchRecord_facet_records_storage": "REUSE",
        "DecisionFactor_as_routing_envelope": "REUSE",
        "alias_slice_helper": "EXPERIMENTAL",
        "wire_into_StandardWorkflow": "DEFER",
        "Reasoning_Matrix_Graph_Core": "REJECT",
        "rationale": (
            "Mode A recall is near zero on robot facets. Mode B recall is high but "
            "dumps Python/CUDA/License. Mode C alias overlap on stored facet_records "
            "raises recall and suppression without a graph. That is a retrieve-a-slice "
            "helper, not a Reasoning Core. Do not Production-wire yet."
        ),
    }

    workflow_k9 = run_standard_workflow(l9["requirement"], store=store, llm_enabled=False)

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "audit": audit,
        "metrics": metrics,
        "cases": case_rows,
        "mode_c_better_than_b_on_suppression": mode_c_better_noise,
        "k9_existing_workflow_reuse": workflow_k9.reuse_assessment,
        "k9_existing_workflow_mentions_handoff": "handoff" in json.dumps(workflow_k9.to_dict()).lower(),
        "core_creation_gate": gate,
        "answer": (
            "The agent can store Research. Existing RequirementFacets cannot pick "
            "Control Authority for a PolyScope resume requirement. A slice of "
            "facet_records by stored aliases can, and can carry Unknown/Conflict "
            "into DecisionFactor without deciding the question."
        ),
    }
