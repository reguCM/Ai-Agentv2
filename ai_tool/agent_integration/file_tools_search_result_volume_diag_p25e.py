"""P2-5E: search_files 結果量・truncated・Native Tool Call 逸脱の診断（診断専用）。"""
from __future__ import annotations

import copy
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.agent_integration.file_tools_integration_verify import file_tools_system_prompt
from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import normalize_arguments
from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile
from tools.system.llm import chat as ollama_chat

_REPO = Path(__file__).resolve().parents[2]

# 同一検索条件（P2-4 C / P2-5A 広い search と整合）
_SEARCH_PATH = "."
_SEARCH_QUERY = "read_file"

_USER_REQUEST = (
    "Tool Registryで read_file がどこで定義または参照されているか探して、"
    "重要なファイルを1つ選んで内容を確認してください。"
)

_RUNS_PER_CASE = 3


def _payload_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def _payload_bytes(result: dict[str, Any]) -> int:
    return len(_payload_json(result).encode("utf-8"))


def _unique_paths(matches: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in matches:
        p = str(m.get("path") or "")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _analyze_result_quality(result: dict[str, Any]) -> dict[str, Any]:
    matches = list(result.get("matches") or [])
    paths = [str(m.get("path") or "") for m in matches]
    unique = _unique_paths(matches)
    path_counts = Counter(paths)
    multi_match_files = [p for p, c in path_counts.items() if c > 1]
    registry_paths = [p for p in paths if "registry" in p.lower()]
    impl_paths = [p for p in unique if p.endswith(".py") and "test" not in p.lower()]
    return {
        "match_count": result.get("match_count"),
        "files_scanned": result.get("files_scanned"),
        "truncated": result.get("truncated"),
        "error": result.get("error"),
        "payload_bytes": _payload_bytes(result),
        "unique_paths_count": len(unique),
        "multi_match_file_count": len(multi_match_files),
        "multi_match_files_sample": multi_match_files[:5],
        "registry_related_in_matches": bool(registry_paths),
        "registry_paths_sample": registry_paths[:5],
        "impl_py_count": len(impl_paths),
        "first_match": matches[0] if matches else None,
        "last_match": matches[-1] if matches else None,
        "first_three_paths": paths[:3],
        "last_three_paths": paths[-3:] if paths else [],
    }


def _slice_search_result(
    base: dict[str, Any],
    n: int,
    *,
    keep_truncated: bool = False,
) -> dict[str, Any]:
    """実 search 結果から matches を n 件に切り詰めた payload（Tool Result 形式変更ではない）。"""
    out = copy.deepcopy(base)
    matches = list(out.get("matches") or [])[:n]
    out["matches"] = matches
    out["match_count"] = len(matches)
    if not keep_truncated:
        out["truncated"] = False
        out["error"] = None
    return out


def _extract_thinking_tool_calls(text: str) -> list[dict[str, Any]]:
    """thinking/content 内 <tool_call> を抽出（実行はしない）。"""
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


def classify_llm_output(response: Any) -> dict[str, Any]:
    """Type 1〜5 分類。"""
    dump = response.message.model_dump()
    tcs = getattr(response.message, "tool_calls", None) or []
    thinking = str(dump.get("thinking") or "")
    content = str(dump.get("content") or "")
    combined = thinking + content

    tool_names = [tc.function.name for tc in tcs]
    thinking_tcs = _extract_thinking_tool_calls(combined)
    thinking_tool_names = [
        str(tc.get("name") or tc.get("function", {}).get("name") or "")
        for tc in thinking_tcs
        if isinstance(tc, dict)
    ]

    if tcs:
        if "read_file" in tool_names:
            output_type = 1
            label = "native_read_file"
        else:
            output_type = 2
            label = "native_other_tool"
    elif "<tool_call>" in combined:
        output_type = 4
        label = "thinking_text_tool_call"
    elif content.strip():
        output_type = 3
        label = "no_tool_natural_language"
    else:
        output_type = 5
        label = "other_empty"

    read_file_args = [
        normalize_arguments(tc.function.arguments)
        for tc in tcs
        if tc.function.name == "read_file"
    ]

    return {
        "output_type": output_type,
        "output_label": label,
        "native_tool_names": tool_names,
        "native_read_file_args": read_file_args,
        "thinking_tool_calls": thinking_tcs,
        "thinking_tool_names": [n for n in thinking_tool_names if n],
        "read_file_intended_in_thinking": "read_file" in thinking_tool_names,
        "content_preview": content[:400],
        "thinking_preview": thinking[:600] if thinking else None,
        "assistant_dump": dump,
    }


def run_post_search_with_payload(
    search_payload: dict[str, Any],
    *,
    model: str,
    search_path: str = _SEARCH_PATH,
    search_query: str = _SEARCH_QUERY,
) -> dict[str, Any]:
    """P2-5A post_search_llm_only 相当: 指定 payload を tool result として LLM へ渡す。"""
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    payload = _payload_json(search_payload)

    messages: list[Any] = [
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
                        "arguments": {"path": search_path, "query": search_query},
                    },
                }
            ],
        },
        {"role": "tool", "content": payload},
    ]

    response = ollama_chat(model=model, messages=messages, tools=llm_tools)
    classified = classify_llm_output(response)
    return {
        "result_quality": _analyze_result_quality(search_payload),
        **classified,
    }


