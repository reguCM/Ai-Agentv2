"""Append-only pipeline observations for Dev Skill E2E timing and progress."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


OBSERVATIONS_FILENAME = "pipeline_observations.jsonl"


class PipelineBudgetExceeded(Exception):
    """Raised when an E2E budget is exhausted."""

    def __init__(self, snapshot: Mapping[str, Any]) -> None:
        super().__init__("pipeline budget exceeded")
        self.snapshot = dict(snapshot)


@dataclass
class PipelineObserver:
    run_dir: Path
    budget_seconds: float | None = None
    e2e_kind: str = "pipeline"
    _started_perf: float = field(default_factory=time.perf_counter)
    _phase_started: dict[str, float] = field(default_factory=dict)
    _skill_started: dict[str, float] = field(default_factory=dict)
    _llm_started: dict[str, float] = field(default_factory=dict)
    _completed_phases: list[str] = field(default_factory=list)
    _current_phase: str | None = None
    _current_skill_id: str | None = None
    _current_llm: dict[str, Any] | None = None
    _remaining_skills: list[str] = field(default_factory=list)
    _include_production_chat: bool = False

    @property
    def path(self) -> Path:
        return self.run_dir / OBSERVATIONS_FILENAME

    def set_work_plan(
        self,
        *,
        composition_steps: list[str],
        include_production_chat: bool = False,
    ) -> None:
        self._remaining_skills = list(composition_steps)
        self._include_production_chat = include_production_chat

    def elapsed_ms(self) -> int:
        return max(0, round((time.perf_counter() - self._started_perf) * 1000))

    def check_budget(self) -> None:
        if self.budget_seconds is None:
            return
        elapsed_s = self.elapsed_ms() / 1000.0
        if elapsed_s < self.budget_seconds:
            return
        raise PipelineBudgetExceeded(self.budget_snapshot(status="exceeded"))

    def budget_snapshot(self, *, status: str) -> dict[str, Any]:
        current_activity: dict[str, Any] | None = None
        if self._current_llm is not None:
            current_activity = {"type": "LLM", **self._current_llm}
        elif self._current_skill_id is not None:
            current_activity = {
                "type": "SKILL",
                "phase": self._current_phase,
                "skill_id": self._current_skill_id,
            }
        elif self._current_phase is not None:
            current_activity = {"type": "PHASE", "phase": self._current_phase}

        remaining = list(self._remaining_skills)
        if self._include_production_chat and status not in {"completed", "budget_exceeded"}:
            remaining.append("production_chat")

        return {
            "status": status,
            "budget_seconds": self.budget_seconds,
            "elapsed_ms": self.elapsed_ms(),
            "reached_phase": self._current_phase,
            "completed_phases": list(self._completed_phases),
            "current_activity": current_activity,
            "remaining_work": remaining,
        }

    def _append(self, payload: dict[str, Any]) -> None:
        row = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            **payload,
        }
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def phase_start(self, phase: str) -> None:
        self.check_budget()
        self._current_phase = phase
        self._phase_started[phase] = time.perf_counter()
        self._append({"event": "PHASE_START", "phase": phase, "e2e_kind": self.e2e_kind})

    def phase_end(self, phase: str, *, status: str = "done") -> None:
        started = self._phase_started.pop(phase, None)
        elapsed_ms = (
            max(0, round((time.perf_counter() - started) * 1000)) if started is not None else None
        )
        if status == "done" and phase not in self._completed_phases:
            self._completed_phases.append(phase)
        if self._current_phase == phase:
            self._current_phase = None
        self._append(
            {
                "event": "PHASE_END",
                "phase": phase,
                "status": status,
                "elapsed_ms": elapsed_ms,
                "e2e_kind": self.e2e_kind,
            }
        )

    def skill_start(self, phase: str, skill_id: str) -> None:
        self.check_budget()
        self._current_skill_id = skill_id
        key = f"{phase}:{skill_id}"
        self._skill_started[key] = time.perf_counter()
        self._append({"event": "SKILL_START", "phase": phase, "skill_id": skill_id})

    def skill_end(self, phase: str, skill_id: str, *, status: str) -> None:
        key = f"{phase}:{skill_id}"
        started = self._skill_started.pop(key, None)
        elapsed_ms = (
            max(0, round((time.perf_counter() - started) * 1000)) if started is not None else None
        )
        if self._current_skill_id == skill_id:
            self._current_skill_id = None
        if status == "done" and skill_id in self._remaining_skills:
            self._remaining_skills = [item for item in self._remaining_skills if item != skill_id]
        self._append(
            {
                "event": "SKILL_END",
                "phase": phase,
                "skill_id": skill_id,
                "status": status,
                "elapsed_ms": elapsed_ms,
            }
        )

    def llm_start(
        self,
        *,
        phase: str,
        skill_id: str,
        model: str,
        round_index: int | None = None,
    ) -> str:
        self.check_budget()
        call_id = f"{phase}:{skill_id}:{round_index or 0}:{len(self._llm_started)}"
        self._current_llm = {
            "phase": phase,
            "skill_id": skill_id,
            "round": round_index,
            "model": model,
        }
        self._llm_started[call_id] = time.perf_counter()
        self._append(
            {
                "event": "LLM_START",
                "call_id": call_id,
                "phase": phase,
                "skill_id": skill_id,
                "round": round_index,
                "model": model,
            }
        )
        return call_id

    def llm_end(
        self,
        call_id: str,
        *,
        phase: str,
        skill_id: str,
        model: str,
        status: str,
        round_index: int | None = None,
        error: str | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> None:
        started = self._llm_started.pop(call_id, None)
        elapsed_ms = (
            max(0, round((time.perf_counter() - started) * 1000)) if started is not None else None
        )
        self._current_llm = None
        payload: dict[str, Any] = {
            "event": "LLM_END",
            "call_id": call_id,
            "phase": phase,
            "skill_id": skill_id,
            "round": round_index,
            "model": model,
            "status": status,
            "elapsed_ms": elapsed_ms,
        }
        if error:
            payload["error"] = error[:240]
        if diagnostics:
            payload["diagnostics"] = {
                key: diagnostics[key]
                for key in (
                    "attempt",
                    "content_len",
                    "thinking_len",
                    "done_reason",
                    "eval_count",
                    "prompt_eval_count",
                    "content_preview",
                    "thinking_preview",
                )
                if key in diagnostics
            }
        self._append(payload)

    def e2e_end(self, *, status: str, notes: list[str] | None = None) -> None:
        payload: dict[str, Any] = {
            "event": "E2E_END",
            "status": status,
            "elapsed_ms": self.elapsed_ms(),
            "e2e_kind": self.e2e_kind,
            "budget": self.budget_snapshot(status=status),
        }
        if notes:
            payload["notes"] = notes
        self._append(payload)

    def summarize_timing(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {
                "total_elapsed_ms": self.elapsed_ms(),
                "by_phase_ms": {},
                "by_skill_ms": {},
                "llm_total_ms": 0,
                "llm_call_count": 0,
            }

        by_phase: dict[str, int] = {}
        by_skill: dict[str, int] = {}
        llm_total = 0
        llm_count = 0

        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = str(row.get("event") or "")
            elapsed = row.get("elapsed_ms")
            if not isinstance(elapsed, int):
                continue
            if event == "PHASE_END":
                phase = str(row.get("phase") or "unknown")
                by_phase[phase] = by_phase.get(phase, 0) + elapsed
            elif event == "SKILL_END":
                skill_id = str(row.get("skill_id") or "unknown")
                by_skill[skill_id] = by_skill.get(skill_id, 0) + elapsed
            elif event == "LLM_END":
                llm_total += elapsed
                llm_count += 1

        return {
            "total_elapsed_ms": self.elapsed_ms(),
            "by_phase_ms": by_phase,
            "by_skill_ms": by_skill,
            "llm_total_ms": llm_total,
            "llm_call_count": llm_count,
        }


def observed_llm_json(
    observer: PipelineObserver | None,
    *,
    phase: str,
    skill_id: str,
    model: str,
    round_index: int | None,
    call_llm: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Run one JSON LLM call with LLM_START/LLM_END observation."""
    call_id = None
    if observer is not None:
        call_id = observer.llm_start(
            phase=phase,
            skill_id=skill_id,
            model=model,
            round_index=round_index,
        )
    status = "ok"
    error_text = None
    diagnostics = None
    try:
        return call_llm(**kwargs)
    except Exception as exc:  # noqa: BLE001
        status = "error"
        error_text = f"{type(exc).__name__}: {exc}"
        diagnostics = getattr(exc, "diagnostics", None)
        raise
    finally:
        if observer is not None and call_id is not None:
            observer.llm_end(
                call_id,
                phase=phase,
                skill_id=skill_id,
                model=model,
                status=status,
                round_index=round_index,
                error=error_text,
                diagnostics=diagnostics if isinstance(diagnostics, Mapping) else None,
            )


__all__ = [
    "OBSERVATIONS_FILENAME",
    "PipelineBudgetExceeded",
    "PipelineObserver",
    "observed_llm_json",
]
