"""
Phase D-1a: 実行観測・execution_id・ログ保存。

観測のみ。allow_execute / AUTO 条件は変更しない。
長時間＝危険とは判定しない。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UNKNOWN = "unknown"

DEFAULT_OBS_DIRNAME = "trusted_personal_obs"


def new_execution_id() -> str:
    return str(uuid.uuid4())


def default_observation_dir() -> Path:
    env = os.environ.get("AI_AGENT_TP_OBS_DIR")
    if env:
        return Path(env)
    # リポジトリ相対（存在しなければ作成）
    root = Path(__file__).resolve().parents[3]
    return root / "research" / "llm_benchmarks" / DEFAULT_OBS_DIRNAME


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_execution_facts(**overrides: Any) -> dict[str, Any]:
    base = {
        "execution_id": UNKNOWN,
        "stage": UNKNOWN,
        "start_time": UNKNOWN,
        "end_time": UNKNOWN,
        "duration_seconds": UNKNOWN,
        "timed_out": UNKNOWN,
        "returncode": UNKNOWN,
        "process_terminated": UNKNOWN,
        "child_process_count": UNKNOWN,
        "child_process_spawned": UNKNOWN,
        "stop_means_available": UNKNOWN,
        "unbounded_execution_signals": [],
        "rationale_codes": [
            "execution_facts_phase_d1a",
            "long_running_not_defined_as_dangerous",
            "observation_only",
        ],
        "note": "実行時間の長さ自体を危険とはみなしません。",
    }
    base.update(overrides)
    return base


def begin_execution_observation(execution_id: str | None = None) -> dict[str, Any]:
    eid = execution_id or new_execution_id()
    start = time.monotonic()
    return {
        "execution_id": eid,
        "start_monotonic": start,
        "start_time": utc_now_iso(),
        "stop_means_available": True,  # 親が timeout / kill 可能な枠組み上
        "rationale_codes": ["execution_observation_started"],
    }


def finalize_execution_observation(
    begun: dict | None,
    *,
    returncode: Any = UNKNOWN,
    timed_out: bool = False,
    child_process_count: Any = UNKNOWN,
    child_process_spawned: Any = UNKNOWN,
    error: str | None = None,
) -> dict[str, Any]:
    begun = begun or begin_execution_observation()
    end_mono = time.monotonic()
    start_mono = begun.get("start_monotonic")
    duration = UNKNOWN
    if isinstance(start_mono, (int, float)):
        duration = float(end_mono - start_mono)

    signals = []
    if timed_out:
        signals.append("timeout_fired")
    if duration != UNKNOWN and isinstance(duration, float) and duration >= 0:
        # 兆候の記録のみ。危険判定はしない
        signals.append("duration_recorded")
    if child_process_spawned is True:
        signals.append("child_process_spawned")
    if child_process_count == UNKNOWN:
        signals.append("child_process_count_unknown")

    terminated = UNKNOWN
    if timed_out:
        terminated = True
    elif returncode is not None and returncode is not UNKNOWN:
        terminated = True

    return empty_execution_facts(
        execution_id=begun.get("execution_id"),
        stage="post",
        start_time=begun.get("start_time"),
        end_time=utc_now_iso(),
        duration_seconds=duration,
        timed_out=bool(timed_out),
        returncode=returncode if returncode is not None else UNKNOWN,
        process_terminated=terminated,
        child_process_count=child_process_count,
        child_process_spawned=child_process_spawned,
        stop_means_available=begun.get("stop_means_available", True),
        unbounded_execution_signals=signals,
        error=error,
        rationale_codes=[
            "execution_facts_phase_d1a",
            "long_running_not_defined_as_dangerous",
            "observation_only",
            "no_long_running_immediate_block_rule",
        ],
    )


def count_child_processes(pid: int | None) -> Any:
    if pid is None:
        return UNKNOWN
    try:
        import psutil  # type: ignore

        proc = psutil.Process(pid)
        children = proc.children(recursive=True)
        return len(children)
    except Exception:
        return UNKNOWN


def build_observation_record(
    *,
    execution_id: str,
    stage: str,
    gate: dict | None = None,
    trusted_personal: dict | None = None,
    git_facts: dict | None = None,
    resource_before: dict | None = None,
    resource_after: dict | None = None,
    resource_delta: dict | None = None,
    execution_facts: dict | None = None,
    candidate: dict | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    gate = gate or {}
    tp = trusted_personal or {}
    record = {
        "phase": "kss-phase-d1a",
        "execution_id": execution_id,
        "stage": stage,
        "recorded_at": utc_now_iso(),
        "candidate": {
            "command": (candidate or {}).get("command"),
            "args": list((candidate or {}).get("args") or []),
        },
        "gate": {
            "decision": gate.get("decision"),
            "allow_execute": gate.get("allow_execute"),
        },
        "trusted_personal": {
            "mode": tp.get("mode"),
            "decision": tp.get("decision"),
            "allow_execute": tp.get("allow_execute"),
        },
        "git_facts": git_facts,
        "resource_before": resource_before,
        "resource_after": resource_after,
        "resource_delta": resource_delta,
        "execution_facts": execution_facts,
        "observation_only": True,
        "allow_execute_expanded": False,
        "policy_unchanged_from_d0": True,
        "web_content_used": False,
        "llm_resource_final_authority": False,
        "thresholds_applied": False,
    }
    if extra:
        record["extra"] = extra
    return record


def append_observation_log(
    record: dict,
    *,
    log_dir: str | Path | None = None,
) -> Path:
    directory = Path(log_dir) if log_dir else default_observation_dir()
    directory.mkdir(parents=True, exist_ok=True)
    eid = str(record.get("execution_id") or "unknown")
    path = directory / f"{eid}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return path


def load_observation_log(execution_id: str, *, log_dir: str | Path | None = None) -> list[dict]:
    directory = Path(log_dir) if log_dir else default_observation_dir()
    path = directory / f"{execution_id}.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows
