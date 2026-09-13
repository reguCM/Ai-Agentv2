"""Context Monitor 観測記録（JSONL append）。"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from tools.system.context_monitor.gpu_snapshot import snapshot_gpu
from tools.system.context_monitor.paths import OBSERVATIONS_JSONL, ensure_monitor_dir
from tools.system.context_monitor.schema import SCHEMA_VERSION, TASK_TYPES


def is_monitor_enabled() -> bool:
    """AI_AGENT_CONTEXT_MONITOR=0 で無効。未設定時は有効。"""
    return os.environ.get("AI_AGENT_CONTEXT_MONITOR", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_task_type(task_type: str | None) -> str:
    if not task_type:
        return "unknown"
    t = str(task_type).strip().lower()
    return t if t in TASK_TYPES else "unknown"


def build_observation(
    *,
    source: str,
    model: str | None,
    profile_id: str | None,
    context_size: int | None,
    tools_enabled: bool,
    task_type: str | None = None,
    scenario_id: str | None = None,
    execution_id: str | None = None,
    gpu_before: dict[str, Any] | None = None,
    gpu_after: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    performance: dict[str, Any] | None = None,
    limits: dict[str, Any] | None = None,
    observation_id: str | None = None,
    timestamp: str | None = None,
    legacy_ref: str | None = None,
) -> dict[str, Any]:
    """1 回の LLM 実行に相当する観測レコード（評価フィールドは含めない）。"""
    obs: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "observation_id": observation_id or str(uuid.uuid4()),
        "timestamp": timestamp or _utc_now_iso(),
        "source": source,
        "execution": {
            "model": model,
            "profile_id": profile_id,
            "context_size": context_size,
            "tools_enabled": tools_enabled,
            "task_type": _normalize_task_type(task_type),
            "scenario_id": scenario_id,
            "execution_id": execution_id,
        },
        "gpu_before": gpu_before,
        "gpu_after": gpu_after,
        "outcome": outcome or {},
        "performance": performance or {},
        "limits": limits or {},
    }
    if legacy_ref:
        obs["legacy_ref"] = legacy_ref
    return obs


def append_observation(observation: dict[str, Any], *, path=None) -> str:
    """観測を JSONL に追記。observation_id を返す。"""
    ensure_monitor_dir()
    target = path or OBSERVATIONS_JSONL
    obs_id = observation.get("observation_id") or str(uuid.uuid4())
    observation["observation_id"] = obs_id
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(observation, ensure_ascii=False) + "\n")
    return obs_id


def load_observations(*, path=None) -> list[dict[str, Any]]:
    target = path or OBSERVATIONS_JSONL
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(target, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


class ChatObservationSession:
    """llm.chat 用の観測セッション（context manager）。"""

    def __init__(self, meta: dict[str, Any], chat_kwargs: dict[str, Any]):
        self._meta = dict(meta or {})
        self._chat_kwargs = chat_kwargs
        self._started_at: datetime | None = None
        self._gpu_before: dict[str, Any] | None = None
        self._observation_id: str | None = None

    def __enter__(self) -> ChatObservationSession:
        if not is_monitor_enabled():
            return self
        self._started_at = datetime.now(timezone.utc)
        try:
            self._gpu_before = snapshot_gpu()
        except Exception:
            self._gpu_before = {"capture_error": True}
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not is_monitor_enabled() or self._started_at is None:
            return
        elapsed_ms = int(
            (datetime.now(timezone.utc) - self._started_at).total_seconds() * 1000
        )
        try:
            gpu_after = snapshot_gpu()
        except Exception:
            gpu_after = {"capture_error": True}

        model = self._chat_kwargs.get("model")
        profile_id = self._meta.get("profile_id")
        context_size = self._meta.get("context_size")
        if context_size is None:
            options = self._chat_kwargs.get("options") or {}
            context_size = options.get("num_ctx")

        outcome: dict[str, Any] = {
            "success": exc_type is None,
            "error": str(exc) if exc else None,
            "timeout": self._meta.get("timeout", False)
            or (exc is not None and "timeout" in str(exc).lower()),
        }
        perf = {"elapsed_ms": elapsed_ms}
        perf.update(self._meta.get("performance") or {})

        obs = build_observation(
            source=self._meta.get("source") or "llm.chat",
            model=model,
            profile_id=profile_id,
            context_size=context_size,
            tools_enabled=bool(self._chat_kwargs.get("tools")),
            task_type=self._meta.get("task_type"),
            scenario_id=self._meta.get("scenario_id"),
            execution_id=self._meta.get("execution_id"),
            gpu_before=self._gpu_before,
            gpu_after=gpu_after,
            outcome=outcome,
            performance=perf,
            limits=self._meta.get("limits") or {},
        )
        if exc_type is None and self._meta.get("outcome"):
            obs["outcome"].update(self._meta["outcome"])
        self._observation_id = append_observation(obs)

    @property
    def observation_id(self) -> str | None:
        return self._observation_id

    def record_outcome(self, outcome: dict[str, Any]) -> None:
        self._meta["outcome"] = outcome

    def mark_timeout(self) -> None:
        self._meta["timeout"] = True


def begin_chat_observation(
    meta: dict[str, Any] | None, chat_kwargs: dict[str, Any]
) -> ChatObservationSession:
    return ChatObservationSession(meta or {}, chat_kwargs)
