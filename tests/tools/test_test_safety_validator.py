"""S2 Test Safety Validator prototype."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from test_safety.validator import evaluate_test_plan, load_reference_case, validate_packet_schema

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "registry" / "schema" / "test_safety_evaluation.schema.json"
P2A = REPO / "tools" / "test_safety" / "reference_cases" / "p2a_development_policy_regression.json"


def test_schema_validates_minimal_packet():
    packet = evaluate_test_plan(
        {"plan_id": "x", "commands": ["python -m pytest tests/foo -q"]},
        repo_root=None,
    )
    validate_packet_schema(packet, SCHEMA)


def test_p2a_reference_case_packet():
    ref = load_reference_case(P2A)
    packet = evaluate_test_plan(
        ref["test_plan"],
        repo_root=REPO,
        host_process_notes=list(ref.get("host_process_notes") or []),
        reference_case_id=ref.get("reference_case_id"),
    )
    validate_packet_schema(packet, SCHEMA)
    ev = packet["evaluation"]
    assert ev["primary_risk_level"] == "LEVEL_2"
    assert ev["safety_dimensions"]["llm"] == "NONE"
    assert ev["recommended_gate_decision"] == "PASS"
    assert ev["human_approval_required"] is False
    assert ev["postflight_git_check_required"] is True
    assert packet["reference_case_id"] == "p2a_development_policy_regression"
    unknowns = ev.get("relevant_unknowns") or []
    assert not any(
        u.get("would_block_if_gate_connected") for u in unknowns if u.get("relevant_to_plan")
    )


def test_relevant_unknown_blocks_when_gate_would():
    packet = evaluate_test_plan(
        {
            "plan_id": "live",
            "commands": ["python run_live_e2e.py --ollama"],
            "declared_dimensions": {"llm": "UNKNOWN"},
        },
    )
    ev = packet["evaluation"]
    assert ev["primary_risk_level"] == "LEVEL_3"
    assert ev["recommended_gate_decision"] == "BLOCKED"
    assert ev["gate_blocked_reasons"]


def test_cli_p2a_emits_valid_json():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "run_test_safety_validator.py"), "--p2a", "--out", str(REPO / "reports" / "_tmp_test_safety_p2a.json")],
        cwd=str(REPO),
        env={**dict(__import__("os").environ), "PYTHONPATH": f"{REPO};{REPO / 'tools'}"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads((REPO / "reports" / "_tmp_test_safety_p2a.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)
