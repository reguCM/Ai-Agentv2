"""Current State の open_questions。長い stderr は History 側に置く。"""

import uuid


def new_question_id():
    return f"q_{uuid.uuid4().hex[:10]}"


def normalize_question_text(text):
    return str(text or "").strip()


def find_open_question_by_text(open_questions, text):
    target = normalize_question_text(text).lower()
    if not target:
        return None
    for item in open_questions or []:
        if item.get("status") != "open":
            continue
        if normalize_question_text(item.get("text")).lower() == target:
            return item
    return None


def question_text_from_finding(finding):
    finding = finding or {}
    text = normalize_question_text(finding.get("question"))
    if text:
        return text[:200]
    text = normalize_question_text(finding.get("finding"))
    return text[:200] if text else ""


def ensure_open_question(state, text, *, event_id=None):
    text = normalize_question_text(text)
    if not text:
        return None
    existing = find_open_question_by_text(state.open_questions, text)
    if existing:
        if event_id and event_id not in (existing.get("related_events") or []):
            existing.setdefault("related_events", []).append(event_id)
        return existing["id"]
    qid = new_question_id()
    entry = {
        "id": qid,
        "text": text[:200],
        "status": "open",
        "related_events": [],
    }
    if event_id:
        entry["related_events"].append(event_id)
    state.open_questions.append(entry)
    return qid


def resolve_open_question(state, question_id, *, history=None, reason=None, finding_ref=None):
    for index, item in enumerate(state.open_questions):
        if item.get("id") != question_id or item.get("status") != "open":
            continue
        if history is not None:
            history.record_question_resolved(
                question_id, reason=reason, finding_ref=finding_ref
            )
        state.open_questions.pop(index)
        return True
    return False


def resolve_open_question_by_text(state, text, *, history=None, reason=None, finding_ref=None):
    item = find_open_question_by_text(state.open_questions, text)
    if not item:
        return False
    return resolve_open_question(
        state,
        item["id"],
        history=history,
        reason=reason,
        finding_ref=finding_ref,
    )


def compact_unresolved_for_state(open_questions):
    """
    既存 STATE.unresolved 互換の最小ビュー。
    長い finding / stderr は載せず、event 参照だけ残す。
    """
    items = []
    for question in open_questions or []:
        if question.get("status") != "open":
            continue
        text = normalize_question_text(question.get("text"))
        if not text:
            continue
        entry = {
            "kind": "output",
            "question": text,
            "confidence": "low",
            "source": "state",
        }
        events = list(question.get("related_events") or [])
        if events:
            entry["finding"] = f"event:{events[-1]}"
        items.append(entry)
    return items


def migrate_legacy_unresolved(unresolved_items):
    """Case JSON 等の legacy unresolved から open_questions を生成（History なし）。"""
    open_questions = []
    for item in unresolved_items or []:
        if not isinstance(item, dict):
            continue
        text = question_text_from_finding(item)
        if not text:
            continue
        if find_open_question_by_text(open_questions, text):
            continue
        open_questions.append(
            {
                "id": new_question_id(),
                "text": text,
                "status": "open",
                "related_events": [],
            }
        )
    return open_questions
