"""Stage-locked テスト改善ループ orchestrator.

Upper LLM may analyze meaning and propose a candidate.
This module owns stage, n-limit, confirm gates, attempt cap, and stop.
It will not run VALIDATE_5 while stage is CANARY_1.
"""
from __future__ import annotations

from typing import Any, Callable

from research.test_improvement_loop.schema import MAX_UPGRADE_ATTEMPTS, STAGE_MAX_N, STAGES


class StageViolation(RuntimeError):
    """Raised when a caller asks to skip or overflow the current stage."""


class Orchestrator:
    def __init__(self, *, max_attempts: int = MAX_UPGRADE_ATTEMPTS) -> None:
        self.stage = "CANARY_1"
        self.attempt = 0
        self.max_attempts = max_attempts
        self.stopped_reason: str | None = None
        self.history: list[dict[str, Any]] = []

    def allowed_n(self) -> int | None:
        return STAGE_MAX_N[self.stage]

    def assert_can_run(self, ids: list[str]) -> None:
        if self.stage == "STOP":
            raise StageViolation(f"stopped: {self.stopped_reason}")
        n = len(ids)
        cap = self.allowed_n()
        if cap is not None and n > cap:
            raise StageViolation(
                f"stage={self.stage} allows n<={cap}, requested n={n}. "
                "Do not skip stages or batch ahead."
            )
        if self.stage == "CANARY_1" and n != 1:
            raise StageViolation("CANARY_1 requires exactly 1 id")
        if self.stage == "HOLDOUT_1" and n != 1:
            raise StageViolation("HOLDOUT_1 requires exactly 1 id")
        if self.stage == "VALIDATE_5" and n != 5:
            raise StageViolation("VALIDATE_5 requires exactly 5 ids")
        if self.stage == "HOLDOUT_5" and n != 5:
            raise StageViolation("HOLDOUT_5 requires exactly 5 ids")

    def begin_attempt(self) -> int:
        if self.attempt >= self.max_attempts:
            self.stop("max_upgrade_attempts")
            raise StageViolation(f"attempt cap {self.max_attempts} reached")
        self.attempt += 1
        return self.attempt

    def record_step(self, name: str, payload: dict[str, Any]) -> None:
        self.history.append({"stage": self.stage, "attempt": self.attempt, "name": name, **payload})

    def confirm_and_advance(self, *, ok: bool, reasons: list[str], next_stage: str) -> bool:
        self.record_step("confirm", {"ok": ok, "reasons": reasons, "next_stage": next_stage})
        if not ok:
            self.stop("confirm_gate_fail: " + "; ".join(reasons))
            return False
        if next_stage not in STAGES:
            raise StageViolation(f"unknown next stage {next_stage}")
        self.stage = next_stage
        return True

    def stop(self, reason: str) -> None:
        self.stopped_reason = reason
        self.stage = "STOP"

    def run_stage(
        self,
        ids: list[str],
        fn: Callable[[list[str]], dict[str, Any]],
    ) -> dict[str, Any]:
        self.assert_can_run(ids)
        out = fn(ids)
        self.record_step("run", {"ids": list(ids), "summary": out.get("summary")})
        return out
