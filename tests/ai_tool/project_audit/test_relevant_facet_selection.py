"""Phase L — relevant facet selection (no new Core)."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.phase_l_relevant_facet_fixtures import CASES
from ai_tool.experimental.development_assistance.phase_l_relevant_facet_harness import (
    existing_structure_audit,
    run_phase_l,
    select_by_alias,
)
from ai_tool.experimental.development_assistance.research_reuse import extract_requirement_facets


def test_l1_existing_requirement_facets_are_oss_env_only():
    audit = existing_structure_audit()
    assert "control_authority" not in audit["requirement_facet_fields"]
    assert audit["requirement_facets_select_robot_ids"] is False
    assert audit["facet_records_on_dataclass"] is True
    rf = extract_requirement_facets("人間がPolyScopeから操作を再開できるか")
    assert rf.python == ""
    assert rf.cuda == ""
    assert "control_authority" not in rf.technologies


def test_l3_mode_c_suppresses_python_cuda():
    selected = {x["facet_id"] for x in select_by_alias("人間がPolyScopeから操作を再開できるか")}
    assert "python_version" not in selected
    assert "cuda" not in selected
    assert "license" not in selected
    assert "human_handoff" in selected


def test_l4_requirements_change_selected_set():
    a = {x["facet_id"] for x in select_by_alias(CASES[2]["requirement"])}
    b = {x["facet_id"] for x in select_by_alias(CASES[3]["requirement"])}
    c = {x["facet_id"] for x in select_by_alias(CASES[4]["requirement"])}
    assert "transport" in a
    assert "urscript_api" in b
    assert "docker" in c or "ursim" in c
    assert a != b
    assert b != c


def test_l6_unknown_reaches_decision_factor():
    result = run_phase_l()
    l6 = next(r for r in result["cases"] if r["id"] == "L6")
    assert l6["unknown_routed"]
    assert all(u["status"] == "unknown" for u in l6["unknown_routed"])


def test_l9_and_gate_no_new_core():
    result = run_phase_l()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["core_creation_gate"]["Reasoning_Matrix_Graph_Core"] == "REJECT"
    l9 = next(r for r in result["cases"] if r["id"] == "L9")
    assert "transport" in l9["mode_c"]["selected"]
    assert "human_handoff" in l9["mode_c"]["selected"]
    assert l9["k9_handoff_conflict_reached"] is True
    assert (result["metrics"]["relevant_recall_mode_c"] or 0) > (
        result["metrics"]["relevant_recall_mode_a"] or 0
    )
