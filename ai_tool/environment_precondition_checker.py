"""Deterministic environment preconditions (Precondition Contract v0)."""
from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from typing import Any

from ai_tool.precondition_contract import (
    STATUS_SATISFIED,
    STATUS_UNSATISFIED,
    Precondition,
    PreconditionEvaluation,
    precondition_definition,
)
from tools.ai.sandbox_workspace import resolve_configured_sandbox_parent

CHECKER_SOURCE = "environment_precondition_checker:v0"


def _mint_env_precondition_id(key: str) -> str:
    return f"pc-env-{key.replace('_', '-')}"


def _evaluate_python_available() -> Precondition:
    key = "python_available"
    base = precondition_definition(
        key=key,
        description="Python interpreter is available for sandbox execution.",
        source=CHECKER_SOURCE,
        blocking=True,
        precondition_id=_mint_env_precondition_id(key),
    )
    executable = str(sys.executable or "").strip()
    if executable and Path(executable).exists():
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(
                status=STATUS_SATISFIED,
                evidence_refs=[
                    f"system:python_executable:{executable}",
                    f"system:python_version:{sys.version.split()[0]}",
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
            status=STATUS_UNSATISFIED,
            evidence_refs=["check:python_available:missing_executable"],
        ),
    )


def _evaluate_pygame_available() -> Precondition:
    key = "pygame_available"
    base = precondition_definition(
        key=key,
        description="pygame is importable (dependency_policy=pygame_allowed).",
        source=CHECKER_SOURCE,
        blocking=False,
        precondition_id=_mint_env_precondition_id(key),
    )
    if importlib.util.find_spec("pygame") is not None:
        try:
            pygame = importlib.import_module("pygame")
            version_mod = getattr(pygame, "version", None)
            version = str(
                getattr(version_mod, "ver", None)
                or getattr(pygame, "__version__", None)
                or "unknown"
            )
        except Exception:  # noqa: BLE001
            return Precondition(
                precondition_id=base.precondition_id,
                key=base.key,
                description=base.description,
                blocking=base.blocking,
                source=CHECKER_SOURCE,
                evaluation=PreconditionEvaluation(
                    status=STATUS_UNSATISFIED,
                    evidence_refs=["check:pygame_available:import_failed"],
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
                evidence_refs=[f"system:pygame_version:{version}"],
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
            evidence_refs=["check:pygame_available:not_installed"],
        ),
    )


def _evaluate_sandbox_writable(*, repo_root: Path) -> Precondition:
    key = "sandbox_writable"
    base = precondition_definition(
        key=key,
        description="Configured Dedicated Sandbox parent directory is writable.",
        source=CHECKER_SOURCE,
        blocking=True,
        precondition_id=_mint_env_precondition_id(key),
    )
    try:
        parent = resolve_configured_sandbox_parent(repo_root)
        parent.mkdir(parents=True, exist_ok=True)
        probe_name = f".precondition_probe_{uuid.uuid4().hex[:8]}"
        probe_path = parent / probe_name
        probe_path.write_text("ok", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        rel = probe_path.parent.as_posix()
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(
                status=STATUS_SATISFIED,
                evidence_refs=[
                    f"system:sandbox_parent:{rel}",
                    "check:sandbox_writable:probe_write_ok",
                ],
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return Precondition(
            precondition_id=base.precondition_id,
            key=base.key,
            description=base.description,
            blocking=base.blocking,
            source=CHECKER_SOURCE,
            evaluation=PreconditionEvaluation(
                status=STATUS_UNSATISFIED,
                evidence_refs=[f"check:sandbox_writable:{type(exc).__name__}:{exc}"],
            ),
        )


def evaluate_environment_preconditions(*, repo_root: Path | None = None) -> list[Precondition]:
    root = repo_root or Path(__file__).resolve().parents[1]
    return [
        _evaluate_python_available(),
        _evaluate_pygame_available(),
        _evaluate_sandbox_writable(repo_root=root),
    ]


__all__ = ["CHECKER_SOURCE", "evaluate_environment_preconditions"]
