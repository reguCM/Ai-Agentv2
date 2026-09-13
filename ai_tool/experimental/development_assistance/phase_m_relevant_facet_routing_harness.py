"""Phase M — wire relevant-facet routing into experimental Standard Workflow.

Not a Reasoning / Matrix / Graph Core. Modes:

  A  facet_routing=off     existing Standard Workflow
  B  facet_routing=full    dump all stored facet_records into Decision Support
  C  facet_routing=relevant alias slice + evidence/unknown/conflict envelope
"""
from __future__ import annotations

import json
import time
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.experimental.development_assistance.phase_l_relevant_facet_fixtures import (
    FACET_CATALOG,
    OSS_IRRELEVANT,
    record_with_catalog,
)
from ai_tool.experimental.development_assistance.relevant_facet_router import RoutingMode
from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import extract_requirement_facets
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow

_TYPED = {f.name for f in fields(ResearchRecord)}
_CATALOG = {str(f["facet_id"]): f for f in FACET_CATALOG}

_UNSAFE_HANDOFF = "tcp disconnect guarantees human handoff"
_HANDOFF_CONFLICT = "tcp disconnect does not clear"


CASES: list[dict[str, Any]] = [
    {
        "id": "M6-1",
        "label": "Robot Human Handoff",
        "requirement": (
            "Dashboardとの通信を切断すれば、人間がPolyScopeから操作を安全に再開できるか？"
        ),
        "expected": [
            "transport",
            "control_authority",
            "operational_mode",
            "operational_mode_source",
            "human_handoff",
        ],
        "irrelevant": list(OSS_IRRELEVANT),
        "require_conflict_substr": _HANDOFF_CONFLICT,
        "forbid_unsafe": True,
    },
    {
        "id": "M6-2",
        "label": "URScript Execution",
        "requirement": "URScriptをURSim 5.15.2で実行できるか？",
        "expected": [
            "urscript_api",
            "version",
            "ursim",
            "program_state",
            "execution_observation",
        ],
        "irrelevant": list(OSS_IRRELEVANT) + ["control_authority", "human_handoff"],
        "not_primary": ["control_authority"],
    },
    {
        "id": "M6-3",
        "label": "Docker Environment",
        "requirement": "URSim 5.15.2を現在のDocker環境で動かせるか？",
        "expected": ["docker", "ursim", "version", "wsl2", "storage", "network_ports"],
        "irrelevant": ["control_authority", "human_handoff"] + list(OSS_IRRELEVANT),
    },
    {
        "id": "M6-4",
        "label": "Version Conflict",
        "requirement": "UR 5.17のPermission仕様を5.15.2へ適用できるか？",
        "expected": ["version", "permission_feature"],
        "envelope_expected": ["conflict", "evidence"],
        "irrelevant": list(OSS_IRRELEVANT) + ["human_handoff"],
        "version_isolation": True,
        "require_conflict_substr": "5.17",
    },
    {
        "id": "M6-5",
        "label": "Unknown Cycle",
        "requirement": "外部トリガによるN回Cycleを実装できるか？",
        "expected": ["cycle_controller"],
        "irrelevant": list(OSS_IRRELEVANT),
        "require_unknown_facet": "cycle_controller",
    },
    {
        "id": "M6-6",
        "label": "Full Reuse Docker Ports",
        "requirement": "以前調べたURSim 5.15.2について、今度はDockerのPort設定だけ詳しく調べたい",
        "expected": ["docker", "network_ports", "ursim", "version"],
        "irrelevant": ["control_authority", "human_handoff", "cycle_controller"] + list(OSS_IRRELEVANT),
        "reuse_focus": True,
    },
    {
        "id": "M6-7",
        "label": "Irrelevant Suppression",
        "requirement": (
            "Dashboardとの通信を切断すれば、人間がPolyScopeから操作を安全に再開できるか？"
            " 混在ノイズ: Python CUDA License CPU"
        ),
        "expected": [
            "transport",
            "control_authority",
            "operational_mode",
            "operational_mode_source",
            "human_handoff",
        ],
        "irrelevant": list(OSS_IRRELEVANT),
        "planted_oss_tokens": True,
    },
    {
        "id": "M6-8",
        "label": "LLM-only Early Exit",
        "requirement": "JSONを検証するToolを作りたい。",
        "expected": [],
        "irrelevant": list(OSS_IRRELEVANT) + [
            "transport",
            "control_authority",
            "human_handoff",
        ],
        "early_exit_gate": True,
    },
    {
        "id": "M8-K7",
        "label": "K-7 Regression",
        "requirement": (
            "URSimをAgentから操作したあと、Dashboardとの通信を切断すれば、"
            "人間がPolyScopeから安全に操作を再開できるToolを作ってください。"
        ),
        "expected": [
            "transport",
            "control_authority",
            "operational_mode",
            "operational_mode_source",
            "human_handoff",
        ],
        "irrelevant": list(OSS_IRRELEVANT),
        "require_conflict_substr": _HANDOFF_CONFLICT,
        "forbid_unsafe": True,
        "k7": True,
    },
]


