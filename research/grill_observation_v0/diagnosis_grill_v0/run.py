"""Diagnosis Grill Observation v0.

Reuses Grill Tool Bridge v0. Does not modify Production or the Bridge.
Cursor does not invent causes or repairs.
"""
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

from research.grill_observation_v0.grill_tool_bridge_v0.bridge import run_grill_tool_turn

SOURCE_RUN = (
    ROOT
    / "research"
    / "grill_observation_v0"
    / "medium_task_reality_v0"
    / "runs"
    / "20260909T030450Z"
)
MAX_STEPS = 10  # Observer safety cap. Never sent to the LLM.

# Observer-only. Never included in prompts.
COMPLETE_PATTERNS = [
    r"これ以上確認する必要がなさそう",
    r"もう確認すべき.{0,12}(ない|なさそう|ありません)",
    r"追加で確認する必要はなさそう",
    r"原因は十分",
    r"修正対象は十分明確",
    r"追加調査なし",
    r"診断を終了",
    r"修正へ進(める|んでよい|んで良い)",
    r"未解決点は残っていない",
    r"このScopeではもう診断",
]
HUMAN_PATTERNS = [
    r"(質問|聞かせて|教えてください|どちらにしますか)",
]

PRINCIPLES = """原則:
1. 問題を修正可能な状態まで理解するため、まだ確認すべきことを1つずつ確認する。
2. 一度に扱う未解決点・確認事項は1つにする。
3. コードベース、Test、既存資料から分かることは人間へ聞かず、search_files / read_file で自分で調べる。
人間へ質問する場合のみ、推奨回答も付ける。
コード生成・Patch・修正・Test修正には進まない。
存在しないものは「現在は存在しない」と事実確認し、自由な新規作成許可とは解釈しない。
仮仕様・実験中・構想を確定済み設計として扱わない。
"""

OPENING = """この問題を修正できる状態まで整理したいです。

まだ確認すべきことを1つずつ確認してください。

コードベースやTestから分かることは、
search_files / read_file を使って
自分で確認してください。

本当に人間の判断が必要なことだけ質問してください。

原因と修正対象が十分明確になり、
これ以上確認する必要がなさそうだと判断したら、
そのことを教えてください。

まだコードは修正しないでください。
"""


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def start_facts() -> list[dict[str, Any]]:
    """Starting observations from the source run. No added causal claims."""
    return [
        {
            "text": "Medium Task name=ScoreIntegration purpose=ラインクリア後のスコア加算処理の統合",
            "source": "medium_task.json",
            "status": "experimental",
        },
        {
            "text": "Gap name=ScoreDependencyGap",
            "source": "medium_task.json",
            "status": "experimental",
        },
        {
            "text": "Local-Implementer は qwen3:14b。Cursor はゲームコードを修正していない。",
            "source": "run.json",
            "status": "experimental",
        },
        {
            "text": "recheck=BLOCKED。test_passed=false。Test collection で失敗。",
            "source": "run.json / phase6_test.json / phase7_recheck.json",
            "status": "experimental",
        },
        {
            "text": "ModuleNotFoundError: No module named 'workspace'",
            "source": "phase6_test.json",
            "status": "experimental",
        },
        {
            "text": "Test は from workspace.window_loop import update, grid, score としている。",
            "source": "tests/test_medium_task_v0.py / phase6_test.json",
            "status": "experimental",
        },
        {
            "text": "開始観測: window_loop.py には想定された module-level grid / score が存在しない。",
            "source": "開始時点の観測事実（workspace/window_loop.py）",
            "status": "experimental",
        },
        {
            "text": "Minimum Focus は line_clear。allowed_write は workspace/window_loop.py と tests/test_medium_task_v0.py。ずれが観測されている。",
            "source": "focus.json / run.json",
            "status": "experimental",
        },
        {
            "text": "Expected Map / Reviewed Expected Map / Actual Map は Planner・Reviewer・AST実測の実験成果物。確定設計ではない。",
            "source": "expected_map_v0.json / reviewed_expected_map.json / actual_map_before.json",
            "status": "experimental",
        },
        {
            "text": "確定Technical Specification は natural-exit 由来のテトリス仕様（この実験系列の正本仕様）。",
            "source": "technical_specification.txt",
            "status": "confirmed_for_this_experiment_series",
        },
    ]


