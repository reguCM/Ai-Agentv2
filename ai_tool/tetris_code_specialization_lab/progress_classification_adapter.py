"""Thin adapters from Tetris lab / production replay artifacts to Progress Classification v0."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ai_tool.chat_interface.progress_classification_v0 import (
    ProgressClassificationV0,
    ProgressStateSnapshot,
    classify_progress_transition,
)


def _failure_signature_from_eval(evaluation: Mapping[str, Any]) -> str | None:
    runnable = evaluation.get("runnable_check") or {}
    stderr = str(runnable.get("stderr") or "").strip()
    if stderr:
        lines = [line.strip() for line in stderr.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    for condition in evaluation.get("conditions") or []:
        if not condition.get("passed"):
            fact = str(condition.get("fact") or "").strip()
            if fact:
                return fact.splitlines()[-1]
    exception_message = evaluation.get("exception_message")
    if exception_message:
        return str(exception_message).strip()
    return None


def _feature_unit_maps(
    evaluation: Mapping[str, Any],
) -> tuple[dict[str, bool], dict[str, bool]]:
    passed_map: dict[str, bool] = {}
    observable_map: dict[str, bool] = {}
    for item in evaluation.get("feature_units") or []:
        unit_id = str(item.get("unit_id") or "")
        if not unit_id:
            continue
        passed_map[unit_id] = bool(item.get("passed"))
        fact = str(item.get("fact") or "")
        observable_map[unit_id] = not (
            "errors=1" in fact and "passed=0 failed=0" in fact
        )
    return passed_map, observable_map


def snapshot_from_tetris_evaluation(
    evaluation: Mapping[str, Any],
) -> ProgressStateSnapshot:
    passed_map, observable_map = _feature_unit_maps(evaluation)
    runnable = evaluation.get("runnable_check") or {}
    return ProgressStateSnapshot(
        completion_ratio=evaluation.get("completion_ratio"),
        requirements_passed=evaluation.get("requirements_passed"),
        requirements_total=evaluation.get("requirements_total"),
        pytest_passed=int(evaluation.get("pytest_passed") or 0),
        pytest_failed=int(evaluation.get("pytest_failed") or 0),
        pytest_blocked=int(evaluation.get("pytest_blocked") or 0),
        pytest_canonical_total=int(evaluation.get("pytest_canonical_total") or 0),
        feature_units_passed=passed_map,
        feature_units_observable=observable_map,
        runnable_ok=bool(runnable.get("ok")),
        playable=bool(evaluation.get("playable")),
        failure_signature=_failure_signature_from_eval(evaluation),
    )


def snapshot_from_case001_canonical(
    canonical: Mapping[str, Any],
) -> ProgressStateSnapshot:
    passed_ids = [
        str(item.get("condition_id"))
        for item in (canonical.get("conditions") or [])
        if item.get("passed")
    ]
    failed_ids = [str(item) for item in (canonical.get("failed_condition_ids") or [])]
    signature = canonical.get("exception_message") or canonical.get("exception_type")
    return ProgressStateSnapshot(
        completion_ratio=canonical.get("completion_ratio"),
        requirements_passed=canonical.get("passed_count"),
        requirements_total=canonical.get("total_count"),
        passed_condition_ids=passed_ids,
        failed_condition_ids=failed_ids,
        failure_signature=str(signature).strip() if signature else None,
    )


def snapshot_from_production_replay_summary(
    summary: Mapping[str, Any],
) -> ProgressStateSnapshot:
    turn = dict(summary.get("run_chat_turn_summary") or {})
    runtime = dict(turn.get("runtime_status_report") or {})
    gap = dict(turn.get("gap_resolution") or {})
    observation = dict(summary.get("observation") or {})
    return ProgressStateSnapshot(
        gap_kind=str(gap.get("gap_kind") or ""),
        gap_resolved=bool(gap.get("gap_resolved")),
        evidence_count=int(runtime.get("evidence_count") or 0),
    )


def classify_lab_steps(
    steps: list[Mapping[str, Any]],
    *,
    evaluation_key: str = "evaluation",
) -> list[ProgressClassificationV0]:
    """Classify each step against its predecessor (lab cycles / attempts)."""
    results: list[ProgressClassificationV0] = []
    prior: ProgressStateSnapshot | None = None
    for step in steps:
        payload = step.get(evaluation_key) or step.get("canonical") or {}
        current = (
            snapshot_from_tetris_evaluation(payload)
            if evaluation_key == "evaluation"
            else snapshot_from_case001_canonical(payload)
        )
        results.append(classify_progress_transition(prior, current))
        prior = current
    return results


def classify_summary_worker_steps(
    summary_path: str | Path,
    *,
    worker_id: str,
    evaluation_key: str = "evaluation",
) -> list[ProgressClassificationV0]:
    data = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    worker = (data.get("workers") or {}).get(worker_id) or {}
    steps = worker.get("cycles") or worker.get("attempts") or []
    return classify_lab_steps(steps, evaluation_key=evaluation_key)
