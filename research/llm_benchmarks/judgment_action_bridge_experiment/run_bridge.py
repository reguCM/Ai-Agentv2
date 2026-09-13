"""LLM なしで橋渡しを実測する。既存実験には接続しない。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.judgment_action_bridge_experiment.bridge import parse_judgment
from research.llm_benchmarks.judgment_action_bridge_experiment.execute import run_scripted
from research.llm_benchmarks.judgment_action_bridge_experiment.workspace import (
    copy_fixture,
    git_init_workspace,
    run_program,
    run_test,
    workspace_filenames,
)


OUT_DIR = Path("research/llm_benchmarks/judgment_action_bridge_experiment/results")
KNOWN = ["main.py", "helper.py", "config.py", "tests/test_main.py"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_parse(text):
    parsed = parse_judgment(text, KNOWN)
    parsed["timestamp"] = _now()
    return parsed


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUT_DIR / stamp
    workspace = copy_fixture(root / "workspace")
    git_init_workspace(workspace)
    pytest_run = run_test(workspace)
    program_run = run_program(workspace)
    phases = {
        "phase1_single": record_parse("helper.pyを確認したい"),
        "phase2_multiple": record_parse("helper.pyを確認したい。その後Testを実行したい。"),
        "phase3_targets": [
            record_parse("helper.pyの中身を確認したい"),
            record_parse("main.pyを読んでからhelper.pyを確認したい"),
            record_parse("config.pyを調べる必要がある"),
            record_parse("このファイルを調べてからTestしたい"),
        ],
        "phase4_no_false_tools": record_parse(
            "helper.pyを確認したい。\n"
            "Testについてはまだ実行しない。\n"
            "パッチ内にはREADYという文字列がある。\n"
            "```python\n"
            "def test_ready():\n"
            "    # READ\n"
            "    # TEST\n"
            "    # READY\n"
            "```\n"
        ),
        "phase5_ambiguous": [
            record_parse("ちょっと確認したい"),
            record_parse("原因を調べる必要がある"),
            record_parse("この辺を見てください"),
        ],
        "phase6_candidates": record_parse("helper.pyを調査したい"),
    }
    helper_parsed = parse_judgment("helper.pyを確認したい", workspace_filenames(workspace) or KNOWN)
    helper_exec = run_scripted(workspace, helper_parsed["selected_actions"])
    config_parsed = parse_judgment("config.pyを確認したい", KNOWN)
    config_exec = run_scripted(workspace, config_parsed["selected_actions"])
    patch1 = parse_judgment(
        "config.py を修正する。\nconfig.py\n```python\nFIELD_COUNT = 3\nREADY = False\n```\n",
        KNOWN,
    )
    patch1_exec = run_scripted(workspace, patch1["selected_actions"])
    mid_test = run_test(workspace)
    patch2 = parse_judgment(
        "config.py を修正する。\nconfig.py\n```python\nFIELD_COUNT = 3\nREADY = True\n```\n",
        KNOWN,
    )
    patch2_exec = run_scripted(workspace, patch2["selected_actions"])
    final_test = run_test(workspace)
    final_program = run_program(workspace)
    payload = {
        "experiment_id": "judgment_action_bridge",
        "at": _now(),
        "llm_used": False,
        "existing_mapping": "not_used",
        "fixture": "fixtures/chain_count",
        "initial_pytest": pytest_run,
        "initial_program": program_run,
        "phases": phases,
        "loop": {
            "read_helper": helper_exec,
            "read_config": config_exec,
            "patch_partial": patch1_exec,
            "test_after_partial": mid_test,
            "patch_full": patch2_exec,
            "test_after_full": final_test,
            "program_after_full": final_program,
        },
        "flags": {
            "judgment_received": phases["phase1_single"]["judgment_received"],
            "action_extracted": phases["phase1_single"]["action_extracted"],
            "tool_selected": phases["phase1_single"]["tool_selected"],
            "multiple_actions": len(phases["phase2_multiple"]["selected_actions"]) == 2,
            "false_run_test": any(
                item["tool_name"] == "run_test"
                for item in phases["phase4_no_false_tools"]["selected_actions"]
            ),
            "ambiguous_stopped": all(
                not item["selected_actions"] for item in phases["phase5_ambiguous"]
            ),
            "loop_test_pass": final_test.get("exit_code") == 0,
            "loop_mid_fail": mid_test.get("exit_code") != 0,
        },
    }
    save_json(root / "run.json", payload)
    print(f"wrote {root}", flush=True)
    print(json.dumps(payload["flags"], ensure_ascii=False), flush=True)
    return root


if __name__ == "__main__":
    main()
