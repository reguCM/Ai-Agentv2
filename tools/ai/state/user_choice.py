"""
ユーザー回答から、機械が STATE へ書く確定事項。

LLM の option.decisions は信じない。
既知の成果物に一意に当たったときだけ書く。
"""

from tools.ai.state.decision_store import (
    ALLOWED_DECISION_KEYS,
    REQUEST_DECISION_KEYS,
    apply_user_option,
    promote_proposed,
)
from tools.ai.state.task_state import TaskState


USER_CHOICE_KEYS = frozenset(ALLOWED_DECISION_KEYS | REQUEST_DECISION_KEYS)

USER_CHOICES = (
    {
        "id": "memory_usage",
        "ids": ("usage",),
        "markers": ("メモリ使用率", "使用率"),
        "decisions": (
            {"key": "request.metric", "value": "使用率"},
            {"key": "status.meaning", "value": "Windowsのメモリ使用率"},
            {"key": "status.unit", "value": "%"},
            {"key": "status.range", "value": "0-100"},
        ),
    },
    {
        "id": "memory_free",
        "ids": ("free",),
        "markers": ("空き容量", "空き"),
        "decisions": (
            {"key": "request.metric", "value": "空き容量"},
            {"key": "status.meaning", "value": "Windowsのメモリ空き容量"},
        ),
    },
    {
        "id": "memory_total",
        "ids": ("total",),
        "markers": ("総容量",),
        "decisions": (
            {"key": "request.metric", "value": "総容量"},
            {"key": "status.meaning", "value": "Windowsのメモリ総容量"},
        ),
    },
)


def _norm(value):
    return str(value or "").strip().lower()


def _hits_choice(text, choice):
    hay = _norm(text)
    if not hay:
        return False
    if hay in {_norm(item) for item in choice.get("ids") or ()}:
        return True
    markers = sorted(choice.get("markers") or (), key=len, reverse=True)
    return any(_norm(marker) and _norm(marker) in hay for marker in markers)


def resolve_user_choice(reply, option=None):
    """複数候補に当たるなら選ばない。"""
    texts = [reply]
    if isinstance(option, dict):
        texts.extend([option.get("id"), option.get("label")])
    matched = []
    for choice in USER_CHOICES:
        if any(_hits_choice(text, choice) for text in texts):
            matched.append(choice)
    unique = {item["id"]: item for item in matched}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def apply_user_reply(state, reply, option=None):
    """
    ユーザー回答で一意に決まった成果物だけを source=user で昇格する。
    カタログに無い選択は、option の request.* だけ（LLM の status.* は使わない）。
    """
    store = state if isinstance(state, TaskState) else TaskState.from_payload(state)
    choice = resolve_user_choice(reply, option)
    if choice:
        return promote_proposed(
            store,
            choice["decisions"],
            source="user",
            extra_keys=USER_CHOICE_KEYS,
        )
    if option:
        return apply_user_option(store, option)
    return store, []
