"""Deterministic Tetris handoff precondition evaluation (Precondition Contract v0).

System checker only — LLM prefault predictions MUST NOT set evaluation.status.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai_tool.environment_policy import merge_policy_into_precondition_bundle
from ai_tool.environment_precondition_checker import evaluate_environment_preconditions
from ai_tool.precondition_contract import (
    STATUS_SATISFIED,
    STATUS_UNKNOWN,
    STATUS_UNSATISFIED,
    Precondition,
    PreconditionEvaluation,
    precondition_definition,
    preconditions_to_dicts,
    tetris_handoff_precondition_fixtures,
    validate_preconditions,
)

CHECKER_SOURCE = "tetris_precondition_checker:v0"
PRECONDITION_EVALUATION_FILENAME = "precondition_evaluation.json"

_TECH_SPEC_EMPTY_MARKERS = (
    "empty prefault",
    "empty response",
    "llmemptyresponseerror",
    "jsondecodeerror",
    "expecting value",
    "message.content",
    "tech-spec",
    "tech_spec",
)


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_document_path(rel: str, *, repo_root: Path) -> Path:
    text = str(rel or "").strip().replace("\\", "/")
    candidate = Path(text)
    if candidate.is_file():
        return candidate.resolve()
    return (repo_root / text).resolve()


def _error_blob(
    pipeline_errors: Sequence[str] | None,
    step_status: Mapping[str, str] | None,
) -> str:
    parts = [str(item).casefold() for item in (pipeline_errors or [])]
    if step_status:
        parts.extend(f"{key}:{value}".casefold() for key, value in step_status.items())
    return " ".join(parts)


def _tech_spec_empty_response_observed(
    pipeline_errors: Sequence[str] | None,
    step_status: Mapping[str, str] | None,
) -> bool:
    blob = _error_blob(pipeline_errors, step_status)
    if "tech-spec" not in blob and "tech_spec" not in blob:
        return False
    return any(marker in blob for marker in _TECH_SPEC_EMPTY_MARKERS)


def _evaluate_tech_spec_exists(
    *,
    handoff_packet: Mapping[str, Any] | None,
    repo_root: Path,
    pipeline_errors: Sequence[str] | None,
    step_status: Mapping[str, str] | None,
) -> Precondition:
    base = next(
        item for item in tetris_handoff_precondition_fixtures() if item.key == "tech_spec_exists"
    )
    if handoff_packet is None:
        return precondition_definition(
            key=base.key,
            description=base.description,
            source=CHECKER_SOURCE,
            blocking=base.blocking,
            precondition_id=base.precondition_id,
        )

    documents = (handoff_packet.get("source") or {}).get("documents") or {}
    tech_spec_rel = str(documents.get("tech_spec") or "").strip()
    if not tech_spec_rel:
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(status=STATUS_UNKNOWN, evidence_refs=[]),
        )

    tech_path = _resolve_document_path(tech_spec_rel, repo_root=repo_root)
    rel = _repo_relative(tech_path, repo_root)
    if tech_path.is_file():
        content = tech_path.read_text(encoding="utf-8", errors="replace").strip()
        if content:
            if (step_status or {}).get("tech-spec") == "done":
                return Precondition(
                    precondition_id=base.precondition_id,
                    key=base.key,
                    description=base.description,
                    blocking=base.blocking,
                    source=CHECKER_SOURCE,
                    evaluation=PreconditionEvaluation(
                        status=STATUS_SATISFIED,
                        evidence_refs=[
                            f"artifact:{rel}",
                            "schema:goal_handoff.source.documents.tech_spec",
                            "pipeline:tech-spec:done",
                        ],
                    ),
                )
            return Precondition(
                precondition_id=base.precondition_id,
                key=base.key,
                description=base.description,
                blocking=base.blocking,
                source=CHECKER_SOURCE,
                evaluation=PreconditionEvaluation(
                    status=STATUS_SATISFIED,
                    evidence_refs=[f"artifact:{rel}", "schema:goal_handoff.source.documents.tech_spec"],
                ),
            )
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(
                status=STATUS_UNSATISFIED,
                evidence_refs=[f"artifact:{rel}", "check:tech_spec_exists:empty_file"],
            ),
        )

    if _tech_spec_empty_response_observed(pipeline_errors, step_status) and (
        (step_status or {}).get("tech-spec") != "done"
    ):
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(
                status=STATUS_UNSATISFIED,
                evidence_refs=["pipeline:error:tech_spec_empty_response"],
            ),
        )

    return Precondition(
        precondition_id=base.precondition_id,
        key=base.key,
        description=base.description,
        blocking=base.blocking,
        source=CHECKER_SOURCE,
        evaluation=PreconditionEvaluation(
            status=STATUS_UNSATISFIED,
            evidence_refs=[
                f"artifact:{rel}",
                "schema:goal_handoff.source.documents.tech_spec",
                "check:tech_spec_exists:missing_file",
            ],
        ),
    )


def _evaluate_task_ids_unique(handoff_packet: Mapping[str, Any] | None) -> Precondition:
    base = next(
        item for item in tetris_handoff_precondition_fixtures() if item.key == "task_ids_unique"
    )
    if handoff_packet is None:
        return precondition_definition(
            key=base.key,
            description=base.description,
            source=CHECKER_SOURCE,
            blocking=base.blocking,
            precondition_id=base.precondition_id,
        )

    tasks = handoff_packet.get("implementation_tasks") or []
    if not isinstance(tasks, list) or not tasks:
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(status=STATUS_UNKNOWN, evidence_refs=[]),
        )

    ids = [str(row.get("id") or "") for row in tasks if isinstance(row, Mapping)]
    if not ids or any(not item for item in ids):
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(status=STATUS_UNKNOWN, evidence_refs=[]),
        )

    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    if duplicate_ids:
        evidence = [
            "handoff:implementation_tasks",
            f"check:task_ids_unique:duplicate:{','.join(duplicate_ids)}",
        ]
        if "T0" in duplicate_ids or ids.count("T0") > 1:
            evidence.append("known_issue:task_id_t0_duplicate")
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(
                status=STATUS_UNSATISFIED,
                evidence_refs=evidence,
            ),
        )

    return Precondition(
        precondition_id=base.precondition_id,
        key=base.key,
        description=base.description,
        blocking=base.blocking,
        source=CHECKER_SOURCE,
        evaluation=PreconditionEvaluation(
            status=STATUS_SATISFIED,
            evidence_refs=[
                "handoff:implementation_tasks",
                f"check:task_ids_unique:ids:{','.join(ids)}",
            ],
        ),
    )


def _evaluate_dependency_refs_resolved(handoff_packet: Mapping[str, Any] | None) -> Precondition:
    base = next(
        item
        for item in tetris_handoff_precondition_fixtures()
        if item.key == "dependency_refs_resolved"
    )
    if handoff_packet is None:
        return precondition_definition(
            key=base.key,
            description=base.description,
            source=CHECKER_SOURCE,
            blocking=base.blocking,
            precondition_id=base.precondition_id,
        )

    tasks = handoff_packet.get("implementation_tasks") or []
    if not isinstance(tasks, list) or not tasks:
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(status=STATUS_UNKNOWN, evidence_refs=[]),
        )

    task_ids = {str(row.get("id") or "") for row in tasks if isinstance(row, Mapping)}
    unresolved: list[str] = []
    for row in tasks:
        if not isinstance(row, Mapping):
            continue
        task_id = str(row.get("id") or "")
        dependencies = [str(item) for item in (row.get("dependencies") or [])]
        for dep in dependencies:
            if dep not in task_ids:
                unresolved.append(f"{task_id}->{dep}:missing")
            elif dep == task_id:
                unresolved.append(f"{task_id}->{dep}:self_ref")

    if unresolved:
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(
                status=STATUS_UNSATISFIED,
                evidence_refs=[
                    "handoff:implementation_tasks.dependencies",
                    f"check:dependency_refs_resolved:{';'.join(unresolved)}",
                ],
            ),
        )

    return Precondition(
        precondition_id=base.precondition_id,
        key=base.key,
        description=base.description,
        blocking=base.blocking,
        source=CHECKER_SOURCE,
        evaluation=PreconditionEvaluation(
            status=STATUS_SATISFIED,
            evidence_refs=[
                "handoff:implementation_tasks.dependencies",
                "check:dependency_refs_resolved:all_refs_valid",
            ],
        ),
    )


def evaluate_all_tetris_preconditions(
    *,
    handoff_packet: Mapping[str, Any] | None,
    repo_root: Path | None = None,
    pipeline_errors: Sequence[str] | None = None,
    step_status: Mapping[str, str] | None = None,
    include_environment: bool = True,
) -> list[Precondition]:
    root = repo_root or Path(__file__).resolve().parents[1]
    items = evaluate_tetris_handoff_preconditions(
        handoff_packet=handoff_packet,
        repo_root=root,
        pipeline_errors=pipeline_errors,
        step_status=step_status,
    )
    if include_environment:
        items.extend(evaluate_environment_preconditions(repo_root=root))
    return items


def evaluate_tetris_handoff_preconditions(
    *,
    handoff_packet: Mapping[str, Any] | None,
    repo_root: Path | None = None,
    pipeline_errors: Sequence[str] | None = None,
    step_status: Mapping[str, str] | None = None,
) -> list[Precondition]:
    root = repo_root or Path(__file__).resolve().parents[1]
    return [
        _evaluate_tech_spec_exists(
            handoff_packet=handoff_packet,
            repo_root=root,
            pipeline_errors=pipeline_errors,
            step_status=step_status,
        ),
        _evaluate_task_ids_unique(handoff_packet),
        _evaluate_dependency_refs_resolved(handoff_packet),
    ]


def build_precondition_evaluation_bundle(
    *,
    handoff_packet: Mapping[str, Any] | None,
    repo_root: Path | None = None,
    pipeline_errors: Sequence[str] | None = None,
    step_status: Mapping[str, str] | None = None,
    handoff_path: str | None = None,
    execution_context: Mapping[str, Any] | None = None,
    include_environment: bool = True,
) -> dict[str, Any]:
    items = evaluate_all_tetris_preconditions(
        handoff_packet=handoff_packet,
        repo_root=repo_root,
        pipeline_errors=pipeline_errors,
        step_status=step_status,
        include_environment=include_environment,
    )
    rows = preconditions_to_dicts(items)
    validation_errors = validate_preconditions(rows)
    handoff_keys = {
        "tech_spec_exists",
        "task_ids_unique",
        "dependency_refs_resolved",
    }
    bundle = {
        "checker": CHECKER_SOURCE,
        "policy": {
            "llm_prefault_does_not_set_status": True,
            "prediction_not_equal_evaluation": True,
            "execution_context_not_equal_precondition": True,
            "unknown_passthrough": True,
            "auto_blocking": False,
        },
        "execution_context": dict(execution_context or {}),
        "handoff_path": handoff_path,
        "handoff_id": (handoff_packet or {}).get("handoff_id"),
        "validation_errors": validation_errors,
        "preconditions": rows,
        "precondition_groups": {
            "handoff": [row for row in rows if row.get("key") in handoff_keys],
            "environment": [row for row in rows if row.get("key") not in handoff_keys],
        },
    }
    return merge_policy_into_precondition_bundle(bundle, execution_context)


def attach_preconditions_to_handoff(
    handoff_packet: Mapping[str, Any],
    preconditions: Sequence[Precondition] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    packet = dict(handoff_packet)
    if preconditions and hasattr(preconditions[0], "as_dict"):
        packet["preconditions"] = preconditions_to_dicts(preconditions)  # type: ignore[arg-type]
    else:
        packet["preconditions"] = [dict(row) for row in preconditions]
    return packet


def load_handoff_artifact(artifact_dir: Path) -> tuple[dict[str, Any], Path]:
    candidates = [
        artifact_dir / "design" / "handoff.json",
        artifact_dir / "handoff.json",
    ]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8")), path
    raise FileNotFoundError(f"handoff.json not found under {artifact_dir}")


__all__ = [
    "CHECKER_SOURCE",
    "PRECONDITION_EVALUATION_FILENAME",
    "attach_preconditions_to_handoff",
    "build_precondition_evaluation_bundle",
    "evaluate_all_tetris_preconditions",
    "evaluate_tetris_handoff_preconditions",
    "load_handoff_artifact",
]