def run_case_repeated(
    case_id: str,
    search_payload: dict[str, Any],
    *,
    model: str,
    runs: int = _RUNS_PER_CASE,
    note: str = "",
) -> dict[str, Any]:
    quality = _analyze_result_quality(search_payload)
    run_results: list[dict[str, Any]] = []
    for i in range(runs):
        run_results.append(
            run_post_search_with_payload(search_payload, model=model)
        )

    label_counts = Counter(r["output_label"] for r in run_results)
    type_counts = Counter(r["output_type"] for r in run_results)

    return {
        "case_id": case_id,
        "note": note,
        "runs": runs,
        "result_quality": quality,
        "summary": {
            "native_read_file": label_counts.get("native_read_file", 0),
            "native_other_tool": label_counts.get("native_other_tool", 0),
            "no_tool_natural_language": label_counts.get("no_tool_natural_language", 0),
            "thinking_text_tool_call": label_counts.get("thinking_text_tool_call", 0),
            "other_empty": label_counts.get("other_empty", 0),
            "type_counts": dict(type_counts),
            "label_counts": dict(label_counts),
        },
        "run_details": run_results,
    }


def _build_volume_cases(wide_raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Case A〜E: 同一 wide search から件数だけ変える。"""
    all_matches = list(wide_raw.get("matches") or [])
    specs = [
        ("A", 1, "1件"),
        ("B", 5, "3〜5件"),
        ("C", 10, "10件"),
        ("D", 20, "20件"),
        ("E", min(30, len(all_matches)), "30件"),
    ]
    cases: dict[str, dict[str, Any]] = {}
    for case_id, n, note in specs:
        n = min(n, len(all_matches))
        if n < 1:
            continue
        cases[case_id] = {
            "payload": _slice_search_result(wide_raw, n, keep_truncated=False),
            "note": note,
        }
    # Case E alternate: 50件（取得できれば）
    if len(all_matches) >= 40:
        cases["E50"] = {
            "payload": _slice_search_result(wide_raw, min(50, len(all_matches)), keep_truncated=False),
            "note": "40〜50件",
        }
    return cases


def _build_control_cases(wide_raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """対照実験: truncated 有無、payload サイズ vs 件数。"""
    all_matches = list(wide_raw.get("matches") or [])
    cases: dict[str, dict[str, Any]] = {}

    # 対照2: 同一20件で truncated=false vs true
    if len(all_matches) >= 20:
        base20 = _slice_search_result(wide_raw, 20, keep_truncated=False)
        trunc20 = copy.deepcopy(base20)
        trunc20["truncated"] = True
        trunc20["error"] = "マッチ数が上限 50 に達したため打ち切りました"
        cases["CTRL_trunc_false_20"] = {
            "payload": base20,
            "note": "20件・truncated=false",
        }
        cases["CTRL_trunc_true_20"] = {
            "payload": trunc20,
            "note": "20件・truncated=true（人工フラグ）",
        }

    # 対照1: 少数長 vs 多数短（自然な matches から）
    # 長い text を持つ match を優先して3件 vs 先頭15件
    by_text_len = sorted(all_matches, key=lambda m: len(str(m.get("text") or "")), reverse=True)
    long3 = _slice_search_result({**wide_raw, "matches": by_text_len[:3]}, 3, keep_truncated=False)
    short15 = _slice_search_result(wide_raw, min(15, len(all_matches)), keep_truncated=False)
    cases["CTRL_few_long_3"] = {
        "payload": long3,
        "note": "少数・各行textが長い3件",
    }
    cases["CTRL_many_short_15"] = {
        "payload": short15,
        "note": "多数・先頭15件（短い行が多い）",
    }

    return cases


def main() -> Path:
    model = str(get_llm_profile().get("model") or "")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    wide_raw = search_files(_SEARCH_QUERY, path=_SEARCH_PATH)
    wide_quality = _analyze_result_quality(wide_raw)

    out: dict[str, Any] = {
        "task_id": "FILE-TOOLS-CHAIN-DIAG-P2-5E",
        "timestamp": ts,
        "model": model,
        "search_condition": {"path": _SEARCH_PATH, "query": _SEARCH_QUERY},
        "user_request": _USER_REQUEST,
        "runs_per_case": _RUNS_PER_CASE,
        "wide_raw_inspection": wide_quality,
        "p25a_reference": {
            "report": "reports/FILE-TOOLS-CHAIN-MESSAGE-DIAG-P2-5A.md",
            "run": "runs/ai_tool/20260902T061739Z_file_tools_message_diag_p25a/message_diag.json",
        },
    }

    cases: dict[str, Any] = {}

    # Case A〜E (+ E50 if available)
    for case_id, spec in _build_volume_cases(wide_raw).items():
        cases[case_id] = run_case_repeated(
            case_id,
            spec["payload"],
            model=model,
            note=spec["note"],
        )

    # Case F: 実際の truncated 結果（改変なし）
    cases["F"] = run_case_repeated(
        "F",
        wide_raw,
        model=model,
        note="実際の truncated 結果（改変なし）",
    )

    # 対照実験
    for ctrl_id, spec in _build_control_cases(wide_raw).items():
        cases[ctrl_id] = run_case_repeated(
            ctrl_id,
            spec["payload"],
            model=model,
            note=spec["note"],
        )

    out["cases"] = cases

    # 集計表用サマリー
    summary_rows: list[dict[str, Any]] = []
    for case_id, case in sorted(cases.items()):
        q = case["result_quality"]
        s = case["summary"]
        summary_rows.append(
            {
                "case_id": case_id,
                "note": case.get("note"),
                "match_count": q["match_count"],
                "payload_bytes": q["payload_bytes"],
                "truncated": q["truncated"],
                "error": q["error"],
                "unique_paths": q["unique_paths_count"],
                "native_read_file": s["native_read_file"],
                "native_other_tool": s["native_other_tool"],
                "no_tool": s["no_tool_natural_language"],
                "thinking_tool_call": s["thinking_text_tool_call"],
                "other": s["other_empty"],
                "runs": case["runs"],
            }
        )
    out["summary_table"] = summary_rows

    run_dir = _REPO / "runs" / "ai_tool" / f"{ts}_file_tools_search_result_volume_diag_p25e"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "volume_diag.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Saved:", path)
    print("wide match_count:", wide_quality["match_count"], "truncated:", wide_quality["truncated"])
    for row in summary_rows:
        print(
            f"  {row['case_id']:20} matches={row['match_count']:3} "
            f"bytes={row['payload_bytes']:5} "
            f"native_rf={row['native_read_file']}/{row['runs']} "
            f"thinking_tc={row['thinking_tool_call']}/{row['runs']}"
        )
    return path


if __name__ == "__main__":
    main()
