"""Case 2: Need LLM を通さず Goal + Current State を System First へ渡す 1回観察。

Production / NEED_QUESTION / Grill / Capability / Registry / Help は変更しない。
既存 Run は書き換えない。Tool / Gemini / Qwen は実行しない。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.grill_observation_v0.grill_system_retry_v0.run_once import where_stopped
from research.grill_observation_v0.resolver_owner_v0.run_once import summarize_resolution
from research.grill_observation_v0.system_first_loop_v0.run_once import system_resolve

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

GOAL = "gridを検索して、その内容を要約してほしい。"
INITIAL_STATE = "まだ何も調査していない。"
BASELINE = (
    ROOT
    / "research/grill_observation_v0/resolver_owner_v0/runs/20260909T064802Z/case2/02_system_first.json"
)

# system_request() は need: str 必須で必ず "Next need:" を付ける。
# system_resolve() は request_text のみ。Need 欄は必須ではない。
# 空の Next need や Goal の Need 複製はしない。
def goal_state_request(*, goal: str, state: str) -> str:
    return f"Goal:\n{goal}\n\nCurrent State:\n{state}\n"


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def row_fields(resolution: dict[str, Any]) -> dict[str, Any]:
    rows = list(resolution.get("resolutions") or [])
    search_row = next(
        (
            row
            for row in rows
            if row.get("required_capability") == "workspace_file_search"
            or row.get("selected_tool") == "search_files"
        ),
        rows[0] if rows else {},
    )
    return {
        "request_text": resolution.get("request_text"),
        "required_capabilities": resolution.get("required_capabilities"),
        "capability_resolution": rows,
        "selected_tool": search_row.get("selected_tool"),
        "next_action": search_row.get("next_action"),
        "resolved_arguments": search_row.get("resolved_arguments"),
        "unresolved_arguments": search_row.get("unresolved_arguments"),
        "unresolved_reason": resolution.get("stopped_at"),
        "label": resolution.get("label"),
        "action": resolution.get("action"),
        "tool_executed": False,
    }


def looks_search_capability(caps: list[Any], selected_tool: Any) -> bool:
    names = [str(c) for c in (caps or [])]
    tool = str(selected_tool or "")
    return any("search" in n.lower() for n in names) or ("search" in tool.lower())


def classify_verdict(current: dict[str, Any]) -> tuple[str, str]:
    stopped = current.get("unresolved_reason")
    caps = list(current.get("required_capabilities") or [])
    selected = current.get("selected_tool")
    if looks_search_capability(caps, selected):
        return (
            "A",
            "元Goal+State だけで search 系 Capability / Tool へ解決した。"
            "Need 生成が System First より前にあることが処理結果へ影響していた可能性を記録する。"
            "因果は断定しない。",
        )
    if stopped == "no_required_capability" and not caps and not selected:
        return (
            "B",
            "元Goalだけでも no_required_capability。"
            "Need 以前に System First / Capability 分類側に未解決点がある可能性を記録する。"
            "因果は断定しない。",
        )
    return ("C", "上記以外。実結果を記録する。原因は推測しない。")


def main() -> int:
    started = time.perf_counter()
    run_id = utc_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    request_text = goal_state_request(goal=GOAL, state=INITIAL_STATE)
    write_text(run_dir / "01_request_text.txt", request_text)

    resolution = system_resolve(request_text)
    resolution["stopped_at"] = where_stopped(resolution)
    dump(run_dir / "02_system_first.json", resolution)

    current = row_fields(resolution)
    baseline_raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline = row_fields(baseline_raw)
    verdict, verdict_reason = classify_verdict(current)

    comparison = {
        "experiment": "need_bypass_system_first_v0",
        "run_id": run_id,
        "production_modified": False,
        "need_llm_called": False,
        "grill_used": False,
        "tool_executed": False,
        "goal": GOAL,
        "initial_state": INITIAL_STATE,
        "request_construction": {
            "used_system_request": False,
            "reason": (
                "system_request は need 必須で Next need を必ず付ける。"
                "system_resolve は request_text のみで Need は必須ではない。"
                "今回は Need 工程をバイパスするため、Goal / Current State 見出しだけを"
                "system_request と同じ形式で組み立てた。"
            ),
        },
        "baseline": {
            "path": str(BASELINE.relative_to(ROOT)).replace("\\", "/"),
            "need": "gridの構造と内容を確認する。",
            **baseline,
        },
        "current": current,
        "diff": {
            "request_text_changed": baseline["request_text"] != current["request_text"],
            "required_capabilities_changed": (
                baseline["required_capabilities"] != current["required_capabilities"]
            ),
            "selected_tool_changed": baseline["selected_tool"] != current["selected_tool"],
            "next_action_changed": baseline["next_action"] != current["next_action"],
            "unresolved_reason_changed": (
                baseline["unresolved_reason"] != current["unresolved_reason"]
            ),
        },
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "summarize_resolution": summarize_resolution(resolution),
        "elapsed_s": round(time.perf_counter() - started, 3),
    }
    dump(run_dir / "comparison.json", comparison)
    dump(run_dir / "observation.json", comparison)

    lines = [
        "# need_bypass_system_first_v0",
        "",
        f"run_id: {run_id}",
        f"verdict: {verdict}",
        "",
        "## Baseline request_text",
        "",
        "```",
        str(baseline["request_text"] or "").rstrip(),
        "```",
        "",
        "## Current request_text",
        "",
        "```",
        str(current["request_text"] or "").rstrip(),
        "```",
        "",
        "## Comparison",
        "",
        f"- required_capabilities baseline={baseline['required_capabilities']!r} current={current['required_capabilities']!r}",
        f"- selected_tool baseline={baseline['selected_tool']!r} current={current['selected_tool']!r}",
        f"- next_action baseline={baseline['next_action']!r} current={current['next_action']!r}",
        f"- resolved_arguments current={current.get('resolved_arguments')!r}",
        f"- unresolved_arguments current={current.get('unresolved_arguments')!r}",
        f"- unresolved_reason baseline={baseline['unresolved_reason']!r} current={current['unresolved_reason']!r}",
        "",
        f"reason: {verdict_reason}",
        "",
    ]
    write_text(run_dir / "COMPARISON.md", "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
