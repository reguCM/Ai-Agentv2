"""Web Tool Practical Evaluation Phase 1 — artifact and constraint checks."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DOC = REPO / "docs" / "ai_tool/project_audit/WEB_TOOL_PRACTICAL_EVALUATION.md"


def test_evaluation_module_defines_cases_a_through_g() -> None:
    from ai_tool.web_tool_practical_evaluation import EVAL_CASES

    ids = {c.case_id for c in EVAL_CASES}
    assert ids == {"A", "B", "C", "D", "E", "F", "G"}


def test_deterministic_lane_runs_without_network() -> None:
    from ai_tool.web_tool_practical_evaluation import EVAL_CASES, run_deterministic_practical_case

    result = run_deterministic_practical_case(EVAL_CASES[0])
    assert result["mode"] == "deterministic_mock"
    assert result["search_web_calls"] >= 1
    assert result["overall"] in ("PASS", "PARTIAL", "FAIL", "UNKNOWN")


def test_run_script_exists() -> None:
    assert (REPO / "ai_tool/run_web_tool_practical_evaluation.py").is_file()


def test_evaluation_doc_exists_after_run() -> None:
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert "Practical Evaluation Phase 1" in text
    assert "NOT EXECUTED" in text or "commit" in text.lower()


def test_registry_unchanged_web_tools_present() -> None:
    reg = json.loads((REPO / "registry/tools.json").read_text(encoding="utf-8"))
    names = {t["name"] for t in reg["tools"] if t.get("visibility") == "agent"}
    assert "search_web" in names
    assert "read_url_text" in names


def test_production_bridge_no_read_url_overlay() -> None:
    from ai_tool.agent_integration.production_bridge import get_experimental_agent_exposure

    exp = get_experimental_agent_exposure()
    assert exp.enabled is False


def test_latest_run_artifacts_exist() -> None:
    runs = sorted((REPO / "runs/ai_tool").glob("*_web_tool_practical_evaluation"))
    assert runs, "run directory missing — execute run_web_tool_practical_evaluation.py"
    latest = runs[-1]
    assert (latest / "evaluation.json").is_file()