def min_context() -> str:
    return """# 資料Status
- technical_specification.txt: confirmed_for_this_experiment_series
- Expected Map / Reviewed Expected Map / Medium Task / Gap: experimental（LLM生成）
- Actual Map: experimental（workspace AST実測）
- focus.json note: provisional observer heuristic
- Grill Tool Bridge / 本診断: experimental。Production 非依存。

# 調査可能なコード/Test（search_files / read_file）
- research/grill_observation_v0/medium_task_reality_v0/workspace
- research/grill_observation_v0/medium_task_reality_v0/tests
- 同Runの workspace_after / workspace_before

# 開始時に渡したRun成果物の場所（Tool境界外。必要なら質問せず、次StepでHarnessが抜粋を足す）
- research/grill_observation_v0/medium_task_reality_v0/runs/20260909T030450Z/
"""


def render_facts(facts: list[dict[str, Any]]) -> str:
    lines = []
    for i, fact in enumerate(facts, 1):
        status = fact.get("status") or "unknown"
        source = fact.get("source") or ""
        lines.append(f"{i}. [{status}] {fact.get('text')} (source: {source})")
    return "\n".join(lines) if lines else "(none)"


def build_user(*, step: int, facts: list[dict[str, Any]], remaining: str, extra_context: str) -> str:
    parts = [PRINCIPLES]
    if step == 1:
        parts.append(OPENING)
    parts.extend(
        [
            "# 現在までに確認済みの事実",
            render_facts(facts),
            "",
            "# 現在残っている未解決点",
            remaining,
            "",
            "# 今回必要な最小Context",
            min_context(),
        ]
    )
    if extra_context.strip():
        parts.extend(["", "# 追加の最小抜粋", extra_context.strip()])
    parts.extend(
        [
            "",
            "今、次に確認する必要があることを1つだけ選んでください。",
            "コード/Testから分かるなら search_files / read_file を使ってください。",
            "まだコードは修正しないでください。",
        ]
    )
    return "\n".join(parts)


def classify(raw: str) -> dict[str, Any]:
    text = str(raw or "")
    complete_hits = [p for p in COMPLETE_PATTERNS if re.search(p, text)]
    humanish = bool(
        any(re.search(p, text) for p in HUMAN_PATTERNS) and re.search(r"[？?]", text)
    )
    still_next = bool(re.search(r"次に(確認|調べ|見る|見る必要)", text))
    if complete_hits and not still_next:
        kind = "DIAGNOSIS_COMPLETE"
    elif humanish:
        kind = "HUMAN_QUESTION"
    else:
        kind = "CONTINUE"
    return {"kind": kind, "complete_hits": complete_hits, "humanish": humanish, "still_next": still_next}


def lookupable_human_question(raw: str) -> bool:
    text = str(raw or "")
    if re.search(r"(好み|新しい仕様|新しい要求|価値判断|どちらが望ましいか)", text):
        return False
    return True


