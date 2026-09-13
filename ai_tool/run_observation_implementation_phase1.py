"""Observation Tool Implementation Phase 1 — validation run (no unrelated file changes)."""
from __future__ import annotations

import json
import platform
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
    ollama_available,
    production_schema_snapshot,
    run_e2e_scenario,
    verify_agent_integration_state,
)
from ai_tool.agent_integration.gpu_process_e2e_scenarios import (
    DETERMINISTIC_SCENARIOS,
    LIVE_SCENARIOS,
    LIVE_SCENARIO_E,
)
from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_observation_implementation_phase1"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def _run_pytest(patterns: list[str]) -> dict:
    cmd = [sys.executable, "-m", "pytest", *patterns, "-q"]
    proc = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, encoding="utf-8")
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=_REPO, text=True, encoding="utf-8")

    integration = verify_agent_integration_state()
    tools = build_production_agent_tools()
    schema = production_schema_snapshot()

    pytest_result = _run_pytest(
        [
            "tests/test_get_cpu_status.py",
            "tests/test_gpu_real_observation.py",
            "tests/test_llm_tool_capability.py",
            "tests/ai_tool/agent_integration/test_observation_agent_e2e_deterministic.py",
            "tests/ai_tool/agent_integration/test_gpu_process_agent_e2e_deterministic.py",
        ]
    )

    det_results = [run_e2e_scenario(s, tools=tools).to_dict() for s in DETERMINISTIC_SCENARIOS]

    gpu_status = execute_registry_tool("get_gpu_status", {}).to_dict()
    gpu_proc = execute_registry_tool("get_gpu_processes", {}).to_dict()
    cpu_new = execute_registry_tool("get_cpu_status", {}).to_dict()
    cpu_legacy = execute_registry_tool("cpu_status", {}).to_dict()

    obs_compare = compare_with_nvidia_smi(gpu_proc.get("result") or {})

    ollama_ok, ollama_err = ollama_available()
    live_results: list[dict] = []
    live_supplementary: list[dict] = []
    live_model: str | None = None
    supplementary_model: str | None = None
    if ollama_ok:
        from ai_tool.run_gpu_process_agent_e2e import (
            TOOL_CAPABLE_FALLBACK_PROFILE,
            _run_live_scenarios,
        )

        live_results, live_model = _run_live_scenarios(tools)
        if live_results and all(r.get("error") for r in live_results):
            err = str(live_results[0].get("error") or "")
            if "does not support tools" in err:
                live_supplementary, supplementary_model = _run_live_scenarios(
                    tools, profile_id=TOOL_CAPABLE_FALLBACK_PROFILE
                )

    stub_left = "RTX 3060" in Path(_REPO / "tools/system/gpu/gpu_status.py").read_text(encoding="utf-8")

    evaluation = {
        "phase": "observation_implementation_phase1",
        "overall": "COMPLETE" if pytest_result["returncode"] == 0 and not stub_left else "FAILED",
        "pytest_pass": pytest_result["returncode"] == 0,
        "gpu_status_stub_removed": not stub_left,
        "agent_tools": sorted(t["function"]["name"] for t in tools),
        "integration": integration.to_dict(),
        "live_ollama_ran": ollama_ok,
        "live_scenario_count": len(live_results),
        "live_supplementary_scenario_count": len(live_supplementary),
        "live_supplementary_routing_pass": all(
            r.get("routing_match") for r in live_supplementary if not r.get("error")
        )
        if live_supplementary
        else None,
        "human_review_applied": ["HR-1", "HR-2", "HR-4", "HR-5", "HR-6", "HR-7"],
        "deferred": ["HR-3 gpu_uuid", "cpu_temperature"],
    }

    report = {
        "git_head": git_head,
        "platform": platform.platform(),
        "schema_snapshot_keys": sorted(schema.keys()),
        "direct_executions": {
            "get_gpu_status": gpu_status,
            "get_gpu_processes": gpu_proc,
            "get_cpu_status": cpu_new,
            "cpu_status": cpu_legacy,
        },
        "deterministic_e2e": det_results,
        "live_e2e": live_results,
        "live_supplementary_e2e": live_supplementary,
        "live_model": live_model,
        "supplementary_model": supplementary_model,
        "observation_comparison_gpu_processes": obs_compare,
        "pytest": pytest_result,
        "evaluation": evaluation,
    }

    (RUN_DIR / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "git_state.txt").write_text(f"HEAD: {git_head}\n\n{git_status}", encoding="utf-8")
    append_audit({"event": "observation_implementation_phase1", "run_dir": str(RUN_DIR), "evaluation": evaluation}, log_path=RUN_DIR / "audit.jsonl")

    payload = json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    return 0 if evaluation["overall"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
