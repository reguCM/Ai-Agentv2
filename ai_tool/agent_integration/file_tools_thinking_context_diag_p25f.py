"""P2-5F: Qwen3:14b Native Tool Calling 不安定化 — Thinking / Context Size 切り分け（診断専用）。"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama import Client

from ai_tool.agent_integration.file_tools_integration_verify import file_tools_system_prompt
from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import normalize_arguments
from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile
from tools.system.llm import chat as production_ollama_chat

_REPO = Path(__file__).resolve().parents[2]

_SEARCH_PATH = "."
_SEARCH_QUERY = "read_file"
_USER_REQUEST = (
    "Tool Registryで read_file がどこで定義または参照されているか探して、"
    "重要なファイルを1つ選んで内容を確認してください。"
)
_RUNS_PER_CONDITION = 3


def _ollama_version() -> str:
    try:
        r = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return (r.stdout or r.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def _ollama_show(model: str) -> str:
    try:
        r = subprocess.run(
            ["ollama", "show", model],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return (r.stdout or r.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def _extract_thinking_tool_calls(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for block in re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", text, flags=re.DOTALL):
        block = block.strip()
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                found.append(parsed)
        except json.JSONDecodeError:
            found.append({"raw": block[:500]})
    return found


def _classify_output(
    *,
    tool_names: list[str],
    content: str,
    thinking: str,
) -> dict[str, Any]:
    combined = (thinking or "") + (content or "")
    thinking_tcs = _extract_thinking_tool_calls(combined)
    thinking_tool_names = [
        str(tc.get("name") or "")
        for tc in thinking_tcs
        if isinstance(tc, dict) and (tc.get("name") or tc.get("raw"))
    ]

    content_has_tool_call_tag = "<tool_call>" in (content or "")

    if tool_names:
        if "read_file" in tool_names:
            anomaly = "normal"
            output_type = 1
        else:
            anomaly = "native_other_tool"
            output_type = 2
    elif "<tool_call>" in combined:
        anomaly = "thinking_or_content_text_tool_call"
        output_type = 4
    elif content.strip():
        # 捏造 heuristic: read_file を言及しつつ code block / 仮想 等
        lower = content.lower()
        fabricated_hint = (
            "仮想" in content
            or "例）" in content
            or "例:" in content
            or ("read_file" in lower and "```" in content and "def " in content)
        )
        anomaly = "no_tool_fabricated_answer" if fabricated_hint else "no_tool_natural_language"
        output_type = 3
    else:
        anomaly = "other_empty"
        output_type = 5

    return {
        "output_type": output_type,
        "anomaly_class": anomaly,
        "native_read_file": "read_file" in tool_names,
        "thinking_has_tool_call_tag": "<tool_call>" in (thinking or ""),
        "content_has_tool_call_tag": content_has_tool_call_tag,
        "thinking_tool_calls": thinking_tcs,
        "thinking_tool_names": [n for n in thinking_tool_names if n],
        "read_file_intended_in_thinking": "read_file" in " ".join(thinking_tool_names)
        or ("read_file" in (thinking or "").lower() and not tool_names),
        "fabricated_answer_suspected": anomaly == "no_tool_fabricated_answer",
    }


def _build_messages(search_payload: dict[str, Any], tool_names: list[str]) -> list[dict[str, Any]]:
    payload = json.dumps(search_payload, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {"role": "user", "content": _USER_REQUEST},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "arguments": {"path": _SEARCH_PATH, "query": _SEARCH_QUERY},
                    },
                }
            ],
        },
        {"role": "tool", "content": payload},
    ]


def _inspect_production_llm_path() -> dict[str, Any]:
    """本番 tools/system/llm.py が渡す設定をコードから記録（変更しない）。"""
    profile = get_llm_profile()
    import inspect
    import tools.system.llm as llm_mod

    return {
        "api_route": "/api/chat (ollama.Client.chat → POST /api/chat)",
        "client_host": "default (OLLAMA_HOST or http://127.0.0.1:11434)",
        "production_chat_module": "tools.system.llm.chat",
        "think_parameter_in_production": "未指定 (None → モデルデフォルト)",
        "profile_context_limit": profile.get("context_limit"),
        "profile_num_predict": profile.get("num_predict"),
        "profile_temperature": profile.get("temperature"),
        "profile_keep_alive": profile.get("keep_alive"),
        "llm_chat_source_excerpt": inspect.getsource(llm_mod.chat),
    }


def run_single(
    *,
    condition_id: str,
    run_number: int,
    think: bool | None,
    context_size: int,
    search_payload: dict[str, Any],
    model: str,
    llm_tools: list[Any],
    tool_names: list[str],
    client: Client,
) -> dict[str, Any]:
    messages = _build_messages(search_payload, tool_names)
    payload_bytes = len(json.dumps(search_payload, ensure_ascii=False, indent=2).encode("utf-8"))

    options = {
        "num_ctx": context_size,
        "num_predict": int(get_llm_profile().get("num_predict") or 2048),
        "temperature": float(get_llm_profile().get("temperature") or 0),
    }

    chat_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "tools": llm_tools,
        "options": options,
        "keep_alive": get_llm_profile().get("keep_alive") or "5m",
    }
    if think is not None:
        chat_kwargs["think"] = think

    error: str | None = None
    response = None
    try:
        response = client.chat(**chat_kwargs)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    if response is None:
        return {
            "condition": condition_id,
            "run_number": run_number,
            "thinking_enabled": think,
            "context_size": context_size,
            "search_result_count": search_payload.get("match_count"),
            "search_result_payload_bytes": payload_bytes,
            "error": error,
        }

    dump = response.model_dump()
    msg = response.message
    msg_dump = msg.model_dump()
    tcs = getattr(msg, "tool_calls", None) or []
    tool_names_out = [tc.function.name for tc in tcs]
    content = str(getattr(msg, "content", None) or "")
    thinking = str(getattr(msg, "thinking", None) or "")

    classified = _classify_output(
        tool_names=tool_names_out,
        content=content,
        thinking=thinking,
    )

    read_file_args = [
        normalize_arguments(tc.function.arguments)
        for tc in tcs
        if tc.function.name == "read_file"
    ]

    return {
        "condition": condition_id,
        "run_number": run_number,
        "thinking_enabled": think,
        "context_size": context_size,
        "search_result_count": search_payload.get("match_count"),
        "search_result_payload_bytes": payload_bytes,
        "truncated": search_payload.get("truncated"),
        "error": error,
        "native_tool_call_count": len(tcs),
        "native_tool_call_names": tool_names_out,
        "native_read_file_args": read_file_args,
        "assistant_content": content,
        "assistant_thinking": thinking,
        "assistant_content_preview": content[:500],
        "assistant_thinking_preview": thinking[:800],
        "finish_reason": dump.get("done_reason"),
        "prompt_eval_count": dump.get("prompt_eval_count"),
        "eval_count": dump.get("eval_count"),
        "total_duration_ns": dump.get("total_duration"),
        "prompt_eval_duration_ns": dump.get("prompt_eval_duration"),
        "eval_duration_ns": dump.get("eval_duration"),
        **classified,
    }


def _summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in runs if not r.get("error")]
    return {
        "runs_total": len(runs),
        "runs_ok": len(ok),
        "runs_error": len(runs) - len(ok),
        "native_read_file": sum(1 for r in ok if r.get("native_read_file")),
        "native_other_tool": sum(
            1 for r in ok if r.get("native_tool_call_names") and not r.get("native_read_file")
        ),
        "no_tool_natural_language": sum(
            1 for r in ok if r.get("anomaly_class") == "no_tool_natural_language"
        ),
        "no_tool_fabricated": sum(
            1 for r in ok if r.get("anomaly_class") == "no_tool_fabricated_answer"
        ),
        "thinking_text_tool_call": sum(
            1 for r in ok if r.get("anomaly_class") == "thinking_or_content_text_tool_call"
        ),
        "other_empty": sum(1 for r in ok if r.get("anomaly_class") == "other_empty"),
    }


def main() -> Path:
    profile = get_llm_profile()
    model = str(profile.get("model") or "")
    current_ctx = int(profile.get("context_limit") or 4096)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    wide_raw = search_files(_SEARCH_QUERY, path=_SEARCH_PATH)
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)

    conditions: list[dict[str, Any]] = [
        {
            "id": "A",
            "label": "Thinking ON (think=True) + current context",
            "think": True,
            "context_size": current_ctx,
        },
        {
            "id": "B",
            "label": "Thinking OFF (think=False) + current context",
            "think": False,
            "context_size": current_ctx,
        },
    ]
    if current_ctx < 8192:
        conditions.append(
            {
                "id": "C",
                "label": "Thinking ON (think=True) + context 8192",
                "think": True,
                "context_size": 8192,
            }
        )
    if current_ctx < 16384:
        conditions.append(
            {
                "id": "D",
                "label": "Thinking ON (think=True) + context 16384",
                "think": True,
                "context_size": 16384,
            }
        )

    # 本番経路参考: think 未指定（P2-5E と同型）
    conditions.append(
        {
            "id": "REF_production_path",
            "label": "Reference: production ollama_chat (think unset, current context)",
            "think": "production",
            "context_size": current_ctx,
        }
    )

    timeout = int(profile.get("timeout_seconds") or 90)
    client = Client(timeout=max(timeout, 180))

    out: dict[str, Any] = {
        "task_id": "FILE-TOOLS-THINKING-CONTEXT-DIAG-P2-5F",
        "timestamp": ts,
        "environment": {
            "ollama_version": _ollama_version(),
            "ollama_show_qwen3_14b": _ollama_show(model),
            "model": model,
            "production_llm_path": _inspect_production_llm_path(),
        },
        "p25e_baseline": {
            "case_f_match_count": 39,
            "case_f_native_read_file": "0/3 (Type 3 捏造回答)",
            "reference_run": "runs/ai_tool/20260902T062345Z_file_tools_search_result_volume_diag_p25e/volume_diag.json",
        },
        "experiment": {
            "search_condition": {"path": _SEARCH_PATH, "query": _SEARCH_QUERY},
            "user_request": _USER_REQUEST,
            "search_payload_inspection": {
                "match_count": wide_raw.get("match_count"),
                "payload_bytes": len(
                    json.dumps(wide_raw, ensure_ascii=False, indent=2).encode("utf-8")
                ),
                "truncated": wide_raw.get("truncated"),
                "error": wide_raw.get("error"),
                "files_scanned": wide_raw.get("files_scanned"),
            },
            "runs_per_condition": _RUNS_PER_CONDITION,
            "conditions": conditions,
        },
        "results": {},
    }

    for cond in conditions:
        cid = cond["id"]
        runs: list[dict[str, Any]] = []
        for run_num in range(1, _RUNS_PER_CONDITION + 1):
            if cond["think"] == "production":
                # 本番経路 1 回参照（think 未指定）
                messages = _build_messages(wide_raw, tool_names)
                try:
                    response = production_ollama_chat(
                        model=model,
                        messages=messages,
                        tools=llm_tools,
                    )
                    dump = response.model_dump()
                    msg = response.message
                    tcs = getattr(msg, "tool_calls", None) or []
                    tool_names_out = [tc.function.name for tc in tcs]
                    content = str(getattr(msg, "content", None) or "")
                    thinking = str(getattr(msg, "thinking", None) or "")
                    classified = _classify_output(
                        tool_names=tool_names_out, content=content, thinking=thinking
                    )
                    runs.append(
                        {
                            "condition": cid,
                            "run_number": run_num,
                            "thinking_enabled": None,
                            "context_size": current_ctx,
                            "via": "tools.system.llm.chat (production)",
                            "search_result_count": wide_raw.get("match_count"),
                            "search_result_payload_bytes": len(
                                json.dumps(wide_raw, ensure_ascii=False, indent=2).encode("utf-8")
                            ),
                            "native_tool_call_count": len(tcs),
                            "native_tool_call_names": tool_names_out,
                            "assistant_content_preview": content[:500],
                            "assistant_thinking_preview": thinking[:800],
                            "finish_reason": dump.get("done_reason"),
                            "prompt_eval_count": dump.get("prompt_eval_count"),
                            "eval_count": dump.get("eval_count"),
                            "total_duration_ns": dump.get("total_duration"),
                            **classified,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    runs.append(
                        {
                            "condition": cid,
                            "run_number": run_num,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
            else:
                runs.append(
                    run_single(
                        condition_id=cid,
                        run_number=run_num,
                        think=cond["think"],
                        context_size=int(cond["context_size"]),
                        search_payload=wide_raw,
                        model=model,
                        llm_tools=llm_tools,
                        tool_names=tool_names,
                        client=client,
                    )
                )

        out["results"][cid] = {
            "condition": cond,
            "summary": _summarize_runs(runs),
            "runs": runs,
        }

    run_dir = _REPO / "runs" / "ai_tool" / f"{ts}_file_tools_thinking_context_diag_p25f"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "diag.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Saved:", path)
    for cid, block in out["results"].items():
        s = block["summary"]
        print(
            f"  {cid:22} native_read_file={s['native_read_file']}/{s['runs_ok']} "
            f"fabricated={s['no_tool_fabricated']} thinking_tc={s['thinking_text_tool_call']}"
        )
    return path


if __name__ == "__main__":
    main()
