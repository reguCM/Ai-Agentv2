"""
要求の明確さ判断の材料。調査結果は入れない。

LLM は候補を出すだけ。採用はユーザー回答のあと機械側が行う。
"""

from tools.ai.state.decision_store import REQUEST_DECISION_KEYS


CLARITY_STATUSES = (
    "clear",
    "needs_clarification",
    "insufficient_information",
)

STATUS_ALIASES = {
    "ok": "clear",
    "ready": "clear",
    "unambiguous": "clear",
    "ambiguous": "needs_clarification",
    "clarify": "needs_clarification",
    "needs_clarify": "needs_clarification",
    "unclear": "insufficient_information",
    "unknown": "insufficient_information",
    "insufficient": "insufficient_information",
}

DEFAULT_QUESTIONS = {
    "needs_clarification": "候補が複数あります。どれを実装しますか？",
    "insufficient_information": "何を取得・操作するToolが必要ですか？",
}


def create_clarity_materials(request, conversation=None):
    """調査 findings や環境コマンドは載せない。"""
    items = []
    for item in conversation or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        text = str(item.get("text") or "").strip()
        if role not in ("user", "assistant") or not text:
            continue
        items.append({"role": role, "text": text})
    return {
        "target_request": request,
        "conversation": items,
    }


def normalize_decisions(items):
    cleaned = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        value = item.get("value")
        if key not in REQUEST_DECISION_KEYS or value in (None, ""):
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        cleaned.append({"key": key, "value": value})
    return cleaned


def normalize_option(item, index):
    if isinstance(item, str):
        label = item.strip()
        if not label:
            return None
        return {"id": f"opt{index}", "label": label, "decisions": []}
    if not isinstance(item, dict):
        return None
    label = str(item.get("label") or item.get("text") or "").strip()
    if not label:
        return None
    option_id = str(item.get("id") or f"opt{index}").strip() or f"opt{index}"
    return {
        "id": option_id,
        "label": label,
        "decisions": normalize_decisions(item.get("decisions")),
    }


def normalize_status(value):
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    text = STATUS_ALIASES.get(text, text)
    if text in CLARITY_STATUSES:
        return text
    return "insufficient_information"


def normalize_clarity(payload):
    """
    未知の status は research に進めない。
    clear のとき question / options は捨てる。
    """
    if not isinstance(payload, dict):
        return {
            "status": "insufficient_information",
            "reason": "",
            "question": DEFAULT_QUESTIONS["insufficient_information"],
            "options": [],
        }
    status = normalize_status(payload.get("status"))
    reason = str(payload.get("reason") or "").strip()
    question = str(payload.get("question") or "").strip()
    options = []
    raw_options = payload.get("options") or []
    if isinstance(raw_options, dict):
        raw_options = [raw_options]
    if not isinstance(raw_options, list):
        raw_options = []
    for index, item in enumerate(raw_options, start=1):
        option = normalize_option(item, index)
        if option:
            options.append(option)
    if status == "clear":
        return {
            "status": status,
            "reason": reason,
            "question": "",
            "options": [],
        }
    if not question:
        question = reason or DEFAULT_QUESTIONS[status]
    return {
        "status": status,
        "reason": reason,
        "question": question,
        "options": options,
    }
