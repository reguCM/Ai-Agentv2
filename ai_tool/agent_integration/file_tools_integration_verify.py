"""P2-4 Workspace File Tools 統合フロー実測ハーネス（検証専用）。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import normalize_arguments
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.llm import chat as ollama_chat

_REPO = Path(__file__).resolve().parents[2]


def file_tools_system_prompt(tool_names: list[str]) -> str:
    names = ", ".join(sorted(tool_names))
    return f"""
あなたはローカル環境の AI Agent です。日本語で簡潔に答えてください。

利用可能 Tool: {names}

Workspace File Tools:
- list_files: Workspace 内の指定ディレクトリ直下のファイル・ディレクトリを一覧（再帰しない）
- search_files: Workspace 内のテキストを部分文字列検索（指定 path 以下を再帰）
- read_file: Workspace 内のテキストファイルを読取（行番号付き）

ルール:
1. ユーザー要求を満たすために必要な Tool を選ぶ。不要な Tool は呼ばない。
2. Tool 結果にない情報を捏造しない。
3. Tool エラー (ok:false) を受け取ったら、別の Tool で正しい対象を探してから再試行してよい。
4. Workspace 外のパスは使えない。
""".strip()


@dataclass
class ToolCallRecord:
    round_index: int
    tool_name: str
    arguments: dict[str, Any]
    ok: bool
    result_summary: dict[str, Any]
    error: str | None = None


@dataclass
class ScenarioResult:
    scenario_id: str
    user_request: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    final_answer: str = ""
    rounds: int = 0
    live: bool = True
    notes: str = ""

    def tool_sequence(self) -> list[str]:
        return [t.tool_name for t in self.tool_calls]


def _summarize_result(tool_name: str, result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"type": type(result).__name__}
    summary: dict[str, Any] = {"ok": result.get("ok")}
    if tool_name == "list_files":
        summary["count"] = result.get("count")
        summary["entry_names"] = [e.get("name") for e in (result.get("entries") or [])[:20]]
    elif tool_name == "search_files":
        summary["match_count"] = result.get("match_count")
        summary["match_paths"] = list({m.get("path") for m in (result.get("matches") or [])[:10]})
    elif tool_name == "read_file":
        summary["path"] = result.get("path")
        summary["returned_lines"] = result.get("returned_lines")
        summary["preview"] = (result.get("lines") or [{}])[0].get("text", "")[:120] if result.get("lines") else None
    if result.get("error"):
        summary["error"] = str(result.get("error"))[:200]
    return summary


def run_file_tools_scenario(
    scenario_id: str,
    user_request: str,
    *,
    max_rounds: int | None = None,
    chat_fn=ollama_chat,
    model: str | None = None,
) -> ScenarioResult:
    pipeline = get_pipeline()
    max_r = max_rounds or int(pipeline.get("max_tool_rounds") or 5)
    model = model or str(get_llm_profile().get("model") or "")
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {"role": "user", "content": user_request},
    ]

    result = ScenarioResult(scenario_id=scenario_id, user_request=user_request)
    for round_index in range(max_r):
        result.rounds = round_index + 1
        response = chat_fn(model=model, messages=messages, tools=llm_tools)
        messages.append(response.message)
        tool_calls = getattr(response.message, "tool_calls", None) or []
        if not tool_calls:
            result.final_answer = str(getattr(response.message, "content", None) or "")
            break
        for tc in tool_calls:
            name = tc.function.name
            args = normalize_arguments(tc.function.arguments)
            rec = execute_registry_tool(name, args)
            ok = bool(rec.ok)
            summary = _summarize_result(name, rec.result)
            result.tool_calls.append(
                ToolCallRecord(
                    round_index=round_index,
                    tool_name=name,
                    arguments=args,
                    ok=ok,
                    result_summary=summary,
                    error=rec.error,
                )
            )
            content = rec.result
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            messages.append({"role": "tool", "tool_name": name, "content": content})
    return result


def run_all_p24_scenarios(*, model: str | None = None) -> dict[str, Any]:
    scenarios = [
        (
            "A_explore_search_read",
            "Workspace内で get_gpu_status の実装場所を探し、"
            "該当するファイルの内容を確認して、その実装が何をしているか説明してください。",
        ),
        (
            "B_list_then_read",
            "tests/fixtures に何があるか確認して、"
            "p2_read_file_sample.txt の内容を読んで説明してください。",
        ),
        (
            "C_search_then_read",
            "Tool Registryで read_file がどこで定義または参照されているか探して、"
            "重要なファイルを1つ選んで内容を確認してください。",
        ),
        (
            "D_error_recovery",
            "tests/fixtures/does_not_exist_p2_4.txt を読んでください。"
            "存在しない場合は Workspace 内から正しい対象を探して、"
            "見つかったファイルを読んで内容を要約してください。",
        ),
        (
            "E1_list_only",
            "tests/fixtures の中に何があるか教えてください。",
        ),
        (
            "E2_read_only",
            "tests/fixtures/p2_read_file_sample.txt の内容を教えてください。",
        ),
    ]
    out: dict[str, Any] = {
        "task_id": "FILE-TOOLS-INTEGRATION-P2-4",
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "model": model or str(get_llm_profile().get("model") or ""),
        "scenarios": {},
    }
    for sid, prompt in scenarios:
        print(f"\n=== {sid} ===", flush=True)
        sr = run_file_tools_scenario(sid, prompt, model=model)
        seq = sr.tool_sequence()
        print("TOOLS:", seq, flush=True)
        print("FINAL:", (sr.final_answer or "")[:200], flush=True)
        out["scenarios"][sid] = {
            **asdict(sr),
            "tool_sequence": seq,
        }
    return out


def save_run(data: dict[str, Any], run_dir: Path | None = None) -> Path:
    ts = data.get("timestamp") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = run_dir or (_REPO / "runs" / "ai_tool" / f"{ts}_file_tools_integration_p24")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    payload = run_all_p24_scenarios()
    saved = save_run(payload)
    print(f"\nSaved: {saved}")
