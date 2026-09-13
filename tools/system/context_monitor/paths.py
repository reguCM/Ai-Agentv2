"""Context Monitor 保存パス。"""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
MONITOR_DIR = _REPO_ROOT / "runs" / "ai_tool" / "context_monitor"
OBSERVATIONS_JSONL = MONITOR_DIR / "observations.jsonl"
SUMMARY_JSON = MONITOR_DIR / "summary.json"
RECALIBRATION_JSON = MONITOR_DIR / "recalibration_status.json"
DASHBOARD_HTML = MONITOR_DIR / "dashboard.html"
LEGACY_MANIFEST_JSON = MONITOR_DIR / "legacy_import_manifest.json"
POLICY_JSON = Path(__file__).resolve().parent / "recalibration_policy.json"
RECOVERY_POLICY_JSON = Path(__file__).resolve().parent / "recovery_policy.json"
RECOVERY_DECISIONS_JSONL = MONITOR_DIR / "recovery_decisions.jsonl"
RECOVERY_RESULTS_JSONL = MONITOR_DIR / "recovery_results.jsonl"
RECOVERY_EXPERIENCE_JSONL = MONITOR_DIR / "recovery_experience.jsonl"
AGENT_RECOVERY_EVALUATIONS_JSONL = MONITOR_DIR / "agent_recovery_evaluations.jsonl"
HARNESS_RUNS_DIR = _REPO_ROOT / "runs" / "ai_tool"


def ensure_monitor_dir() -> Path:
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    return MONITOR_DIR
