"""S3 Shadow Gate — synthetic packets only; no live LLM/GPU/network/git mutation."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from test_safety.comparison import MISMATCH_NONE, build_comparison_evidence
from test_safety.shadow_gate import (
    INVALID_GATE_REASON,
    decide_gate_from_evaluation,
    evaluate_shadow_gate,
    validate_shadow_gate_schema,
)
from test_safety.validator import evaluate_test_plan, load_reference_case, validate_packet_schema

REPO = Path(__file__).resolve().parents[2]
EVAL_SCHEMA = REPO / "registry" / "schema" / "test_safety_evaluation.schema.json"
GATE_SCHEMA = REPO / "registry" / "schema" / "test_safety_shadow_gate.schema.json"
REF_DIR = REPO / "tools" / "test_safety" / "reference_cases"

REFERENCE_IDS = (
    "p2a_development_policy_regression",
    "pure_unit",
    "relevant_unknown_gpu",
    "irrelevant_unknown_ollama",
    "intentional_repo_write",
    "external_uncontrolled",
)


def _preflight_s3_tests() -> None:
    packet = evaluate_test_plan(
        {
            "plan_id": "s3_test_preflight",
            "commands": ["python -m pytest tests/tools/test_test_safety_shadow_gate.py -q"],
            "declared_primary_risk_level": "LEVEL_1",
            "declared_dimensions": {
                "llm": "NONE",
                "gpu": "NONE",
                "network": "NONE",
                "git_operation": "NONE",
            },
        },
        repo_root=None,
    )
    gate = evaluate_shadow_gate(packet, schema_path=EVAL_SCHEMA)
    assert gate["gate_decision"] == "PASS"
    assert gate["execution_authoritative"] is False


@pytest.fixture(scope="module", autouse=True)
def _module_preflight():
    _preflight_s3_tests()


def _run_reference(case_id: str) -> dict:
    ref_path = REF_DIR / f"{case_id}.json"
    if case_id == "p2a_development_policy_regression":
        ref_path = REF_DIR / "p2a_development_policy_regression.json"
    ref = load_reference_case(ref_path)
    packet = evaluate_test_plan(
        ref["test_plan"],
        repo_root=REPO if case_id.startswith("p2a") else None,
        host_process_notes=list(ref.get("host_process_notes") or []),
        reference_case_id=ref.get("reference_case_id"),
    )
    validate_packet_schema(packet, EVAL_SCHEMA)
    gate = evaluate_shadow_gate(packet, schema_path=EVAL_SCHEMA)
    validate_shadow_gate_schema(gate, GATE_SCHEMA)
    return build_comparison_evidence(
        reference_case_id=str(ref["reference_case_id"]),
        validator_result=packet,
        shadow_gate_packet=gate,
        expectation=dict(ref.get("expectation") or {}),
    )


@pytest.mark.parametrize("case_id", REFERENCE_IDS)
def test_reference_case_shadow_matches_human(case_id: str):
    evidence = _run_reference(case_id)
    assert evidence["mismatch"] == MISMATCH_NONE
    assert evidence["match"] is True
    assert evidence["shadow_gate_decision"] == evidence["expected_shadow_gate_decision"]
    gate = evidence["shadow_gate_packet"]
    assert gate["shadow_mode"] is True
    assert gate["execution_authoritative"] is False
    assert gate["gate_decision"] in ("PASS", "BLOCKED")


def test_relevant_unknown_does_not_pass():
    ev = {
        "primary_risk_level": "LEVEL_2",
        "safety_dimensions": {"gpu": "UNKNOWN", "llm": "NONE", "network": "NONE"},
        "relevant_unknowns": [
            {
                "dimension": "gpu",
                "observation": "dimension_state=UNKNOWN",
                "relevant_to_plan": True,
                "safety_verifiable": False,
            }
        ],
        "warnings": [],
    }
    decision, blocked, _, _, _ = decide_gate_from_evaluation(ev)
    assert decision == "BLOCKED"
    assert blocked


def test_prohibited_side_effect_does_not_pass():
    ev = {
        "primary_risk_level": "LEVEL_1",
        "safety_dimensions": {"credentials": "PRESENT", "llm": "NONE"},
        "relevant_unknowns": [],
        "warnings": [],
    }
    decision, blocked, _, _, _ = decide_gate_from_evaluation(ev)
    assert decision == "BLOCKED"
    assert any("credentials" in b for b in blocked)


def test_irrelevant_unknown_does_not_block():
    ev = {
        "primary_risk_level": "LEVEL_1",
        "safety_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
        "relevant_unknowns": [
            {
                "dimension": "long_running_process",
                "observation": "ollama on host",
                "relevant_to_plan": False,
                "safety_verifiable": False,
            }
        ],
        "warnings": [],
    }
    decision, blocked, warnings, _, _ = decide_gate_from_evaluation(ev)
    assert decision == "PASS"
    assert not blocked
    assert warnings


def test_warnings_alone_do_not_block():
    ev = {
        "primary_risk_level": "LEVEL_2",
        "safety_dimensions": {"filesystem_write": "PRESENT", "llm": "NONE"},
        "relevant_unknowns": [],
        "warnings": ["declared_write_scope:repo"],
    }
    decision, blocked, _, _, _ = decide_gate_from_evaluation(ev)
    assert decision == "PASS"
    assert not blocked


def test_l1_controlled_not_false_blocked():
    ev = {
        "primary_risk_level": "LEVEL_1",
        "safety_dimensions": {
            "llm": "NONE",
            "gpu": "NONE",
            "network": "NONE",
            "subprocess": "CONTROLLED",
        },
        "relevant_unknowns": [],
        "warnings": [],
    }
    decision, blocked, _, _, _ = decide_gate_from_evaluation(ev)
    assert decision == "PASS"
    assert not blocked


def test_invalid_packet_fail_safe_blocked():
    gate = evaluate_shadow_gate(None, schema_path=EVAL_SCHEMA)
    validate_shadow_gate_schema(gate, GATE_SCHEMA)
    assert gate["gate_decision"] == "BLOCKED"
    assert gate["gate_reason"] == INVALID_GATE_REASON
    assert gate["execution_authoritative"] is False


def test_malformed_packet_not_unconditional_pass():
    gate = evaluate_shadow_gate({"packet_type": "WRONG", "schema_version": "1"}, schema_path=EVAL_SCHEMA)
    assert gate["gate_decision"] == "BLOCKED"


def test_postflight_carried_to_gate_packet():
    ref = load_reference_case(REF_DIR / "intentional_repo_write.json")
    packet = evaluate_test_plan(ref["test_plan"], reference_case_id=ref["reference_case_id"])
    gate = evaluate_shadow_gate(packet, schema_path=EVAL_SCHEMA)
    assert gate["required_postflight"]["postflight_git_check_required"] is True


def test_cli_all_references_json_schema():
    import subprocess
    import sys

    out = REPO / "reports" / "_tmp_shadow_all_refs.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "run_test_safety_shadow_gate.py"),
            "--all-references",
            "--out",
            str(out),
        ],
        cwd=str(REPO),
        env={**dict(__import__("os").environ), "PYTHONPATH": f"{REPO};{REPO / 'tools'}"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    gate_schema = json.loads(GATE_SCHEMA.read_text(encoding="utf-8"))
    for row in data["reference_evidence"]:
        jsonschema.Draft202012Validator(gate_schema).validate(row["shadow_gate_packet"])
