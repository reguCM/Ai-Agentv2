"""
PROJECT_AGENT capability_route ログ収集ランナー。

- 通常の対話利用でも logs/capability_route.jsonl に溜まる（本スクリプト必須ではない）
- 意図的な多様ケースを非対話で回すときに使う
- AI_AGENT_TOOL_GATE=off は使わない（収集用 trust で公開Toolを昇格）
- Clarity は収集時のみ AI_AGENT_SKIP_CLARITY=1
- Pipeline は起動しない

例:
  .venv\\Scripts\\python.exe research/llm_benchmarks/capability_route_cases/run_collection.py
  .venv\\Scripts\\python.exe research/llm_benchmarks/capability_route_cases/run_collection.py --only web_unneeded_cpu
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "cases.json"
COLLECTION_TRUST = ROOT / "registry" / "agent_tool_trust.collection.json"


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_cases(cases_path: Path) -> list[dict]:
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    return list(data.get("cases") or [])


def run_case(
    case: dict,
    *,
    out_dir: Path,
    python_exe: str,
    timeout_sec: int,
) -> dict:
    case_id = str(case.get("id") or "case")
    category = str(case.get("category") or "")
    group_id = str(case.get("group_id") or "").strip()
    request = str(case.get("request") or "").strip()
    case_dir = out_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    cap_log = case_dir / "capability_route.jsonl"
    id_log = case_dir / "execution_identity.jsonl"
    stdout_path = case_dir / "stdout.txt"
    meta_path = case_dir / "meta.json"

    env = os.environ.copy()
    env["AI_AGENT_USER_REQUEST"] = request
    env["AI_AGENT_SKIP_CLARITY"] = "1"
    env["AI_AGENT_TOOL_TRUST"] = str(COLLECTION_TRUST)
    env.pop("AI_AGENT_TOOL_GATE", None)
    # pre_web_answer_candidate を取得する（スキップしない）
    env.pop("AI_AGENT_SKIP_PRE_WEB", None)
    env["AI_AGENT_CAPABILITY_ROUTE_LOG"] = str(cap_log)
    env["AI_AGENT_EXECUTION_LOG"] = str(id_log)
    env["AI_AGENT_COLLECTION_CASE_ID"] = case_id
    env["AI_AGENT_COLLECTION_CATEGORY"] = category
    if group_id:
        env["AI_AGENT_COLLECTION_GROUP_ID"] = group_id
    else:
        env.pop("AI_AGENT_COLLECTION_GROUP_ID", None)
    env.pop("AI_AGENT_IDENTITY_SMOKE", None)

    meta = {
        "case": case,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "env": {
            "AI_AGENT_SKIP_CLARITY": "1",
            "AI_AGENT_TOOL_TRUST": str(COLLECTION_TRUST),
            "AI_AGENT_CAPABILITY_ROUTE_LOG": str(cap_log),
            "note": "AI_AGENT_TOOL_GATE=off not used",
        },
    }
    proc = subprocess.run(
        [python_exe, str(ROOT / "agent.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
    )
    stdout_path.write_text(
        (proc.stdout or "") + "\n--- STDERR ---\n" + (proc.stderr or ""),
        encoding="utf-8",
    )
    meta["exit_code"] = proc.returncode
    meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    meta["capability_route_log_exists"] = cap_log.is_file()
    meta["capability_route_lines"] = (
        len(cap_log.read_text(encoding="utf-8").splitlines()) if cap_log.is_file() else 0
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect capability_route logs via PROJECT_AGENT")
    parser.add_argument("--only", action="append", default=[], help="case id (repeatable)")
    parser.add_argument(
        "--cases",
        default=None,
        help="path to cases.json (default: sibling cases.json or dataset v0)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory",
    )
    parser.add_argument("--timeout", type=int, default=900, help="per-case timeout seconds")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="python executable (default: current)",
    )
    args = parser.parse_args(argv)

    cases_path = Path(args.cases) if args.cases else DEFAULT_CASES_PATH
    if not cases_path.is_file():
        alt = (
            ROOT
            / "research"
            / "llm_benchmarks"
            / "capability_route_dataset"
            / "v0"
            / "cases.json"
        )
        if alt.is_file():
            cases_path = alt
        else:
            print(f"cases not found: {cases_path}", file=sys.stderr)
            return 2

    cases = load_cases(cases_path)
    if args.only:
        wanted = set(args.only)
        cases = [c for c in cases if c.get("id") in wanted]
        missing = wanted - {c.get("id") for c in cases}
        if missing:
            print(f"unknown case ids: {sorted(missing)}", file=sys.stderr)
            return 2

    out_dir = Path(args.out) if args.out else (
        ROOT
        / "research"
        / "llm_benchmarks"
        / "capability_route_dataset"
        / "v0"
        / "results"
        / f"run_{_now_tag()}"
    )
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cases_snapshot.json").write_text(
        cases_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = {
        "out_dir": str(out_dir),
        "cases_path": str(cases_path),
        "results": [],
    }
    print(f"collection out_dir={out_dir}")
    print(f"cases_path={cases_path} count={len(cases)}")
    for case in cases:
        print(f"\n=== case {case.get('id')} ({case.get('category')}) ===")
        print(f"request: {case.get('request')}")
        try:
            meta = run_case(
                case,
                out_dir=out_dir,
                python_exe=args.python,
                timeout_sec=args.timeout,
            )
        except subprocess.TimeoutExpired:
            meta = {
                "case": case,
                "exit_code": -1,
                "error": "timeout",
            }
            print("TIMEOUT", file=sys.stderr)
        summary["results"].append(
            {
                "id": case.get("id"),
                "category": case.get("category"),
                "group_id": case.get("group_id"),
                "exit_code": meta.get("exit_code"),
                "capability_route_lines": meta.get("capability_route_lines"),
                "error": meta.get("error"),
            }
        )
        print(
            f"exit={meta.get('exit_code')} lines={meta.get('capability_route_lines')}"
        )

    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nsummary: {summary_path}")
    return 0 if all((r.get("exit_code") == 0) for r in summary["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
