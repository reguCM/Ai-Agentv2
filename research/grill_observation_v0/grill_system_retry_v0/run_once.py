"""Grill → System Retry 接続の最小観察（1ケース）。

既存 System First 研究の system_resolve / classify と、
Grill Tool Bridge の execute_exposed_tool を再利用する。
Production / Registry / Help / Capability は変更しない。
Harness 独自の意味→Tool mapping は持たない。
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

from ai_tool.chat_interface.concept_resolution import load_workspace_index
from ai_tool.chat_interface.task_orchestration import _help_confirmed_tool_for_capability
from ai_tool.help.api import describe, prefer_tool_for_capability
from research.grill_observation_v0.grill_tool_bridge_v0.bridge import (
    ALLOWED_TOOLS,
    execute_exposed_tool,
)
from research.grill_observation_v0.medium_task_reality_v0.apply_patch import strip_think
from research.grill_observation_v0.natural_exit_v0.run import call_freeform
from research.grill_observation_v0.system_first_loop_v0.run_once import (
    FORBIDDEN_IN_QWEN,
    assert_qwen_prompt_clean,
    classify_research_label,
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

GOAL = "gridを検索して、その内容を要約してほしい。"
INITIAL_STATE = "まだ何も調査していない。"

NEED_QUESTION = """現在のGoalを進めるため、
今まず解決する必要があることを1つだけ出してください。

完全な作業計画は不要です。
一度に1つだけ答えてください。
"""

GRILL_QUESTION = """現在なぜ進めないのかを1段掘り、
次の処理を再開するために必要な情報を具体化してください。

一度に1段だけ掘ってください。
"""

GRILL_GROUNDING = """【Grounding】

未確認の意味・対象・値・構造を具体化する際は、
確認済みの事実から導けない具体情報で不足を埋めないこと。

分からないことは、分からない状態として保持すること。

具体化のために追加情報が必要なら、
その情報自体を「次に確認すべきこと」として扱うこと。

