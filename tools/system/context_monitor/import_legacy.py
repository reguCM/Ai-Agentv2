"""P2-6～P2-8 verify.json を観測形式へ変換（元ファイルは変更しない）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from tools.system.context_monitor.paths import LEGACY_MANIFEST_JSON, ensure_monitor_dir
from tools.system.context_monitor.record import append_observation, build_observation

_REPO_ROOT = Path(__file__).resolve().parents[3]

LEGACY_SOURCES = (
    {
        "phase": "P2-6",
        "verify_path": _REPO_ROOT
        / "runs"
        / "ai_tool"
        / "20260902T070613Z_file_tools_context_fix_verify_p26"
        / "verify.json",
        "context_size": 8192,
    },
    {
        "phase": "P2-7",
        "verify_path": _REPO_ROOT
        / "runs"
        / "ai_tool"
        / "20260902T071425Z_file_tools_context_32768_verify_p27"
        / "verify.json",
        "context_size": 32768,
    },
    {
        "phase": "P2-8",
        "verify_path": _REPO_ROOT
        / "runs"
        / "ai_tool"
        / "20260902T075445Z_file_tools_context_16384_verify_p28"
        / "verify.json",
        "context_size": 16384,
    },
)


def _task_type_from_keys(test_key: str, scenario_id: str) -> str:
    key = (test_key or "").lower()
    sid = (scenario_id or "").lower()
    if "fixed" in key or "fixed" in sid:
        return "large_result"
    if "list_read" in key or "list_read" in sid:
        return "list_read"
    if "multi_read" in key or "multi_read" in sid:
        return "multi_read"
    if "main" in key or "instrumented" in key or "chain" in key:
        return "search_read"
    return "unknown"


def _normalize_gpu_block(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw or not isinstance(raw, dict):
        return None
    if "gpu_status" in raw or "vram_free_mib" in raw:
        return raw
    if "memory_free_mib" in raw or "memory_total_mib" in raw:
        total = raw.get("memory_total_mib")
        used = raw.get("memory_used_mib")
        free = raw.get("memory_free_mib")
        return {
            "gpu_name": raw.get("name"),
            "vram_total_mib": total,
            "vram_used_mib": used,
            "vram_free_mib": free,
            "gpu_utilization": raw.get("gpu_util_percent"),
            "gpu_status": {
                "gpu": raw.get("name"),
                "vram_total": total,
                "vram_used": used,
                "utilization": raw.get("gpu_util_percent"),
            },
        }
    status = raw.get("gpu_status")
    if isinstance(status, dict):
        used = status.get("vram_used")
        total = status.get("vram_total")
        return {
            "gpu_status": status,
            "gpu_processes": raw.get("gpu_processes"),
            "gpu_name": status.get("gpu"),
            "vram_total_mib": total,
            "vram_used_mib": used,
            "vram_free_mib": (total - used) if isinstance(used, int) and isinstance(total, int) else None,
            "gpu_utilization": status.get("utilization"),
            "gpu_temperature": status.get("temperature"),
        }
    return raw


def _timestamp_from_verify(verify: dict[str, Any]) -> str:
    ts = verify.get("timestamp") or verify.get("started_at")
    if ts and len(str(ts)) == 16 and str(ts).endswith("Z"):
        # 20260902T075445Z → ISO
        s = str(ts)
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}Z"
    if ts:
        return str(ts)
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _model_from_verify(verify: dict[str, Any]) -> tuple[str, str]:
    profile = verify.get("llm_profile") or (verify.get("environment") or {}).get("llm_profile") or {}
    model = verify.get("model") or profile.get("model") or "qwen3:14b"
    profile_id = profile.get("id") or "qwen3_14b"
    return str(model), str(profile_id)


def _iter_p26_runs(verify: dict[str, Any], *, phase: str, context_size: int, legacy_ref: str, ts: str) -> Iterator[dict[str, Any]]:
    model, profile_id = _model_from_verify(verify)
    for run in verify.get("runs") or []:
        if not isinstance(run, dict):
            continue
        run_no = run.get("run_number") or "?"
        native = bool(run.get("native_read_file_generated"))
        success = bool(
            run.get("native_read_file_generated")
            and run.get("read_file_executed")
            and run.get("read_file_after_search")
            and not run.get("type3_fabrication_suspected")
        )
        tool_seq = run.get("tool_sequence") or []
        yield build_observation(
            source=f"import:{phase.lower()}",
            model=model,
            profile_id=profile_id,
            context_size=context_size,
            tools_enabled=True,
            task_type="search_read",
            scenario_id=f"p26_instrumented_run_{run_no}",
            execution_id=f"{phase}:run_{run_no}",
            gpu_before=None,
            gpu_after=None,
            outcome={
                "success": success,
                "timeout": False,
                "native_tool_call": native,
                "native_tool_names": [n for n in tool_seq if n == "read_file"],
                "type3": bool(run.get("type3_fabrication_suspected")),
                "type4": False,
                "tool_execution_success": bool(run.get("read_file_executed")),
            },
            performance={"elapsed_ms": None, "round_count": len(run.get("rounds_summary") or [])},
            limits={"configured_context_limit": context_size, "import_phase": phase},
            timestamp=ts,
            legacy_ref=legacy_ref,
        )


def _obs_from_round(
    rnd: dict[str, Any],
    *,
    phase: str,
    context_size: int,
    legacy_ref: str,
    ts: str,
    model: str,
    profile_id: str,
    test_key: str,
    scenario_id: str,
    round_suffix: str,
    trace_success: bool | None = None,
    trace_timeout: bool | None = None,
) -> dict[str, Any]:
    gpu_before = _normalize_gpu_block(rnd.get("gpu_pre") or rnd.get("gpu_before"))
    gpu_after = _normalize_gpu_block(rnd.get("gpu_post") or rnd.get("gpu_after"))
    native_names = rnd.get("native_tool_call_names") or rnd.get("llm_tool_names") or []
    timeout = bool(rnd.get("timeout"))
    if trace_timeout and rnd.get("round_index", 0) == 1:
        timeout = True
    success = not timeout and not rnd.get("error")
    if trace_success is not None and rnd.get("round_index", 0) == 0:
        success = trace_success and success
    return build_observation(
        source=f"import:{phase.lower()}",
        model=model,
        profile_id=profile_id,
        context_size=context_size,
        tools_enabled=True,
        task_type=_task_type_from_keys(test_key, scenario_id),
        scenario_id=scenario_id,
        execution_id=f"{phase}:{scenario_id}:{round_suffix}",
        gpu_before=gpu_before,
        gpu_after=gpu_after,
        outcome={
            "success": success,
            "timeout": timeout,
            "error": rnd.get("error"),
            "native_tool_call": bool(native_names),
            "native_tool_names": list(native_names),
            "type3": bool(rnd.get("type3")),
            "type4": bool(rnd.get("type4")),
            "tool_execution_success": rnd.get("result_ok"),
        },
        performance={
            "elapsed_ms": rnd.get("elapsed_ms"),
            "round_index": rnd.get("round_index"),
            "prompt_eval_count": rnd.get("prompt_eval_count"),
            "eval_count": rnd.get("eval_count"),
        },
        limits={"configured_context_limit": context_size, "import_phase": phase, "test_key": test_key},
        timestamp=ts,
        legacy_ref=legacy_ref,
    )


def _iter_p27_p28_tests(verify: dict[str, Any], *, phase: str, context_size: int, legacy_ref: str, ts: str) -> Iterator[dict[str, Any]]:
    model, profile_id = _model_from_verify(verify)
    tests = verify.get("tests") or {}
    if not isinstance(tests, dict):
        return

    for test_key, block in tests.items():
        if not isinstance(block, dict):
            continue
        traces = block.get("traces") or []
        for trace in traces:
            if not isinstance(trace, dict):
                continue
            scenario_id = str(trace.get("scenario_id") or f"{test_key}_unknown")
            trace_timeout = bool(trace.get("timeout_occurred"))
            trace_success = bool(
                trace.get("read_file_after_search")
                and trace.get("native_read_file_generated")
                and not trace.get("any_type3")
                and not trace.get("any_type4")
                and not trace_timeout
            )
            rounds = trace.get("rounds") or []
            if rounds:
                for rnd in rounds:
                    if not isinstance(rnd, dict):
                        continue
                    idx = rnd.get("round_index", 0)
                    yield _obs_from_round(
                        rnd,
                        phase=phase,
                        context_size=context_size,
                        legacy_ref=legacy_ref,
                        ts=ts,
                        model=str(trace.get("model") or model),
                        profile_id=profile_id,
                        test_key=test_key,
                        scenario_id=scenario_id,
                        round_suffix=f"r{idx}",
                        trace_success=trace_success,
                        trace_timeout=trace_timeout,
                    )
            else:
                gpu_before = _normalize_gpu_block(trace.get("gpu_before_run"))
                yield build_observation(
                    source=f"import:{phase.lower()}",
                    model=str(trace.get("model") or model),
                    profile_id=profile_id,
                    context_size=int(trace.get("context_limit") or context_size),
                    tools_enabled=True,
                    task_type=_task_type_from_keys(test_key, scenario_id),
                    scenario_id=scenario_id,
                    execution_id=f"{phase}:{scenario_id}:trace",
                    gpu_before=gpu_before,
                    gpu_after=_normalize_gpu_block(trace.get("gpu_after_run")),
                    outcome={
                        "success": trace_success,
                        "timeout": trace_timeout,
                        "native_tool_call": bool(trace.get("native_read_file_generated")),
                        "native_tool_names": ["read_file"] if trace.get("native_read_file_generated") else [],
                        "type3": bool(trace.get("any_type3")),
                        "type4": bool(trace.get("any_type4")),
                    },
                    performance={"elapsed_ms": trace.get("total_elapsed_ms")},
                    limits={"configured_context_limit": context_size, "import_phase": phase, "test_key": test_key},
                    timestamp=ts,
                    legacy_ref=legacy_ref,
                )

        for run in block.get("runs_detail") or []:
            if not isinstance(run, dict):
                continue
            run_no = run.get("run_number") or "?"
            scenario_id = str(run.get("scenario") or f"{test_key}_run_{run_no}")
            yield build_observation(
                source=f"import:{phase.lower()}",
                model=model,
                profile_id=profile_id,
                context_size=context_size,
                tools_enabled=True,
                task_type=_task_type_from_keys(test_key, scenario_id),
                scenario_id=scenario_id,
                execution_id=f"{phase}:{scenario_id}",
                gpu_before=_normalize_gpu_block(run.get("gpu_pre")),
                gpu_after=_normalize_gpu_block(run.get("gpu_post") or run.get("gpu_at_error")),
                outcome={
                    "success": bool(run.get("native_read_file")) and not run.get("timeout"),
                    "timeout": bool(run.get("timeout")),
                    "error": run.get("error"),
                    "native_tool_call": bool(run.get("native_tool_call_count") or run.get("native_read_file")),
                    "native_tool_names": run.get("native_tool_call_names") or [],
                    "type3": bool(run.get("type3")),
                    "type4": bool(run.get("type4")),
                },
                performance={"elapsed_ms": run.get("elapsed_ms")},
                limits={"configured_context_limit": context_size, "import_phase": phase, "test_key": test_key},
                timestamp=ts,
                legacy_ref=legacy_ref,
            )


def observations_from_verify(
    verify: dict[str, Any],
    *,
    phase: str,
    verify_path: Path,
    context_size: int,
) -> list[dict[str, Any]]:
    legacy_ref = str(verify_path.relative_to(_REPO_ROOT)).replace("\\", "/")
    ts = _timestamp_from_verify(verify)
    rows: list[dict[str, Any]] = []
    if verify.get("runs") and not verify.get("tests"):
        rows.extend(_iter_p26_runs(verify, phase=phase, context_size=context_size, legacy_ref=legacy_ref, ts=ts))
    if verify.get("tests"):
        rows.extend(
            _iter_p27_p28_tests(
                verify, phase=phase, context_size=context_size, legacy_ref=legacy_ref, ts=ts
            )
        )
    return rows


def import_legacy_verifications(*, skip_existing: bool = True) -> dict[str, Any]:
    """P2-6～P2-8 をインポート。manifest を更新。"""
    ensure_monitor_dir()
    manifest: dict[str, Any] = {"imports": [], "observation_ids": []}
    if LEGACY_MANIFEST_JSON.exists():
        with open(LEGACY_MANIFEST_JSON, encoding="utf-8") as f:
            manifest = json.load(f)
    existing_refs = {i.get("legacy_ref") for i in manifest.get("imports", [])}

    imported = 0
    for spec in LEGACY_SOURCES:
        path = spec["verify_path"]
        legacy_ref = str(path.relative_to(_REPO_ROOT)).replace("\\", "/")
        if skip_existing and legacy_ref in existing_refs:
            continue
        if not path.exists():
            manifest["imports"].append(
                {"phase": spec["phase"], "legacy_ref": legacy_ref, "status": "NOT_FOUND"}
            )
            continue
        with open(path, encoding="utf-8") as f:
            verify = json.load(f)
        obs_list = observations_from_verify(
            verify,
            phase=spec["phase"],
            verify_path=path,
            context_size=spec["context_size"],
        )
        ids = [append_observation(obs) for obs in obs_list]
        imported += len(ids)
        manifest["imports"].append(
            {
                "phase": spec["phase"],
                "legacy_ref": legacy_ref,
                "status": "imported",
                "observation_count": len(ids),
                "observation_ids": ids,
            }
        )
        manifest["observation_ids"].extend(ids)

    with open(LEGACY_MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return {"imported": imported, "manifest_path": str(LEGACY_MANIFEST_JSON)}
