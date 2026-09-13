"""
Clarity 問答から作った STATE の引き継ぎ検査。LLM は呼ばない。

1. ユーザー回答が STATE になる
2. Research / Judge プロンプトに STATE が載る
3. 意味維持は persistence_classify（LLM ベンチ側）
4. Research/Judge が user の confirmed を上書きしない
"""

from tools.ai.llm.adapter import (
    build_research_judge_messages,
    build_web_candidate_messages,
)
from tools.ai.state.decision_store import apply_judgment
from tools.ai.state.task_state import snapshot_state
from tools.ai.tool_builder.research_judge import create_research_judgment
from tools.ai.tool_builder.web import web_research
from tools.system.tool_builder.clarity import run_clarity_gate


REQUEST = "Windowsのメモリを取得するToolを作って"
USER_REPLY = "使用率です"

CLARITY_ASK = {
    "status": "needs_clarification",
    "question": "使用率、空き容量、総容量のどれが必要ですか？",
    "options": [
        {"id": "usage", "label": "使用率"},
        {"id": "free", "label": "空き容量"},
        {"id": "total", "label": "総容量"},
    ],
}

REQUIRED_USER_STATE = (
    ("status.meaning", "Windowsのメモリ使用率"),
    ("status.unit", "%"),
    ("status.range", "0-100"),
)

AMBIGUOUS_VALUE_MATERIALS = {
    "tool": {"return_value": {"status": 43.2}},
    "question": "このToolが返した 43.2 は何を表していますか？単位も答えてください。",
}


def run_scripted_handoff(request=REQUEST, reply=USER_REPLY):
    calls = []

    def complete(materials, state):
        calls.append(materials)
        if len(calls) == 1:
            return CLARITY_ASK
        return {"status": "clear"}

    result = run_clarity_gate(
        request,
        ask=lambda question, options: reply,
        complete=complete,
    )
    result["clarity_calls"] = calls
    return result


def inspect_user_state(state):
    checks = []
    for key, value in REQUIRED_USER_STATE:
        item = state.get_decision(key) if state is not None else None
        checks.append(
            {
                "key": key,
                "ok": bool(
                    item
                    and item.get("value") == value
                    and item.get("source") == "user"
                ),
                "value": None if item is None else item.get("value"),
                "source": None if item is None else item.get("source"),
            }
        )
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def _joined(messages):
    return "\n".join(
        str(item.get("content") or "") if isinstance(item, dict) else str(item)
        for item in messages or []
    )


def inspect_state_in_research_messages(state):
    web_materials = web_research(
        items=[{"kind": "output", "question": "output 'status' の取得方法"}],
        search_results=[],
        inventory={"available_commands": ["powershell"]},
        subject={"subcategory": "memory"},
    )
    judge_materials = create_research_judgment(
        REQUEST,
        {"output": ["status"]},
        {
            "usable_findings": [
                {
                    "evidence": {
                        "command": "powershell",
                        "args": [],
                        "sample": ["43.2"],
                    }
                }
            ]
        },
    )
    reports = {}
    for name, builder, materials in (
        ("research", build_web_candidate_messages, web_materials),
        ("judge", build_research_judge_messages, judge_materials),
    ):
        messages = builder(materials, state=state)
        joined = _joined(messages)
        user = messages[1]["content"] if len(messages) > 1 else ""
        has_source = '"source": "user"' in joined or '"source":"user"' in joined
        state_first = (
            "TASK STATE" in user
            and "TASK MATERIALS" in user
            and user.find("TASK STATE") < user.find("TASK MATERIALS")
        )
        reports[name] = {
            "ok": (
                "TASK STATE" in joined
                and "Windowsのメモリ使用率" in joined
                and has_source
                and state_first
            ),
            "has_state": "TASK STATE" in joined,
            "has_meaning": "Windowsのメモリ使用率" in joined,
            "has_user_source": has_source,
            "state_before_materials": state_first,
        }
        if name == "judge":
            materials_only = user[user.find("TASK MATERIALS") :] if "TASK MATERIALS" in user else user
            reports[name]["sample_in_materials"] = "43.2" in materials_only
            reports[name]["meaning_not_only_from_materials"] = (
                "Windowsのメモリ使用率" in user[: user.find("TASK MATERIALS")]
                if "TASK MATERIALS" in user
                else False
            )
    ok = all(item["ok"] for item in reports.values())
    return {"ok": ok, "prompts": reports}


def inspect_not_overwritten(state):
    before = snapshot_state(state)
    apply_judgment(
        state,
        {
            "satisfies_request": True,
            "proposed_decisions": [
                {"key": "status.meaning", "value": "CPU temperature"},
                {"key": "status.unit", "value": "bytes"},
                {"key": "status.range", "value": "unknown"},
            ],
        },
    )
    checks = []
    for key, value in REQUIRED_USER_STATE:
        item = state.get_decision(key)
        checks.append(
            {
                "key": key,
                "ok": bool(
                    item
                    and item.get("value") == value
                    and item.get("source") == "user"
                ),
            }
        )
    return {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "before": before,
        "after": snapshot_state(state),
    }


def inspect_meaning_from_state(payload, labels):
    """
    回答に『メモリ使用率』と書いたかではなく、STATE の意味を参照したか。
    used_state_keys の status.meaning / status.unit も認める。
    """
    labels = labels or {}
    keys = [
        str(item).strip().lower()
        for item in (payload or {}).get("used_state_keys") or []
        if str(item).strip()
    ]
    meaning_from_keys = any("meaning" in key for key in keys)
    unit_from_keys = any("unit" in key for key in keys)
    memory = bool(labels.get("recognized_memory_usage")) or meaning_from_keys
    unit = bool(labels.get("unit_percent")) or unit_from_keys
    state_based = labels.get("reason_class") == "state_based" or meaning_from_keys or unit_from_keys
    return {
        "ok": memory and unit and state_based,
        "memory": memory,
        "unit": unit,
        "state_based": state_based,
        "used_state_keys": keys,
    }