確認されていない具体例を、
確認済み事実として扱わないこと。
"""

TOOL_NAME_TOKENS = ("search_files", "read_file", "list_files")
CAPABILITY_NAME_TOKENS = (
    "workspace_file_search",
    "workspace_file_read",
    "workspace_file_list",
)


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def contains_any(text: str, tokens: tuple[str, ...]) -> list[str]:
    return [token for token in tokens if token in text]


def where_stopped(resolution: dict[str, Any]) -> str:
    caps = list(resolution.get("required_capabilities") or [])
    rows = list(resolution.get("resolutions") or [])
    selected = [row.get("selected_tool") for row in rows if row.get("selected_tool")]
    actions = [row.get("next_action") for row in rows if row.get("next_action")]
    action = resolution.get("action")
    if action and action.get("tool") and action.get("arguments"):
        return "executable_action"
    if resolution.get("label") == "RESOLVED":
        return "labeled_resolved_without_recorded_action"
    if selected and not actions:
        return "tool_selected_arguments_incomplete"
    if caps and not selected:
        return "capability_without_selected_tool"
    if not caps:
        return "no_required_capability"
    return "unresolved_other"


def help_index_trace(capability: str | None, selected_tool: str | None) -> dict[str, Any]:
    """Record existing Help / Index confirmation. Does not invent a search path."""
    cap = str(capability or "").strip()
    if not cap:
        return {
            "skipped": True,
            "reason": "no_capability",
            "prefer_tool_for_capability": None,
            "help_confirmed_tool": None,
            "index_tools": [],
            "describe_selected": None,
        }
    spec = (load_workspace_index().get("capabilities") or {}).get(cap) or {}
    selected = str(selected_tool or "").strip()
    describe_selected = describe(f"local:{selected}") if selected else None
    return {
        "skipped": False,
        "capability": cap,
        "index_tools": list(spec.get("tools") or []),
        "prefer_tool_for_capability": prefer_tool_for_capability(cap),
        "help_confirmed_tool": _help_confirmed_tool_for_capability(cap),
        "describe_selected": describe_selected,
        "tool_selected_because": (
            "resolve_capabilities selected the Help-available Index tool; "
            "next_capability_action filled arguments from the request text"
        ),
    }


def grill_beyond_meaning(text: str) -> dict[str, Any]:
    body = str(text or "")
    return {
        "mentions_file_or_location": bool(
            re.search(r"(ファイル|場所|パス|path|保存|どこに|対象)", body, re.I)
        ),
        "mentions_observation": bool(
            re.search(r"(検索|探す|読む|確認|観測|調べ)", body)
        ),
        "mentions_parameter": bool(
            re.search(r"(クエリ|query|キーワード|引数|パラメータ|\"[^\"]+\"|「[^」]+」)", body, re.I)
        ),
        "quoted_token": bool(re.search(r"[\"「]([^\"」]{1,80})[\"」]", body)),
        "tool_names_present": contains_any(body, TOOL_NAME_TOKENS),
        "capability_names_present": contains_any(body, CAPABILITY_NAME_TOKENS),
    }


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

    goal = GOAL
    state = INITIAL_STATE
    observation: dict[str, Any] = {
        "experiment": "grill_system_retry_v0",
        "run_id": run_id,
        "model_id": model_id,
        "model": provider,
        "goal": goal,
        "initial_state": state,
    }

    need_user = (
        f"Goal:\n{goal}\n\nCurrent State:\n{state}\n\n質問:\n{NEED_QUESTION}"
    )
    need_got = llm(need_user, "need")
    write_text(run_dir / "01_need_prompt.txt", need_user)
    write_text(run_dir / "01_need_raw.txt", need_got["raw"])
    need = str(need_got["visible"] or "").strip()
    observation["need"] = {
        "prompt": need_user,
        "raw": need_got["raw"],
        "visible": need,
        "elapsed_s": need_got["elapsed_s"],
        "error": need_got["error"],
    }
    if need_got["error"] or not need:
        observation["verdict"] = "FAIL"
        observation["verdict_reason"] = "最初の未解決点を取得できなかった。"
        observation["elapsed_s"] = round(time.perf_counter() - started, 3)
        dump(run_dir / "observation.json", observation)
        print(json.dumps({"run_id": run_id, "verdict": "FAIL"}, ensure_ascii=False), flush=True)
        return 1

    first_request = system_request(goal=goal, state=state, need=need)
    first = system_resolve(first_request)
    first["stopped_at"] = where_stopped(first)
    dump(run_dir / "02_system_first.json", first)
    observation["system_first"] = first

    grill_got = None
    retry = None
    tool_exec = None
    help_trace = None

    if first["stopped_at"] == "executable_action":
        observation["grill_skipped"] = True
        observation["verdict"] = "FAIL"
        observation["verdict_reason"] = (
            "System First だけで実行可能 Action に到達したため、"
            "Grill → System Retry 接続は今回観測できなかった。"
        )
    else:
        gap = (
            "既存Systemだけでは次の実行可能Actionまで解決できませんでした。\n"
            f"停止場所: {first['stopped_at']}\n"
            "不足: Goal と現在の未解決点だけでは、次に実行する対象・条件・引数まで確定できなかった。"
        )
        grill_user = (
            f"Goal:\n{goal}\n\n"
            f"Current State:\n{state}\n\n"
            f"現在の未解決点:\n{need}\n\n"
            f"System First で解決できなかった事実:\n{gap}\n\n"
            f"依頼:\n{GRILL_QUESTION}\n"
            f"{GRILL_GROUNDING}"
        )
        grill_got = llm(grill_user, "grill")
        write_text(run_dir / "03_grill_prompt.txt", grill_user)
        write_text(run_dir / "03_grill_raw.txt", grill_got["raw"])
        grill_visible = str(grill_got["visible"] or "").strip()
        grill_obs = grill_beyond_meaning(grill_visible)
        observation["grill"] = {
            "prompt": grill_user,
            "raw": grill_got["raw"],
            "visible": grill_visible,
            "elapsed_s": grill_got["elapsed_s"],
            "error": grill_got["error"],
            "concretized": grill_obs,
            "tool_names_in_output": grill_obs["tool_names_present"],
            "capability_names_in_output": grill_obs["capability_names_present"],
        }
        if grill_got["error"] or not grill_visible:
            observation["verdict"] = "FAIL"
            observation["verdict_reason"] = "Grill が再処理できる情報を返せなかった。"
        else:
            retry_request = (
                f"Goal:\n{goal}\n\n"
                f"Current State:\n{state}\n\n"
                f"現在の未解決点:\n{need}\n\n"
                f"Grill:\n{grill_visible}\n"
            )
            retry = system_resolve(retry_request)
            retry["stopped_at"] = where_stopped(retry)
            dump(run_dir / "04_system_retry.json", retry)
            selected_cap = next(
                (
                    row.get("required_capability")
                    for row in (retry.get("resolutions") or [])
                    if row.get("required_capability")
                ),
                None,
            )
            selected_tool = next(
                (
                    row.get("selected_tool")
                    for row in (retry.get("resolutions") or [])
                    if row.get("selected_tool")
                ),
                None,
            )
            help_trace = help_index_trace(selected_cap, selected_tool)
            dump(run_dir / "05_help_index.json", help_trace)
            observation["system_retry"] = retry
            observation["help_index"] = help_trace

            action = retry.get("action") or {}
            next_actions = [
                row.get("next_action")
                for row in (retry.get("resolutions") or [])
                if row.get("next_action")
            ]
            executable = action if action.get("tool") and action.get("arguments") else (
                next_actions[0] if len(next_actions) == 1 else None
            )
            observation["selected_tool"] = selected_tool
            observation["next_action"] = executable or (next_actions[0] if next_actions else None)
            observation["tool_selection_actor"] = (
                "existing_system: ChatTaskOrchestrator.configure_tool_expectation "
                "+ resolve_capabilities + next_capability_action"
            )
            observation["tool_execution_actor"] = None

            first_caps = list(first.get("required_capabilities") or [])
            retry_caps = list(retry.get("required_capabilities") or [])
            info_increased = grill_visible != need and (
                bool(grill_obs["mentions_file_or_location"])
                or bool(grill_obs["mentions_observation"])
                or bool(grill_obs["mentions_parameter"])
                or retry_caps != first_caps
                or retry.get("label") != first.get("label")
                or retry.get("stopped_at") != first.get("stopped_at")
            )

            if executable and executable.get("tool"):
                tool = str(executable["tool"])
                arguments = dict(executable.get("arguments") or {})
                if tool not in ALLOWED_TOOLS:
                    tool_exec = {
                        "status": "BLOCKED",
                        "reason": "existing_research_workspace_gate_does_not_expose_tool",
                        "tool": tool,
                        "arguments": arguments,
                    }
                    observation["tool_execution_actor"] = "not_executed"
                else:
                    executed = execute_exposed_tool(tool, arguments)
                    tool_exec = executed
                    observation["tool_execution_actor"] = (
                        "existing_research_execute_exposed_tool -> execute_registry_tool"
                    )
                    dump(run_dir / "06_tool.json", executed)
                    if executed.get("denied"):
                        tool_exec = {**executed, "status": "BLOCKED"}
                observation["tool_execution"] = tool_exec

                blocked = bool(
                    (tool_exec or {}).get("status") == "BLOCKED"
                    or (tool_exec or {}).get("denied")
                )
                if blocked:
                    observation["verdict"] = "PARTIAL"
                    observation["verdict_reason"] = (
                        "Grill → System Retry → Tool選択まで到達したが、"
                        "既存 research workspace 制約で Tool 実行は BLOCKED。"
                    )
                elif not info_increased:
                    observation["verdict"] = "FAIL"
                    observation["verdict_reason"] = "Tool は選ばれたが、Grill による情報増加が確認できない。"
                else:
                    observation["verdict"] = "PASS"
                    observation["verdict_reason"] = (
                        "System First では Action 化できず、Grill が未解決点を1段掘ったあと、"
                        "既存 Capability Resolution / Help / Index が Tool を選び、実行した。"
                    )
            elif selected_tool or retry_caps:
                observation["verdict"] = "PARTIAL"
                observation["verdict_reason"] = (
                    f"Grill 後に System は前進したが、実行可能 Action までは未到達 "
                    f"(stopped_at={retry.get('stopped_at')})。"
                )
            elif not info_increased:
                observation["verdict"] = "FAIL"
                observation["verdict_reason"] = "Grill 後も未解決点が実質変化せず、System が仕事を再開できなかった。"
            else:
                observation["verdict"] = "PARTIAL"
                observation["verdict_reason"] = (
                    "Grill は具体化したが、System Retry でも Capability まで届かなかった。"
                )

    elapsed = round(time.perf_counter() - started, 3)
    observation["elapsed_s"] = elapsed
    observation["timeline"] = {
        "1_goal": goal,
        "2_initial_state": state,
        "3_need": need,
        "4_system_first_input": first_request,
        "5_system_first_result": {
            "label": first.get("label"),
            "required_capabilities": first.get("required_capabilities"),
            "resolutions": first.get("resolutions"),
            "action": first.get("action"),
        },
        "6_system_stopped_at": first.get("stopped_at"),
        "7_grill_prompt": None if grill_got is None else grill_got.get("prompt"),
        "8_grill_raw": None if grill_got is None else grill_got.get("raw"),
        "9_grill_visible": None if not observation.get("grill") else observation["grill"]["visible"],
        "10_grill_beyond_meaning": None if not observation.get("grill") else observation["grill"]["concretized"],
        "11_grill_has_tool_name": None if not observation.get("grill") else observation["grill"]["tool_names_in_output"],
        "12_grill_has_capability_name": (
            None if not observation.get("grill") else observation["grill"]["capability_names_in_output"]
        ),
        "13_system_retry_input": None if retry is None else retry.get("request_text"),
        "14_retry_required_capabilities": None if retry is None else retry.get("required_capabilities"),
        "15_retry_capability_resolution": None if retry is None else retry.get("resolutions"),
        "16_help_index": help_trace,
        "17_selected_tool": observation.get("selected_tool"),
        "18_next_action": observation.get("next_action"),
        "19_tool_selection_actor": observation.get("tool_selection_actor"),
        "20_tool_execution_actor": observation.get("tool_execution_actor"),
        "21_tool_result": None if tool_exec is None else {
            k: tool_exec.get(k)
            for k in (
                "tool_name",
                "requested_arguments",
                "executed_arguments",
                "denied",
                "status",
                "normalized",
                "result",
            )
            if k in tool_exec or True
        },
        "22_elapsed_s": elapsed,
    }
    dump(run_dir / "observation.json", observation)
    dump(run_dir / "run.json", {
        "experiment": "grill_system_retry_v0",
        "run_id": run_id,
        "model": provider,
        "verdict": observation.get("verdict"),
        "verdict_reason": observation.get("verdict_reason"),
        "elapsed_s": elapsed,
        "production_modified": False,
    })
    print(
        json.dumps(
            {
                "run_id": run_id,
                "verdict": observation.get("verdict"),
                "system_first": first.get("label"),
                "retry": None if retry is None else retry.get("label"),
                "selected_tool": observation.get("selected_tool"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(f"RUN {run_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
