"""P2-5A: Native Tool Calling messages 構造比較（診断専用）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama._client import _copy_messages
from ollama._types import Message

from ai_tool.agent_integration.file_tools_integration_verify import file_tools_system_prompt
from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import normalize_arguments
from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile
from tools.system.llm import chat as ollama_chat

_REPO = Path(__file__).resolve().parents[2]


def _serialize_message_item(item: Any, *, index: int) -> dict[str, Any]:
    """messages リスト内 1 件を JSON 化可能な dict に。"""
    info: dict[str, Any] = {"index": index, "input_type": type(item).__name__}

    if isinstance(item, Message):
        info["source"] = "ollama.Message"
        dump = item.model_dump()
        info["model_dump"] = dump
        info["role"] = dump.get("role")
        info["has_tool_calls"] = bool(dump.get("tool_calls"))
        info["tool_call_ids"] = _extract_tool_call_ids(dump.get("tool_calls"))
        info["tool_name_field"] = dump.get("tool_name")
        info["content_len"] = len(dump.get("content") or "")
        info["thinking_len"] = len(dump.get("thinking") or "")
        return info

    if isinstance(item, dict):
        info["source"] = "dict"
        info["raw_dict"] = item
        info["role"] = item.get("role")
        info["keys"] = sorted(item.keys())
        info["has_tool_calls"] = "tool_calls" in item
        info["tool_call_ids"] = _extract_tool_call_ids(item.get("tool_calls"))
        info["tool_name_field"] = item.get("tool_name")
        info["content_len"] = len(str(item.get("content") or ""))
        return info

    info["repr"] = repr(item)[:500]
    return info


def _extract_tool_call_ids(tool_calls: Any) -> list[str | None]:
    if not tool_calls:
        return []
    ids: list[str | None] = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            ids.append(tc.get("id"))
        else:
            dump = tc.model_dump() if hasattr(tc, "model_dump") else {}
            ids.append(dump.get("id") if isinstance(dump, dict) else None)
    return ids


def _serialize_messages_pipeline(messages: list[Any]) -> dict[str, Any]:
    """LLM へ渡す直前: 入力 messages と _copy_messages 後の正規化結果。"""
    normalized = list(_copy_messages(messages))
    return {
        "input_count": len(messages),
        "normalized_count": len(normalized),
        "input_messages": [_serialize_message_item(m, index=i) for i, m in enumerate(messages)],
        "normalized_messages": [
            {
                "index": i,
                "model_dump": m.model_dump(),
                "role": m.role,
                "tool_name": m.tool_name,
                "has_tool_calls": bool(m.tool_calls),
                "tool_call_ids": _extract_tool_call_ids(
                    [tc.model_dump() for tc in (m.tool_calls or [])]
                ),
            }
            for i, m in enumerate(normalized)
        ],
    }


def _tool_payload(path: str, query: str) -> str:
    rec = execute_registry_tool("search_files", {"path": path, "query": query})
    return json.dumps(rec.result, ensure_ascii=False, indent=2)


def capture_instrumented_before_round2(
    user_request: str,
    *,
    scenario_id: str,
    model: str,
) -> dict[str, Any]:
    """run_instrumented_chain 相当: search_files 実行後・2回目 LLM 直前の messages を保存。"""
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    messages: list[Any] = [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {"role": "user", "content": user_request},
    ]

    trace: dict[str, Any] = {"scenario_id": scenario_id, "path": "instrumented_chain"}

    # Round 0
    response0 = ollama_chat(model=model, messages=messages, tools=llm_tools)
    tool_calls0 = getattr(response0.message, "tool_calls", None) or []
    trace["round0_tool_names"] = [tc.function.name for tc in tool_calls0]
    messages.append(response0.message)

    if not tool_calls0:
        trace["error"] = "round0_no_tool_calls"
        trace["messages_before_round2"] = _serialize_messages_pipeline(messages)
        return trace

    round0_name = tool_calls0[0].function.name
    args0 = normalize_arguments(tool_calls0[0].function.arguments)
    rec0 = execute_registry_tool(round0_name, args0)
    payload0 = json.dumps(rec0.result, ensure_ascii=False, indent=2)
    tool_msg = {"role": "tool", "tool_name": round0_name, "content": payload0}
    messages.append(tool_msg)

    trace["round0_executed"] = round0_name
    trace["round0_arguments"] = args0
    trace["round0_payload_bytes"] = len(payload0.encode("utf-8"))
    trace["messages_before_round2"] = _serialize_messages_pipeline(messages)

    # Round 1 — 観測のみ（この時点の messages 構造が主目的）
    response1 = ollama_chat(model=model, messages=messages, tools=llm_tools)
    tcs1 = getattr(response1.message, "tool_calls", None) or []
    trace["round1_tool_names"] = [tc.function.name for tc in tcs1]
    trace["round1_content_preview"] = str(getattr(response1.message, "content", None) or "")[:300]
    trace["round1_assistant_dump"] = response1.message.model_dump()
    return trace


def capture_post_search_llm_only(
    search_payload: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    """run_post_search_llm_only 相当: LLM 呼び出し直前の messages。"""
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    payload = json.dumps(search_payload, ensure_ascii=False, indent=2)

    messages: list[Any] = [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {
            "role": "user",
            "content": (
                "tools/system/gpu 以下で get_gpu_status の定義ファイルを探し、"
                "read_file で実装を読んで説明してください。"
            ),
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "arguments": {
                            "path": "tools/system/gpu",
                            "query": "def get_gpu_status",
                        },
                    },
                }
            ],
        },
        {"role": "tool", "content": payload},
    ]

    trace: dict[str, Any] = {
        "path": "post_search_llm_only",
        "messages_before_llm": _serialize_messages_pipeline(messages),
    }

    response = ollama_chat(model=model, messages=messages, tools=llm_tools)
    tcs = getattr(response.message, "tool_calls", None) or []
    trace["llm_tool_names"] = [tc.function.name for tc in tcs]
    trace["read_file_called"] = any(tc.function.name == "read_file" for tc in tcs)
    trace["llm_content_preview"] = str(getattr(response.message, "content", None) or "")[:300]
    return trace


def capture_synthetic_variants(narrow_payload: str, *, model: str) -> dict[str, Any]:
    """tool_name 有無・assistant 型の差分を同一 payload で比較。"""
    tools = build_production_agent_tools()
    llm_tools = ollama_tools_for_llm(tools)
    user = (
        "tools/system/gpu 以下で get_gpu_status の定義ファイルを探し、"
        "read_file で実装を読んで説明してください。"
    )
    system = file_tools_system_prompt([t["function"]["name"] for t in tools])
    assistant_tc = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": "search_files",
                    "arguments": {"path": "tools/system/gpu", "query": "def get_gpu_status"},
                }
            }
        ],
    }

    variants = {
        "tool_with_tool_name": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            assistant_tc,
            {"role": "tool", "tool_name": "search_files", "content": narrow_payload},
        ],
        "tool_without_tool_name": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            assistant_tc,
            {"role": "tool", "content": narrow_payload},
        ],
    }

    results: dict[str, Any] = {}
    for name, msgs in variants.items():
        pipeline = _serialize_messages_pipeline(msgs)
        response = ollama_chat(model=model, messages=msgs, tools=llm_tools)
        tcs = getattr(response.message, "tool_calls", None) or []
        results[name] = {
            "messages_pipeline": pipeline,
            "llm_tool_names": [tc.function.name for tc in tcs],
            "read_file_called": any(tc.function.name == "read_file" for tc in tcs),
        }
    return results


def diff_message_pipelines(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    """normalized_messages の差分（構造のみ）。"""
    diffs: list[dict[str, Any]] = []
    na = a.get("normalized_messages") or []
    nb = b.get("normalized_messages") or []
    for i in range(max(len(na), len(nb))):
        ma = na[i] if i < len(na) else None
        mb = nb[i] if i < len(nb) else None
        if ma != mb:
            diffs.append({"index": i, "a": ma, "b": mb})
    return diffs


def main() -> Path:
    model = str(get_llm_profile().get("model") or "")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    narrow = search_files("def get_gpu_status", path="tools/system/gpu")
    narrow_payload = json.dumps(narrow, ensure_ascii=False, indent=2)

    out: dict[str, Any] = {
        "task_id": "FILE-TOOLS-CHAIN-MESSAGE-DIAG-P2-5A",
        "timestamp": ts,
        "model": model,
        "ollama_tool_call_has_id": False,
        "ollama_message_fields_note": "Message.tool_name exists; ToolCall has no id field",
    }

    # 失敗寄り: 広い search（P2-4 C 再現）
    out["instrumented_wide_search_fail"] = capture_instrumented_before_round2(
        "Tool Registryで read_file がどこで定義または参照されているか探して、"
        "重要なファイルを1つ選んで内容を確認してください。",
        scenario_id="p24_c_wide",
        model=model,
    )

    # 成功: 狭い search 明示
    out["instrumented_narrow_search_success"] = capture_instrumented_before_round2(
        "search_files ツールを使って tools/system/gpu 以下で def get_gpu_status を検索し、"
        "見つかったファイルを read_file で読んで説明してください。",
        scenario_id="narrow_force_search",
        model=model,
    )

    out["post_search_success"] = capture_post_search_llm_only(narrow, model=model)

    out["synthetic_tool_name_ab"] = capture_synthetic_variants(narrow_payload, model=model)

    # 比較: instrumented success round2 messages vs post_search
    inst_ok = out["instrumented_narrow_search_success"].get("messages_before_round2") or {}
    post = out["post_search_success"].get("messages_before_llm") or {}
    out["diff_instrumented_success_vs_post_search"] = diff_message_pipelines(inst_ok, post)

    run_dir = _REPO / "runs" / "ai_tool" / f"{ts}_file_tools_message_diag_p25a"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "message_diag.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Saved:", path)
    print("wide round1:", out["instrumented_wide_search_fail"].get("round1_tool_names"))
    print("narrow round1:", out["instrumented_narrow_search_success"].get("round1_tool_names"))
    print("post_search:", out["post_search_success"].get("llm_tool_names"))
    print("diff count:", len(out["diff_instrumented_success_vs_post_search"]))
    return path


if __name__ == "__main__":
    main()
