"""Research イベント履歴。append-only。LLM prompt には載せない。"""

import uuid
from datetime import datetime, timezone


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_event_id(prefix="evt"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ResearchHistory:
    """Verify / Judge / resolve 等のイベントを追記保存する。"""

    def __init__(self, events=None):
        self.events = list(events or [])

    def append(
        self,
        event_type,
        *,
        action=None,
        result=None,
        related_question_ids=None,
        metadata=None,
    ):
        event = {
            "id": new_event_id(),
            "ts": _utc_now_iso(),
            "type": str(event_type or "").strip(),
            "action": dict(action or {}),
            "result": dict(result or {}),
            "related_question_ids": list(related_question_ids or []),
            "metadata": dict(metadata or {}),
        }
        self.events.append(event)
        return event["id"]

    def record_finding(self, finding, *, event_type, round_num=None):
        finding = finding or {}
        evidence = finding.get("evidence") if isinstance(finding.get("evidence"), dict) else {}
        evidence = evidence or {}
        error = str(evidence.get("error") or evidence.get("stderr") or "").strip()
        return self.append(
            event_type,
            action={
                "command": evidence.get("command"),
                "args": list(evidence.get("args") or []),
            },
            result={
                "ok": event_type == "verify_ok",
                "error": error,
                "stderr": str(evidence.get("stderr") or "").strip(),
                "sample": evidence.get("sample"),
                "returncode": evidence.get("returncode"),
            },
            metadata={
                "round": round_num,
                "question": finding.get("question"),
                "finding": finding.get("finding"),
                "confidence": finding.get("confidence"),
                "source": finding.get("source"),
            },
        )

    def record_judge(self, judgment, *, round_num=None):
        judgment = judgment or {}
        return self.append(
            "judge",
            result={
                "satisfies_request": judgment.get("satisfies_request"),
                "reason": judgment.get("reason"),
                "missing": list(judgment.get("missing") or []),
            },
            metadata={"round": round_num},
        )

    def record_question_resolved(self, question_id, *, reason=None, finding_ref=None):
        return self.append(
            "question_resolved",
            related_question_ids=[str(question_id)],
            result={"reason": reason, "finding_ref": finding_ref},
        )

    def snapshot(self):
        return list(self.events)

    @classmethod
    def from_snapshot(cls, events):
        if isinstance(events, ResearchHistory):
            return events
        return cls(events)
