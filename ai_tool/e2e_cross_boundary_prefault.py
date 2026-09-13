"""Cross-boundary failure prediction experiment (E2E preflight v0).

Runs before Tetris full E2E: local LLM investigates code/mapping/changes and
emits frozen boundary predictions. After E2E, compares without mutating predictions.
Does not modify Production code based on predictions alone.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ai_tool.dev_skill_pipeline import composition_steps, load_registry
from ai_tool.llm_json_parse import LLMEmptyResponseError, llm_response_diagnostics, message_content
from tools.system.llm import chat as llm_chat

REPO_ROOT = Path(__file__).resolve().parents[1]
INVESTIGATION_FILENAME = "prefault_investigation.json"
PREFAULT_FILENAME = "cross_boundary_prefault.json"
COMPARISON_FILENAME = "cross_boundary_prefault_comparison.json"
PRECONDITION_EVALUATION_FILENAME = "precondition_evaluation.json"

PREDICTION_FIELDS = (
    "prediction_id",
    "boundary",
    "invariant",
    "failure_hypothesis",
    "evidence",
    "suggested_test",
    "confidence",
)

GRADE_VALUES = frozenset(
    {"EXACT_HIT", "BOUNDARY_HIT", "INVARIANT_HIT", "RELATED", "MISS"}
)

KNOWN_ISSUES = [
    {
        "known_issue_id": "tech_spec_empty_response",
        "title": "tech-spec LLM empty response / JSONDecodeError",
        "observation_markers": (
            "empty response",
            "llmemptyresponseerror",
            "jsondecodeerror",
            "expecting value",
            "tech-spec",
            "tech_spec",
        ),
        "prediction_markers": (
            "empty",
            "jsondecode",
            "tech-spec",
            "tech_spec",
            "thinking",
            "num_predict",
            "message.content",
        ),
    },
    {
        "known_issue_id": "task_id_t0_duplicate",
        "title": "task ID T0 normalization duplicate",
        "observation_markers": (
            "non-unique",
            "'t0'",
            "t0",
            "task_ids_unique",
            "duplicate",
        ),
        "prediction_markers": (
            "t0",
            "duplicate",
            "task id",
            "task_id",
            "unique",
            "normalize",
            "implementation_tasks",
        ),
    },
]

CROSS_CUTTING_CHECKLIST = [
    "0件 / 1件 / 複数件",
    "新規状態 / restore済み状態",
    "同一Execution / 跨Execution",
    "ID / ref / provenance",
    "session → runtime → persistence",
    "ProducerとConsumerのschema差",
    "全件処理か先頭1件だけか",
    "stale state",
    "resume後の再接続",
]

KNOWN_BOUNDARIES = [
    {
        "boundary": "phase1_grill-me → write-prd",
        "producer": "grill_me_loop / aligned_spec",
        "consumer": "dev_skill_pipeline._generate_prd",
        "paths": ["ai_tool/grill_me_loop.py", "ai_tool/dev_skill_pipeline.py"],
    },
    {
        "boundary": "write-prd → tech-spec",
        "producer": "prd JSON artifact",
        "consumer": "dev_skill_pipeline._generate_tech_spec",
        "paths": ["ai_tool/dev_skill_pipeline.py"],
    },
    {
        "boundary": "tech-spec → planning-and-task-breakdown",
        "producer": "tech_spec JSON",
        "consumer": "dev_skill_pipeline._generate_plan",
        "paths": ["ai_tool/dev_skill_pipeline.py"],
    },
    {
        "boundary": "planning-and-task-breakdown → goal-handoff",
        "producer": "plan.tasks",
        "consumer": "build_handoff_packet / normalize_implementation_tasks",
        "paths": ["ai_tool/dev_skill_pipeline.py", "registry/schema/goal_handoff.schema.json"],
    },
    {
        "boundary": "goal-handoff → production_chat",
        "producer": "handoff / implementation_prompt",
        "consumer": "agent_turn.run_chat_turn",
        "paths": ["ai_tool/dev_skill_pipeline.py", "ai_tool/chat_interface/agent_turn.py"],
    },
    {
        "boundary": "production_chat → sandbox tools",
        "producer": "task_orchestration / capability bridge",
        "consumer": "create_file / list_files in sandbox",
        "paths": [
            "ai_tool/chat_interface/task_orchestration.py",
            "ai_tool/chat_interface/agent_turn.py",
        ],
    },
    {
        "boundary": "mission_memory evidence_refs (跨Execution)",
        "producer": "chat_persist / boundary_grill",
        "consumer": "mission_memory.store.put_execution",
        "paths": ["ai_tool/mission_memory/chat_persist.py", "ai_tool/mission_memory/store.py"],
    },
    {
        "boundary": "goal_continuation resume",
        "producer": "goal_continuation_resume packet",
        "consumer": "agent_turn restore orchestrator",
        "paths": [
            "ai_tool/chat_interface/goal_continuation_resume.py",
            "ai_tool/chat_interface/agent_turn.py",
        ],
    },
    {
        "boundary": "session → runtime → persistence",
        "producer": "chat_session",
        "consumer": "mission_memory / local_state",
        "paths": [
            "ai_tool/chat_interface/chat_session.py",
            "ai_tool/mission_memory/store.py",
        ],
    },
]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=cwd,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _read_snippet(path: Path, *, max_chars: int = 2400) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars]


def collect_investigation_bundle(
    *,
    composition_id: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or REPO_ROOT
    registry = load_registry()
    steps = composition_steps(composition_id, registry)
    changed_files = [
        line.strip()
        for line in _run_git(["diff", "--name-only", "HEAD"], root).splitlines()
        if line.strip()
    ]
    untracked = [
        line.strip()
        for line in _run_git(["ls-files", "--others", "--exclude-standard"], root).splitlines()
        if line.strip()
    ]
    recent_commits = _run_git(["log", "-8", "--oneline", "--no-decorate"], root)
    diff_stat = _run_git(["diff", "--stat", "HEAD"], root)
    head = _run_git(["rev-parse", "HEAD"], root)
    branch = _run_git(["branch", "--show-current"], root)

    snippets: dict[str, str] = {}
    snippet_paths = sorted(
        {
            path
            for row in KNOWN_BOUNDARIES
            for path in row.get("paths") or []
        }
    )
    for rel in snippet_paths:
        snippets[rel] = _read_snippet(root / rel)

    focus_paths = changed_files[:20] + [
        p for p in untracked if p.startswith("ai_tool/") and p.endswith(".py")
    ][:15]
    recent_snippets = {
        rel: _read_snippet(root / rel, max_chars=1200)
        for rel in dict.fromkeys(focus_paths)
        if (root / rel).is_file()
    }

    return {
        "generated_at": _utc_stamp(),
        "repo_root": str(root),
        "git": {
            "branch": branch,
            "head": head,
            "recent_commits": recent_commits,
            "diff_stat": diff_stat,
            "changed_files": changed_files,
            "untracked_py_sample": [p for p in untracked if p.endswith(".py")][:30],
        },
        "composition": {
            "composition_id": composition_id,
            "skill_steps": steps,
        },
        "known_boundaries": KNOWN_BOUNDARIES,
        "cross_cutting_checklist": CROSS_CUTTING_CHECKLIST,
        "code_snippets": snippets,
        "recent_change_snippets": recent_snippets,
    }


def _prediction_rows_from_payload(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in (
        "predictions",
        "failure_risk_predictions",
        "failure_predictions",
        "risks",
        "items",
    ):
        rows = payload.get(key)
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, Mapping)]
    return []


def _normalize_predictions(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, Mapping):
        rows = _prediction_rows_from_payload(raw)
    elif isinstance(raw, list):
        rows = [row for row in raw if isinstance(row, Mapping)]
    else:
        return []
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:10], 1):
        prediction_id = str(row.get("prediction_id") or row.get("id") or f"P{index:02d}")
        boundary = str(
            row.get("boundary")
            or row.get("producer_consumer_boundary")
            or row.get("boundary_name")
            or ""
        ).strip()
        invariant = str(
            row.get("invariant")
            or row.get("risk_type")
            or row.get("invariant_at_risk")
            or ""
        ).strip()
        failure_hypothesis = str(
            row.get("failure_hypothesis")
            or row.get("description")
            or row.get("hypothesis")
            or row.get("failure_mode")
            or ""
        ).strip()
        evidence = str(
            row.get("evidence")
            or row.get("evidence_paths")
            or row.get("source_paths")
            or ""
        ).strip()
        suggested_test = str(
            row.get("suggested_test")
            or row.get("test")
            or row.get("verification")
            or ""
        ).strip()
        item = {
            "prediction_id": prediction_id,
            "boundary": boundary,
            "invariant": invariant,
            "failure_hypothesis": failure_hypothesis,
            "evidence": evidence,
            "suggested_test": suggested_test,
            "confidence": str(row.get("confidence") or "medium").strip().lower(),
        }
        if item["failure_hypothesis"] and (item["boundary"] or item["invariant"]):
            out.append(item)
    return out


def _error_matches_known_issue(error: str) -> str | None:
    lowered = str(error).casefold()
    for row in KNOWN_ISSUES:
        markers = row.get("observation_markers") or ()
        if any(str(marker).casefold() in lowered for marker in markers):
            return str(row["known_issue_id"])
    return None


def _has_novel_failures(observation: Mapping[str, Any]) -> bool:
    errors = [str(item) for item in (observation.get("errors") or [])]
    step_status = observation.get("step_status") or {}
    step_errors = [skill for skill, status in step_status.items() if status == "error"]
    if not errors and not step_errors:
        return False
    for error in errors:
        if _error_matches_known_issue(error) is None:
            return True
    if step_errors:
        blob = json.dumps(observation, ensure_ascii=False).casefold()
        for skill in step_errors:
            skill_blob = skill.casefold()
            matched = False
            for row in KNOWN_ISSUES:
                if skill_blob in blob and any(
                    str(marker).casefold() in blob for marker in (row.get("observation_markers") or ())
                ):
                    matched = True
                    break
            if not matched:
                return True
    return False


def _detect_observation_known_issues(observation: Mapping[str, Any]) -> list[str]:
    blob = json.dumps(observation, ensure_ascii=False).casefold()
    error_blob = " ".join(str(item) for item in (observation.get("errors") or [])).casefold()
    combined = f"{blob} {error_blob}"
    found: list[str] = []
    for row in KNOWN_ISSUES:
        markers = row.get("observation_markers") or ()
        if any(str(marker).casefold() in combined for marker in markers):
            found.append(str(row["known_issue_id"]))
    return sorted(dict.fromkeys(found))


def _prediction_known_issue_id(prediction: Mapping[str, Any]) -> str | None:
    blob = " ".join(
        str(prediction.get(key) or "")
        for key in ("boundary", "invariant", "failure_hypothesis", "evidence", "suggested_test")
    ).casefold()
    for row in KNOWN_ISSUES:
        markers = row.get("prediction_markers") or ()
        if any(str(marker).casefold() in blob for marker in markers):
            return str(row["known_issue_id"])
    return None


def run_cross_boundary_prefault(
    *,
    run_dir: Path,
    model: str,
    composition_id: str = "tetris-sandbox-e2e",
    chat_fn: Any | None = None,
    preconditions: list[dict[str, Any]] | None = None,
    precondition_evaluation: Mapping[str, Any] | None = None,
    handoff_packet: Mapping[str, Any] | None = None,
    execution_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Investigate with local LLM and freeze up to 10 boundary predictions before E2E.

    Evaluated preconditions are read-only inputs. The LLM must NOT set or override
    precondition evaluation.status (prediction ≠ precondition evaluation).
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    investigation = collect_investigation_bundle(composition_id=composition_id)
    if preconditions is not None:
        investigation["evaluated_preconditions"] = preconditions
    if execution_context is not None:
        investigation["execution_context"] = dict(execution_context)
    if handoff_packet is not None:
        investigation["handoff_packet_summary"] = {
            "handoff_id": handoff_packet.get("handoff_id"),
            "status": handoff_packet.get("status"),
            "implementation_task_ids": [
                row.get("id")
                for row in (handoff_packet.get("implementation_tasks") or [])
                if isinstance(row, Mapping)
            ],
            "documents": ((handoff_packet.get("source") or {}).get("documents") or {}),
        }
    investigation["preflight_policy"] = {
        "prediction_does_not_set_precondition_status": True,
        "execution_context_not_equal_precondition": True,
        "unknown_preconditions_remain_unknown": True,
        "known_issues_catalog": [row["known_issue_id"] for row in KNOWN_ISSUES],
    }
    (run_dir / INVESTIGATION_FILENAME).write_text(
        json.dumps(investigation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if precondition_evaluation is not None:
        (run_dir / PRECONDITION_EVALUATION_FILENAME).write_text(
            json.dumps(dict(precondition_evaluation), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    fn = chat_fn or llm_chat
    system = (
        "You are a cross-boundary failure forecaster for an AI agent E2E harness. "
        "You do NOT fix code. You predict Producer→Consumer risks before the next E2E phase. "
        "Respond ONLY with JSON: {\"predictions\": [ ... max 10 items ... ]}. "
        "Each prediction MUST include non-empty keys: "
        "prediction_id, boundary (Producer→Consumer), invariant, failure_hypothesis, "
        "evidence (repo-relative paths), suggested_test, confidence (low|medium|high). "
        "Use the top-level key \"predictions\" (not failure_risk_predictions). "
        "If evaluated_preconditions are provided, treat evaluation.status as final. "
        "Do NOT output precondition status fields and do NOT upgrade UNKNOWN to SATISFIED/UNSATISFIED. "
        "prediction ≠ precondition evaluation. "
        "Focus on invariants and boundaries, not exact bug names. "
        "Use repository-relative paths in evidence when possible."
    )
    user = (
        f"Experiment: Tetris full E2E ({composition_id})\n"
        f"Model: {model}\n\n"
        "Cross-cutting checklist to apply:\n"
        + "\n".join(f"- {item}" for item in CROSS_CUTTING_CHECKLIST)
        + "\n\nInvestigation bundle:\n"
        + json.dumps(investigation, ensure_ascii=False)[:28000]
        + "\n\nEmit the top failure-risk predictions (max 10). "
        "Use evaluated_preconditions only as observational context."
    )

    llm_status = "ok"
    llm_error = None
    diagnostics: dict[str, Any] = {}
    predictions: list[dict[str, Any]] = []
    last_empty: LLMEmptyResponseError | None = None
    try:
        for attempt in range(1, 4):
            response = fn(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                format="json",
                execution_profile="structured_output",
            )
            diagnostics = llm_response_diagnostics(response)
            raw = message_content(response)
            if not raw.strip():
                last_empty = LLMEmptyResponseError(
                    "empty prefault LLM response",
                    diagnostics=diagnostics,
                )
                continue
            payload = json.loads(raw)
            predictions = _normalize_predictions(payload if isinstance(payload, Mapping) else {})
            if predictions:
                break
        if not predictions:
            if last_empty is not None:
                raise last_empty
            raise ValueError("prefault LLM returned no predictions")
    except Exception as exc:  # noqa: BLE001
        llm_status = "error"
        llm_error = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, LLMEmptyResponseError):
            diagnostics = dict(getattr(exc, "diagnostics", None) or diagnostics)

    frozen = {
        "experiment": "cross_boundary_prefault_v0",
        "status": "frozen_before_e2e",
        "generated_at": _utc_stamp(),
        "model": model,
        "composition_id": composition_id,
        "investigation_path": INVESTIGATION_FILENAME,
        "precondition_evaluation_path": (
            PRECONDITION_EVALUATION_FILENAME if precondition_evaluation is not None else None
        ),
        "evaluated_preconditions": preconditions or [],
        "execution_context": dict(execution_context or {}),
        "llm_status": llm_status,
        "llm_error": llm_error,
        "llm_diagnostics": diagnostics,
        "prediction_count": len(predictions),
        "predictions": predictions,
        "known_issues": KNOWN_ISSUES,
        "policy": {
            "no_production_fix_from_prediction": True,
            "prediction_does_not_set_precondition_status": True,
            "max_predictions": 10,
            "grade_labels": sorted(GRADE_VALUES),
        },
    }
    out_path = run_dir / PREFAULT_FILENAME
    out_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return frozen


def build_e2e_observation(
    *,
    summary: Mapping[str, Any],
    pipeline_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pipeline = pipeline_result or {}
    skill_pipeline = summary.get("skill_pipeline") or {}
    step_status = skill_pipeline.get("step_status") or {}
    errors = list(skill_pipeline.get("errors") or pipeline.get("errors") or [])
    events_tail = summary.get("events_tail") or []
    return {
        "judgment": summary.get("judgment"),
        "judgment_ja": summary.get("judgment_ja"),
        "status": summary.get("status"),
        "step_status": step_status,
        "handoff_valid": skill_pipeline.get("handoff_valid"),
        "errors": errors,
        "goals_complete": summary.get("goals_complete"),
        "pipeline_phase_complete": summary.get("pipeline_phase_complete"),
        "mutation_tools_used": summary.get("mutation_tools_used"),
        "tetris_candidate_files": summary.get("tetris_candidate_files"),
        "sandbox_root": summary.get("sandbox_root"),
        "stop_reason": summary.get("stop_reason"),
        "awaiting_human_grill": summary.get("awaiting_human_grill"),
        "events_tail_types": [
            e.get("type") if isinstance(e, dict) else None for e in events_tail
        ],
        "value_consumption_rounds": (skill_pipeline.get("value_consumption") or {}).get(
            "round_count"
        ),
    }


def _tokenize(text: str) -> set[str]:
    return {t.casefold() for t in re.findall(r"[a-zA-Z0-9_./-]+", text) if len(t) >= 3}


def _heuristic_grade(
    prediction: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> tuple[str, str]:
    boundary = str(prediction.get("boundary") or "")
    invariant = str(prediction.get("invariant") or "")
    hypothesis = str(prediction.get("failure_hypothesis") or "")
    evidence = str(prediction.get("evidence") or "")

    obs_blob = json.dumps(observation, ensure_ascii=False).casefold()
    error_blob = " ".join(str(e) for e in (observation.get("errors") or [])).casefold()
    step_blob = json.dumps(observation.get("step_status") or {}, ensure_ascii=False).casefold()

    hyp_tokens = _tokenize(hypothesis) | _tokenize(invariant)
    boundary_tokens = _tokenize(boundary)

    boundary_hit = any(tok in obs_blob or tok in error_blob for tok in boundary_tokens if tok)
    invariant_hit = any(tok in error_blob or tok in obs_blob for tok in _tokenize(invariant))
    exact_hit = any(tok in error_blob for tok in hyp_tokens if len(tok) >= 5)

    if exact_hit and (boundary_hit or invariant_hit):
        return "EXACT_HIT", "failure/error text overlaps hypothesis and boundary/invariant"
    if boundary_hit and invariant_hit:
        return "INVARIANT_HIT", "observed errors/status touch boundary and invariant tokens"
    if boundary_hit:
        return "BOUNDARY_HIT", "observed failure near named producer→consumer boundary"
    related_tokens = _tokenize(evidence) | hyp_tokens
    if any(tok in obs_blob for tok in related_tokens):
        return "RELATED", "observation mentions related code or symptom tokens"
    return "MISS", "no strong overlap between prediction and E2E observation"


def compare_prefault_to_e2e(
    *,
    prefault: Mapping[str, Any],
    observation: Mapping[str, Any],
    model: str | None = None,
    chat_fn: Any | None = None,
) -> dict[str, Any]:
    """Grade frozen predictions against E2E outcome without modifying predictions."""
    observation_known_issues = _detect_observation_known_issues(observation)
    novel_failures_observed = _has_novel_failures(observation)
    failures_observed = bool(observation.get("errors")) or any(
        status == "error"
        for status in (observation.get("step_status") or {}).values()
    )
    known_issue_only_failure = failures_observed and not novel_failures_observed and bool(
        observation_known_issues
    )
    comparisons: list[dict[str, Any]] = []
    for prediction in prefault.get("predictions") or []:
        if not isinstance(prediction, Mapping):
            continue
        predicted_known_issue = _prediction_known_issue_id(prediction)
        known_issue_match = (
            predicted_known_issue in observation_known_issues if predicted_known_issue else False
        )
        if known_issue_only_failure:
            grade = "EXCLUDED_KNOWN_ISSUE"
            reason = "failure attributed to cataloged known issue; excluded from novel evaluation"
            evaluation_class = "known_issue_excluded"
        elif not novel_failures_observed:
            grade, reason = _heuristic_grade(prediction, observation)
            evaluation_class = "not_applicable"
        else:
            grade, reason = _heuristic_grade(prediction, observation)
            evaluation_class = "novel_failure"
            if observation_known_issues and predicted_known_issue:
                evaluation_class = (
                    "known_issue" if known_issue_match else "known_issue_mismatch"
                )
            elif observation_known_issues and not predicted_known_issue:
                evaluation_class = "novel_failure_unpredicted"
        comparisons.append(
            {
                "prediction_id": prediction.get("prediction_id"),
                "grade": grade,
                "grade_reason": reason,
                "known_issue_id": predicted_known_issue,
                "known_issue_observed": observation_known_issues,
                "known_issue_match": known_issue_match,
                "evaluation_class": evaluation_class,
                "excluded_from_novel_evaluation": known_issue_only_failure,
                "prediction": dict(prediction),
            }
        )

    strong_hits = [
        row
        for row in comparisons
        if row["grade"] in {"EXACT_HIT", "BOUNDARY_HIT", "INVARIANT_HIT"}
        and not row.get("excluded_from_novel_evaluation")
    ]
    catchable = (
        failures_observed
        and bool(strong_hits)
        and observation.get("judgment") in {"NOT_CONNECTED", "FAIL", "PARTIAL_PASS"}
    )
    if known_issue_only_failure:
        catchable_before_e2e = "EXCLUDED_KNOWN_ISSUE"
    elif novel_failures_observed and not strong_hits:
        catchable_before_e2e = "UNLIKELY"
    elif novel_failures_observed and strong_hits:
        catchable_before_e2e = "LIKELY"
    elif not failures_observed:
        catchable_before_e2e = "NOT_APPLICABLE"
    else:
        catchable_before_e2e = "UNCERTAIN"

    llm_review: dict[str, Any] | None = None
    if model and chat_fn is not None and prefault.get("predictions"):
        try:
            response = chat_fn(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Grade each frozen prediction against E2E results. "
                            "Do NOT rewrite predictions. "
                            "Respond JSON: {\"reviews\":[{\"prediction_id\",\"grade\",\"notes\"}]}. "
                            f"grade in {sorted(GRADE_VALUES)}."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "predictions": prefault.get("predictions"),
                                "e2e_observation": observation,
                                "heuristic_grades": comparisons,
                            },
                            ensure_ascii=False,
                        )[:24000],
                    },
                ],
                format="json",
                execution_profile="deep_reasoning",
            )
            raw = message_content(response)
            if raw.strip():
                llm_review = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            llm_review = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "experiment": "cross_boundary_prefault_comparison_v0",
        "generated_at": _utc_stamp(),
        "prefault_generated_at": prefault.get("generated_at"),
        "predictions_unchanged": True,
        "e2e_observation": dict(observation),
        "comparisons": comparisons,
        "summary": {
            "total_predictions": len(comparisons),
            "exact_hit": sum(1 for r in comparisons if r["grade"] == "EXACT_HIT"),
            "boundary_hit": sum(1 for r in comparisons if r["grade"] == "BOUNDARY_HIT"),
            "invariant_hit": sum(1 for r in comparisons if r["grade"] == "INVARIANT_HIT"),
            "related": sum(1 for r in comparisons if r["grade"] == "RELATED"),
            "miss": sum(1 for r in comparisons if r["grade"] == "MISS"),
            "known_issue_hits": sum(1 for r in comparisons if r.get("known_issue_match")),
            "known_issue_observed": observation_known_issues,
            "known_issue_only_failure": known_issue_only_failure,
            "novel_failures_observed": novel_failures_observed,
            "failures_observed": failures_observed,
            "preflight_catchable_before_e2e": catchable_before_e2e,
        },
        "observation_known_issues": observation_known_issues,
        "llm_review": llm_review,
    }


def write_prefault_comparison(run_dir: Path, comparison: Mapping[str, Any]) -> Path:
    path = run_dir / COMPARISON_FILENAME
    path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = [
    "COMPARISON_FILENAME",
    "INVESTIGATION_FILENAME",
    "KNOWN_ISSUES",
    "PREFAULT_FILENAME",
    "PRECONDITION_EVALUATION_FILENAME",
    "build_e2e_observation",
    "collect_investigation_bundle",
    "compare_prefault_to_e2e",
    "run_cross_boundary_prefault",
    "write_prefault_comparison",
]
