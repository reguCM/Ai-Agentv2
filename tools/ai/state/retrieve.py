"""History Retriever。State の event 参照から必要な断片だけ取得する。"""

import re

EVENT_REF_PREFIX = "event:"

# 簡易 error_class（反復検出用。完璧な分類は不要）
_ERROR_CLASS_PATTERNS = (
    ("property_not_found", re.compile(r"not found|does not exist|unknown property|no property", re.I)),
    ("type_convert", re.compile(r"cannot convert|type.*cannot|ExpandProperty|InvalidCast", re.I)),
    ("command_not_found", re.compile(r"not recognized|command not found|is not recognized", re.I)),
    ("timeout", re.compile(r"timed? ?out|deadline exceeded", re.I)),
    ("empty_sample", re.compile(r"empty|no output|blank", re.I)),
    ("access_denied", re.compile(r"access denied|permission|unauthorized", re.I)),
)


def classify_error_class(text):
    """stderr / error 文字列から簡易 error_class を返す。"""
    raw = str(text or "").strip()
    if not raw:
        return "empty_sample"
    for name, pattern in _ERROR_CLASS_PATTERNS:
        if pattern.search(raw):
            return name
    return "other"


def event_error_class(event):
    result = event.get("result") if isinstance((event or {}).get("result"), dict) else {}
    result = result or {}
    if result.get("error_class"):
        return str(result.get("error_class"))
    text = str(result.get("error") or result.get("stderr") or "").strip()
    return classify_error_class(text)


def parse_event_ref(value):
    text = str(value or "").strip()
    if not text.startswith(EVENT_REF_PREFIX):
        return None
    event_id = text[len(EVENT_REF_PREFIX) :].strip()
    return event_id or None


def get_event(history, event_id):
    event_id = str(event_id or "").strip()
    if not event_id or history is None:
        return None
    for event in getattr(history, "events", None) or []:
        if event.get("id") == event_id:
            return event
    return None


def resolve_event_refs(history, values, *, limit=10):
    """文字列 / finding 内の event: 参照を解決する。"""
    found = []
    seen = set()
    for value in values or []:
        if len(found) >= limit:
            break
        candidates = []
        if isinstance(value, dict):
            candidates.append(value.get("finding"))
            candidates.append(value.get("finding_ref"))
            evidence = value.get("evidence") if isinstance(value.get("evidence"), dict) else {}
            candidates.append((evidence or {}).get("finding_ref"))
        else:
            candidates.append(value)
        for candidate in candidates:
            event_id = parse_event_ref(candidate) or (
                str(candidate).strip() if str(candidate or "").startswith("evt_") else None
            )
            if not event_id or event_id in seen:
                continue
            event = get_event(history, event_id)
            if event:
                seen.add(event_id)
                found.append(event)
                break
    return found


def retrieve_events_for_question(state, question_id, *, limit=3):
    """open_question.related_events から History を取得（新しい順）。"""
    history = getattr(state, "research_history", None)
    if history is None:
        return []
    question_id = str(question_id or "").strip()
    related = []
    for question in getattr(state, "open_questions", None) or []:
        if question.get("id") != question_id:
            continue
        related = list(question.get("related_events") or [])
        break
    events = []
    for event_id in reversed(related):
        if len(events) >= limit:
            break
        event = get_event(history, event_id)
        if event:
            events.append(event)
    return events


def retrieve_failures_for_open_questions(state, *, limit_per_question=2, total_limit=6):
    """未解決 open_questions に紐づく失敗イベントを取得する。"""
    history = getattr(state, "research_history", None)
    if history is None:
        return []
    collected = []
    seen = set()
    for question in getattr(state, "open_questions", None) or []:
        if question.get("status") != "open":
            continue
        qid = question.get("id")
        for event in retrieve_events_for_question(state, qid, limit=limit_per_question):
            if event.get("id") in seen:
                continue
            if event.get("type") != "verify_fail" and (event.get("result") or {}).get("ok") is not False:
                continue
            seen.add(event["id"])
            collected.append(event)
            if len(collected) >= total_limit:
                return collected
    return collected


def retrieve_by_command(history, command, args=None, *, limit=3):
    """同一 command/args の過去イベントを新しい順で取得する。"""
    command = str(command or "").strip()
    args_tuple = tuple(str(arg) for arg in (args or []))
    if not command or history is None:
        return []
    matched = []
    for event in reversed(getattr(history, "events", None) or []):
        action = event.get("action") or {}
        if str(action.get("command") or "").strip() != command:
            continue
        event_args = tuple(str(arg) for arg in (action.get("args") or []))
        if args is not None and event_args != args_tuple:
            continue
        matched.append(event)
        if len(matched) >= limit:
            break
    return matched


def retrieve_by_error_class(history, error_class, *, limit=5):
    """同一 error_class の失敗イベントを新しい順で取得する。"""
    error_class = str(error_class or "").strip()
    if not error_class or history is None:
        return []
    matched = []
    for event in reversed(getattr(history, "events", None) or []):
        if event.get("type") != "verify_fail" and (event.get("result") or {}).get("ok") is not False:
            continue
        if event_error_class(event) != error_class:
            continue
        matched.append(event)
        if len(matched) >= limit:
            break
    return matched


def count_consecutive_failures(history, *, by="command_key", n_lookback=8):
    """
    直近失敗の連続数を数える。
    by: "command_key" | "error_class"
    戻り値: (streak, key_value)
    """
    if history is None:
        return 0, None
    fails = []
    for event in reversed(getattr(history, "events", None) or []):
        if event.get("type") != "verify_fail" and (event.get("result") or {}).get("ok") is not False:
            if event.get("type") == "verify_ok":
                break
            continue
        fails.append(event)
        if len(fails) >= n_lookback:
            break
    if not fails:
        return 0, None
    if by == "error_class":
        first_key = event_error_class(fails[0])
        streak = 0
        for event in fails:
            if event_error_class(event) != first_key:
                break
            streak += 1
        return streak, first_key
    action0 = fails[0].get("action") if isinstance(fails[0].get("action"), dict) else {}
    first_key = (
        str((action0 or {}).get("command") or "").strip(),
        tuple(str(a) for a in ((action0 or {}).get("args") or [])),
    )
    if not first_key[0]:
        return 0, None
    streak = 0
    for event in fails:
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        key = (
            str((action or {}).get("command") or "").strip(),
            tuple(str(a) for a in ((action or {}).get("args") or [])),
        )
        if key != first_key:
            break
        streak += 1
    return streak, first_key


def event_preview(event, *, error_chars=120):
    """escalation / prompt 用の短いプレビュー。全文 stderr は載せない。"""
    event = event or {}
    result = event.get("result") if isinstance(event.get("result"), dict) else {}
    result = result or {}
    error = str(result.get("error") or result.get("stderr") or "").strip()
    if len(error) > error_chars:
        error = error[:error_chars] + "…"
    action = event.get("action") if isinstance(event.get("action"), dict) else {}
    return {
        "id": event.get("id"),
        "type": event.get("type"),
        "command": (action or {}).get("command"),
        "ok": result.get("ok"),
        "error_preview": error,
        "error_class": event_error_class(event),
        "round": (event.get("metadata") or {}).get("round"),
    }


def preview_events(events, *, error_chars=120):
    return [event_preview(event, error_chars=error_chars) for event in events or []]
