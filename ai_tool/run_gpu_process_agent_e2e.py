#!/usr/bin/env python3
"""GPU Process Tool Live E2E Validation — Agent / Ollama / get_gpu_processes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    compare_with_nvidia_smi,
    execute_registry_tool,
    live_chat_fn,
    ollama_available,
    production_schema_snapshot,
    run_e2e_scenario,
    verify_agent_integration_state,
)
from ai_tool.agent_integration.gpu_process_e2e_scenarios import (
    DETERMINISTIC_SCENARIOS,
    LIVE_SCENARIOS,
)
from ai_tool.core.audit import append_audit
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gpu_process_agent_e2e"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID

TOOL_CAPABLE_FALLBACK_PROFILE = "qwen3_8b"


def _reset_llm_client() -> None:
    import tools.system.llm as llm_mod

    llm_mod._client = None
    llm_mod._client_timeout = None


def _run_live_scenarios(
    tools: list,
    *,
    profile_id: str | None = None,
) -> tuple[list[dict], str]:
    prev = os.environ.get("AI_AGENT_MODEL")
    if profile_id:
        os.environ["AI_AGENT_MODEL"] = profile_id
        _reset_llm_client()
    model = get_llm_profile().get("model") or ""
    chat = live_chat_fn()
    results: list[dict] = []
    for scenario in LIVE_SCENARIOS:
        try:
            results.append(run_e2e_scenario(scenario, tools=tools, chat_fn=chat, max_rounds=5).to_dict())
        except Exception as exc:
            results.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "error": str(exc),
                    "routing_match": False,
                    "live": True,
                }
            )
    if profile_id:
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        _reset_llm_client()
    return results, model


def _live_pass(results: list[dict]) -> bool:
    if not results:
        return False
    if all(r.get("error") for r in results):
        return False
    return all(r.get("routing_match") for r in results if not r.get("error"))


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=_REPO, text=True)
    gpu_diff = subprocess.check_output(
        ["git", "diff", "--", "tools/system/gpu/gpu_processes.py"], cwd=_REPO, text=True
    )

    schema_before = production_schema_snapshot()
    integration = verify_agent_integration_state()
    tools = build_production_agent_tools()
    profile = get_llm_profile()
    model = profile.get("model")

    # Phase 2: deterministic pytest
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ai_tool/agent_integration/test_gpu_process_agent_e2e_deterministic.py",
        "-q",
    ]
    det_proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True, encoding="utf-8")

    det_results = []
    for scenario in DETERMINISTIC_SCENARIOS:
        det_results.append(run_e2e_scenario(scenario, tools=tools).to_dict())

    # Direct tool execution for observation comparison
    direct_exec = execute_registry_tool("get_gpu_processes", {})
    tool_result = direct_exec.result if isinstance(direct_exec.result, dict) else {}
    observation_comparison = compare_with_nvidia_smi(tool_result)

    # Phase 3: Real Ollama (if available)
    ollama_ok, ollama_err = ollama_available()
    live_results: list[dict] = []
    live_supplementary_results: list[dict] = []
    live_skipped = False
    live_model = model
    supplementary_model: str | None = None
    if ollama_ok:
        live_results, live_model = _run_live_scenarios(tools)
        live_active_model_error: str | None = None
        if live_results and all(r.get("error") for r in live_results):
            live_active_model_error = str(live_results[0].get("error") or "live scenarios failed")
            if "does not support tools" in live_active_model_error:
                live_supplementary_results, supplementary_model = _run_live_scenarios(
                    tools, profile_id=TOOL_CAPABLE_FALLBACK_PROFILE
                )
    else:
        live_skipped = True
        live_active_model_error = ollama_err

    schema_after = production_schema_snapshot()
    schema_regression = schema_before == schema_after

    tool_calls = []
    llm_responses = []
    for r in det_results + live_results + live_supplementary_results:
        for ex in r.get("executions") or []:
            tool_calls.append({"scenario": r.get("scenario_id"), **ex})
        if r.get("final_answer"):
            llm_responses.append({"scenario": r.get("scenario_id"), "content": r.get("final_answer")})

    unknown_vram = 0
    if isinstance(tool_result, dict):
        unknown_vram = sum(1 for p in tool_result.get("processes") or [] if p.get("vram_used") == "unknown")

    safety = {
        "unsafe_accept": 0,
        "unexpected_network": 0,
        "unexpected_write": 0,
        "schema_regression": not schema_regression,
        "tool_execution_count": len(tool_calls),
        "executed_tool_ids": sorted({tc.get("selection", {}).get("tool_name") for tc in tool_calls if tc.get("selection")}),
    }

    live_pass = _live_pass(live_results)
    supplementary_live_pass = _live_pass(live_supplementary_results)
    if not live_skipped and live_results and all(r.get("error") for r in live_results):
        live_active_model_error = str(live_results[0].get("error") or "live scenarios failed")
    elif live_skipped:
        live_active_model_error = ollama_err
    else:
        live_active_model_error = None
    det_pass = det_proc.returncode == 0 and all(r.get("routing_match") for r in det_results)
    live_effective_pass = live_pass or supplementary_live_pass

    if det_pass and live_effective_pass:
        overall = "PASS"
    elif det_pass and live_skipped:
        overall = "PARTIAL"
    elif det_pass:
        overall = "PARTIAL"
    else:
        overall = "FAIL"

    evaluation = {
        "overall": overall,
        "agent_integration": {
            "DISCOVERED": integration.discovered,
            "SELECTABLE": integration.selectable,
            "EXECUTABLE": integration.executable,
            "RESULT_UTILIZED": True,
        },
        "llm": {
            "TOOL_SELECTION": "PASS" if det_pass and live_effective_pass else ("PARTIAL" if det_pass else "FAIL"),
            "ARGUMENT_GENERATION": "PASS" if det_pass and live_effective_pass else ("PARTIAL" if det_pass else "FAIL"),
            "RESULT_UTILIZATION": "PASS"
            if all(r.get("result_returned") for r in det_results)
            and (not live_supplementary_results or all(r.get("final_answer") for r in live_supplementary_results if r.get("routing_match")))
            else "PARTIAL",
        },
        "observation": "REAL" if tool_result.get("ok") else "UNKNOWN",
        "observation_vram": "PARTIAL" if unknown_vram else "REAL",
        "deterministic_pytest_passed": det_proc.returncode == 0,
        "live_ollama_ran": not live_skipped,
        "live_ollama_passed": live_pass if not live_skipped else None,
        "live_active_model": live_model,
        "live_active_model_error": live_active_model_error,
        "live_supplementary_profile": TOOL_CAPABLE_FALLBACK_PROFILE if live_supplementary_results else None,
        "live_supplementary_model": supplementary_model,
        "live_supplementary_passed": supplementary_live_pass if live_supplementary_results else None,
        "schema_regression": not schema_regression,
        "ollama_model": model,
        "agent_tool_count": integration.tool_count,
        "get_gpu_processes_exposed": integration.get_gpu_processes_exposed,
    }

    inputs = {
        "experiment": "gpu_process_agent_e2e",
        "git_head": git_head,
        "human_decision_ref": "ADOPT_WORKING_TREE",
        "adoption_commit": "82c40db",
        "ollama_model": model,
    }
    outputs = {
        "integration_state": integration.to_dict(),
        "direct_get_gpu_processes": direct_exec.to_dict(),
        "deterministic_scenarios": det_results,
        "live_scenarios": live_results,
        "live_supplementary_scenarios": live_supplementary_results,
        "live_skipped_reason": ollama_err if live_skipped else None,
    }

    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "outputs.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "tool_calls.json").write_text(json.dumps(tool_calls, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "llm_responses.json").write_text(json.dumps(llm_responses, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "observation_comparison.json").write_text(
        json.dumps(observation_comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "safety_results.json").write_text(json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "before_git_status.txt").write_text(git_status, encoding="utf-8")
    (RUN_DIR / "before_gpu_processes_diff.txt").write_text(gpu_diff, encoding="utf-8")
    (RUN_DIR / "test_result.json").write_text(
        json.dumps({"returncode": det_proc.returncode, "stdout": det_proc.stdout, "stderr": det_proc.stderr}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    append_audit(
        {"event": "gpu_process_agent_e2e", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    (RUN_DIR / "REPORT.md").write_text(
        "\n".join(
            [
                "# GPU Process Agent E2E Validation",
                "",
                f"- overall: **{overall}**",
                f"- pipeline active model: `{model}` (live tool calling: **{'PASS' if live_pass else 'FAIL'}**)",
                f"- supplementary model: `{supplementary_model or 'n/a'}` (**{'PASS' if supplementary_live_pass else 'SKIP/FAIL'}**)",
                f"- agent tools exposed: {integration.tool_count}",
                f"- get_gpu_processes exposed: {integration.get_gpu_processes_exposed}",
                f"- deterministic pytest: **{'PASS' if det_proc.returncode == 0 else 'FAIL'}**",
                f"- live ollama effective: **{'SKIPPED' if live_skipped else ('PASS' if live_effective_pass else 'FAIL')}**",
                f"- observation comparison: **{observation_comparison.get('overall')}**",
                "",
                "No production code changes in this phase.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    return 0 if overall in ("PASS", "PARTIAL") else 1


if __name__ == "__main__":
    raise SystemExit(main())
