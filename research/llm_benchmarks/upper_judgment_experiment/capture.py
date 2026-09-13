"""実 Failure を保存する。既存実験結果は上書きしない。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.upper_judgment_experiment.execute import (
    build_solver_prompt,
    run_program,
    run_test,
    split_outcomes,
)
from research.llm_benchmarks.upper_judgment_experiment.workspace import copy_fixture


OUT_DIR = Path("research/llm_benchmarks/upper_judgment_experiment/results")


def _now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    fixture_copy = root / "fixture"
    copy_fixture(fixture_copy)
    pytest_run = run_test(fixture_copy)
    program_run = run_program(fixture_copy)
    initial = root / "initial_execution"
    initial.mkdir(parents=True, exist_ok=True)
    save_json(initial / "pytest.json", pytest_run)
    save_json(initial / "python_main.json", program_run)
    (initial / "pytest.stdout.txt").write_text(pytest_run["stdout"], encoding="utf-8")
    (initial / "pytest.stderr.txt").write_text(pytest_run["stderr"], encoding="utf-8")
    (initial / "main.stdout.txt").write_text(program_run["stdout"], encoding="utf-8")
    (initial / "main.stderr.txt").write_text(program_run["stderr"], encoding="utf-8")
    prompt = build_solver_prompt(pytest_run, program_run)
    (root / "SOLVER_PROMPT.txt").write_text(prompt, encoding="utf-8")
    gpt_dir = root / "gpt"
    gpt_dir.mkdir(parents=True, exist_ok=True)
    (gpt_dir / "PROMPT.txt").write_text(prompt, encoding="utf-8")
    save_json(
        gpt_dir / "status.json",
        {
            "live_call": False,
            "reason": "NOT_CONNECTED",
            "detail": "この環境に GPT / OpenAI API 呼び出し経路は無い。PROMPT.txt が GPT へ渡す予定の一次入力。",
            "at": _now(),
        },
    )
    cursor_ws = root / "cursor" / "workspace"
    copy_fixture(cursor_ws)
    save_json(
        root / "run.json",
        {
            "experiment_id": "upper_judgment",
            "fixture_version": "lane_bay_v1",
            "at": _now(),
            "prompt": "この問題を解決してください。",
            "initial_pytest_exit_code": pytest_run["exit_code"],
            "initial_main_exit_code": program_run["exit_code"],
            "outcomes": split_outcomes(pytest_run, program_run),
            "cursor_workspace": str(cursor_ws.resolve()),
            "gpt_live_call": False,
        },
    )
    print(f"wrote {root}", flush=True)
    print(f"cursor_workspace={cursor_ws.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
