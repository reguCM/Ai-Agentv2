"""Web Tool Formal Adoption — Implementation Phase run script."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    ollama_available,
    production_schema_snapshot,
)
from ai_tool.agent_integration.production_bridge import get_experimental_agent_exposure
from ai_tool.agent_integration.trial import run_trial_scenario
from ai_tool.agent_integration.trial_scenarios import URL_FETCH_SCENARIO, WEB_SEARCH_SCENARIO

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_formal_adoption_implementation"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID

PYTEST_PATTERNS = [
    "tests/test_general_web_search.py",
    "tests/ai_tool/experimental/test_read_url_text.py",
    "tests/ai_tool/agent_integration/test_production_bridge.py",
    "tests/ai_tool/project_audit/test_web_tool_formal_adoption_implementation.py",
    "tests/ai_tool/project_audit/test_web_tool_formal_adoption_review.py",
    "tests/ai_tool/agent_integration/test_discovery.py",
    "tests/ai_tool/agent_integration/test_hook.py",
    "tests/test_get_cpu_status.py::GetCpuStatusRegistryTests::test_registry_entry_agent_visible",
    "tests/test_gpu_real_observation.py::GpuRealObservationTests::test_registry_marks_gpu_tools_real",
]


def _run_pytest(patterns: list[str]) -> dict:
    cmd = [sys.executable, "-m", "pytest", *patterns, "-q"]
    proc = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, encoding="utf-8")
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _live_e2e(tools: list) -> dict:
    ok, err = ollama_available()
    if not ok:
        return {"status": "SKIP", "reason": err or "ollama unavailable"}
    import os

    from ai_tool.run_gpu_process_agent_e2e import TOOL_CAPABLE_FALLBACK_PROFILE, _run_live_scenarios

    prev = os.environ.get("AI_AGENT_MODEL")
    os.environ["AI_AGENT_MODEL"] = TOOL_CAPABLE_FALLBACK_PROFILE
    try:
        import tools.system.llm as llm_mod

        llm_mod._client = None
        results, model = _run_live_scenarios(tools, profile_id=TOOL_CAPABLE_FALLBACK_PROFILE)
        return {"status": "RUN", "model": model, "results": results}
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}
    finally:
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    git_head_before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=_REPO, text=True, encoding="utf-8")

    tools = build_production_agent_tools()
    tool_names = sorted(t["function"]["name"] for t in tools)
    overlay = get_experimental_agent_exposure().to_dict()
    schema = production_schema_snapshot()

    det_a = run_trial_scenario(WEB_SEARCH_SCENARIO, tools=tools).to_dict()
    det_b = run_trial_scenario(URL_FETCH_SCENARIO, tools=tools).to_dict()
    ssrf = execute_registry_tool("read_url_text", {"url": "http://127.0.0.1/x"}).to_dict()

    pytest_result = _run_pytest(PYTEST_PATTERNS)
    live = _live_e2e(tools)

    evaluation = {
        "phase": "web_tool_formal_adoption_implementation",
        "git_head_before": git_head_before,
        "search_web": {
            "registry": "search_web" in tool_names,
            "agent_schema": "search_web" in tool_names,
            "experimental_overlay": False,
        },
        "read_url_text": {
            "registry": "read_url_text" in tool_names,
            "agent_schema": "read_url_text" in tool_names,
            "experimental_overlay": overlay.get("enabled", False),
        },
        "production_tool_names": tool_names,
        "experimental_overlay": overlay,
        "deterministic_e2e": {"search_only": det_a, "url_fetch": det_b, "ssrf_block": ssrf},
        "pytest_pass": pytest_result["returncode"] == 0,
        "live_llm": live,
        "overall": "COMPLETE" if pytest_result["returncode"] == 0 else "FAIL",
    }

    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, indent=2, ensure_ascii=False), encoding="utf-8")
    (RUN_DIR / "pytest.txt").write_text(pytest_result["stdout"] + pytest_result["stderr"], encoding="utf-8")
    (RUN_DIR / "git_status_before.txt").write_text(git_status, encoding="utf-8")
    (RUN_DIR / "schema_snapshot.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"run_dir": str(RUN_DIR.resolve()), "evaluation": evaluation}, indent=2, ensure_ascii=False))
    return 0 if evaluation["overall"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
