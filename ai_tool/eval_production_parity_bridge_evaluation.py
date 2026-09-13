"""CC-01 Eval Production Parity Bridge — evaluation harness and integrity checks."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.agent_integration.eval_production_parity_bridge import (
    PATH_CANONICAL,
    PATH_DIAGNOSTIC_DIRECT,
    compare_path_divergence,
    defensive_core_policy,
    run_canonical_web_eval,
    run_diagnostic_direct_eval,
    validate_stop_decision_integrity,
)
from ai_tool.agent_integration.trial import make_mock_chat_fn
from ai_tool.agent_integration.trial_scenarios import TrialScenario
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[1]


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def run_path_separation_verification() -> dict[str, Any]:
    """Verify canonical vs diagnostic paths differ and metadata is distinct."""
    divergence = compare_path_divergence()
    canonical = divergence["canonical"]
    diagnostic = divergence["diagnostic"]

    checks = {
        "canonical_production_equivalent": canonical["production_equivalent"] is True,
        "diagnostic_not_production_equivalent": diagnostic["production_equivalent"] is False,
        "canonical_has_boundary": canonical["boundary_applied"] is True,
        "diagnostic_no_boundary": diagnostic["boundary_applied"] is False,
        "canonical_has_tracker": canonical["web_session_tracker"] is True,
        "diagnostic_no_tracker": diagnostic["web_session_tracker"] is False,
        "paths_distinct": canonical["path_label"] != diagnostic["path_label"],
        "gap_confirmed": divergence["gap_confirmed"],
        "mock_pass_not_production_pass": divergence["mock_pass_implies_production_pass"] is False,
    }
    return {
        "divergence": divergence,
        "checks": checks,
        "pass": all(checks.values()),
    }


def run_stop_decision_integrity() -> dict[str, Any]:
    """Mock path must not authorize Production STOP decisions."""
    _, diag_meta = run_diagnostic_direct_eval("search_web", {"query": "nonsense"})
    _, canon_meta = run_canonical_web_eval(
        "probe",
        chat_fn=make_mock_chat_fn(
            TrialScenario(
                scenario_id="stop_integrity",
                user_request="probe",
                expected_tool="search_web",
                routing_note="stop integrity",
                mock_tool_calls=[{"name": "search_web", "arguments": {"query": "q"}}],
                mock_final_answer="ok",
            )
        ),
        model="mock",
        search_web_fn=lambda **_kw: {"ok": True, "hits": [], "backends_tried": ["fixture"]},
        max_rounds=2,
    )

    cases = [
        validate_stop_decision_integrity(decision="STOP_NO_CHANGE", path_meta=diag_meta),
        validate_stop_decision_integrity(decision="STOP_D", path_meta=diag_meta),
        validate_stop_decision_integrity(decision="STOP_NO_CHANGE", path_meta=canon_meta),
        validate_stop_decision_integrity(decision="DIAGNOSTIC_OBSERVATION", path_meta=diag_meta),
    ]
    return {
        "cases": cases,
        "pass": cases[0]["allowed"] is False
        and cases[1]["allowed"] is False
        and cases[2]["allowed"] is True
        and cases[3]["allowed"] is True,
    }


def run_production_equivalent_smoke() -> dict[str, Any]:
    """Canonical path applies boundary on empty-search numeric hallucination."""

    def _empty_search(**_kw: Any) -> dict[str, Any]:
        return {"ok": True, "hits": [], "error": "empty", "backends_tried": ["fixture"]}

    scenario = TrialScenario(
        scenario_id="canonical_smoke",
        user_request="大阪市の人口",
        expected_tool="search_web",
        routing_note="empty search boundary smoke",
        mock_tool_calls=[{"name": "search_web", "arguments": {"query": "大阪市 人口"}}],
        mock_final_answer="人口は275万人です。",
    )
    loop, meta = run_canonical_web_eval(
        "大阪市の人口",
        chat_fn=make_mock_chat_fn(scenario),
        model="mock",
        search_web_fn=_empty_search,
        read_url_text_fn=read_url_text,
        max_rounds=2,
    )
    suppressed = "275" not in (loop.final_answer or "")
    return {
        "path_label": meta.path_label,
        "production_equivalent": meta.production_equivalent,
        "boundary_applied": loop.boundary_applied,
        "numeric_suppressed": suppressed,
        "web_status": (loop.web_session_aggregate or {}).get("overall"),
        "pass": meta.production_equivalent and loop.boundary_applied and suppressed,
    }


def discover_future_capabilities() -> list[dict[str, Any]]:
    """Post CC-01 — remaining candidates (max 3)."""
    return [
        {
            "id": "CC-03",
            "name": "Capability Lifecycle Registry",
            "classification": "C1",
            "summary": "Machine-readable experimental capability inventory with sunset tracking.",
            "rationale": "CC-01 implemented; registry still valuable as harness count grows.",
        },
        {
            "id": "CC-02",
            "name": "Verification Metadata Envelope",
            "classification": "C3",
            "summary": "Retain mechanical_verification; observation-only.",
            "rationale": "Already experimental; no Production connection.",
        },
    ]


def run_eval_production_parity_bridge_evaluation(*, fetch_live_baseline: bool = True) -> dict[str, Any]:
    head = _git_head()
    golden = run_production_golden(fetch_live=fetch_live_baseline)
    separation = run_path_separation_verification()
    stop_integrity = run_stop_decision_integrity()
    canonical_smoke = run_production_equivalent_smoke()
    policy = defensive_core_policy()
    candidates = discover_future_capabilities()

    integrity_pass = separation["pass"] and stop_integrity["pass"] and canonical_smoke["pass"]
    golden_pass = golden.get("overall") == "PASS"

    decisions: list[str] = []
    if golden_pass and integrity_pass:
        decisions.append("STOP_NO_CHANGE")  # Production unchanged
    decisions.append("EXPERIMENTAL_CAPABILITY")  # CC-01 bridge deployed
    decisions.append("RECORD_FUTURE_CAPABILITIES")  # CC-03
    if not golden_pass:
        decisions.append("HUMAN_REVIEW_REQUIRED")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": head,
        "final_head": head,
        "overall": "PASS" if golden_pass and integrity_pass else "PARTIAL",
        "cc01_implemented": True,
        "production_changes": [],
        "registry_changes": [],
        "agent_changes": [],
        "prompt_changes": [],
        "eval_canonical_path": {
            "policy": "SCR-01 adopted (harness level)",
            "canonical_labels": [PATH_CANONICAL, "production_mirror"],
            "diagnostic_label": PATH_DIAGNOSTIC_DIRECT,
            "bridge_module": "ai_tool/agent_integration/eval_production_parity_bridge.py",
        },
        "path_separation": separation,
        "stop_decision_integrity": stop_integrity,
        "canonical_smoke": canonical_smoke,
        "golden_baseline": {
            "overall": golden.get("overall"),
            "pass_count": golden.get("pass_count"),
            "total": golden.get("total"),
        },
        "defensive_core_policy": policy,
        "future_capabilities": candidates,
        "decisions": decisions,
        "human_review_required": not golden_pass,
        "next_phase_candidates": [
            "Migrate phase1/2/3 eval-direct harnesses to run_canonical_web_eval",
            "CC-03 Capability Lifecycle Registry (C1) when active experimental > 3",
        ],
        "stop_reason": None if integrity_pass else "path separation or STOP integrity failed",
    }
