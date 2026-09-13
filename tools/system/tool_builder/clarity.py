"""
Clarity の機械側ルーティング。

LLM は clear / needs_clarification / insufficient_information を出す。
次工程はここが決める。Research で曖昧さを解消しない。
STATE へ書くのは、ユーザー回答から機械が一意に解けた成果物だけ。
"""

import json

from tools.ai.state.user_choice import apply_user_reply
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.clarity import (
    create_clarity_materials,
    normalize_clarity,
)
from tools.system.config import get_pipeline


def next_clarity_step(judgment):
    if (judgment or {}).get("status") == "clear":
        return "research"
    return "ask_user"


def format_clarity_question(question, options=None):
    lines = [str(question or "").strip()]
    for option in options or []:
        option_id = str(option.get("id") or "").strip()
        label = str(option.get("label") or "").strip()
        if option_id and label:
            lines.append(f"- {option_id}: {label}")
        elif label:
            lines.append(f"- {label}")
    return "\n".join(line for line in lines if line)


def _norm_text(value):
    return str(value or "").strip().lower()


def match_option(options, reply):
    """
    一意に当たるときだけ採用する。
    「容量」が空き容量と総容量の両方に当たるなら選ばない。
    """
    text = str(reply or "").strip()
    if not text:
        return None
    lowered = _norm_text(text)
    exact = []
    partial = []
    for option in options or []:
        option_id = str(option.get("id") or "").strip()
        label = str(option.get("label") or "").strip()
        id_lower = _norm_text(option_id)
        label_lower = _norm_text(label)
        if option_id and (text == option_id or lowered == id_lower):
            exact.append(option)
            continue
        if label and (text == label or lowered == label_lower):
            exact.append(option)
            continue
        if label_lower and (label_lower in lowered or lowered in label_lower):
            partial.append(option)
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    if len(partial) == 1:
        return partial[0]
    return None


def extract_json_object(text):
    if isinstance(text, dict):
        return text
    if not text:
        return None
    stripped = str(text).strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            payload = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def max_clarity_rounds(pipeline=None):
    data = pipeline if pipeline is not None else get_pipeline()
    return int((data or {}).get("max_clarity_rounds") or 5)


def run_clarity_gate(request, *, ask, complete, max_rounds=None, state=None):
    """
    ask(question, options) -> ユーザー回答。空や None なら調査へ進まない。
    complete(materials, state) -> LLM の JSON または dict。
    """
    store = state if isinstance(state, TaskState) else TaskState(task=request)
    if not store.task:
        store.task = str(request or "")
    conversation = []
    judgment = normalize_clarity(None)
    rounds = max_clarity_rounds() if max_rounds is None else int(max_rounds)
    rounds = max(1, rounds)

    for _ in range(rounds):
        materials = create_clarity_materials(request, conversation)
        judgment = normalize_clarity(extract_json_object(complete(materials, store)))
        step = next_clarity_step(judgment)
        if step == "research":
            return {
                "status": judgment["status"],
                "next_step": "research",
                "state": store,
                "judgment": judgment,
                "conversation": list(conversation),
            }
        reply = ask(judgment["question"], judgment["options"])
        text = str(reply or "").strip()
        if not text:
            return {
                "status": judgment["status"],
                "next_step": "ask_user",
                "state": store,
                "judgment": judgment,
                "conversation": list(conversation),
            }
        conversation.append({"role": "assistant", "text": judgment["question"]})
        conversation.append({"role": "user", "text": text})
        option = match_option(judgment["options"], text)
        apply_user_reply(store, text, option=option)

    return {
        "status": judgment["status"],
        "next_step": "ask_user",
        "state": store,
        "judgment": judgment,
        "conversation": list(conversation),
    }