def seeded_store() -> ResearchStore:
    rec = ResearchRecord(**{k: v for k, v in record_with_catalog().items() if k in _TYPED})
    store = ResearchStore()
    store.add(rec)
    return store


def existing_workflow_audit() -> dict[str, Any]:
    """M-1 — insertion points on the existing Standard Workflow (pre-wiring facts)."""
    wf_src = Path(__file__).with_name("standard_workflow.py").read_text(encoding="utf-8")
    reuse_src = Path(__file__).with_name("research_reuse.py").read_text(encoding="utf-8")
    rf = extract_requirement_facets(
        "URSimをAgentから操作したあと、人間がPolyScopeから操作を再開できるようにしたい"
    )
    return {
        "standard_path": [
            "Requirement",
            "Gate",
            "L0/L1/L2",
            "Capability Discovery",
            "Research Reuse Check",
            "不足分のみ Web",
            "Candidate",
            "Decision Support",
            "Tool Spec",
        ],
        "1_requirement_facets_generated": {
            "where": "run_standard_workflow research path, after Gate, via extract_requirement_facets",
            "fields": ["technologies", "python", "cuda", "os", "license_preference", "topic_tokens"],
            "robot_facets_emitted": False,
            "sample_technologies": list(rf.technologies),
            "sample_python": rf.python,
        },
        "2_research_reuse_searches": {
            "matcher": "_facet_overlap: license / python / cuda / version / source / topic / tech names",
            "robot_facet_keys": False,
            "source_mentions_python": "python" in reuse_src,
            "source_mentions_control_authority": "control_authority" in reuse_src,
        },
        "3_decision_support_receives": {
            "default": "compare_candidates_for_decision(candidates) only",
            "with_routing": "candidates + relevant_slice / slice_factors from facet_records",
            "facet_records_passed_when_off": False,
        },
        "4_facet_records_usable": {
            "on_research_record": True,
            "workflow_reads_when_routing_on": "facet_routing" in wf_src and "route_relevant_facets" in wf_src,
            "default_mode": "off",
        },
        "5_full_research_record_pass": {
            "legacy_off": False,
            "mode_b": "facet_routing='full'",
        },
        "6_reuse_summary_only": {
            "llm_material_base": "reuse_conversation_material (python/cuda/license)",
            "slice_appended_when_routing_on": True,
        },
        "insertion_point": (
            "After Research Reuse / Web Research, before API Observation and Decision Support. "
            "Skipped entirely on Gate RESEARCH_NOT_REQUIRED."
        ),
        "not_a_reasoning_engine": True,
    }


def _selected_ids(result: Any) -> list[str]:
    slice_ = result.relevant_slice or {}
    return list(slice_.get("facet_ids") or [])


def _item_blob(result: Any) -> str:
    return json.dumps(result.relevant_slice or {}, ensure_ascii=False).lower() + "\n" + (
        json.dumps(result.decision_support or {}, ensure_ascii=False).lower()
    )


def _recall(selected: list[str], expected: list[str]) -> float | None:
    if not expected:
        return None
    hit = len(set(selected) & set(expected))
    return hit / len(expected)


def _suppression(selected: list[str], irrelevant: list[str]) -> float | None:
    if not irrelevant:
        return None
    leaked = len(set(selected) & set(irrelevant))
    return 1.0 - (leaked / len(irrelevant))


