"""
CURSOR_VALIDATION: Actor Identity ログの最小確認。
Project Agent 能力測定ではない。
"""
from __future__ import annotations

import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT, bootstrap_repo_root

bootstrap_repo_root()
ROOT = REPO_ROOT

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.is_file():
    PY = Path(sys.executable)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def main() -> int:
    print("EXECUTION_ACTOR=CURSOR_VALIDATION (this script)")
    failures = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        agent_log = tmp_path / "agent.jsonl"
        pipe_log = tmp_path / "pipeline.jsonl"
        cursor_log = tmp_path / "cursor_direct.jsonl"

        # --- A/B: PROJECT_AGENT via agent.py + identity smoke ---
        env = os.environ.copy()
        env["AI_AGENT_EXECUTION_LOG"] = str(agent_log)
        env["AI_AGENT_IDENTITY_SMOKE"] = "1"
        env.setdefault("AI_AGENT_MODEL", "qwen3_8b")
        env.setdefault("OLLAMA_MODELS", r"D:\ollama\models")
        proc = subprocess.run(
            [str(PY), str(ROOT / "agent.py")],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        print("--- agent.py stdout (tail) ---")
        print("\n".join((proc.stdout or "").splitlines()[-20:]))
        if proc.returncode not in (0,):
            # clarity early exit is also informative; smoke needs clarity pass
            print("--- agent.py stderr (tail) ---")
            print("\n".join((proc.stderr or "").splitlines()[-30:]))

        agent_rows = _read_jsonl(agent_log)
        print(f"agent_log_events={len(agent_rows)}")
        actors = {r.get("execution_actor") for r in agent_rows}
        events = {r.get("event") for r in agent_rows}
        print("agent_actors", actors)
        print("agent_events", events)

        if "PROJECT_AGENT" not in actors:
            failures.append("A: PROJECT_AGENT not in agent log")
        if not any(
            r.get("event") == "agent_start" and r.get("entrypoint") == "agent.py"
            for r in agent_rows
        ):
            failures.append("A: agent_start/entrypoint missing")
        if not any(
            r.get("event") == "tool_call"
            and r.get("execution_actor") == "PROJECT_AGENT"
            and r.get("tool_name") == "list_files"
            for r in agent_rows
        ):
            failures.append("B: tool_call list_files missing (clarity may have blocked smoke)")
        if not any(
            r.get("event") == "tool_result"
            and r.get("execution_actor") == "PROJECT_AGENT"
            for r in agent_rows
        ):
            failures.append("B: tool_result missing")

        # --- C: RESEARCH_PIPELINE (REPEAT=0 → no full bench) ---
        env2 = os.environ.copy()
        env2["AI_AGENT_EXECUTION_LOG"] = str(pipe_log)
        env2["AI_AGENT_CREATE_REPEAT"] = "0"
        env2.setdefault("OLLAMA_MODELS", r"D:\ollama\models")
        proc2 = subprocess.run(
            [str(PY), "-m", "research.llm_benchmarks.research_implement"],
            cwd=str(ROOT),
            env=env2,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        print("--- research_implement stdout (tail) ---")
        print("\n".join((proc2.stdout or "").splitlines()[-15:]))
        pipe_rows = _read_jsonl(pipe_log)
        print(f"pipeline_log_events={len(pipe_rows)}")
        if not any(
            r.get("execution_actor") == "RESEARCH_PIPELINE"
            and r.get("event") == "pipeline_start"
            for r in pipe_rows
        ):
            failures.append("C: RESEARCH_PIPELINE pipeline_start missing")
        if any(r.get("execution_actor") == "PROJECT_AGENT" for r in pipe_rows):
            failures.append("C: PROJECT_AGENT leaked into pipeline log")

        # --- D: Cursor direct Tool call must NOT write PROJECT_AGENT to a fresh log ---
        env3 = os.environ.copy()
        env3["AI_AGENT_EXECUTION_LOG"] = str(cursor_log)
        # Direct import call (CURSOR_SHELL / CURSOR_VALIDATION) — no agent logging API
        code = (
            "from tools.file.workspace.list_files import list_files\n"
            "print(list_files(path='registry')['ok'])\n"
        )
        proc3 = subprocess.run(
            [str(PY), "-c", code],
            cwd=str(ROOT),
            env=env3,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        print("--- cursor direct ---", proc3.stdout.strip(), "rc", proc3.returncode)
        cursor_rows = _read_jsonl(cursor_log)
        if cursor_rows:
            failures.append(
                f"D: Cursor direct wrote unexpected identity log: {cursor_rows}"
            )
        else:
            print("D: OK — Cursor direct list_files did not write execution_identity log")

        # Separation: agent log must not contain RESEARCH_PIPELINE
        if any(r.get("execution_actor") == "RESEARCH_PIPELINE" for r in agent_rows):
            failures.append("D: RESEARCH_PIPELINE in agent log")

    if failures:
        print("FAILURES:")
        for item in failures:
            print(" -", item)
        return 1

    print("ALL IDENTITY CHECKS PASSED (CURSOR_VALIDATION only; not capability)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
