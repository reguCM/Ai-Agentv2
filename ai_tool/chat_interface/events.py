"""観測可能な Agent Event。思考過程は保存しない。全 Memory も保存しない。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ai_tool.chat_interface.tool_observation import observe_tool_result


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def event(type_: str, **fields: Any) -> dict[str, Any]:
    payload = {"type": type_, "timestamp": now_iso()}
    payload.update(fields)
    return payload


def public_status_lines(
    *,
    tool_used: bool,
    tools: list[dict[str, Any]] | None = None,
    error: str | None = None,
    web_search: bool = False,
    cursor_connected: bool = False,
    model: str | None = None,
    user_error: str | None = None,
    research_saved: bool = False,
) -> list[str]:
    """ユーザー向け。思考過程は含めない。未実行を実行済みと書かない。"""
    lines = ["● ユーザー入力を受信しました", "● Local Agent が処理しています"]
    if model:
        lines.append(f"● LLMへ問い合わせています（モデル: {model}）")
    else:
        lines.append("● LLMへ問い合わせています")
    if error:
        lines.append(f"● エラー: {user_error or error}")
        return lines
    if not tool_used:
        lines.append("● Tool は使いませんでした")
    else:
        for item in tools or []:
            name = str(item.get("name") or "tool")
            lines.append(f"● {name} を選択しました")
            lines.append(f"● {name} を実行しました")
            lines.append("● Tool結果を取得しました")
        lines.append("● 結果をLLMへ戻しています")
    lines.append("● 回答を生成しています")
    lines.append("● Web Search を実行しました" if web_search else "● Web Search は実行していません")
    if research_saved:
        lines.append("● Research: 保存した")
        lines.append("● Matrix Write: 保存した")
    else:
        lines.append("● Research: NOT CONNECTED")
        lines.append("● Matrix Write: NOT OBSERVED")
    lines.append("● Cursor 接続: あり" if cursor_connected else "● Cursor 接続: なし")
    return lines


def pipeline_steps(
    *,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    error: str | None = None,
    user_error: str | None = None,
    web_search: bool = False,
    search_available: bool = True,
    research_saved: bool = False,
) -> list[dict[str, Any]]:
    """確認用の短い経路。未実行ステップを done にしない。"""
    steps: list[dict[str, Any]] = [
        {"id": "user_input", "label": "ユーザー入力", "status": "done"},
        {"id": "local_agent", "label": "Local Agent", "status": "done"},
        {
            "id": "llm",
            "label": "LLM",
            "status": "error" if error else "done",
            "model": model,
        },
    ]
    for item in tools or []:
        name = str(item.get("name") or "tool")
        status = str(item.get("status") or "success")
        summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
        tool_label = f"TOOL_CALL {name}" if name == "search_web" else f"Tool: {name}"
        tool_step: dict[str, Any] = {"id": "tool", "label": tool_label, "status": status, "name": name}
        if name == "search_web" and summary:
            tool_step["query"] = summary.get("query")
            tool_step["hit_count"] = summary.get("hit_count")
        steps.append(tool_step)
        section_keys = summary.get("composed_section_keys") if summary else None
        if isinstance(section_keys, list) and section_keys:
            steps.append(
                {
                    "id": "compose",
                    "label": "Compose",
                    "status": "observed",
                    "name": name,
                    "sections": section_keys,
                    "independent_tool_calls": False,
                    "note": "Returned sections only. Child TOOL_CALL was not recorded.",
                }
            )
        if name == "search_web" and summary:
            steps.append(
                {
                    "id": "search",
                    "label": "SEARCH",
                    "status": status,
                    "name": name,
                    "query": summary.get("query"),
                    "hit_count": summary.get("hit_count"),
                    "executed": True,
                }
            )
        result_label = "SEARCH_RESULT" if name == "search_web" else "Tool Result"
        steps.append(
            {
                "id": "tool_result",
                "label": result_label,
                "status": status,
                "name": name,
                "summary": item.get("summary"),
            }
        )
    if error:
        steps.append(
            {
                "id": "error",
                "label": "エラー",
                "status": "error",
                "message": user_error or error,
            }
        )
    else:
        steps.append({"id": "answer", "label": "回答", "status": "done"})
    steps.append(
        {
            "id": "research_path",
            "label": "Research",
            "status": "NOT_CONNECTED",
            "executed": False,
            "note": "ResearchRecord は TDA に存在する。Chat からは呼び出していない。",
        }
    )
    steps.append(
        {
            "id": "research_write",
            "label": "WRITE",
            "status": "saved" if research_saved else "NOT_OBSERVED",
            "executed": bool(research_saved),
            "note": "Matrix Write 関数は無い。ResearchStore.add も Chat では未実行。",
        }
    )
    steps.append(
        {
            "id": "search_capability",
            "label": "Search Tool available" if search_available else "Search Tool unavailable",
            "status": "available" if search_available else "unavailable",
            "executed": bool(web_search),
            "note": "available は存在。executed だけが今回の実行。",
        }
    )
    return steps


def runtime_ui_summary(task_runtime: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Compact Task / Goal state for Chat UI and Session replay."""
    if not isinstance(task_runtime, Mapping):
        return None
    tasks = [
        {
            "task_id": item.get("task_id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "satisfied_conditions": list(item.get("satisfied_conditions") or []),
        }
        for item in (task_runtime.get("tasks") or [])
        if isinstance(item, Mapping)
    ]
    goals = [
        {
            "goal_id": item.get("goal_id"),
            "title": item.get("title"),
            "status": item.get("status"),
        }
        for item in (task_runtime.get("goals") or [])
        if isinstance(item, Mapping)
    ]
    evidence = task_runtime.get("evidence") or []
    return {
        "current_goal_id": task_runtime.get("current_goal_id"),
        "current_task_id": task_runtime.get("current_task_id"),
        "tasks": tasks,
        "goals": goals,
        "awaiting_goal_completion_human": bool(
            task_runtime.get("awaiting_goal_completion_human")
        ),
        "awaiting_human_grill": bool(task_runtime.get("awaiting_human_grill")),
        "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
    }


def mission_ui_summary(mission_memory: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Compact Mission Memory fields for Chat UI and Session replay."""
    if not isinstance(mission_memory, Mapping):
        return None
    return {
        "ok": mission_memory.get("ok"),
        "mission_id": mission_memory.get("mission_id"),
        "execution_id": mission_memory.get("execution_id"),
        "execution_end_state_judgment": mission_memory.get("execution_end_state_judgment"),
        "execution_end_state": mission_memory.get("execution_end_state"),
        "goal_achievement_performed": mission_memory.get("goal_achievement_performed"),
        "goal_achievement_result": mission_memory.get("goal_achievement_result"),
        "stop_reason": mission_memory.get("stop_reason"),
        "evidence_refs": list(mission_memory.get("evidence_refs") or []),
    }


def summarize_tool_result(tool_name: str, result: Any, *, limit: int = 800) -> Any:
    """Event / UI 用の観測。LLM へ渡す raw result ではない。limit は非 dict の切詰めに使う。"""
    observed = observe_tool_result(tool_name, result)
    if isinstance(observed, dict):
        return observed
    text = str(observed)
    return text[:limit] + ("…" if len(text) > limit else "")
