"""
別ファイル参照の調査連鎖用 fixture。

Ground truth（LLM には渡さない）:
- 例外は main.run の rows[2]
- rows は helper.load_rows() が返す
- load_rows は config.STATUS_LABELS[:FIELD_COUNT]
- FIELD_COUNT は 2、STATUS_LABELS は 3 要素

初期入力に helper.py / config.py の内容は含めない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.file.workspace._paths import to_workspace_relative, workspace_root


CASE_ID = "cross_file_index_error"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cross_file_index_error"
MAIN_PY = FIXTURE_DIR / "main.py"
HELPER_PY = FIXTURE_DIR / "helper.py"
CONFIG_PY = FIXTURE_DIR / "config.py"

PROMPT_HEADER = """Analyze the problem below.

Do not fix the problem yet."""

FAILURE = {
    "tool_name": CASE_ID,
    "status": "fail",
    "error_type": "IndexError",
    "error": "list index out of range",
}


def fixture_rel_dir():
    return to_workspace_relative(FIXTURE_DIR)


def fixture_rel_files():
    return {
        "main.py": to_workspace_relative(MAIN_PY),
        "helper.py": to_workspace_relative(HELPER_PY),
        "config.py": to_workspace_relative(CONFIG_PY),
    }


def capture_traceback():
    completed = subprocess.run(
        [sys.executable, str(MAIN_PY)],
        cwd=str(FIXTURE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stderr = (completed.stderr or "").rstrip()
    if "IndexError" not in stderr:
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


def build_initial_prompt():
    captured = capture_traceback()
    traceback_text = captured["traceback"] if captured["ok"] else "NOT_RECORDED"
    prompt = (
        PROMPT_HEADER
        + "\n\n"
        + json.dumps(FAILURE, ensure_ascii=False, indent=2)
        + "\n\ntraceback:\n"
        + traceback_text
        + "\n"
    )
    helper_src = HELPER_PY.read_text(encoding="utf-8")
    config_src = CONFIG_PY.read_text(encoding="utf-8")
    return {
        "case_id": CASE_ID,
        "prompt": prompt,
        "failure": FAILURE,
        "traceback": traceback_text,
        "traceback_capture_ok": captured["ok"],
        "capture": captured,
        "fixture_dir": fixture_rel_dir(),
        "fixture_files": fixture_rel_files(),
        "workspace_root": str(workspace_root()),
        "helper_leaked_in_prompt": helper_src.strip() in prompt,
        "config_leaked_in_prompt": config_src.strip() in prompt,
    }