def _envelope_preservation(result: Any, kind: str) -> float | None:
    items = list((result.relevant_slice or {}).get("items") or [])
    if not items:
        return None
    catalog_had = 0
    kept = 0
    for item in items:
        fid = str(item.get("facet_id") or "")
        cat = _CATALOG.get(fid) or {}
        src = list(cat.get(kind) or [])
        if not src:
            continue
        catalog_had += 1
        got = list(item.get("evidence" if kind == "evidence" else kind) or [])
        if kind == "unknown":
            got = list(item.get("unknown") or [])
        if kind == "conflicts":
            got = list(item.get("conflicts") or [])
        if got:
            kept += 1
    if catalog_had == 0:
        return None
    return kept / catalog_had


def _value_version_provenance_kept(result: Any) -> dict[str, float | None]:
    items = list((result.relevant_slice or {}).get("items") or [])
    if not items:
        return {"value": None, "version": None, "provenance": None}
    n = len(items)
    return {
        "value": sum(1 for i in items if i.get("value") not in (None, "")) / n,
        "version": sum(1 for i in items if i.get("version")) / n,
        "provenance": sum(1 for i in items if i.get("provenance")) / n,
    }


def _failure_stage(case: dict[str, Any], selected: list[str], result: Any) -> str:
    if case.get("early_exit_gate"):
        if result.stop_reason == "EARLY_EXIT_GATE" and not selected:
            return ""
        return "Requirement Gate"
    if result.stop_reason == "EARLY_EXIT_GATE":
        return "Requirement理解"
    missing = [f for f in case.get("expected") or [] if f not in selected]
    if not missing:
        blob = _item_blob(result)
        if case.get("require_conflict_substr") and case["require_conflict_substr"] not in blob:
            return "Evidence Routing"
        if case.get("require_unknown_facet"):
            unk_ok = any(
                i.get("facet_id") == case["require_unknown_facet"] and i.get("unknown")
                for i in (result.relevant_slice or {}).get("items") or []
            )
            if not unk_ok:
                return "Evidence Routing"
        return ""
    req = case["requirement"]
    mapping = []
    for fid in missing:
        cat = _CATALOG.get(fid) or {}
        aliases = [str(a) for a in (cat.get("aliases") or [])]
        hit = any((a.lower() in req.lower() or a in req) for a in aliases if a)
        if not hit and not any(
            fid in ((_CATALOG.get(src) or {}).get("pull_with") or []) for src in _CATALOG
        ):
            mapping.append(fid)
    if mapping:
        return "Requirement → Facet Mapping不足"
    if missing:
        return "Facet Selection"
    return "Decision Support"


