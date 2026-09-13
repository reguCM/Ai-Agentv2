"""Minimal Grill Tool Bridge: reuse Production Tool Calling for two file tools.

Does not register new tools. Does not modify ai_tool/chat_interface/agent_turn.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from ai_tool.agent_integration.production_bridge import ollama_tools_for_llm
from ai_tool.agent_integration.trial import normalize_arguments
from tools.file.workspace._paths import path_error, workspace_root
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.llm import chat as ollama_chat
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)
from tools.system.tool_contract import list_agent_visible_tools, registry_entry_to_ollama_tool
from tools.system.tool_result_contract import normalize_tool_result

ALLOWED_TOOLS = ("read_file", "search_files")

# Medium Task Reality Loop replica used by run 20260909T030450Z.
DEFAULT_SEARCH_PATH = "research/grill_observation_v0/medium_task_reality_v0/workspace"
ALLOWED_PATH_PREFIXES = (
    "research/grill_observation_v0/medium_task_reality_v0/workspace",
    "research/grill_observation_v0/medium_task_reality_v0/tests",
    "research/grill_observation_v0/medium_task_reality_v0/runs/20260909T030450Z/workspace_after",
    "research/grill_observation_v0/medium_task_reality_v0/runs/20260909T030450Z/workspace_before",
)

SYSTEM = """あなたは Grill 観察用の調査役です。
コードベースから分かることは、人間に聞かず Tool で調べてください。
利用できる Tool は search_files と read_file だけです。
調査対象は指定された実験 workspace 配下だけです。
Tool 結果にない内容を捏造しないでください。
まだコードは修正しないでください。
"""


def exposed_ollama_tools() -> list[dict[str, Any]]:
    tools = [
        registry_entry_to_ollama_tool(entry)
        for entry in list_agent_visible_tools()
        if str(entry.get("name") or "") in ALLOWED_TOOLS
    ]
    names = [t["function"]["name"] for t in tools]
    if set(names) != set(ALLOWED_TOOLS):
        raise RuntimeError(f"unexpected exposed tools: {names}")
    return ollama_tools_for_llm(tools)


def _posix(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("./")


def _is_allowed_rel(rel: str) -> bool:
    posix = _posix(rel)
    for prefix in ALLOWED_PATH_PREFIXES:
        if posix == prefix or posix.startswith(prefix + "/"):
            return True
    return False


def _remap_rel(rel: str) -> str | None:
    posix = _posix(rel)
    if _is_allowed_rel(posix):
        return posix
    if posix and "/" not in posix:
        candidate = f"{DEFAULT_SEARCH_PATH}/{posix}"
        if _is_allowed_rel(candidate):
            return candidate
    return None


def constrain_arguments(tool_name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Harness gate on existing Tool `path`. Does not change Tool implementations."""
    args = dict(arguments)
    raw_path = args.get("path")
    if tool_name == "search_files":
        if raw_path is None or str(raw_path).strip() in ("", "."):
            args["path"] = DEFAULT_SEARCH_PATH
            return args, None
        mapped = _remap_rel(str(raw_path))
        if mapped is None:
            return args, path_error(
                "experiment workspace 外への search は禁止です",
                code="experiment_boundary",
                path=raw_path,
            )
        args["path"] = mapped
        return args, None
    if tool_name == "read_file":
        if raw_path is None or not str(raw_path).strip():
            return args, path_error("path が空です", code="invalid_path")
        mapped = _remap_rel(str(raw_path))
        if mapped is None:
            return args, path_error(
                "experiment workspace 外への read は禁止です",
                code="experiment_boundary",
                path=raw_path,
            )
        args["path"] = mapped
        return args, None
    return args, path_error(f"tool not exposed: {tool_name}", code="tool_not_exposed")


def execute_exposed_tool(tool_name: str, arguments: Any) -> dict[str, Any]:
    args = normalize_arguments(arguments)
    if tool_name not in ALLOWED_TOOLS:
        denied = path_error(f"tool not exposed: {tool_name}", code="tool_not_exposed")
        return {
            "tool_name": tool_name,
            "requested_arguments": args,
            "executed_arguments": args,
            "denied": True,
            "record": None,
            "result": denied,
            "normalized": normalize_tool_result(denied, tool_name=tool_name),
        }
    constrained, err = constrain_arguments(tool_name, args)
    if err is not None:
        return {
            "tool_name": tool_name,
            "requested_arguments": args,
            "executed_arguments": constrained,
            "denied": True,
            "record": None,
            "result": err,
            "normalized": normalize_tool_result(err, tool_name=tool_name),
        }
    rec = execute_registry_tool(tool_name, constrained)
    result = rec.result if isinstance(rec.result, dict) else {"ok": rec.ok, "result": rec.result}
    return {
        "tool_name": tool_name,
        "requested_arguments": args,
        "executed_arguments": constrained,
        "denied": False,
        "record": rec.to_dict(),
        "result": result,
        "normalized": normalize_tool_result(result, tool_name=tool_name),
    }


def run_grill_tool_turn(
    *,
    user_request: str,
    max_rounds: int | None = None,
) -> dict[str, Any]:
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    pipeline = get_pipeline()
    rounds = int(max_rounds if max_rounds is not None else (pipeline.get("max_tool_rounds") or 5))
    llm_tools = exposed_ollama_tools()
    messages: list[Any] = [
        {
            "role": "system",
            "content": SYSTEM
            + f"\n調査起点 path: {DEFAULT_SEARCH_PATH}\n"
            + f"Production workspace root: {workspace_root().as_posix()}\n",
        },
        {"role": "user", "content": user_request},
    ]
    executions: list[dict[str, Any]] = []
    final = ""
    for round_index in range(rounds):
        response = ollama_chat(model=provider, messages=messages, tools=llm_tools)
        messages.append(response.message)
        calls = getattr(response.message, "tool_calls", None) or []
        if not calls:
            final = str(getattr(response.message, "content", None) or "")
            break
        for tc in calls:
            name = tc.function.name
            raw_args = tc.function.arguments
            executed = execute_exposed_tool(name, raw_args)
            executions.append(
                {
                    "round_index": round_index,
                    "tool_name": name,
                    "requested_arguments": executed["requested_arguments"],
                    "executed_arguments": executed["executed_arguments"],
                    "denied": executed["denied"],
                    "ok": bool((executed.get("normalized") or {}).get("ok")),
                    "normalized_status": (executed.get("normalized") or {}).get("status"),
                    "result": executed["result"],
                }
            )
            content = executed["result"]
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            messages.append({"role": "tool", "tool_name": name, "content": content})
    else:
        final = str(getattr(messages[-1], "content", None) or "") if messages else ""

    return {
        "model_id": model_id,
        "provider_model": provider,
        "num_ctx": profile.get("context_limit"),
        "max_rounds": rounds,
        "exposed_tools": list(ALLOWED_TOOLS),
        "workspace_root": str(workspace_root()),
        "experiment_default_path": DEFAULT_SEARCH_PATH,
        "allowed_path_prefixes": list(ALLOWED_PATH_PREFIXES),
        "user_request": user_request,
        "executions": executions,
        "final_answer": final,
    }
