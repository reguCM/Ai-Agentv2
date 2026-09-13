"""
タスク終了まで持ち回る確定事項。LLM には読ませるが、ここへ直接は書かせない。

昇格は tools.ai.state.decision_store が機械側で行う。
Phase 1: open_questions + research_history を追加。History は prompt に載せない。
"""

from tools.ai.state.open_questions import (
    compact_unresolved_for_state,
    migrate_legacy_unresolved,
)
from tools.ai.state.research_history import ResearchHistory


LIST_KEYS = (
    "facts",
    "decisions",
    "selected_findings",
    "constraints",
    "open_questions",
    "unresolved",
)


def empty_state(task=""):
    return {
        "task": str(task or ""),
        "facts": [],
        "decisions": [],
        "selected_findings": [],
        "constraints": [],
        "open_questions": [],
        "unresolved": [],
    }


def snapshot_state(state):
    """TaskState / dict をプロンプト用の素の dict にする。"""
    if state is None:
        return None
    if isinstance(state, TaskState):
        return state.snapshot()
    if not isinstance(state, dict):
        return empty_state()
    payload = empty_state(state.get("task"))
    for key in LIST_KEYS:
        value = state.get(key) or []
        payload[key] = [dict(item) if isinstance(item, dict) else item for item in value]
    if not payload.get("open_questions") and payload.get("unresolved"):
        payload["open_questions"] = migrate_legacy_unresolved(payload["unresolved"])
        payload["unresolved"] = compact_unresolved_for_state(payload["open_questions"])
    return payload


class TaskState:
    def __init__(
        self,
        task="",
        facts=None,
        decisions=None,
        selected_findings=None,
        constraints=None,
        open_questions=None,
        unresolved=None,
        research_history=None,
        banned_actions=None,
    ):
        self.task = str(task or "")
        self.facts = list(facts or [])
        self.decisions = [dict(item) for item in decisions or [] if isinstance(item, dict)]
        self.selected_findings = list(selected_findings or [])
        self.constraints = list(constraints or [])
        self.banned_actions = [
            dict(item) for item in banned_actions or [] if isinstance(item, dict)
        ]
        self.research_history = ResearchHistory.from_snapshot(research_history)
        if open_questions is not None:
            self.open_questions = [dict(item) for item in open_questions if isinstance(item, dict)]
        elif unresolved:
            self.open_questions = migrate_legacy_unresolved(unresolved)
        else:
            self.open_questions = []
        self.unresolved = compact_unresolved_for_state(self.open_questions)

    @classmethod
    def from_payload(cls, payload):
        data = snapshot_state(payload) or empty_state()
        history = None
        if isinstance(payload, dict):
            history = payload.get("research_history")
        return cls(
            task=data.get("task"),
            facts=data.get("facts"),
            decisions=data.get("decisions"),
            selected_findings=data.get("selected_findings"),
            constraints=data.get("constraints"),
            open_questions=data.get("open_questions"),
            unresolved=data.get("unresolved"),
            research_history=history,
            banned_actions=(payload.get("banned_actions") if isinstance(payload, dict) else None),
        )

    def snapshot(self):
        self.unresolved = compact_unresolved_for_state(self.open_questions)
        return {
            "task": self.task,
            "facts": list(self.facts),
            "decisions": [dict(item) for item in self.decisions],
            "selected_findings": list(self.selected_findings),
            "constraints": list(self.constraints),
            "open_questions": [dict(item) for item in self.open_questions],
            "unresolved": list(self.unresolved),
        }

    def persistence_snapshot(self):
        """run 保存用。History / banned_actions を含む。Prompt には載せない。"""
        payload = self.snapshot()
        payload["research_history"] = self.research_history.snapshot()
        payload["banned_actions"] = [dict(item) for item in self.banned_actions]
        return payload

    def get_decision(self, key):
        for item in self.decisions:
            if item.get("key") == key:
                return item
        return None

    def add_decision(self, key, value, *, source, confidence):
        """機械側専用。同じ key は上書きしない。"""
        key = str(key or "").strip()
        if not key or self.get_decision(key) is not None:
            return False
        self.decisions.append(
            {
                "key": key,
                "value": value,
                "source": source,
                "confidence": confidence,
            }
        )
        return True

    def set_unresolved(self, items):
        """
        Legacy API: research unresolved を open_questions へ取り込み、
        State には compact view だけ残す。
        """
        from tools.ai.state.state_sync import sync_research_into_state

        sync_research_into_state(
            self,
            research={"unresolved": list(items or [])},
            round_num=None,
            round_research={"unresolved": list(items or [])},
        )
