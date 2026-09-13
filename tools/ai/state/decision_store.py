"""
proposed_decisions を機械側で確認して STATE へ昇格する。

LLM が返した decisions をそのまま STATE にしない。
Judge は satisfies_request のときだけ、許可した key を confirmed にする。
Clarity はユーザーが選んだ option だけを source=user で書く。
"""

from tools.ai.state.task_state import TaskState


ALLOWED_DECISION_KEYS = frozenset(
    {
        "status.meaning",
        "status.unit",
        "status.range",
        "status.type",
    }
)

# Clarity でユーザーが選んだ要求の確定。Judge の戻り値意味とは別。
REQUEST_DECISION_KEYS = frozenset(
    {
        "request.subject",
        "request.action",
        "request.metric",
        "request.target",
    }
)

COMMAND_MARKERS = (
    "get-ciminstance",
    "get-wmiobject",
    "win32_",
    "wmic ",
    "subprocess",
    "powershell -",
)
MAX_VALUE_CHARS = 80


def extra_keys_from_proposal(proposal):
    keys = []
    for name in (proposal or {}).get("output") or ["status"]:
        name = str(name or "").strip()
        if not name:
            continue
        for suffix in ("meaning", "unit", "range", "type"):
            keys.append(f"{name}.{suffix}")
    return keys


def is_allowed_key(key, *, extra_keys=None):
    text = str(key or "").strip()
    allowed = set(ALLOWED_DECISION_KEYS)
    allowed.update(extra_keys or ())
    return text in allowed


def is_command_like(value):
    text = str(value or "").lower()
    return any(marker in text for marker in COMMAND_MARKERS)


def normalize_proposed(item, *, extra_keys=None):
    if not isinstance(item, dict):
        return None
    key = str(item.get("key") or "").strip()
    value = item.get("value")
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
    if value in ("", [], {}):
        return None
    if not is_allowed_key(key, extra_keys=extra_keys):
        return None
    rendered = str(value)
    if len(rendered) > MAX_VALUE_CHARS or is_command_like(rendered):
        return None
    return {"key": key, "value": value}


def promote_proposed(state, proposed, *, source, extra_keys=None):
    """key/value だけ採用し、confidence は機械が付ける。既存 key は触らない。"""
    store = state if isinstance(state, TaskState) else TaskState.from_payload(state)
    promoted = []
    for item in proposed or []:
        normalized = normalize_proposed(item, extra_keys=extra_keys)
        if not normalized:
            continue
        added = store.add_decision(
            normalized["key"],
            normalized["value"],
            source=source,
            confidence="confirmed",
        )
        if added:
            promoted.append(normalized["key"])
    return store, promoted


def apply_judgment(state, judgment, *, extra_keys=None):
    """
    Judge が要求を満たしたと判定したあとにだけ STATE へ昇格する。
    satisfies_request が false なら何も書かない。
    """
    store = state if isinstance(state, TaskState) else TaskState.from_payload(state)
    if not (judgment or {}).get("satisfies_request"):
        return store, []
    return promote_proposed(
        store,
        (judgment or {}).get("proposed_decisions") or [],
        source="judge",
        extra_keys=extra_keys,
    )


def apply_user_option(state, option):
    """
    ユーザーが選んだ option の decisions だけを STATE へ昇格する。
    LLM の clear 判定や未選択の options からは書かない。
    Judge 用の status.* キーはここでは採用しない。
    """
    store = state if isinstance(state, TaskState) else TaskState.from_payload(state)
    decisions = []
    for item in (option or {}).get("decisions") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key in REQUEST_DECISION_KEYS:
            decisions.append(item)
    return promote_proposed(
        store,
        decisions,
        source="user",
        extra_keys=REQUEST_DECISION_KEYS,
    )
