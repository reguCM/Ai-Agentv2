"""P2-5 search_files → read_file 連鎖 原因調査（診断専用・本番経路は変更しない）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.agent_integration.file_tools_integration_verify import (
    file_tools_system_prompt,
    run_file_tools_scenario,
)
from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import normalize_arguments
from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.llm import chat as ollama_chat

_REPO = Path(__file__).resolve().parents[2]


def _tool_result_json(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, indent=2)


def inspect_search_result(path: str, query: str) -> dict[str, Any]:
    raw = search_files(query, path=path)
    matches = raw.get("matches") or []
    paths = [m.get("path") for m in matches]
    gpu_impl = [p for p in paths if p and "gpu_status.py" in p]
    return {
        "path": path,
        "query": query,
        "ok": raw.get("ok"),
        "match_count": raw.get("match_count"),
        "files_scanned": raw.get("files_scanned"),
        "truncated": raw.get("truncated"),
        "error": raw.get("error"),
        "unique_paths_count": len(set(paths)),
        "sample_paths": paths[:8],
        "has_gpu_status_py": bool(gpu_impl),
        "gpu_status_paths": gpu_impl[:5],
        "first_match": matches[0] if matches else None,
        "payload_bytes": len(_tool_result_json(raw).encode("utf-8")),
    }


def run_instrumented_chain(
    user_request: str,
    *,
    scenario_id: str,
    model: str | None = None,
) -> dict[str, Any]:
    """2ラウンド目の LLM 応答（tool_calls 有無）を記録する。"""
    model = model or str(get_llm_profile().get("model") or "")
    pipeline = get_pipeline()
    max_r = int(pipeline.get("max_tool_rounds") or 5)
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {"role": "user", "content": user_request},
    ]

    trace: dict[str, Any] = {
        "scenario_id": scenario_id,
        "user_request": user_request,
        "model": model,
        "rounds": [],
    }

    for round_index in range(max_r):
        response = ollama_chat(model=model, messages=messages, tools=llm_tools)
        tool_calls = getattr(response.message, "tool_calls", None) or []
        content = str(getattr(response.message, "content", None) or "")
        round_info: dict[str, Any] = {
            "round_index": round_index,
            "llm_tool_call_count": len(tool_calls),
            "llm_content_preview": content[:500],
            "llm_tool_names": [tc.function.name for tc in tool_calls],
        }
        messages.append(response.message)

        if not tool_calls:
            round_info["stopped_reason"] = "no_tool_calls_final_answer"
            trace["rounds"].append(round_info)
            trace["final_answer"] = content
            trace["tool_sequence"] = [
                r.get("executed_tool")
                for r in trace["rounds"]
                if r.get("executed_tool")
            ]
            break

        for tc in tool_calls:
            name = tc.function.name
            args = normalize_arguments(tc.function.arguments)
            rec = execute_registry_tool(name, args)
            payload = _tool_result_json(rec.result)
            round_info["executed_tool"] = name
            round_info["tool_arguments"] = args
            round_info["harness_ok"] = rec.ok
            round_info["harness_error"] = rec.error
            round_info["result_ok_field"] = (
                rec.result.get("ok") if isinstance(rec.result, dict) else None
            )
            round_info["result_error_field"] = (
                rec.result.get("error") if isinstance(rec.result, dict) else None
            )
            round_info["payload_bytes"] = len(payload.encode("utf-8"))
            if name == "search_files" and isinstance(rec.result, dict):
                ms = rec.result.get("matches") or []
                round_info["match_count"] = rec.result.get("match_count")
                round_info["match_paths_sample"] = [m.get("path") for m in ms[:5]]
                round_info["payload_head"] = payload[:1200]
            if name == "list_files" and isinstance(rec.result, dict):
                round_info["entry_names"] = [
                    e.get("name") for e in (rec.result.get("entries") or [])
                ]
                round_info["payload_head"] = payload[:800]
            messages.append({"role": "tool", "tool_name": name, "content": payload})

        trace["rounds"].append(round_info)

    trace["tool_sequence"] = [r.get("executed_tool") for r in trace["rounds"] if r.get("executed_tool")]
    trace["read_file_after_search"] = (
        "search_files" in trace["tool_sequence"]
        and "read_file" in trace["tool_sequence"]
        and trace["tool_sequence"].index("read_file") > trace["tool_sequence"].index("search_files")
    )
    return trace


def run_post_search_llm_only(
    search_payload: dict[str, Any],
    *,
    model: str | None = None,
) -> dict[str, Any]:
    """Test 3: 実際の search_files 結果 JSON を tool メッセージとして渡し、次の LLM 応答のみ観測。"""
    model = model or str(get_llm_profile().get("model") or "")
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    payload = json.dumps(search_payload, ensure_ascii=False, indent=2)

    messages: list[dict[str, Any]] = [
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

    response = ollama_chat(model=model, messages=messages, tools=llm_tools)
    tool_calls = getattr(response.message, "tool_calls", None) or []
    return {
        "test": "post_real_search_payload_llm_only",
        "llm_tool_call_count": len(tool_calls),
        "llm_tool_names": [tc.function.name for tc in tool_calls],
        "read_file_called": any(tc.function.name == "read_file" for tc in tool_calls),
        "read_file_args": [
            normalize_arguments(tc.function.arguments)
            for tc in tool_calls
            if tc.function.name == "read_file"
        ],
        "llm_content_preview": str(getattr(response.message, "content", None) or "")[:400],
        "payload_match_count": search_payload.get("match_count"),
        "payload_bytes": len(payload.encode("utf-8")),
    }


def main() -> Path:
    model = str(get_llm_profile().get("model") or "")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out: dict[str, Any] = {
        "task_id": "FILE-TOOLS-CHAIN-DIAG-P2-5",
        "timestamp": ts,
        "model": model,
    }

    out["search_result_inspection"] = {
        "narrow_gpu": inspect_search_result("tools/system/gpu", "def get_gpu_status"),
        "narrow_symbol": inspect_search_result("tools/system/gpu", "get_gpu_status"),
        "wide_root": inspect_search_result(".", "get_gpu_status"),
    }

    narrow_prompt = (
        "tools/system/gpu 以下から get_gpu_status の定義を探し、"
        "見つかった実装ファイルを read_file で読んで、その実装内容を説明してください。"
    )
    out["narrow_search_read"] = run_instrumented_chain(
        narrow_prompt, scenario_id="narrow_gpu_search_read"
    )

    list_prompt = (
        "tests/fixtures に何があるか list_files で確認し、"
        "p2_read_file_sample.txt を read_file で読んで説明してください。"
    )
    out["list_read_control"] = run_instrumented_chain(
        list_prompt, scenario_id="list_read_control"
    )

    try:
        out["post_search_llm_only"] = run_post_search_llm_only(
            search_files("def get_gpu_status", path="tools/system/gpu"),
            model=model,
        )
    except Exception as exc:  # noqa: BLE001
        out["post_search_llm_only"] = {"error": f"{type(exc).__name__}: {exc}"}

    out["p24_c_replay"] = run_instrumented_chain(
        "Tool Registryで read_file がどこで定義または参照されているか探して、"
        "重要なファイルを1つ選んで内容を確認してください。",
        scenario_id="p24_c_replay",
    )

    run_dir = _REPO / "runs" / "ai_tool" / f"{ts}_file_tools_chain_diag_p25"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "diag.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=== search inspection (narrow) ===")
    print(json.dumps(out["search_result_inspection"]["narrow_gpu"], ensure_ascii=False, indent=2))
    print("\n=== narrow search→read sequence ===", out["narrow_search_read"]["tool_sequence"])
    print("read_file after search:", out["narrow_search_read"].get("read_file_after_search"))
    print("\n=== list→read control ===", out["list_read_control"]["tool_sequence"])
    print("\n=== post_search_llm_only ===", out.get("post_search_llm_only"))
    print(f"\nSaved: {path}")
    return path


if __name__ == "__main__":
    main()
