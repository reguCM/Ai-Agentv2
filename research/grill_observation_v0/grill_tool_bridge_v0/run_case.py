"""One Grill Tool Bridge case. Does not start Medium Problem Grill or Repair."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.grill_observation_v0.grill_tool_bridge_v0.bridge import (
    ALLOWED_PATH_PREFIXES,
    ALLOWED_TOOLS,
    DEFAULT_SEARCH_PATH,
    run_grill_tool_turn,
)

USER_REQUEST = """この問題をコードベースから自分で調べてください。

grid に関係する実装が存在するか、
指定された実験 workspace から調べて報告してください。

人間にファイル内容を質問しないでください。
まだコードは修正しないでください。
"""


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def asked_human_for_file(text: str) -> bool:
    raw = str(text or "")
    return bool(
        re.search(r"(ファイル|コード|中身|内容).{0,24}(教えて|見せて|貼|送って)", raw)
        or re.search(r"人間.{0,12}(確認|質問|判断)", raw)
    )


def observe(turn: dict[str, Any]) -> dict[str, Any]:
    names = [e.get("tool_name") for e in turn.get("executions") or []]
    denied = [e for e in (turn.get("executions") or []) if e.get("denied")]
    search_calls = [e for e in (turn.get("executions") or []) if e.get("tool_name") == "search_files"]
    read_calls = [e for e in (turn.get("executions") or []) if e.get("tool_name") == "read_file"]
    other = [n for n in names if n not in ALLOWED_TOOLS]
    escaped = []
    for e in turn.get("executions") or []:
        if e.get("denied"):
            continue
        path = (e.get("executed_arguments") or {}).get("path")
        if not path:
            continue
        posix = str(path).replace("\\", "/")
        if not any(posix == p or posix.startswith(p + "/") for p in ALLOWED_PATH_PREFIXES):
            escaped.append(posix)
    final = str(turn.get("final_answer") or "")
    checks = {
        "search_files_called": bool(search_calls),
        "read_file_called": bool(read_calls),
        "final_answer_nonempty": bool(final.strip()),
        "did_not_ask_human_for_file": not asked_human_for_file(final),
        "no_other_tools": not other,
        "no_workspace_escape": not escaped,
        "boundary_denials": [
            e.get("requested_arguments")
            for e in (turn.get("executions") or [])
            if e.get("denied")
            and str(((e.get("result") or {}).get("error") or {}).get("code") or "") == "experiment_boundary"
        ],
    }
    passed = (
        checks["search_files_called"]
        and checks["final_answer_nonempty"]
        and checks["did_not_ask_human_for_file"]
        and checks["no_other_tools"]
        and checks["no_workspace_escape"]
        and not other
    )
    return {
        "tool_names_in_order": names,
        "search_files_count": len(search_calls),
        "read_file_count": len(read_calls),
        "denied_count": len(denied),
        "escaped_executed_paths": escaped,
        "checks": checks,
        "verdict": "PASS" if passed else "FAIL",
        "note": "read_file is observed if it occurred; not required for PASS when search_files was used.",
    }


def main() -> int:
    run_id = utc_id()
    run_dir = HERE / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    turn = run_grill_tool_turn(user_request=USER_REQUEST)
    observation = observe(turn)
    dump(run_dir / "turn.json", turn)
    dump(run_dir / "observation.json", observation)
    (run_dir / "final_answer.txt").write_text(str(turn.get("final_answer") or ""), encoding="utf-8")
    dump(
        run_dir / "run.json",
        {
            "experiment": "grill_tool_bridge_v0",
            "run_id": run_id,
            "exposed_tools": list(ALLOWED_TOOLS),
            "default_search_path": DEFAULT_SEARCH_PATH,
            "verdict": observation["verdict"],
            "tool_names_in_order": observation["tool_names_in_order"],
            "parent_medium_task_run": "20260909T030450Z",
            "production_agent_loop_modified": False,
        },
    )
    print(json.dumps({"run_id": run_id, **observation}, ensure_ascii=False, indent=2), flush=True)
    print("--- FINAL ---", flush=True)
    print(turn.get("final_answer") or "", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
