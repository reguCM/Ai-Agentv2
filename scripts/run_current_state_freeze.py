#!/usr/bin/env python3
"""Read-only current-state freeze run — inventories HEAD, runs tests, writes run artifacts."""
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

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_current_state_freeze"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID

FREEZE_TESTS = [
    "tests/ai_tool/agent_integration/test_observation_agent_e2e_deterministic.py",
    "tests/ai_tool/agent_integration/test_gpu_process_agent_e2e_deterministic.py",
    "tests/ai_tool/agent_integration/test_production_bridge.py",
    "tests/test_get_cpu_status.py",
    "tests/test_gpu_real_observation.py",
    "tests/test_llm_tool_capability.py",
    "tests/ai_tool/tool_creation/test_observation_spec_v2_draft.py",
]


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=_REPO, text=True, encoding="utf-8").strip()


def _registry_inventory() -> dict:
    data = json.loads((_REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    tools = data.get("tools") or []
    agent = [t for t in tools if t.get("visibility") == "agent"]
    return {
        "total_registry_tools": len(tools),
        "agent_visible": [
            {
                "name": t["name"],
                "module": t.get("module"),
                "observation_source": t.get("observation_source"),
            }
            for t in agent
        ],
        "agent_visible_names": sorted(t["name"] for t in agent),
    }


def _agent_inventory() -> dict:
    from ai_tool.agent_integration.gpu_process_e2e import (
        build_production_agent_tools,
        verify_agent_integration_state,
    )
    from ai_tool.agent_integration.production_bridge import (
        enabled_experimental_tool_ids,
        experimental_read_url_enabled,
    )

    tools = build_production_agent_tools()
    names = sorted(t["function"]["name"] for t in tools)
    exp_names = [
        t["function"]["name"]
        for t in tools
        if (t.get("_agent_meta") or {}).get("experimental_agent_tool")
    ]

    return {
        "ollama_tool_count": len(tools),
        "ollama_tool_names": names,
        "registry_agent_tools": [n for n in names if n not in exp_names],
        "experimental_overlay_tools": exp_names,
        "experimental_catalog_ids": enabled_experimental_tool_ids(),
        "read_url_overlay_enabled": experimental_read_url_enabled(),
        "integration_state": verify_agent_integration_state().to_dict(),
    }


def _tool_contract_probe() -> dict:
    import importlib

    probes: dict = {}
    try:
        gs = importlib.import_module("tools.system.gpu.gpu_status").get_gpu_status()
        probes["get_gpu_status"] = {
            "ok": gs.get("ok"),
            "keys": sorted(gs.keys()),
            "has_stub_rtx3060": gs.get("gpu") == "RTX 3060" and gs.get("temperature") == 60,
            "observation_source": gs.get("observation_source"),
        }
    except Exception as exc:  # noqa: BLE001
        probes["get_gpu_status"] = {"error": str(exc)}

    try:
        gp = importlib.import_module("tools.system.gpu.gpu_processes").get_gpu_processes()
        procs = gp.get("processes") or []
        probes["get_gpu_processes"] = {
            "ok": gp.get("ok"),
            "process_count": len(procs),
            "vram_unknown_count": sum(1 for p in procs if p.get("vram_used") == "unknown"),
        }
    except Exception as exc:  # noqa: BLE001
        probes["get_gpu_processes"] = {"error": str(exc)}

    try:
        cs = importlib.import_module("tools.system.cpu.cpu_status").cpu_status()
        probes["cpu_status"] = {"keys": sorted(cs.keys()), "legacy_status_only": list(cs.keys()) == ["status"]}
    except Exception as exc:  # noqa: BLE001
        probes["cpu_status"] = {"error": str(exc)}

    try:
        ncs = importlib.import_module("tools.system.cpu.get_cpu_status").get_cpu_status()
        probes["get_cpu_status"] = {
            "ok": ncs.get("ok"),
            "keys": sorted(ncs.keys()),
            "temperature_field": "temperature" in ncs,
        }
    except Exception as exc:  # noqa: BLE001
        probes["get_cpu_status"] = {"error": str(exc)}

    return probes


def _safety_inventory() -> dict:
    return {
        "agent_tool_gate": "tools/system/agent_tool_gate.py — default require_confirm",
        "observation_tools_network": False,
        "observation_tools_local_subprocess_only": True,
        "experimental_read_url_ssrf_boundary": "catalog entry + production_bridge (88febb3)",
        "capability_route_obs": "observation_only — does not authorize execution",
        "note": "No new safety features in this freeze phase",
    }


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    status = _git("status", "--short")
    staged = _git("diff", "--cached", "--name-only")

    pytest_cmd = [sys.executable, "-m", "pytest", *FREEZE_TESTS, "-q"]
    pytest_proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True, encoding="utf-8")

    registry_inv = _registry_inventory()
    agent_inv = _agent_inventory()
    tool_probe = _tool_contract_probe()
    safety = _safety_inventory()

    stub_detected = tool_probe.get("get_gpu_status", {}).get("has_stub_rtx3060") is True
    tests_pass = pytest_proc.returncode == 0
    agent_registry_match = set(registry_inv["agent_visible_names"]).issubset(
        set(agent_inv["registry_agent_tools"])
    )

    stop_reasons: list[str] = []
    if stub_detected:
        stop_reasons.append("get_gpu_status FIXED_STUB detected")
    if not tests_pass:
        stop_reasons.append("freeze tests failed")
    if not agent_registry_match:
        stop_reasons.append("registry agent tools not subset of ollama schema")

    evaluation = {
        "phase": "development_reentry_freeze",
        "overall": "COMPLETE" if not stop_reasons else "STOP",
        "stop_reasons": stop_reasons,
        "git_head": head,
        "git_branch": branch,
        "pytest_pass": tests_pass,
        "pytest_count": pytest_proc.stdout.strip().split()[-2] if "passed" in pytest_proc.stdout else None,
        "gpu_stub_removed": not stub_detected,
        "registry_agent_tools": registry_inv["agent_visible_names"],
        "experimental_overlay": agent_inv["experimental_overlay_tools"],
    }

    report = {
        "git": {"head": head, "branch": branch},
        "platform": platform.platform(),
        "registry_inventory": registry_inv,
        "agent_inventory": agent_inv,
        "tool_contract_probe": tool_probe,
        "safety_inventory": safety,
        "environment": {
            "verified_on_audit_host": "Windows + NVIDIA + nvidia-smi + PowerShell CIM",
            "linux": "UNKNOWN",
            "amd_gpu": "UNKNOWN",
            "intel_gpu": "UNKNOWN",
            "multi_gpu": "UNKNOWN",
            "cpu_temperature": "UNSUPPORTED via current CIM path",
        },
        "pytest": {
            "returncode": pytest_proc.returncode,
            "stdout": pytest_proc.stdout,
            "stderr": pytest_proc.stderr,
            "suites": FREEZE_TESTS,
        },
        "evaluation": evaluation,
    }

    (RUN_DIR / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "git_state.txt").write_text(
        f"HEAD: {head}\nbranch: {branch}\n\nstaged:\n{staged or '(none)'}\n\nstatus:\n{status}",
        encoding="utf-8",
    )
    (RUN_DIR / "registry_inventory.json").write_text(
        json.dumps(registry_inv, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "agent_inventory.json").write_text(
        json.dumps(agent_inv, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "safety_inventory.json").write_text(
        json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "audit.jsonl").write_text(
        json.dumps({"event": "current_state_freeze", "run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    payload = json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    return 0 if not stop_reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
