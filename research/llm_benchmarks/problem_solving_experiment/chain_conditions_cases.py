"""
調査連鎖条件の fixture / 初期入力。

F4 は F2_S1（traceback に helper が出ない）として観測する。
F5 は F2_S3（helper 本文は渡すが config は渡さない）として観測する。

Ground truth は LLM に渡さない。既存成功事例の結果は変更しない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.file.workspace._paths import to_workspace_relative, workspace_root


PROMPT_HEADER = """Analyze the problem below.
Do not fix the problem.
Do not use tools."""

ROOT = Path(__file__).resolve().parent / "fixtures" / "chain_conditions"

FIXTURES = {
    "f1_direct": {
        "error_type": "IndexError",
        "error": "list index out of range",
        "files": ("main.py", "helper.py"),
    },
    "f2_indirect": {
        "error_type": "IndexError",
        "error": "list index out of range",
        "files": ("main.py", "helper.py", "config.py"),
    },
    "f3_multiple": {
        "error_type": "IndexError",
        "error": "list index out of range",
        "files": ("main.py", "helper.py", "validator.py", "config.py"),
    },
    "f6_misleading": {
        "error_type": "KeyError",
        "error": "'cpu'",
        "files": ("main.py", "helper.py", "config.py"),
    },
}

# 全組合せは回さない。差が出やすい条件だけ。
RUN_CASES = (
    {
        "id": "F1_S1",
        "family": "F1",
        "source_level": "S1",
        "fixture": "f1_direct",
        "source_files": (),
        "note": "traceback に helper.py が出る直接参照",
    },
    {
        "id": "F2_S1",
        "family": "F2",
        "source_level": "S1",
        "fixture": "f2_indirect",
        "source_files": (),
        "note": "1段階間接。F4（traceback に参照先が出ない）もこの条件で見る",
    },
    {
        "id": "F2_S2",
        "family": "F2",
        "source_level": "S2",
        "fixture": "f2_indirect",
        "source_files": ("main.py",),
        "note": "main.py 本文で import が見える",
    },
    {
        "id": "F2_S3",
        "family": "F2",
        "source_level": "S3",
        "fixture": "f2_indirect",
        "source_files": ("main.py", "helper.py"),
        "note": "helper 本文あり config なし。F5（次の調査が続くか）",
    },
    {
        "id": "F3_S2",
        "family": "F3",
        "source_level": "S2",
        "fixture": "f3_multiple",
        "source_files": ("main.py",),
        "note": "helper と validator の両方を import",
    },
    {
        "id": "F6_S1",
        "family": "F6",
        "source_level": "S1",
        "fixture": "f6_misleading",
        "source_files": (),
        "note": "KeyError から main 側欠落キー仮説が立ちやすい",
    },
    {
        "id": "F6_S2",
        "family": "F6",
        "source_level": "S2",
        "fixture": "f6_misleading",
        "source_files": ("main.py",),
        "note": "main に load_metrics が見えるが config 値は見えない",
    },
)


def fixture_dir(name):
    return ROOT / name


def fixture_rel_dir(name):
    return to_workspace_relative(fixture_dir(name))


def fixture_rel_files(name):
    spec = FIXTURES[name]
    directory = fixture_dir(name)
    return {
        filename: to_workspace_relative(directory / filename)
        for filename in spec["files"]
    }


def read_fixture_file(name, filename):
    return (fixture_dir(name) / filename).read_text(encoding="utf-8")


def capture_traceback(name):
    spec = FIXTURES[name]
    directory = fixture_dir(name)
    main_py = directory / "main.py"
    completed = subprocess.run(
        [sys.executable, str(main_py)],
        cwd=str(directory),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stderr = (completed.stderr or "").rstrip()
    if spec["error_type"] not in stderr:
        return {
            "ok": False,
            "traceback": "NOT_RECORDED",
            "stderr": stderr,
            "stdout": completed.stdout,
            "returncode": completed.returncode,
        }
    return {
        "ok": True,
        "traceback": stderr,
        "stderr": stderr,
        "stdout": completed.stdout,
        "returncode": completed.returncode,
    }


def failure_for(name):
    spec = FIXTURES[name]
    return {
        "tool_name": name,
        "status": "fail",
        "error_type": spec["error_type"],
        "error": spec["error"],
    }


def build_prompt(case):
    fixture_name = case["fixture"]
    captured = capture_traceback(fixture_name)
    traceback_text = captured["traceback"] if captured["ok"] else "NOT_RECORDED"
    failure = failure_for(fixture_name)
    parts = [
        PROMPT_HEADER,
        "",
        json.dumps(failure, ensure_ascii=False, indent=2),
        "",
        "traceback:",
        traceback_text,
    ]
    for filename in case["source_files"]:
        parts.extend(
            [
                "",
                f"source {filename}:",
                read_fixture_file(fixture_name, filename).rstrip(),
            ]
        )
    prompt = "\n".join(parts) + "\n"
    bodies = {
        filename: read_fixture_file(fixture_name, filename)
        for filename in FIXTURES[fixture_name]["files"]
    }
    leaked = {
        filename: bodies[filename].strip() in prompt
        for filename in bodies
        if filename not in case["source_files"]
    }
    return {
        "case_id": case["id"],
        "family": case["family"],
        "source_level": case["source_level"],
        "fixture": fixture_name,
        "note": case["note"],
        "prompt": prompt,
        "failure": failure,
        "traceback": traceback_text,
        "traceback_capture_ok": captured["ok"],
        "capture": captured,
        "source_files": list(case["source_files"]),
        "fixture_dir": fixture_rel_dir(fixture_name),
        "fixture_files": fixture_rel_files(fixture_name),
        "workspace_root": str(workspace_root()),
        "bodies_leaked_that_should_not": leaked,
        "prompt_header": PROMPT_HEADER,
    }