def facts_from_executions(executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for exe in executions:
        name = exe.get("tool_name")
        args = exe.get("executed_arguments") or {}
        result = exe.get("result") if isinstance(exe.get("result"), dict) else {}
        if name == "search_files":
            matches = result.get("matches") or []
            paths = sorted({str(m.get("path") or "") for m in matches if m.get("path")})
            out.append(
                {
                    "text": (
                        f"search_files query={args.get('query')!r} path={args.get('path')!r} "
                        f"match_count={result.get('match_count')} files={paths}"
                    ),
                    "source": "tool:search_files",
                    "status": "experimental",
                }
            )
        elif name == "read_file":
            lines = result.get("lines") or []
            head = " | ".join(str(x.get("text") or "") for x in lines[:12])
            out.append(
                {
                    "text": (
                        f"read_file path={result.get('path') or args.get('path')} "
                        f"returned_lines={result.get('returned_lines')} "
                        f"ok={result.get('ok')} head={head[:400]}"
                    ),
                    "source": "tool:read_file",
                    "status": "experimental",
                }
            )
        elif exe.get("denied"):
            out.append(
                {
                    "text": f"tool denied name={name} args={args} result={result.get('error')}",
                    "source": "tool:denied",
                    "status": "experimental",
                }
            )
    return out


def qwen_next_check(raw: str) -> str:
    text = str(raw or "").strip()
    m = re.search(r"次に.{0,40}(確認|調べ|見る).{0,80}", text)
    if m:
        return m.group(0)
    return "NOT EXTRACTED from final text"


def maybe_map_excerpt(next_check: str) -> str:
    blob = next_check.lower()
    extras: list[str] = []
    if "expected" in blob or "expected map" in next_check or "Expected" in next_check:
        path = SOURCE_RUN / "reviewed_expected_map.json"
        extras.append("Reviewed Expected Map excerpt (experimental):\n" + path.read_text(encoding="utf-8")[:1800])
    if "actual" in blob or "Actual" in next_check:
        path = SOURCE_RUN / "actual_map_after.json"
        extras.append("Actual Map after excerpt (experimental, truncated):\n" + path.read_text(encoding="utf-8")[:1800])
    if "focus" in blob or "Minimum Focus" in next_check or "allowed_write" in next_check:
        path = SOURCE_RUN / "focus.json"
        extras.append("focus.json (experimental / provisional heuristic):\n" + path.read_text(encoding="utf-8")[:1800])
    return "\n\n".join(extras)


def main() -> int:
    run_id = utc_id()
    run_dir = HERE / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    facts = start_facts()
    remaining = "開始時点。次に確認すべき一点は未選択。Qwenが1つ選ぶ。"
    extra = ""
    stop_reason = "max_steps"
    last_kind = "CONTINUE"
    last_final = ""
    history: list[dict[str, Any]] = []

    dump(run_dir / "source_run.json", {"source_run": str(SOURCE_RUN), "max_steps_not_sent_to_llm": MAX_STEPS})

    for step in range(1, MAX_STEPS + 1):
        user = build_user(step=step, facts=facts, remaining=remaining, extra_context=extra)
        print(f"STEP {step} CALL", flush=True)
        turn = run_grill_tool_turn(user_request=user)
        judged = classify(turn.get("final_answer") or "")
        tool_facts = facts_from_executions(turn.get("executions") or [])
        facts.extend(tool_facts)
        next_check = qwen_next_check(turn.get("final_answer") or "")
        step_rec = {
            "step": step,
            "classification": judged,
            "qwen_next_check": next_check,
            "human_or_self": "self_investigate" if (turn.get("executions") or []) else "text_only",
            "tool_names": [e.get("tool_name") for e in (turn.get("executions") or [])],
            "tool_facts_added": tool_facts,
            "final_answer": turn.get("final_answer"),
        }
        dump(run_dir / f"step_{step}.json", step_rec)
        dump(run_dir / f"step_{step}_turn.json", turn)
        (run_dir / f"step_{step}_raw.txt").write_text(str(turn.get("final_answer") or ""), encoding="utf-8")
        dump(run_dir / f"step_{step}_user.txt", {"user": user})
        history.append(
            {
                "step": step,
                "classification": judged["kind"],
                "next_check": next_check,
                "tools": step_rec["tool_names"],
            }
        )
        last_kind = judged["kind"]
        last_final = str(turn.get("final_answer") or "")
        print(f"STEP {step} CLASS={judged['kind']} tools={step_rec['tool_names']}", flush=True)

        if judged["kind"] == "DIAGNOSIS_COMPLETE":
            stop_reason = "diagnosis_complete"
            break
        if judged["kind"] == "HUMAN_QUESTION":
            if lookupable_human_question(last_final):
                remaining = (
                    "前回の内容はコード / Test / 既存資料から確認できる可能性がある。"
                    "人間には上げない。search_files / read_file で自分で確認すること。\n"
                    + last_final[:800]
                )
                extra = maybe_map_excerpt(last_final)
                continue
            stop_reason = "human_question"
            break
        remaining = next_check if next_check != "NOT EXTRACTED from final text" else last_final[:600]
        extra = maybe_map_excerpt(remaining + "\n" + last_final[:400])

    all_tools: list[str] = []
    for item in history:
        all_tools.extend(item.get("tools") or [])
    summary = {
        "experiment": "diagnosis_grill_v0",
        "run_id": run_id,
        "source_run": "20260909T030450Z",
        "steps": len(history),
        "stop_reason": stop_reason,
        "last_classification": last_kind,
        "tool_call_sequence": all_tools,
        "search_files_count": all_tools.count("search_files"),
        "read_file_count": all_tools.count("read_file"),
        "history": history,
        "repair_started": False,
        "production_modified": False,
        "bridge_modified": False,
    }
    dump(run_dir / "run.json", summary)
    (run_dir / "last_raw.txt").write_text(last_final, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
