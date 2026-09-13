"""Unknown の解決主体を実ケースで観察する（1回、研究ラベルのみ）。

再利用: system_resolve / call_freeform / 既存 Grounded Grill Prompt /
既存 Capability Resolution / 既存 Help / Index。
Harness 独自の意味→Tool mapping は持たない。
Production / Registry / Help / Capability は変更しない。
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.grill_observation_v0.medium_task_reality_v0.apply_patch import strip_think
from research.grill_observation_v0.natural_exit_v0.run import call_freeform
from research.grill_observation_v0.grill_system_retry_v0.run_once import (
    GRILL_GROUNDING,
    GRILL_QUESTION,
    NEED_QUESTION,
    grill_beyond_meaning,
    help_index_trace,
    where_stopped,
)
from research.grill_observation_v0.system_first_loop_v0.run_once import (
    assert_qwen_prompt_clean,
    system_request,
    system_resolve,
)
from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

# Observation-only. Not a Production Rule.
UNCONFIRMED_CONCRETIZATION = (
    "商品名",
    "価格",
    "在庫数",
    "売上データ",
    "売上",
    "ユーザー情報",
    "製品一覧",
)

CASE1 = {
    "case": "Case 1",
    "expected_label": "SYSTEM_RESOLVABLE",
    "goal": "registry/tools.json を読んで、内容を確認してほしい。",
    "unknown": "registry/tools.json の内容が未確認である。",
    "initial_state": "まだ何も調査していない。",
    "allow_need_llm": False,
    "allow_grill": False,
    "max_grills": 0,
    "selection_evidence": (
        "tests/ai_tool/chat_interface/test_h4_selection_core.py の "
        "test_registry_tools_json_read_bridges_that_path / "
        "test_registry_path_read_injects_single_pending_action と、"
        "本実験前の system_resolve 実測で executable_action を確認済み。"
        "path は Canonical Workspace 実在ファイル。"
    ),
}

CASE2 = {
    "case": "Case 2",
    "expected_label": "AI_RESOLVABLE",
    "goal": "gridを検索して、その内容を要約してほしい。",
    "unknown": "grid の所在・形式・アクセス方法が未確認である。",
    "initial_state": "まだ何も調査していない。",
    "allow_need_llm": True,
    "allow_grill": True,
    "max_grills": 2,
    "selection_evidence": (
        "既存 Grounded Run と同系統。"
        "research/grill_observation_v0/grill_system_retry_v0/"
        "runs/20260909T061247Z"
    ),
}

CASE3 = {
    "case": "Case 3",
    "expected_label": "HUMAN_REQUIRED",
    "goal": (
        "来週の人間レビュー資料は、詳細な技術解説を優先するか、"
        "結論だけ短くまとめた報告を優先するか、好みを決めてほしい。"
    ),
    "unknown": "レビュー資料の詳しさについてのユーザー好みが未決定である。",
    "initial_state": "まだ何も調査していない。方針ファイルの指定もない。",
    "allow_need_llm": False,
    "allow_grill": True,
    "max_grills": 1,
    "selection_evidence": (
        "技術調査や既存 Capability では答えが決まらない小さい Decision。"
        "実験前 system_resolve は no_required_capability。"
        "Human Approval / destructive ではない。"
    ),
}

# Case 4 は Canonical 空 tools[] は存在するが、現行 required_capabilities が
# それらへ束縛する実リクエストを確認できなかったため実行しない。
CASE4_NOT_AVAILABLE = {
    "case": "Case 4",
    "expected_label": "SYSTEM_GAP",
    "status": "NOT_AVAILABLE",
    "reason": (
        "Canonical Index で tools[] が空の Capability は存在する "
        "(workspace_file_write / command_execution / python_execution / "
        "test_execution / tool_validation / tool_registration)。"
        "しかし現行 required_capabilities は Registry keyword 逆引きのため、"
        "空 tools[] の Capability へ自然言語リクエストを束縛できない。"
        "pytestを実行する / Pythonを実行して / コマンドを実行して 等の実測は "
        "no_required_capability であり、必要能力が System 上で明確になっていない。"
        "推測で SYSTEM_GAP ケースを作らない。"
    ),
    "canonical_empty_tools": [
        "workspace_file_write",
        "command_execution",
        "python_execution",
        "test_execution",
        "tool_validation",
        "tool_registration",
    ],
}


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def executable_from(resolution: dict[str, Any]) -> dict[str, Any] | None:
    action = resolution.get("action") or {}
    if action.get("tool") and action.get("arguments"):
        return dict(action)
    next_actions = [
        row.get("next_action")
        for row in (resolution.get("resolutions") or [])
        if row.get("next_action")
    ]
    if len(next_actions) == 1 and isinstance(next_actions[0], dict):
        item = next_actions[0]
        if item.get("tool") and item.get("arguments"):
            return dict(item)
    return None


def selected_from(resolution: dict[str, Any]) -> tuple[str | None, str | None]:
    cap = next(
        (
            row.get("required_capability")
            for row in (resolution.get("resolutions") or [])
            if row.get("required_capability")
        ),
        None,
    )
    tool = next(
        (
            row.get("selected_tool")
            for row in (resolution.get("resolutions") or [])
            if row.get("selected_tool")
        ),
        None,
    )
    return cap, tool


def grounding_violation(text: str, confirmed: str) -> dict[str, Any]:
    body = str(text or "")
    hits = [token for token in UNCONFIRMED_CONCRETIZATION if token in body]
    invented = [token for token in hits if token not in confirmed]
    return {
        "present": bool(invented),
        "unconfirmed_tokens_in_output": invented,
        "note": (
            "研究観察。確認済み Goal/State/Need に無い具体化トークン。"
            "Production Grounding Rule ではない。"
        ),
    }


def summarize_resolution(resolution: dict[str, Any] | None) -> dict[str, Any] | None:
    if resolution is None:
        return None
    cap, tool = selected_from(resolution)
    return {
        "label": resolution.get("label"),
        "stopped_at": resolution.get("stopped_at"),
        "required_capabilities": resolution.get("required_capabilities"),
        "resolutions": resolution.get("resolutions"),
        "action": resolution.get("action"),
        "selected_capability": cap,
        "selected_tool": tool,
        "next_action": executable_from(resolution),
        "request_text": resolution.get("request_text"),
    }


def classify_from_observation(record: dict[str, Any]) -> tuple[str, str]:
    """研究ラベルのみ。Production 契約へ追加しない。"""
    case = record["case"]
    first_stop = (record.get("system_first") or {}).get("stopped_at")
    last = record.get("system_retry") or record.get("system_first") or {}
    last_stop = last.get("stopped_at")
    grill_called = bool(record.get("grill_called"))
    executable_first = first_stop == "executable_action"
    executable_last = last_stop == "executable_action"

    if case == "Case 1":
        if executable_first and not grill_called:
            return (
                "SYSTEM_RESOLVABLE",
                "System First だけで read_file の実行可能 Action に到達した。Grill は呼ばない。",
            )
        return (
            "BLOCKED",
            f"Case 1 は System First のみ。executable_action ではない "
            f"(stopped_at={first_stop})。修正再実行しない。",
        )

    if case == "Case 2":
        if executable_first and not grill_called:
            return (
                "SYSTEM_RESOLVABLE",
                "Grill 前に System 単独で Action 化した。AI_RESOLVABLE ではない。",
            )
        if grill_called and executable_last:
            return (
                "AI_RESOLVABLE",
                "System First では Action 化できず、Grounded Grill 後の System Retry で Action 化した。",
            )
        return (
            "BLOCKED",
            "Grill 後も実行可能 Action まで到達していない。"
            f" last_stopped_at={last_stop}。"
            "未到達を AI_RESOLVABLE にも SYSTEM_GAP にもしない。",
        )

    if case == "Case 3":
        if executable_first and not grill_called:
            return (
                "SYSTEM_RESOLVABLE",
                "好み Decision のはずが System First で Action 化した。HUMAN_REQUIRED にしない。",
            )
        if grill_called and executable_last:
            return (
                "BLOCKED",
                "Retry が Action 化した。追加 Evidence を取っていないため、"
                "答えが Human Decision であることは確定できない。"
                "『System で解けなかったから Human』にもしない。",
            )
        grill_text = str(((record.get("grills") or [{}])[-1]).get("visible") or "")
        decided = bool(
            re.search(r"(採用すべき|こちらがよい|正式採用は|結論として.{0,12}優先)", grill_text)
        ) and not bool(re.search(r"(ユーザー|人間|本人).{0,12}(決|選|意図|好み)", grill_text))
        if decided:
            return (
                "BLOCKED",
                "Grill がユーザー好みを確定したように読める。AI が好みを決めてはいけない。"
                "HUMAN_REQUIRED にも AI_RESOLVABLE にもしない。",
            )
        if (not executable_last) and grill_called:
            return (
                "HUMAN_REQUIRED",
                "System First でも Grill 後 System Retry でも Action 化できず、"
                "残った Unknown は追加観測ではなくユーザーの好み・価値判断そのもの。",
            )
        return (
            "BLOCKED",
            "Human Decision とも Action 化とも確定できない。",
        )

    return ("BLOCKED", "未知の Case。")


def main() -> int:
    started = time.perf_counter()
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    if provider != "qwen3:14b":
        model_id = "qwen3_14b"
        provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = utc_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    def llm(user: str, label: str) -> dict[str, Any]:
        assert_qwen_prompt_clean(user)
        call = call_freeform(
            model=provider,
            messages=[{"role": "user", "content": user}],
            num_ctx=int(profile.get("context_limit") or 8192),
            num_predict=int(profile.get("num_predict") or 2048),
            temperature=float(
                profile.get("temperature") if profile.get("temperature") is not None else 0
            ),
            timeout_s=int(profile.get("hard_timeout_seconds") or 300),
            label=label,
        )
        raw = str(call.get("raw_text") or "")
        return {
            "label": label,
            "prompt": user,
            "raw": raw,
            "visible": strip_think(raw),
            "elapsed_s": call.get("elapsed_s"),
            "error": call.get("error"),
            "model": provider,
        }

    cases = [CASE1, CASE2, CASE3]
    records: list[dict[str, Any]] = []

    for spec in cases:
        case_name = spec["case"]
        case_dir = run_dir / case_name.replace(" ", "").lower()
        case_dir.mkdir(parents=True, exist_ok=True)
        goal = spec["goal"]
        state = spec["initial_state"]
        unknown = spec["unknown"]
        record: dict[str, Any] = {
            "case": case_name,
            "goal": goal,
            "unknown": unknown,
            "initial_state": state,
            "selection_evidence": spec["selection_evidence"],
            "expected_label_before_run": spec["expected_label"],
            "grill_called": False,
            "grills": [],
            "system_retry": None,
            "second_grill": False,
            "production_contract": False,
        }

        need = unknown
        if spec["allow_need_llm"]:
            need_user = f"Goal:\n{goal}\n\nCurrent State:\n{state}\n\n質問:\n{NEED_QUESTION}"
            need_got = llm(need_user, f"{case_name}_need")
            write_text(case_dir / "01_need_prompt.txt", need_user)
            write_text(case_dir / "01_need_raw.txt", need_got["raw"])
            need = str(need_got["visible"] or "").strip() or unknown
            record["need_llm"] = {
                "prompt": need_user,
                "raw": need_got["raw"],
                "visible": need,
                "elapsed_s": need_got["elapsed_s"],
                "error": need_got["error"],
            }
            if need_got["error"]:
                record["final_label"] = "BLOCKED"
                record["classification_reason"] = "Need LLM が失敗した。修正再実行しない。"
                dump(case_dir / "case.json", record)
                records.append(record)
                continue
        else:
            record["need_llm"] = None

        first_request = system_request(goal=goal, state=state, need=need)
        first = system_resolve(first_request)
        first["stopped_at"] = where_stopped(first)
        dump(case_dir / "02_system_first.json", first)
        record["system_first_input"] = first_request
        record["system_first"] = summarize_resolution(first)
        record["system_stopped_reason"] = first["stopped_at"]

        last = first
        confirmed = f"{goal}\n{state}\n{need}"

        if spec["allow_grill"] and first["stopped_at"] != "executable_action":
            grill_budget = int(spec["max_grills"])
            grill_index = 0
            current_need = need
            while grill_index < grill_budget:
                if grill_index == 0:
                    gap = (
                        "既存Systemだけでは次の実行可能Actionまで解決できませんでした。\n"
                        f"停止場所: {last['stopped_at']}\n"
                        "不足: Goal と現在の未解決点だけでは、"
                        "次に実行する対象・条件・引数まで確定できなかった。"
                    )
                else:
                    gap = (
                        "Grill 後の System Retry でも実行可能 Action の引数が不足しています。\n"
                        f"停止場所: {last['stopped_at']}\n"
                        "不足している arguments 等だけを1段掘ってください。"
                    )
                    if last["stopped_at"] != "tool_selected_arguments_incomplete":
                        break
                grill_user = (
                    f"Goal:\n{goal}\n\n"
                    f"Current State:\n{state}\n\n"
                    f"現在の未解決点:\n{current_need}\n\n"
                    f"System で解決できなかった事実:\n{gap}\n\n"
                    f"依頼:\n{GRILL_QUESTION}\n"
                    f"{GRILL_GROUNDING}"
                )
                grill_got = llm(grill_user, f"{case_name}_grill_{grill_index + 1}")
                prefix = f"{3 + grill_index * 2:02d}"
                write_text(case_dir / f"{prefix}_grill_prompt.txt", grill_user)
                write_text(case_dir / f"{prefix}_grill_raw.txt", grill_got["raw"])
                visible = str(grill_got["visible"] or "").strip()
                violation = grounding_violation(visible, confirmed)
                grill_row = {
                    "n": grill_index + 1,
                    "prompt": grill_user,
                    "raw": grill_got["raw"],
                    "visible": visible,
                    "elapsed_s": grill_got["elapsed_s"],
                    "error": grill_got["error"],
                    "grounding_violation": violation,
                    "concretized": grill_beyond_meaning(visible),
                    "tool_names_in_output": grill_beyond_meaning(visible)["tool_names_present"],
                }
                record["grills"].append(grill_row)
                record["grill_called"] = True
                if grill_index == 1:
                    record["second_grill"] = True
                if grill_got["error"] or not visible:
                    record["final_label"] = "BLOCKED"
                    record["classification_reason"] = "Grill が再処理できる情報を返せなかった。"
                    break
                retry_request = (
                    f"Goal:\n{goal}\n\n"
                    f"Current State:\n{state}\n\n"
                    f"現在の未解決点:\n{current_need}\n\n"
                    f"Grill:\n{visible}\n"
                )
                retry = system_resolve(retry_request)
                retry["stopped_at"] = where_stopped(retry)
                dump(case_dir / f"{4 + grill_index * 2:02d}_system_retry.json", retry)
                record["system_retry"] = summarize_resolution(retry)
                last = retry
                current_need = visible
                grill_index += 1
                if retry["stopped_at"] == "executable_action":
                    break
                if grill_index >= grill_budget:
                    break
                if retry["stopped_at"] != "tool_selected_arguments_incomplete":
                    break
        else:
            record["grill_called"] = False

        last_summary = record.get("system_retry") or record.get("system_first") or {}
        cap = last_summary.get("selected_capability")
        tool = last_summary.get("selected_tool")
        help_trace = help_index_trace(cap, tool)
        dump(case_dir / "05_help_index.json", help_trace)
        record["help_index"] = help_trace
        record["capability"] = cap
        record["selected_tool"] = tool
        record["next_action"] = last_summary.get("next_action")
        record["final_unresolved"] = None if last_summary.get("stopped_at") == "executable_action" else {
            "stopped_at": last_summary.get("stopped_at"),
            "required_capabilities": last_summary.get("required_capabilities"),
            "need": need,
            "last_grill_visible": None if not record["grills"] else record["grills"][-1].get("visible"),
        }
        label, reason = classify_from_observation(record)
        record["final_label"] = label
        record["classification_reason"] = reason
        if label == "HUMAN_REQUIRED":
            record["human_question_to_ask"] = (
                "来週の人間レビュー資料は、詳細な技術解説と短い結論報告のどちらを優先するか。"
            )
            record["human_question_sent"] = False
        dump(case_dir / "case.json", record)
        records.append(record)

    comparison = {
        "experiment": "resolver_owner_v0",
        "run_id": run_id,
        "model": provider,
        "production_modified": False,
        "router_implemented": False,
        "labels_are_research_only": True,
        "case4": CASE4_NOT_AVAILABLE,
        "cases": [
            {
                "case": item["case"],
                "goal": item["goal"],
                "grill_called": item.get("grill_called"),
                "second_grill": item.get("second_grill"),
                "system_first_stopped_at": (item.get("system_first") or {}).get("stopped_at"),
                "system_retry_stopped_at": None
                if not item.get("system_retry")
                else item["system_retry"].get("stopped_at"),
                "capability": item.get("capability"),
                "selected_tool": item.get("selected_tool"),
                "next_action": item.get("next_action"),
                "final_label": item.get("final_label"),
                "classification_reason": item.get("classification_reason"),
            }
            for item in records
        ],
        "elapsed_s": round(time.perf_counter() - started, 3),
    }
    dump(run_dir / "comparison.json", comparison)

    lines = [
        "# resolver_owner_v0 比較（研究ラベルのみ）",
        "",
        f"run_id: `{run_id}`",
        f"model: `{provider}`",
        "Production 未変更。Router 未実装。ラベルは研究観察のみ。",
        "",
        "| Case | Goal 要約 | Grill | System First | Retry | Tool / next_action | 分類 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in comparison["cases"]:
        action = item.get("next_action")
        action_s = "—" if not action else f"{action.get('tool')} {action.get('arguments')}"
        goal_s = str(item.get("goal") or "").replace("|", "/")
        if len(goal_s) > 40:
            goal_s = goal_s[:40] + "…"
        lines.append(
            "| {case} | {goal} | {grill} | {first} | {retry} | {action} | {label} |".format(
                case=item["case"],
                goal=goal_s,
                grill="yes" if item.get("grill_called") else "no",
                first=item.get("system_first_stopped_at"),
                retry=item.get("system_retry_stopped_at") or "—",
                action=action_s,
                label=item.get("final_label"),
            )
        )
    lines.extend(
        [
            "",
            "## Case 4",
            "",
            "NOT_AVAILABLE（実行していない）。",
            "",
            CASE4_NOT_AVAILABLE["reason"],
            "",
        ]
    )
    write_text(run_dir / "COMPARISON.md", "\n".join(lines) + "\n")
    dump(run_dir / "run.json", {
        "experiment": "resolver_owner_v0",
        "run_id": run_id,
        "model": provider,
        "production_modified": False,
        "elapsed_s": comparison["elapsed_s"],
    })
    print(json.dumps({"run_id": run_id, "dir": str(run_dir)}, ensure_ascii=False), flush=True)
    print(f"RUN {run_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
