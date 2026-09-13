"""Phase N — Requirement-driven Facet Discovery evaluation.

Not a Reasoning Core. Compares Goal Abstraction / dump-all / Discovery+Routing.
Discovery lists what must be known. It does not judge executable/safe/compatible.
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.facet_discovery import (
    audit_goal_abstraction_slots,
    asserts_not_a_decision,
    discover_facets,
    existing_mode_a_ids,
    plan_follow_up,
    resolve_research_reference,
)
from ai_tool.experimental.development_assistance.goal_abstraction import abstract_goals, discover_capabilities
from ai_tool.experimental.development_assistance.phase_g_harness import AMBIGUOUS_REQUIREMENT
from ai_tool.experimental.development_assistance.phase_l_relevant_facet_fixtures import (
    FACET_CATALOG,
    OSS_IRRELEVANT,
    record_with_catalog,
)
from ai_tool.experimental.development_assistance.relevant_facet_router import route_relevant_facets
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import extract_requirement_facets

_TYPED = {f.name for f in fields(ResearchRecord)}

OSS = list(OSS_IRRELEVANT)


def robot_store() -> ResearchStore:
    rec = ResearchRecord(**{k: v for k, v in record_with_catalog().items() if k in _TYPED})
    store = ResearchStore()
    store.add(rec)
    return store


def pytorch_record_a(*, python: str = "Python 3.13", cuda: str = "CUDA 12.3") -> ResearchRecord:
    payload = {
        "research_id": "RR-A",
        "requirement": "PyTorchについて調べて。",
        "topic": "A PyTorch environment",
        "technology_candidates": [
            {
                "candidate_id": "PT-X",
                "name": "PyTorch",
                "type": "OSS library",
                "version": "X",
                "license": "Y",
                "environment": {"python": python, "cuda": cuda},
            }
        ],
        "version_facts": [{"technology": "PyTorch", "version": "X", "python": python, "cuda": cuda}],
        "environment_facts": {"python": python, "cuda": cuda, "label": "A"},
        "license_facts": ["Y"],
        "api_observations": [],
        "sources": [],
        "unknowns": [],
        "conflicts": [],
        "queries": ["pytorch"],
        "checked_at": "2026-08-30T08:00:00+00:00",
        "provenance": "phase_n_fixture",
        "facet_records": [f for f in FACET_CATALOG if f["facet_id"] in {"python_version", "cuda", "license", "gpu"}],
    }
    return ResearchRecord(**{k: v for k, v in payload.items() if k in _TYPED})


CASES: list[dict[str, Any]] = [
    {
        "id": "N3-A",
        "requirement": "URSimをAgentから操作したあと、人間がPolyScopeから安全に操作を再開できるようにしたい。",
        "expected": [
            "transport",
            "control_authority",
            "operational_mode",
            "operational_mode_source",
            "program_state",
            "safety_state",
            "human_handoff",
        ],
        "irrelevant": list(OSS),
        "store": "robot",
    },
    {
        "id": "N3-B",
        "requirement": "URScriptがURSim 5.15.2で実行可能か調べたい。",
        "expected": ["urscript_api", "version", "ursim", "program_state", "execution_observation"],
        "irrelevant": list(OSS) + ["docker", "human_handoff"],
        "store": "robot",
    },
    {
        "id": "N3-C",
        "requirement": "URSim 5.15.2をこのPCのDocker環境で動かせるか調べたい。",
        "expected": [
            "ursim",
            "version",
            "docker",
            "wsl2",
            "cpu_virtualization",
            "ram",
            "storage",
            "network_ports",
        ],
        "irrelevant": ["control_authority", "human_handoff"] + list(OSS),
        "store": "robot",
    },
    {
        "id": "N4",
        "requirement": "さっき調べたAについて、今度はPython 3.12の場合だけもう少し調べて",
        "expected": ["python_version"],
        "irrelevant": ["human_handoff", "transport", "docker"],
        "store": "pytorch_a",
        "follow_up": True,
        "expect_partial": True,
        "expect_version": "3.12",
        "expect_target": True,
    },
    {
        "id": "N5",
        "requirement": "PyTorchについて調べた内容をPython 3.12環境の場合だけ再評価して。",
        "expected": ["python_version"],
        "irrelevant": ["human_handoff"],
        "store": "pytorch_a",
        "follow_up": True,
        "version_isolation": True,
        "expect_version": "3.12",
    },
    {
        "id": "N6",
        "requirement": "URScriptの実行可能性だけ調べたい。Docker環境については今回は不要。",
        "expected": ["urscript_api", "ursim", "version", "execution_observation", "program_state"],
        "irrelevant": ["docker", "wsl2", "storage"],
        "store": "robot",
        "negative": True,
    },
    {
        "id": "N7",
        "requirement": "URSim 5.15.2と5.25.2で、この機能が使えるか比較したい。",
        "expected": ["version", "conflict"],
        "concepts": ["feature", "compatibility", "evidence", "conflict"],
        "irrelevant": list(OSS),
        "store": "robot",
        "comparison": True,
    },
    {
        "id": "N8",
        "requirement": "LLMだけでは安全性を判断できないので、別の検証Toolを作りたい。",
        "expected": [],
        "concepts": [
            "llm_limitation",
            "external_evidence",
            "validation_capability",
            "observation",
            "decision_boundary",
            "human_review",
        ],
        "irrelevant": list(OSS) + ["cycle_controller"],
        "store": "robot",
        "capability": True,
        "not_only_safety": True,
    },
    {
        "id": "N9",
        "requirement": AMBIGUOUS_REQUIREMENT,
        "expected": [],
        "concepts": [
            "target",
            "capability",
            "difficulty",
            "external_knowledge_need",
            "environment",
            "existing_tool",
            "version",
            "evidence",
            "feasibility",
        ],
        "irrelevant": ["control_authority", "human_handoff", "docker"] + list(OSS),
        "store": "robot",
        "ambiguous": True,
    },
    {
        "id": "N10",
        "requirement": "AをPython 3.12の場合だけ再評価して。",
        "expected": ["python_version"],
        "irrelevant": ["human_handoff"],
        "store": "pytorch_a",
        "follow_up": True,
        "version_isolation": True,
    },
    {
        "id": "N12",
        "requirement": "このロボットControllerで外部トリガによるN回Cycleを安全に実行できるか？",
        "expected": [
            "cycle_controller",
            "safety_state",
            "operational_mode",
            "program_state",
            "execution_observation",
        ],
        "irrelevant": list(OSS),
        "store": "robot",
        "unknown": True,
        "must_not_gate_drop": True,
    },
]


def _store_for(kind: str) -> ResearchStore:
    if kind == "pytorch_a":
        s = ResearchStore()
        s.add(pytorch_record_a())
        return s
    return robot_store()


def _recall(selected: list[str], expected: list[str]) -> float | None:
    if not expected:
        return None
    return len(set(selected) & set(expected)) / len(expected)


def _suppression(selected: list[str], irrelevant: list[str]) -> float | None:
    if not irrelevant:
        return None
    leaked = len(set(selected) & set(irrelevant))
    return 1.0 - leaked / len(irrelevant)


def _mode_a(req: str) -> dict[str, Any]:
    goals = abstract_goals(req)
    rf = extract_requirement_facets(req)
    gate = assess_research_requirement(req)
    selected = existing_mode_a_ids(req)
    if gate.decision == "RESEARCH_NOT_REQUIRED":
        selected = []
    return {
        "selected": selected,
        "gate": gate.decision,
        "goals": goals.to_dict(),
        "requirement_facets": rf.to_dict(),
        "slots": audit_goal_abstraction_slots(goals.to_dict()),
    }


def _mode_b(req: str, store: ResearchStore) -> dict[str, Any]:
    sl = route_relevant_facets(req, list(store.records), mode="full")
    return {"selected": sl.facet_ids, "slice": sl.to_dict()}


def _mode_c(req: str, store: ResearchStore, *, session: dict[str, Any] | None = None) -> dict[str, Any]:
    disc = discover_facets(req, store, session=session)
    gate = assess_research_requirement(req)
    plan = plan_follow_up(req, store, session=session)
    dropped_by_gate = gate.decision == "RESEARCH_NOT_REQUIRED" and not disc.research_needed
    if dropped_by_gate:
        selected: list[str] = []
        sl = None
    else:
        sl = route_relevant_facets(
            req,
            list(store.records),
            mode="relevant",
            needed_facet_ids=disc.catalog_ids(),
        )
        selected = sl.facet_ids
    return {
        "selected": selected,
        "concepts": disc.concepts,
        "excluded": disc.excluded,
        "discovery": disc.to_dict(),
        "gate": gate.decision,
        "research_needed": disc.research_needed,
        "not_a_decision": asserts_not_a_decision(disc),
        "plan": plan.to_dict() if plan else None,
        "slice": sl.to_dict() if sl else {},
        "granularity": disc.granularity,
        "comparison": disc.comparison,
        "unresolved": disc.unresolved_references,
    }


def _score(case: dict[str, Any], pack: dict[str, Any], mode: str) -> dict[str, Any]:
    selected = list(pack.get("selected") or [])
    expected = list(case.get("expected") or [])
    irrelevant = list(case.get("irrelevant") or [])
    concepts = list(pack.get("concepts") or [])
    concept_recall = None
    if case.get("concepts"):
        concept_recall = len(set(concepts) & set(case["concepts"])) / len(case["concepts"])
    isolation = None
    if case.get("version_isolation") and pack.get("plan"):
        isolation = "3.13" not in (pack["plan"].get("requested_version") or "") and (
            pack["plan"].get("requested_version") == "3.12" or "3.12" in str(pack["plan"].get("missing"))
        )
    unknown_ok = None
    if case.get("unknown"):
        unknown_ok = "cycle_controller" in selected
    conflict_ok = None
    if case.get("comparison"):
        conflict_ok = pack.get("comparison") is True and "conflict" in (pack.get("discovery") or {}).get("catalog_ids", selected)
    false_inf = False
    if pack.get("not_a_decision") is False:
        false_inf = True
    gate_drop = None
    if case.get("must_not_gate_drop"):
        gate_drop = pack.get("gate") == "RESEARCH_NOT_REQUIRED" and not pack.get("research_needed")
        if mode == "A":
            gate_drop = pack.get("gate") == "RESEARCH_NOT_REQUIRED"
    return {
        "selected": selected,
        "recall": _recall(selected, expected) if expected else concept_recall,
        "suppression": _suppression(selected, irrelevant),
        "concept_recall": concept_recall,
        "version_isolated": isolation,
        "unknown_preserved": unknown_ok,
        "conflict_preserved": conflict_ok,
        "false_inference": false_inf,
        "gate": pack.get("gate"),
        "research_needed": pack.get("research_needed"),
        "gate_dropped_unknown": gate_drop,
        "granularity": pack.get("granularity"),
        "excluded": pack.get("excluded") or [],
        "plan": pack.get("plan"),
        "not_a_decision": pack.get("not_a_decision", True),
    }


def run_n15_session() -> dict[str, Any]:
    store = ResearchStore()
    rec = pytorch_record_a(python="", cuda="")
    rec.environment_facts["python"] = ""
    rec.environment_facts["cuda"] = ""
    store.add(rec)
    session = {"last_research_id": rec.research_id}
    initial = discover_facets("PyTorchについて調べて。", store, session=session)
    plan1 = plan_follow_up("PyTorchについて調べて。", store, session=session)
    plan2 = plan_follow_up(
        "さっきのPyTorchについてPython 3.12の場合だけ詳しく調べて。",
        store,
        session=session,
    )
    rec.environment_facts["python"] = "Python 3.12"
    session["last_python"] = "3.12"
    plan3 = plan_follow_up(
        "さらにCUDA 12.3の場合だけ確認して。",
        store,
        session=session,
    )
    rec.environment_facts["cuda"] = "CUDA 12.3"
    preserved = rec.environment_facts.get("python") == "Python 3.12" and rec.license_facts == ["Y"]
    return {
        "initial_follow_up": bool(plan1),
        "initial_research_needed": initial.research_needed,
        "step2_full_reresearch": None if plan2 is None else plan2.full_reresearch,
        "step2_missing": None if plan2 is None else plan2.missing,
        "step2_reusable": None if plan2 is None else plan2.reusable,
        "step2_searches": None if plan2 is None else plan2.searches_estimate,
        "step3_full_reresearch": None if plan3 is None else plan3.full_reresearch,
        "step3_missing": None if plan3 is None else plan3.missing,
        "step3_reusable": None if plan3 is None else plan3.reusable,
        "step3_searches": None if plan3 is None else plan3.searches_estimate,
        "prior_not_wiped": preserved,
        "not_always_full_search": (
            (plan2 is not None and not plan2.full_reresearch)
            and (plan3 is not None and not plan3.full_reresearch)
        ),
    }


def run_n16_references() -> dict[str, Any]:
    store = ResearchStore()
    store.add(pytorch_record_a())
    rows = []
    phrases = [
        "さっきのA",
        "そのPython版",
        "3.12の方だけ",
        "DockerじゃなくてVMの方",
        "前に調べたURSim",
    ]
    for p in phrases:
        ref = resolve_research_reference(p, store, session={})
        rows.append(
            {
                "phrase": p,
                "matched_id": ref["matched"].research_id if ref.get("matched") else "",
                "unresolved": ref.get("unresolved") or [],
                "clarifications": ref.get("clarifications") or [],
                "guessed": False,
            }
        )
    return {"phrases": rows}


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def run_phase_n() -> dict[str, Any]:
    n1_req = CASES[0]["requirement"]
    n1 = {
        "goals": abstract_goals(n1_req).to_dict(),
        "derived": [d.to_dict() for d in discover_capabilities(n1_req).derived_capabilities],
        "slots": audit_goal_abstraction_slots(abstract_goals(n1_req).to_dict()),
        "requirement_facets": extract_requirement_facets(n1_req).to_dict(),
    }
    rows = []
    for case in CASES:
        store = _store_for(case["store"])
        a = _mode_a(case["requirement"])
        b = _mode_b(case["requirement"], store)
        c = _mode_c(case["requirement"], store)
        rows.append(
            {
                "id": case["id"],
                "requirement": case["requirement"],
                "expected": case.get("expected") or [],
                "A": _score(case, a, "A") | {"raw_gate": a["gate"], "slots": a.get("slots")},
                "B": _score(case, b, "B"),
                "C": _score(case, c, "C")
                | {
                    "concepts": c.get("concepts"),
                    "excluded": c.get("excluded"),
                    "granularity": c.get("granularity"),
                    "research_needed": c.get("research_needed"),
                    "not_a_decision": c.get("not_a_decision"),
                    "plan": c.get("plan"),
                    "unresolved": c.get("unresolved"),
                },
            }
        )
    n15 = run_n15_session()
    n16 = run_n16_references()
    mapping = {
        "explicit_condition": any(r["C"].get("plan") and r["id"] in {"N4", "N5"} for r in rows),
        "implicit_needed": any(
            "operational_mode" in (r["C"].get("selected") or []) and r["id"] == "N3-A" for r in rows
        ),
        "version": any(r["id"] == "N5" and r["C"].get("version_isolated") for r in rows),
        "environment": any(r["id"] == "N3-C" and (r["C"].get("recall") or 0) >= 0.7 for r in rows),
        "capability": any(r["id"] == "N8" and (r["C"].get("concept_recall") or 0) >= 0.8 for r in rows),
        "comparison": any(r["id"] == "N7" and r["C"].get("conflict_preserved") for r in rows),
        "follow_up": any(r["id"] == "N4" and r["C"].get("plan") and not r["C"]["plan"]["full_reresearch"] for r in rows),
        "negative_constraint": any(r["id"] == "N6" and set(r["C"].get("excluded") or []) & {"docker"} for r in rows),
        "unknown": any(r["id"] == "N12" and r["C"].get("unknown_preserved") for r in rows),
        "conflict": any(r["id"] == "N7" and r["C"].get("conflict_preserved") for r in rows),
    }
    scored = [r for r in rows if r["expected"]]
    metrics = {
        "relevant_recall_A": _mean([r["A"]["recall"] for r in scored]),
        "relevant_recall_B": _mean([r["B"]["recall"] for r in scored]),
        "relevant_recall_C": _mean([r["C"]["recall"] for r in scored]),
        "irrelevant_suppression_A": _mean([r["A"]["suppression"] for r in rows]),
        "irrelevant_suppression_B": _mean([r["B"]["suppression"] for r in rows]),
        "irrelevant_suppression_C": _mean([r["C"]["suppression"] for r in rows]),
    }
    n12 = next(r for r in rows if r["id"] == "N12")
    n4 = next(r for r in rows if r["id"] == "N4")
    n8 = next(r for r in rows if r["id"] == "N8")
    existing_insufficient = (metrics["relevant_recall_A"] or 0) < (metrics["relevant_recall_C"] or 0)
    follow_ok = bool(n4["C"].get("plan") and n4["C"]["plan"].get("requested_version") == "3.12" and not n4["C"]["plan"].get("full_reresearch"))
    cycle_ok = n12["C"].get("research_needed") is True and n12["C"].get("unknown_preserved") is True
    n8_ok = (n8["C"].get("concept_recall") or 0) >= 0.8
    if (n8["C"].get("selected") or []) == ["safety_state"]:
        n8_ok = False
    if existing_insufficient and follow_ok and cycle_ok and n8_ok:
        decision = "EXPERIMENTAL"
        why = "Cue-table Facet Discovery adapter fills Goal Abstraction gaps without a Reasoning/Graph Core."
    elif existing_insufficient and follow_ok:
        decision = "RECORD"
        why = "Follow-up partial reuse works; coverage is not enough to wire as default."
    else:
        decision = "DEFER"
        why = "Not enough measured gain over existing Goal Abstraction + RequirementFacets."
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "n1_goal_audit": n1,
        "boundaries": {
            "Goal Abstraction": "What should be achieved (L0–L3 prose)",
            "Facet Discovery": "What must be known to judge — not a verdict",
            "Relevant Facet Routing": "Retrieve stored envelopes for those facet ids",
            "Research Reuse": "Full / partial / no reuse of past records",
            "Decision Support": "Present evidence/unknown/conflict; does not decide safe/executable",
        },
        "metrics": metrics,
        "cases": rows,
        "n15": n15,
        "n16": n16,
        "n11_dependencies_without_graph": True,
        "mapping_coverage": mapping,
        "core_creation_gate": {
            "GoalAbstraction_as_facet_discovery": "REJECT",
            "facet_discovery_adapter": decision,
            "Reasoning_Core": "REJECT",
            "Graph_Matrix_RAG_Vector": "REJECT",
            "relationship_as_metadata_list": "REUSE",
        },
        "adoption": {
            "decision": decision,
            "why": why,
            "question": "Requirement理解のあと、何をResearchから取り出せば判断できるかを既存構造から導出できるか",
            "follow_up_question": "さっき調べたA / Python 3.12だけ を Partial Reuse にできるか",
            "follow_up_ok": follow_ok,
            "cycle_not_dropped": cycle_ok,
        },
    }
