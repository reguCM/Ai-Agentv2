"""P2-8: context_limit=16384 + 実行前後 GPU 状態検証（診断専用）。"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.agent_integration.file_tools_integration_verify import file_tools_system_prompt
from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import normalize_arguments
from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.gpu.gpu_processes import get_gpu_processes
from tools.system.gpu.gpu_status import get_gpu_status
from tools.system.llm import chat as ollama_chat

_REPO = Path(__file__).resolve().parents[2]

_WIDE_USER = (
    "Tool Registryで read_file がどこで定義または参照されているか探して、"
    "重要なファイルを1つ選んで内容を確認してください。"
)
_LIST_READ_USER = (
    "tests/fixtures に何があるか確認して、"
    "p2_read_file_sample.txt の内容を読んで説明してください。"
)
_MULTI_READ_USER = (
    "search_files で registry 以下の read_file を検索し、"
    "見つかったファイルを read_file で読んだ後、"
    "続けて registry/tools.json も read_file で読んで要点を説明してください。"
)

_MAIN_RUNS = 5
_FIXED_PAYLOAD_RUNS = 3


def _ollama_version() -> str:
    try:
        r = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=15)
        return (r.stdout or r.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def _ollama_show(model: str) -> str:
    try:
        r = subprocess.run(["ollama", "show", model], capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def _vram_free_mib(status: dict[str, Any]) -> int | None:
    used = status.get("vram_used")
    total = status.get("vram_total")
    if isinstance(used, int) and isinstance(total, int):
        return total - used
    return None


def snapshot_gpu() -> dict[str, Any]:
    """get_gpu_status + get_gpu_processes を実行直前/直後に取得。"""
    status = get_gpu_status()
    processes = get_gpu_processes()
    free = _vram_free_mib(status)
    proc_list = processes.get("processes") or []
    return {
        "gpu_status": status,
        "gpu_processes": processes,
        "gpu_name": status.get("gpu"),
        "vram_total_mib": status.get("vram_total"),
        "vram_used_mib": status.get("vram_used"),
        "vram_free_mib": free,
        "gpu_utilization": status.get("utilization"),
        "gpu_temperature": status.get("temperature"),
        "processes": [
            {
                "pid": p.get("pid"),
                "name": p.get("process_name") or p.get("name"),
                "vram_mib": p.get("used_gpu_memory") or p.get("vram_mib"),
            }
            for p in proc_list
            if isinstance(p, dict)
        ],
        "process_count": len(proc_list),
    }


def _extract_thinking_tool_calls(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for block in re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", text, flags=re.DOTALL):
        block = block.strip()
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                found.append(parsed)
        except json.JSONDecodeError:
            found.append({"raw": block[:500]})
    return found


def classify_round(response: Any) -> dict[str, Any]:
    dump = response.message.model_dump()
    resp_dump = response.model_dump()
    tcs = getattr(response.message, "tool_calls", None) or []
    thinking = str(dump.get("thinking") or "")
    content = str(dump.get("content") or "")
    combined = thinking + content
    tool_names = [tc.function.name for tc in tcs]

    if tcs:
        label = "normal"
        output_type = 1 if "read_file" in tool_names else 2
    elif "<tool_call>" in combined:
        output_type = 4
        label = "type4_thinking_text_tool_call"
    elif content.strip():
        fabricated = (
            "仮想" in content
            or "```python" in content
            or ("def " in content and "read_file" in content.lower())
            or ("read_file" in content.lower() and len(content) > 300)
        )
        output_type = 3
        label = "type3_fabricated" if fabricated else "type3_natural_language"
    else:
        output_type = 5
        label = "empty"

    return {
        "output_type": output_type,
        "output_label": label,
        "native_tool_call_count": len(tcs),
        "native_tool_call_names": tool_names,
        "type3": output_type == 3 and label == "type3_fabricated",
        "type4": output_type == 4,
        "thinking_preview": thinking[:600] if thinking else None,
        "content_preview": content[:400],
        "thinking_tool_calls": _extract_thinking_tool_calls(combined),
        "finish_reason": resp_dump.get("done_reason"),
        "prompt_eval_count": resp_dump.get("prompt_eval_count"),
        "eval_count": resp_dump.get("eval_count"),
        "total_duration_ns": resp_dump.get("total_duration"),
    }


def run_observed_chain(
    user_request: str,
    *,
    scenario_id: str,
    max_rounds: int | None = None,
) -> dict[str, Any]:
    profile = get_llm_profile()
    model = str(profile.get("model") or "")
    pipeline = get_pipeline()
    max_r = max_rounds or int(pipeline.get("max_tool_rounds") or 5)
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    messages: list[Any] = [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {"role": "user", "content": user_request},
    ]

    trace: dict[str, Any] = {
        "scenario_id": scenario_id,
        "user_request": user_request,
        "model": model,
        "context_limit": profile.get("context_limit"),
        "rounds": [],
        "errors": [],
    }
    trace["gpu_before_run"] = snapshot_gpu()
    started = time.perf_counter()

    for round_index in range(max_r):
        round_started = time.perf_counter()
        gpu_pre = snapshot_gpu()
        try:
            response = ollama_chat(model=model, messages=messages, tools=llm_tools)
            err = None
        except Exception as exc:  # noqa: BLE001
            gpu_timeout = snapshot_gpu()
            trace["errors"].append(
                {
                    "round": round_index,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_ms": int((time.perf_counter() - round_started) * 1000),
                    "gpu_at_timeout": gpu_timeout,
                }
            )
            break

        gpu_post = snapshot_gpu()
        classified = classify_round(response)
        tool_calls = getattr(response.message, "tool_calls", None) or []
        messages.append(response.message)

        round_info: dict[str, Any] = {
            "round_index": round_index,
            "elapsed_ms": int((time.perf_counter() - round_started) * 1000),
            "gpu_pre": gpu_pre,
            "gpu_post": gpu_post,
            "timeout": False,
            **classified,
        }

        if not tool_calls:
            trace["final_answer"] = str(getattr(response.message, "content", None) or "")
            trace["rounds"].append(round_info)
            break

        for tc in tool_calls:
            name = tc.function.name
            args = normalize_arguments(tc.function.arguments)
            rec = execute_registry_tool(name, args)
            payload = json.dumps(rec.result, ensure_ascii=False, indent=2)
            round_info["executed_tool"] = name
            round_info["tool_arguments"] = args
            round_info["result_ok"] = rec.ok
            round_info["payload_bytes"] = len(payload.encode("utf-8"))
            if name == "search_files" and isinstance(rec.result, dict):
                round_info["match_count"] = rec.result.get("match_count")
                round_info["truncated"] = rec.result.get("truncated")
            messages.append({"role": "tool", "tool_name": name, "content": payload})

        trace["rounds"].append(round_info)

    trace["total_elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    trace["gpu_after_run"] = snapshot_gpu()
    trace["tool_sequence"] = [r.get("executed_tool") for r in trace["rounds"] if r.get("executed_tool")]
    trace["read_file_after_search"] = (
        "search_files" in trace["tool_sequence"]
        and "read_file" in trace["tool_sequence"]
        and trace["tool_sequence"].index("read_file") > trace["tool_sequence"].index("search_files")
    )
    trace["native_read_file_generated"] = any(
        "read_file" in (r.get("native_tool_call_names") or []) for r in trace["rounds"]
    )
    trace["read_file_executed"] = "read_file" in trace["tool_sequence"]
    trace["any_type3"] = any(r.get("type3") for r in trace["rounds"])
    trace["any_type4"] = any(r.get("type4") for r in trace["rounds"])
    trace["timeout_occurred"] = any(isinstance(e, dict) and "Timeout" in str(e.get("error", "")) for e in trace["errors"])
    return trace


def run_fixed_payload_post_search(search_payload: dict[str, Any], *, run_number: int) -> dict[str, Any]:
    profile = get_llm_profile()
    model = str(profile.get("model") or "")
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    payload = json.dumps(search_payload, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {"role": "user", "content": _WIDE_USER},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "arguments": {"path": ".", "query": "read_file"},
                    },
                }
            ],
        },
        {"role": "tool", "content": payload},
    ]
    started = time.perf_counter()
    gpu_pre = snapshot_gpu()
    try:
        response = ollama_chat(model=model, messages=messages, tools=llm_tools)
        classified = classify_round(response)
        err = None
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.perf_counter() - started) * 1000)
        return {
            "run_number": run_number,
            "timeout": "Timeout" in type(exc).__name__ or "Timeout" in str(exc),
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": elapsed,
            "gpu_pre": gpu_pre,
            "gpu_at_error": snapshot_gpu(),
        }
    gpu_post = snapshot_gpu()
    return {
        "run_number": run_number,
        "scenario": "fixed_50match_payload_post_search",
        "match_count": search_payload.get("match_count"),
        "payload_bytes": len(payload.encode("utf-8")),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "gpu_pre": gpu_pre,
        "gpu_post": gpu_post,
        "timeout": False,
        **classified,
        "native_read_file": "read_file" in (classified.get("native_tool_call_names") or []),
    }


def _summarize_chain_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [
        t
        for t in traces
        if t.get("read_file_after_search")
        and t.get("native_read_file_generated")
        and t.get("read_file_executed")
        and not t.get("any_type3")
        and not t.get("any_type4")
        and not t.get("timeout_occurred")
    ]
    pre_free = [
        t.get("gpu_before_run", {}).get("vram_free_mib")
        for t in traces
        if isinstance(t.get("gpu_before_run", {}).get("vram_free_mib"), int)
    ]
    return {
        "runs_total": len(traces),
        "pass_runs": len(ok),
        "native_read_file_runs": sum(1 for t in traces if t.get("native_read_file_generated")),
        "read_file_executed_runs": sum(1 for t in traces if t.get("read_file_executed")),
        "read_file_after_search_runs": sum(1 for t in traces if t.get("read_file_after_search")),
        "type3_runs": sum(1 for t in traces if t.get("any_type3")),
        "type4_runs": sum(1 for t in traces if t.get("any_type4")),
        "timeout_runs": sum(1 for t in traces if t.get("timeout_occurred")),
        "avg_elapsed_ms": int(sum(t.get("total_elapsed_ms") or 0 for t in traces) / max(len(traces), 1)),
        "avg_vram_free_before_mib": int(sum(pre_free) / len(pre_free)) if pre_free else None,
    }


def main() -> Path:
    profile = get_llm_profile()
    model = str(profile.get("model") or "")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wide_raw = search_files("read_file", path=".")

    out: dict[str, Any] = {
        "task_id": "FILE-TOOLS-CONTEXT-16384-VERIFY-P2-8",
        "timestamp": ts,
        "environment": {
            "ollama_version": _ollama_version(),
            "ollama_show": _ollama_show(model),
            "python": sys.version,
            "platform": platform.platform(),
            "gpu_initial": snapshot_gpu(),
            "llm_profile": profile,
            "api_route": "POST /api/chat (tools.system.llm.chat)",
            "think_setting": "未指定 (None)",
            "context_limit_before_p28": "P2-7 適用後 32768 → 今回 16384",
        },
        "search_payload_inspection": {
            "match_count": wide_raw.get("match_count"),
            "payload_bytes": len(json.dumps(wide_raw, ensure_ascii=False, indent=2).encode("utf-8")),
            "truncated": wide_raw.get("truncated"),
            "error": wide_raw.get("error"),
        },
        "tests": {},
    }

    main_traces: list[dict[str, Any]] = []
    for i in range(1, _MAIN_RUNS + 1):
        print(f"main run {i}/{_MAIN_RUNS}...", flush=True)
        main_traces.append(run_observed_chain(_WIDE_USER, scenario_id=f"p28_main_{i}"))
    out["tests"]["main_search_read_instrumented"] = {
        "runs": _MAIN_RUNS,
        "summary": _summarize_chain_traces(main_traces),
        "traces": main_traces,
    }

    fixed_runs: list[dict[str, Any]] = []
    for i in range(1, _FIXED_PAYLOAD_RUNS + 1):
        print(f"fixed payload run {i}/{_FIXED_PAYLOAD_RUNS}...", flush=True)
        fixed_runs.append(run_fixed_payload_post_search(wide_raw, run_number=i))
    out["tests"]["fixed_large_payload_post_search"] = {
        "runs": _FIXED_PAYLOAD_RUNS,
        "summary": {
            "native_read_file": sum(1 for r in fixed_runs if r.get("native_read_file")),
            "type3": sum(1 for r in fixed_runs if r.get("type3")),
            "type4": sum(1 for r in fixed_runs if r.get("type4")),
            "timeout": sum(1 for r in fixed_runs if r.get("timeout")),
            "avg_elapsed_ms": int(
                sum(r.get("elapsed_ms") or 0 for r in fixed_runs) / max(len(fixed_runs), 1)
            ),
        },
        "runs_detail": fixed_runs,
    }

    list_traces: list[dict[str, Any]] = []
    for i in range(1, 3):
        print(f"list→read run {i}/2...", flush=True)
        list_traces.append(run_observed_chain(_LIST_READ_USER, scenario_id=f"p28_list_read_{i}"))
    out["tests"]["list_then_read"] = {
        "summary": _summarize_chain_traces(list_traces),
        "traces": list_traces,
    }

    multi_traces: list[dict[str, Any]] = []
    for i in range(1, 3):
        print(f"multi read run {i}/2...", flush=True)
        multi_traces.append(run_observed_chain(_MULTI_READ_USER, scenario_id=f"p28_multi_read_{i}"))
    out["tests"]["multi_read_chain"] = {
        "summary": _summarize_chain_traces(multi_traces),
        "traces": multi_traces,
    }

    main_s = out["tests"]["main_search_read_instrumented"]["summary"]
    fixed_s = out["tests"]["fixed_large_payload_post_search"]["summary"]
    gpu_final = snapshot_gpu()

    if (
        main_s["pass_runs"] >= _MAIN_RUNS - 1
        and fixed_s["native_read_file"] >= 2
        and main_s["type3_runs"] == 0
        and main_s["type4_runs"] == 0
        and main_s["timeout_runs"] <= 1
    ):
        verdict = "PASS"
    elif main_s["native_read_file_runs"] >= 1 or fixed_s["native_read_file"] >= 1:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    out["verdict"] = verdict
    out["gpu_final"] = gpu_final

    run_dir = _REPO / "runs" / "ai_tool" / f"{ts}_file_tools_context_16384_verify_p28"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "verify.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Saved:", path)
    print("context_limit:", profile.get("context_limit"))
    print("verdict:", verdict)
    print("main pass:", main_s["pass_runs"], "/", _MAIN_RUNS)
    print("fixed native read_file:", fixed_s["native_read_file"], "/", _FIXED_PAYLOAD_RUNS)
    print("VRAM free (final):", gpu_final.get("vram_free_mib"), "MiB")
    return path


if __name__ == "__main__":
    main()