def _score_mode(case: dict[str, Any], result: Any, elapsed_ms: float, mode: str) -> dict[str, Any]:
    selected = _selected_ids(result)
    blob = _item_blob(result)
    expected = list(case.get("expected") or [])
    irrelevant = list(case.get("irrelevant") or [])
    routing_stage = [
        s for s in result.stages if (s.get("stage") if isinstance(s, dict) else getattr(s, "stage", "")) == "Relevant Facet Routing"
    ]
    conflict_ok = True
    if case.get("require_conflict_substr"):
        conflict_ok = case["require_conflict_substr"] in blob
    unknown_ok = True
    if case.get("require_unknown_facet"):
        unknown_ok = any(
            i.get("facet_id") == case["require_unknown_facet"] and i.get("unknown")
            for i in (result.relevant_slice or {}).get("items") or []
        )
    version_ok = True
    if case.get("version_isolation"):
        version_ok = "5.17" in blob and "5.15.2" in json.dumps(result.relevant_slice or {})
        # must not treat 5.17 as applying to 5.15.2
        if "does not apply" in blob or "not applied" in blob or "do not mix" in blob or "not applying" in blob:
            version_ok = True
        elif "apply 5.17" in blob and "5.15.2" in blob and "not" not in blob:
            version_ok = False
    false_inf = False
    if case.get("forbid_unsafe"):
        false_inf = _UNSAFE_HANDOFF in blob
        if conflict_ok:
            false_inf = False
        elif mode != "A" and selected and not conflict_ok:
            false_inf = True
    decision_acc = None
    if case.get("require_conflict_substr"):
        decision_acc = 1.0 if conflict_ok else 0.0
    elif case.get("early_exit_gate"):
        decision_acc = 1.0 if result.stop_reason == "EARLY_EXIT_GATE" and not routing_stage else 0.0
    elif expected:
        decision_acc = _recall(selected, expected)

    env = {
        "evidence": _envelope_preservation(result, "evidence"),
        "unknown": _envelope_preservation(result, "unknown"),
        "conflicts": _envelope_preservation(result, "conflicts"),
        **_value_version_provenance_kept(result),
    }
    return {
        "mode": mode,
        "stop_reason": result.stop_reason,
        "web_searches": result.web_searches,
        "complexity_steps": result.complexity_steps,
        "stage_names": [
            s["stage"] if isinstance(s, dict) else s.stage for s in result.stages
        ],
        "routing_stage_present": bool(routing_stage),
        "elapsed_ms": round(elapsed_ms, 3),
        "selected": selected,
        "recall": _recall(selected, expected),
        "suppression": _suppression(selected, irrelevant),
        "expected_hit": [f for f in expected if f in selected],
        "expected_miss": [f for f in expected if f not in selected],
        "irrelevant_leaked": [f for f in irrelevant if f in selected],
        "envelope": env,
        "conflict_preserved": conflict_ok if case.get("require_conflict_substr") else None,
        "unknown_reached": unknown_ok if case.get("require_unknown_facet") else None,
        "version_isolated": version_ok if case.get("version_isolation") else None,
        "false_inference": false_inf,
        "decision_accuracy": decision_acc,
        "reuse_assessment": result.reuse_assessment.get("mode") if result.reuse_assessment else "",
        "spec_has_slice_unknown": bool(
            result.spec_draft and (result.spec_draft.get("unknowns") or [])
        ),
        "llm_material_has_slice": "Relevant Research Slice" in (result.llm_material or ""),
        "failure_stage": _failure_stage(case, selected, result) if mode == "C" else "",
    }


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    modes: list[tuple[str, RoutingMode]] = [("A", "off"), ("B", "full"), ("C", "relevant")]
    scored: dict[str, Any] = {}
    for label, routing in modes:
        store = seeded_store()
        t0 = time.perf_counter()
        result = run_standard_workflow(
            case["requirement"],
            store=store,
            llm_enabled=False,
            facet_routing=routing,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        scored[label] = _score_mode(case, result, elapsed, label)
    return {
        "id": case["id"],
        "label": case["label"],
        "requirement": case["requirement"],
        "expected": case.get("expected") or [],
        "modes": scored,
        "planted_oss_tokens": bool(case.get("planted_oss_tokens")),
        "early_exit_gate": bool(case.get("early_exit_gate")),
        "k7": bool(case.get("k7")),
    }


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _agg(rows: list[dict[str, Any]], mode: str, key: str) -> float | None:
    return _mean([r["modes"][mode].get(key) for r in rows])


def _idea_preservation() -> dict[str, str]:
    return {
        "Cross-Facet Reasoning Core": "DEFER",
        "Relationship Graph Core": "REJECT",
        "Matrix / Knowledge Graph / RAG / Vector DB": "REJECT",
        "relevant_facet_router experimental adapter": "EXPERIMENTAL",
        "ResearchRecord.facet_records field": "REUSE",
        "DecisionFactor envelope for slice items": "REUSE",
        "note": "Facet-to-facet relationship graph still not implemented; alias + stored pull_with only.",
    }


def _adoption(metrics: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    m8 = next(r for r in rows if r["id"] == "M6-8")
    m7 = next(r for r in rows if r["id"] == "M6-7")
    k7 = next(r for r in rows if r["id"] == "M8-K7")
    json_not_inflated = (
        m8["modes"]["C"]["stop_reason"] == "EARLY_EXIT_GATE"
        and m8["modes"]["C"]["web_searches"] == 0
        and m8["modes"]["C"]["routing_stage_present"] is False
        and m8["modes"]["C"]["complexity_steps"] == m8["modes"]["A"]["complexity_steps"]
    )
    k7_c_ok = (
        len(k7["modes"]["C"]["expected_hit"]) >= 5
        and k7["modes"]["C"]["conflict_preserved"] is True
    )
    c_better_a = (metrics["relevant_recall_C"] or 0) > (metrics["relevant_recall_A"] or 0)
    c_better_b_sup = (metrics["irrelevant_suppression_C"] or 0) > (metrics["irrelevant_suppression_B"] or 0)
    mapping_gaps = [r["id"] for r in rows if r["modes"]["C"].get("failure_stage") == "Requirement → Facet Mapping不足"]
    m7_leak = m7["modes"]["C"]["irrelevant_leaked"]

    if c_better_a and k7_c_ok and json_not_inflated and not m7_leak and not mapping_gaps:
        decision = "ADOPT"
        why = "Mode C beats A on recall, keeps K-7 evidence, does not inflate JSON Gate, and suppresses OSS noise."
    elif c_better_a and k7_c_ok and json_not_inflated:
        decision = "EXPERIMENTAL_RETAIN"
        why = (
            "Mode C delivers the K-7 slice and does not complicate Gate-exit tools, "
            "but Facet Mapping / planted-token suppression is incomplete."
        )
    elif c_better_a:
        decision = "RECORD"
        why = "Routing helps recall but is not ready to be the default Standard Workflow path."
    else:
        decision = "DEFER"
        why = "Measured gain over existing Standard Workflow is not sufficient."

    return {
        "decision": decision,
        "why": why,
        "json_not_inflated": json_not_inflated,
        "k7_mode_c_min_facets_and_conflict": k7_c_ok,
        "mode_c_recall_beats_a": c_better_a,
        "mode_c_suppression_beats_b": c_better_b_sup,
        "m7_irrelevant_leaked": m7_leak,
        "mapping_gap_cases": mapping_gaps,
        "question": (
            "Requirementに応じてResearchの必要部分だけをDecision Supportへ届けることで、"
            "現在のStandard Workflowより実際に良くなるか？"
        ),
        "answer": (
            "Yes, on recall and K-7 evidence, without Gate-path complexity - "
            "with remaining alias/mapping limits."
            if decision in {"ADOPT", "EXPERIMENTAL_RETAIN"}
            else "Not as a Standard Workflow default yet."
        ),
    }


def run_phase_m() -> dict[str, Any]:
    audit = existing_workflow_audit()
    rows = [run_case(c) for c in CASES]
    core_rows = [r for r in rows if r["id"].startswith("M6-")]
    metrics = {
        "relevant_recall_A": _agg(core_rows, "A", "recall"),
        "relevant_recall_B": _agg(core_rows, "B", "recall"),
        "relevant_recall_C": _agg(core_rows, "C", "recall"),
        "irrelevant_suppression_A": _agg(core_rows, "A", "suppression"),
        "irrelevant_suppression_B": _agg(core_rows, "B", "suppression"),
        "irrelevant_suppression_C": _agg(core_rows, "C", "suppression"),
        "evidence_preservation_C": _mean([r["modes"]["C"]["envelope"]["evidence"] for r in core_rows]),
        "unknown_preservation_C": _mean([r["modes"]["C"]["envelope"]["unknown"] for r in core_rows]),
        "conflict_preservation_C": _mean([r["modes"]["C"]["envelope"]["conflicts"] for r in core_rows]),
        "mean_elapsed_ms_A": _agg(core_rows, "A", "elapsed_ms"),
        "mean_elapsed_ms_B": _agg(core_rows, "B", "elapsed_ms"),
        "mean_elapsed_ms_C": _agg(core_rows, "C", "elapsed_ms"),
        "mean_complexity_A": _agg(core_rows, "A", "complexity_steps"),
        "mean_complexity_B": _agg(core_rows, "B", "complexity_steps"),
        "mean_complexity_C": _agg(core_rows, "C", "complexity_steps"),
        "mean_web_A": _agg(core_rows, "A", "web_searches"),
        "mean_web_B": _agg(core_rows, "B", "web_searches"),
        "mean_web_C": _agg(core_rows, "C", "web_searches"),
        "decision_accuracy_A": _agg(core_rows, "A", "decision_accuracy"),
        "decision_accuracy_B": _agg(core_rows, "B", "decision_accuracy"),
        "decision_accuracy_C": _agg(core_rows, "C", "decision_accuracy"),
    }
    k7 = next(r for r in rows if r["id"] == "M8-K7")
    adoption = _adoption(metrics, rows)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "audit": audit,
        "metrics": metrics,
        "cases": rows,
        "k7": k7,
        "idea_preservation": _idea_preservation(),
        "adoption": adoption,
        "core_creation_gate": {
            "Reasoning_Matrix_Graph_Core": "REJECT",
            "relevant_facet_router": adoption["decision"],
            "StandardWorkflow_default_routing": "off",
        },
    }
