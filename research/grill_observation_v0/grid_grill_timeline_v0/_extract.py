"""One-shot READ-ONLY extractor. Does not call LLM or modify source runs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "research/grill_observation_v0/resolver_owner_v0/runs/20260909T064802Z/case2"
OUT = ROOT / "research/grill_observation_v0/grid_grill_timeline_v0"
GDIR = OUT / "gemini_inputs"


def main() -> None:
    GDIR.mkdir(parents=True, exist_ok=True)
    need_p = (SRC / "01_need_prompt.txt").read_text(encoding="utf-8")
    need_r = (SRC / "01_need_raw.txt").read_text(encoding="utf-8")
    first = json.loads((SRC / "02_system_first.json").read_text(encoding="utf-8"))
    g1p = (SRC / "03_grill_prompt.txt").read_text(encoding="utf-8")
    g1r = (SRC / "03_grill_raw.txt").read_text(encoding="utf-8")
    r1 = json.loads((SRC / "04_system_retry.json").read_text(encoding="utf-8"))
    g2p = (SRC / "05_grill_prompt.txt").read_text(encoding="utf-8")
    g2r = (SRC / "05_grill_raw.txt").read_text(encoding="utf-8")
    r2 = json.loads((SRC / "06_system_retry.json").read_text(encoding="utf-8"))
    case = json.loads((SRC / "case.json").read_text(encoding="utf-8"))
    g1v = case["grills"][0]["visible"]
    g2v = case["grills"][1]["visible"]
    need_v = case["need_llm"]["visible"]

    shutil.copyfile(SRC / "03_grill_prompt.txt", GDIR / "01_grill_1_input.txt")
    shutil.copyfile(SRC / "03_grill_prompt.txt", GDIR / "01_grill_1_user.txt")
    shutil.copyfile(SRC / "05_grill_prompt.txt", GDIR / "02_grill_2_input.txt")
    shutil.copyfile(SRC / "05_grill_prompt.txt", GDIR / "02_grill_2_user.txt")
    shutil.copyfile(SRC / "01_need_prompt.txt", GDIR / "00_need_user.txt")
    (GDIR / "LLM_CALL_FACTS.txt").write_text(
        "\n".join(
            [
                "Source run: research/grill_observation_v0/resolver_owner_v0/runs/20260909T064802Z/case2",
                "Code: research/grill_observation_v0/resolver_owner_v0/run_once.py llm()",
                "call_freeform messages = [role=user, content=user prompt only]",
                "system_prompt_present: false",
                "format=json: false",
                "Need / Grill 1 / Grill 2: saved raw equals visible (no think-tag strip change).",
                "These files are the user prompts Qwen received. Qwen outputs are not included.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    steps = {
        "source_run": "research/grill_observation_v0/resolver_owner_v0/runs/20260909T064802Z/case2",
        "model": "qwen3:14b",
        "llm_call": {
            "messages_roles": ["user"],
            "system_prompt_present": False,
            "format_json": False,
            "code": "research/grill_observation_v0/resolver_owner_v0/run_once.py llm() -> call_freeform",
        },
        "harness_unknown_field_not_in_llm_prompt": case.get("unknown"),
        "steps": [
            {
                "id": "S00",
                "name": "User Goal",
                "producer": "USER",
                "provenance": "USER_GOAL",
                "input": None,
                "output": case["goal"],
                "added": ["grid", "検索", "内容", "要約"],
                "removed": [],
                "transformed": [],
            },
            {
                "id": "S00s",
                "name": "State",
                "producer": "USER",
                "provenance": "STATE",
                "input": None,
                "output": case["initial_state"],
                "added": ["まだ何も調査していない。"],
                "removed": [],
                "transformed": [],
            },
            {
                "id": "S01",
                "name": "Need LLM Input",
                "producer": "SYSTEM",
                "provenance": "SYSTEM",
                "input": need_p,
                "output": None,
                "added": ["今まず解決する必要があることを1つだけ出してください。"],
                "removed": [],
                "transformed": [],
                "note": "Goal and State copied into user prompt. case.json unknown field was not in this prompt.",
            },
            {
                "id": "S02",
                "name": "Need LLM Output",
                "producer": "QWEN",
                "provenance": "QWEN",
                "input": need_p,
                "output_raw": need_r,
                "output_visible": need_v,
                "strip_think_changed": need_r != need_v,
                "added": ["構造", "確認する"],
                "removed": ["要約してほしい", "検索して"],
                "transformed": ["その内容を要約 -> 構造と内容を確認する"],
            },
            {
                "id": "S03",
                "name": "System First",
                "producer": "SYSTEM",
                "provenance": "SYSTEM",
                "input": first["request_text"],
                "output": first,
                "added": [
                    "label=UNRESOLVED",
                    "stopped_at=no_required_capability",
                    "status=NOT_NEEDED",
                    "next_action=null",
                ],
                "removed": [],
                "transformed": [],
            },
            {
                "id": "S04",
                "name": "Grill 1 Input",
                "producer": "SYSTEM",
                "provenance": "SYSTEM",
                "input": g1p,
                "output": None,
                "added": [
                    "停止場所: no_required_capability",
                    "【Grounding】",
                    "一度に1段だけ掘ってください。",
                ],
                "removed": [],
                "transformed": ["Next need: -> 現在の未解決点:"],
            },
            {
                "id": "S05",
                "name": "Grill 1 Output",
                "producer": "QWEN",
                "provenance": "QWEN",
                "input": g1p,
                "output_raw": g1r,
                "output_visible": g1v,
                "strip_think_changed": g1r != g1v,
                "added": [
                    "ヘッダー",
                    "列名",
                    "行/列の数",
                    "データの形式",
                    "セル",
                    "10行×5列",
                    "確認済みと仮定",
                    "リンク",
                ],
                "removed": [],
                "transformed": [
                    "構造と内容 -> 構造（例: 行/列の数、ヘッダーの内容、データの形式）と具体的な情報（例: 文字列/数値/日付など）が不明"
                ],
            },
            {
                "id": "S06",
                "name": "System Retry 1",
                "producer": "SYSTEM",
                "provenance": "SYSTEM",
                "input": r1["request_text"],
                "output": r1,
                "added": [
                    "workspace_file_search",
                    "search_files",
                    "label=PARTIAL",
                    "stopped_at=tool_selected_arguments_incomplete",
                ],
                "removed": ["label=UNRESOLVED", "stopped_at=no_required_capability"],
                "transformed": ["Grill 1 visible concatenated under Grill:"],
            },
            {
                "id": "S07",
                "name": "Grill 2 Input",
                "producer": "SYSTEM",
                "provenance": "SYSTEM",
                "input": g2p,
                "output": None,
                "added": [
                    "停止場所: tool_selected_arguments_incomplete",
                    "不足している arguments 等だけを1段掘ってください。",
                ],
                "removed": ["現在の未解決点: gridの構造と内容を確認する。"],
                "transformed": ["現在の未解決点 := Grill 1 visible"],
            },
            {
                "id": "S08",
                "name": "Grill 2 Output",
                "producer": "QWEN",
                "provenance": "QWEN",
                "input": g2p,
                "output_raw": g2r,
                "output_visible": g2v,
                "strip_think_changed": g2r != g2v,
                "added": [
                    '"ID"',
                    '"名前"',
                    '"金額"',
                    '"山田太郎"',
                    '"123"',
                    '"2023-01-01"',
                    '"https://example.com"',
                    '"数百行×数十列"',
                ],
                "removed": [],
                "transformed": ["例: 文字列/数値/日付 -> 例: \"ID\", \"名前\" ... は不明"],
            },
            {
                "id": "S09",
                "name": "System Retry 2 Input",
                "producer": "SYSTEM",
                "provenance": "SYSTEM",
                "input": r2["request_text"],
                "output": None,
                "added": ["Grill: + Grill 2 visible"],
                "removed": [],
                "transformed": [],
            },
            {
                "id": "S10",
                "name": "System Retry 2 Extraction / next_action",
                "producer": "SYSTEM",
                "provenance": "SYSTEM",
                "input": r2["request_text"],
                "output": {
                    "label": r2["label"],
                    "stopped_at": r2["stopped_at"],
                    "required_capabilities": r2["required_capabilities"],
                    "resolutions": r2["resolutions"],
                    "tool_expectation": r2["tool_expectation"],
                    "action": r2["action"],
                },
                "added": [
                    "workspace_file_read",
                    "read_file",
                    "url_fetch",
                    "read_url_text",
                    'query="ID"',
                    'path="."',
                    "stopped_at=executable_action",
                    "label=RESOLVED",
                ],
                "removed": ["search_files next_action=null"],
                "transformed": [
                    'Qwen text 例: "ID" ... が不明 -> System next_action.arguments.query="ID"'
                ],
                "note": "Qwen output does not contain query= or search_files. Those strings appear first in System output.",
            },
        ],
        "adjacent_diffs": [
            {
                "from": "S00",
                "to": "S02",
                "ADDED": ["構造", "確認する"],
                "REMOVED": ["要約してほしい"],
                "REFRAMED": ["内容を要約 -> 構造と内容を確認"],
                "UNCHANGED": ["grid"],
            },
            {
                "from": "S02",
                "to": "S03",
                "ADDED": ["UNRESOLVED", "no_required_capability"],
                "REMOVED": [],
                "REFRAMED": ["Need string placed under Next need:"],
                "UNCHANGED": ["Goal", "State", "Need visible text"],
            },
            {
                "from": "S03",
                "to": "S04",
                "ADDED": ["Grounding block", "停止場所: no_required_capability"],
                "REMOVED": [],
                "REFRAMED": ["Next need -> 現在の未解決点"],
                "UNCHANGED": ["Goal", "State", "Need visible"],
            },
            {
                "from": "S04",
                "to": "S05",
                "ADDED": ["ヘッダー", "列名", "10行×5列", "確認済みと仮定"],
                "REMOVED": [],
                "REFRAMED": ["構造と内容 -> 不明な構造の例示"],
                "UNCHANGED": ["grid"],
            },
            {
                "from": "S05",
                "to": "S06",
                "ADDED": ["workspace_file_search", "search_files", "tool_selected_arguments_incomplete"],
                "REMOVED": [],
                "REFRAMED": ["Grill 1 visible copied under Grill:"],
                "UNCHANGED": ["Grill 1 visible text body"],
            },
            {
                "from": "S06",
                "to": "S07",
                "ADDED": ["不足している arguments 等だけを1段掘ってください。"],
                "REMOVED": ["Need-only 未解決点 as the 未解決点 field"],
                "REFRAMED": ["現在の未解決点 := Grill 1 output"],
                "UNCHANGED": ["Goal", "State", "Grounding block"],
            },
            {
                "from": "S07",
                "to": "S08",
                "ADDED": ['"ID"', '"名前"', '"金額"', '"山田太郎"', "https://example.com"],
                "REMOVED": [],
                "REFRAMED": ["unquoted type examples -> quoted column-name examples marked 不明"],
                "UNCHANGED": ["ヘッダー（列名）", "セルのデータ種類", "行数や列数"],
            },
            {
                "from": "S08",
                "to": "S09",
                "ADDED": ["Grill 2 visible concatenated"],
                "REMOVED": [],
                "REFRAMED": [],
                "UNCHANGED": ["Grill 2 visible body"],
            },
            {
                "from": "S09",
                "to": "S10",
                "ADDED": ['query="ID"', 'path="."', "read_file", "url_fetch", "executable_action"],
                "REMOVED": ["search_files next_action=null"],
                "REFRAMED": ['quoted example ID -> Action argument query'],
                "UNCHANGED": ["request_text body"],
            },
        ],
        "term_first_seen": [
            {"term": "grid", "first_seen_step": "S00", "producer": "USER", "provenance": "USER_GOAL"},
            {"term": "検索", "first_seen_step": "S00", "producer": "USER", "provenance": "USER_GOAL"},
            {"term": "内容", "first_seen_step": "S00", "producer": "USER", "provenance": "USER_GOAL"},
            {"term": "要約", "first_seen_step": "S00", "producer": "USER", "provenance": "USER_GOAL"},
            {"term": "構造", "first_seen_step": "S02", "producer": "QWEN", "provenance": "QWEN"},
            {"term": "未解決点", "first_seen_step": "S04", "producer": "SYSTEM", "provenance": "SYSTEM"},
            {"term": "UNRESOLVED", "first_seen_step": "S03", "producer": "SYSTEM", "provenance": "SYSTEM"},
            {"term": "no_required_capability", "first_seen_step": "S03", "producer": "SYSTEM", "provenance": "SYSTEM"},
            {"term": "next_action", "first_seen_step": "S03", "producer": "SYSTEM", "provenance": "SYSTEM", "value": None},
            {"term": "ヘッダー", "first_seen_step": "S05", "producer": "QWEN", "provenance": "QWEN"},
            {"term": "日付", "first_seen_step": "S05", "producer": "QWEN", "provenance": "QWEN", "form": "例: 文字列/数値/日付など"},
            {"term": "workspace_file_search", "first_seen_step": "S06", "producer": "SYSTEM", "provenance": "SYSTEM"},
            {"term": "search_files", "first_seen_step": "S06", "producer": "SYSTEM", "provenance": "SYSTEM"},
            {"term": "ID", "first_seen_step": "S08", "producer": "QWEN", "provenance": "QWEN", "form": '例: "ID" ... が不明'},
            {"term": "名前", "first_seen_step": "S08", "producer": "QWEN", "provenance": "QWEN"},
            {"term": "金額", "first_seen_step": "S08", "producer": "QWEN", "provenance": "QWEN"},
            {"term": "query", "first_seen_step": "S10", "producer": "SYSTEM", "provenance": "SYSTEM", "value": "ID"},
            {"term": "path", "first_seen_step": "S10", "producer": "SYSTEM", "provenance": "SYSTEM", "value": "."},
            {"term": "workspace_file_read", "first_seen_step": "S10", "producer": "SYSTEM", "provenance": "SYSTEM"},
            {"term": "read_file", "first_seen_step": "S10", "producer": "SYSTEM", "provenance": "SYSTEM"},
            {"term": "場所", "first_seen_step": "S04", "producer": "SYSTEM", "provenance": "SYSTEM", "form": "停止場所", "note": "not 保存場所"},
            {"term": "ファイル", "first_seen_step": None, "producer": None, "provenance": None, "note": "not in Goal/Need/Grill/Retry request_text; appears later in 05_help_index.json Help describe"},
            {"term": "DB", "first_seen_step": None, "note": "not present in this Case 2 run files (excluding Help catalog text)"},
            {"term": "API", "first_seen_step": None, "note": "not present in this Case 2 run files"},
            {"term": "保存場所", "first_seen_step": None, "note": "not present"},
            {"term": "所在 / 形式 / アクセス方法", "first_seen_step": None, "note": "only in case.json unknown harness field; not in Need/Grill/Retry prompts"},
        ],
    }
    (OUT / "steps.json").write_text(
        json.dumps(steps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("OK", OUT)


if __name__ == "__main__":
    main()
