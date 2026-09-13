"""Agent Task Runtime v1: explicit goal, task, evidence, and recovery state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from tools.ai.sandbox_workspace import (
    SandboxSession,
    create_dedicated_sandbox_session,
    verify_sandbox_identity,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class GoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressState(str, Enum):
    PROGRESS = "progress"
    STAGNATION = "stagnation"
    REGRESSION = "regression"


class ConditionStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"


class InformationCertainty(str, Enum):
    CONFIRMED = "CONFIRMED"
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"
    UNVERIFIED = "UNVERIFIED"


AUTHORITATIVE_CERTAINTIES = {
    InformationCertainty.CONFIRMED.value,
    InformationCertainty.OBSERVED.value,
}
CERTAINTY_PRIORITY = {
    InformationCertainty.UNVERIFIED.value: 0,
    InformationCertainty.HYPOTHESIS.value: 0,
    InformationCertainty.INFERRED.value: 1,
    InformationCertainty.OBSERVED.value: 2,
    InformationCertainty.CONFIRMED.value: 3,
}


@dataclass
class GoalNode:
    goal_id: str
    title: str
    description: str = ""
    parent_goal_id: str | None = None
    status: str = GoalStatus.PENDING.value
    completion_conditions: list[str] = field(default_factory=list)
    child_goal_ids: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


@dataclass
class TaskRecord:
    task_id: str
    goal_id: str
    title: str
    instruction: str
    completion_conditions: list[str]
    status: str = TaskStatus.PENDING.value
    depends_on: list[str] = field(default_factory=list)
    result_summary: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    failure_history: list[str] = field(default_factory=list)
    satisfied_conditions: list[str] = field(default_factory=list)
    condition_status: dict[str, str] = field(default_factory=dict)
    condition_evidence: dict[str, list[str]] = field(default_factory=dict)
    progress_state: str | None = None
    source: str | None = None
    source_task_id: str | None = None
    superseded_by_task_id: str | None = None
    supersedes_task_id: str | None = None
    decision_premises: list[dict[str, str]] = field(default_factory=list)
    revalidation: dict[str, Any] | None = None


@dataclass
class ActionRecord:
    action_id: str
    task_id: str
    type: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    result_status: str | None = None
    relevance: str = "unknown"
    evidence_gain: bool = False
    created_at: str = field(default_factory=_now)


@dataclass
class EvidenceRecord:
    evidence_id: str
    source_type: str
    source: str
    summary: str
    created_by_action: str
    tool_name: str | None = None
    target: str | None = None
    relevant_content: str | None = None
    supported_completion_conditions: list[str] = field(default_factory=list)
    certainty: str = InformationCertainty.OBSERVED.value
    verified: bool = True
    task_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)


@dataclass
class ClaimRecord:
    claim_id: str
    claim: str
    certainty: str
    source: str
    evidence_ids: list[str] = field(default_factory=list)
    verified: bool = False
    created_at: str = field(default_factory=_now)


@dataclass
class FailureRecord:
    failure_id: str
    task_id: str
    action_id: str
    tool_name: str | None
    arguments: dict[str, Any]
    failure_code: str
    evidence_gain: bool = False
    created_at: str = field(default_factory=_now)


@dataclass
class MutationRecord:
    tool: str
    sandbox_session_id: str
    relative_path: str
    action: str
    before_hash: str | None
    after_hash: str
    changed: bool
    timestamp: str


@dataclass
class ToolGapCandidate:
    gap_id: str
    task_id: str
    required_capability: str
    existing_tool_match: str = "none"
    alternative_available: bool = False
    candidate_tool: str | None = None
    side_effect: str = "read_only"
    reason: str = ""
    reuse_score: str = "unknown"
    risk: str = "unknown"
    status: str = "candidate"
    occurrences: int = 1
    registry_checked: bool = False
    capability_index_checked: bool = False
    existing_candidates: list[str] = field(default_factory=list)
    rejected_candidates: list[dict[str, str]] = field(default_factory=list)
    missing_capability: str | None = None
    suggested_minimal_tool: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    certainty: str = InformationCertainty.UNVERIFIED.value
    requires_human_approval: bool = False


@dataclass
class ReplanRecord:
    replan_id: str
    scope_goal_id: str
    reason: str
    added_goal_ids: list[str] = field(default_factory=list)
    added_task_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)


class AgentTaskRuntime:
    """In-memory runtime. Persistence occurs only through explicit ``save``."""

    def __init__(
        self,
        runtime_id: str,
        *,
        stagnation_threshold: int = 2,
        sandbox_session: SandboxSession | None = None,
    ):
        self.runtime_id = runtime_id
        self.stagnation_threshold = stagnation_threshold
        self.goals: dict[str, GoalNode] = {}
        self.tasks: dict[str, TaskRecord] = {}
        self.actions: list[ActionRecord] = []
        self.evidence: dict[str, EvidenceRecord] = {}
        self.claims: list[ClaimRecord] = []
        self.failures: list[FailureRecord] = []
        self.mutations: list[MutationRecord] = []
        self.tool_gaps: dict[str, ToolGapCandidate] = {}
        self.replans: list[ReplanRecord] = []
        self.agent_runtime_events: list[dict[str, Any]] = []
        self.task_events: list[dict[str, Any]] = []
        self.sandbox_session: SandboxSession | None = None
        if sandbox_session is not None:
            self.attach_sandbox_session(sandbox_session)

    def attach_sandbox_session(self, session: SandboxSession) -> None:
        """Attach a controller-created session after fail-closed identity validation."""
        verify_sandbox_identity(session)
        self.sandbox_session = session
        self.emit_event("SANDBOX_SESSION_ATTACHED", session_id=session.session_id)

    def start_dedicated_sandbox(
        self, source_worktree: Path | str, sandbox_parent: Path | str
    ) -> SandboxSession:
        """Create and own a dedicated session using trusted Runtime inputs."""
        if self.sandbox_session is not None:
            raise ValueError("runtime already owns a sandbox session")
        session = create_dedicated_sandbox_session(source_worktree, sandbox_parent)
        self.attach_sandbox_session(session)
        return session

    def sandbox_identity(self) -> dict[str, object] | None:
        """Revalidate identity on use and expose the recorded Runtime-owned state."""
        if self.sandbox_session is None:
            return None
        verify_sandbox_identity(self.sandbox_session)
        return self.sandbox_session.as_dict()

    def record_mutation(self, record: MutationRecord) -> None:
        """Record an observed Sandbox mutation without completing any Task."""
        if self.sandbox_session is None:
            raise ValueError("runtime has no Sandbox Session")
        if self.sandbox_session.session_kind != "DEDICATED":
            raise ValueError("mutations require a Dedicated Sandbox Session")
        verify_sandbox_identity(self.sandbox_session)
        if record.sandbox_session_id != self.sandbox_session.session_id:
            raise ValueError("mutation Sandbox Session does not match Runtime")
        if not record.changed:
            raise ValueError("only actual mutations can be recorded")
        self.mutations.append(record)
        self.emit_event(
            "SANDBOX_MUTATION_RECORDED",
            tool=record.tool,
            relative_path=record.relative_path,
            action=record.action,
        )

    def emit_event(self, type_: str, **fields: Any) -> dict[str, Any]:
        row = {"type": type_, "timestamp": _now(), **fields}
        self.task_events.append(row)
        return row

    def add_goal(self, goal: GoalNode) -> None:
        if goal.goal_id in self.goals:
            raise ValueError(f"duplicate goal_id: {goal.goal_id}")
        if goal.parent_goal_id and goal.parent_goal_id not in self.goals:
            raise ValueError(f"unknown parent goal: {goal.parent_goal_id}")
        self.goals[goal.goal_id] = goal
        self.emit_event("GOAL_CREATED", goal_id=goal.goal_id)
        if goal.parent_goal_id:
            self.goals[goal.parent_goal_id].child_goal_ids.append(goal.goal_id)
            self.emit_event(
                "GOAL_DECOMPOSED",
                goal_id=goal.parent_goal_id,
                child_goal_id=goal.goal_id,
            )

    def add_task(self, task: TaskRecord) -> None:
        if task.task_id in self.tasks:
            raise ValueError(f"duplicate task_id: {task.task_id}")
        if task.goal_id not in self.goals:
            raise ValueError(f"unknown goal: {task.goal_id}")
        task.condition_status = {
            condition: task.condition_status.get(condition, ConditionStatus.UNKNOWN.value)
            for condition in task.completion_conditions
        }
        task.condition_evidence = {
            condition: list(task.condition_evidence.get(condition) or [])
            for condition in task.completion_conditions
        }
        self.tasks[task.task_id] = task
        self.goals[task.goal_id].task_ids.append(task.task_id)
        self.emit_event("TASK_CREATED", task_id=task.task_id, goal_id=task.goal_id)

    def patch_action_result(
        self,
        action_id: str,
        *,
        result_status: str | None,
        evidence_gain: bool | None = None,
    ) -> bool:
        """S9: continuation resume for run_test_plan — update existing action, no second record."""
        token = str(action_id or "").strip()
        for action in reversed(self.actions):
            if action.action_id == token:
                if result_status is not None:
                    action.result_status = result_status
                if evidence_gain is not None:
                    action.evidence_gain = evidence_gain
                self.emit_event(
                    "ACTION_COMPLETED",
                    action_id=action.action_id,
                    task_id=action.task_id,
                    result_status=action.result_status,
                )
                return True
        return False

    def record_action(self, action: ActionRecord) -> None:
        if action.task_id not in self.tasks:
            raise ValueError(f"unknown task: {action.task_id}")
        self.actions.append(action)
        task = self.tasks[action.task_id]
        if task.status == TaskStatus.PENDING.value:
            self.emit_event("TASK_STARTED", task_id=task.task_id)
        task.status = TaskStatus.IN_PROGRESS.value
        if action.evidence_gain:
            task.progress_state = ProgressState.PROGRESS.value
        self.emit_event(
            "ACTION_COMPLETED",
            action_id=action.action_id,
            task_id=action.task_id,
            result_status=action.result_status,
        )

    def add_evidence(self, record: EvidenceRecord, task_ids: Iterable[str]) -> None:
        ids = list(dict.fromkeys(task_ids))
        for task_id in ids:
            if task_id not in self.tasks:
                raise ValueError(f"unknown task: {task_id}")
        record.task_ids = list(dict.fromkeys([*record.task_ids, *ids]))
        self.evidence[record.evidence_id] = record
        for task_id in record.task_ids:
            task = self.tasks[task_id]
            if record.evidence_id not in task.evidence_ids:
                task.evidence_ids.append(record.evidence_id)
                task.progress_state = ProgressState.PROGRESS.value
        self.emit_event(
            "EVIDENCE_ADDED", evidence_id=record.evidence_id, task_ids=record.task_ids
        )

    def add_claim(self, record: ClaimRecord) -> ClaimRecord:
        if record.certainty not in {item.value for item in InformationCertainty}:
            raise ValueError(f"invalid claim certainty: {record.certainty}")
        record.evidence_ids = list(dict.fromkeys(record.evidence_ids))
        record.verified = bool(
            record.verified
            and record.certainty in AUTHORITATIVE_CERTAINTIES
            and record.evidence_ids
            and all(
                evidence_id in self.evidence
                and self.evidence[evidence_id].verified
                and self.evidence[evidence_id].certainty in AUTHORITATIVE_CERTAINTIES
                for evidence_id in record.evidence_ids
            )
        )
        self.claims.append(record)
        self.emit_event(
            "CLAIM_RECORDED",
            claim_id=record.claim_id,
            certainty=record.certainty,
            verified=record.verified,
        )
        return record

    def effective_claims(self) -> list[ClaimRecord]:
        """Return the strongest record for identical claims.

        An unverified LLM claim can coexist in the audit trail but can never
        override an observed or confirmed record.
        """
        selected: dict[str, ClaimRecord] = {}
        for record in self.claims:
            key = " ".join(record.claim.casefold().split())
            current = selected.get(key)
            if current is None or (
                CERTAINTY_PRIORITY[record.certainty], record.verified
            ) > (CERTAINTY_PRIORITY[current.certainty], current.verified):
                selected[key] = record
        return list(selected.values())

    def record_failure(self, failure: FailureRecord) -> None:
        if failure.task_id not in self.tasks:
            raise ValueError(f"unknown task: {failure.task_id}")
        self.failures.append(failure)
        self.tasks[failure.task_id].failure_history.append(failure.failure_id)
        if self.is_stagnating(failure.task_id):
            self.tasks[failure.task_id].progress_state = ProgressState.STAGNATION.value
            self.emit_event("STAGNATION_DETECTED", task_id=failure.task_id)

    def is_stagnating(self, task_id: str) -> bool:
        rows = [item for item in self.failures if item.task_id == task_id]
        if len(rows) < self.stagnation_threshold:
            return False
        tail = rows[-self.stagnation_threshold :]
        first = tail[0]
        return all(
            item.tool_name == first.tool_name
            and item.arguments == first.arguments
            and item.failure_code == first.failure_code
            and not item.evidence_gain
            for item in tail
        )

    def evaluate_task(self, task_id: str, satisfied_conditions: Iterable[str]) -> bool:
        task = self.tasks[task_id]
        task.satisfied_conditions = list(dict.fromkeys(satisfied_conditions))
        for condition in task.completion_conditions:
            if condition in task.satisfied_conditions:
                task.condition_status[condition] = ConditionStatus.SATISFIED.value
        complete = bool(task.completion_conditions) and all(
            task.condition_status.get(condition) == ConditionStatus.SATISFIED.value
            for condition in task.completion_conditions
        )
        task.status = TaskStatus.COMPLETE.value if complete else TaskStatus.IN_PROGRESS.value
        if complete:
            self.emit_event("TASK_COMPLETED", task_id=task_id)
        return complete

    def evaluate_task_from_evidence(self, task_id: str) -> bool:
        """Complete a Task only when every condition has authoritative Evidence."""
        task = self.tasks[task_id]
        supported: list[str] = []
        for condition in task.completion_conditions:
            refs = list(task.condition_evidence.get(condition) or [])
            authoritative = any(
                evidence_id in self.evidence
                and self.evidence[evidence_id].verified
                and self.evidence[evidence_id].certainty in AUTHORITATIVE_CERTAINTIES
                and condition
                in self.evidence[evidence_id].supported_completion_conditions
                for evidence_id in refs
            )
            task.condition_status[condition] = (
                ConditionStatus.SATISFIED.value
                if authoritative
                else ConditionStatus.UNKNOWN.value
            )
            if authoritative:
                supported.append(condition)
        was_complete = task.status == TaskStatus.COMPLETE.value
        complete = bool(task.completion_conditions) and len(supported) == len(
            task.completion_conditions
        )
        task.satisfied_conditions = supported
        task.status = TaskStatus.COMPLETE.value if complete else TaskStatus.IN_PROGRESS.value
        if complete and not was_complete:
            self.emit_event("TASK_COMPLETED", task_id=task_id)
        return complete

    def support_completion_conditions(
        self,
        task_id: str,
        evidence_id: str,
        conditions: Iterable[str],
    ) -> None:
        task = self.tasks[task_id]
        evidence = self.evidence.get(evidence_id)
        if (
            evidence is None
            or not evidence.verified
            or evidence.certainty not in AUTHORITATIVE_CERTAINTIES
        ):
            self.emit_event(
                "COMPLETION_SUPPORT_REJECTED",
                task_id=task_id,
                evidence_id=evidence_id,
                reason="evidence_not_verified",
            )
            return
        for condition in dict.fromkeys(conditions):
            if condition not in task.completion_conditions:
                continue
            task.condition_status[condition] = ConditionStatus.SATISFIED.value
            refs = task.condition_evidence.setdefault(condition, [])
            if evidence_id not in refs:
                refs.append(evidence_id)
            if condition not in task.satisfied_conditions:
                task.satisfied_conditions.append(condition)
            self.emit_event(
                "COMPLETION_CONDITION_SATISFIED",
                task_id=task_id,
                condition=condition,
                evidence_id=evidence_id,
            )
            self.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.claims) + 1}",
                    claim=condition,
                    certainty=InformationCertainty.CONFIRMED.value,
                    source=f"completion_condition:{task_id}",
                    evidence_ids=[evidence_id],
                    verified=True,
                )
            )

    def evaluate_goal(self, goal_id: str, satisfied_conditions: Iterable[str]) -> bool:
        goal = self.goals[goal_id]
        children_done = all(
            self.goals[item].status == GoalStatus.COMPLETE.value
            for item in goal.child_goal_ids
        )
        tasks_done = all(
            self.tasks[item].status == TaskStatus.COMPLETE.value for item in goal.task_ids
        )
        conditions_done = set(goal.completion_conditions) <= set(satisfied_conditions)
        complete = children_done and tasks_done and conditions_done
        goal.status = GoalStatus.COMPLETE.value if complete else GoalStatus.IN_PROGRESS.value
        goal.updated_at = _now()
        if complete:
            self.emit_event("GOAL_COMPLETED", goal_id=goal_id)
        return complete

    def has_reusable_evidence(
        self, task_id: str, tool_name: str, arguments: Mapping[str, Any]
    ) -> bool:
        shared_action_ids = {
            self.evidence[evidence_id].created_by_action
            for evidence_id in self.tasks[task_id].evidence_ids
        }
        return any(
            item.tool_name == tool_name
            and item.arguments == dict(arguments)
            and item.evidence_gain
            and (item.task_id == task_id or item.action_id in shared_action_ids)
            for item in self.actions
        )

    def audit_relevance(
        self, task_id: str, *, tool_name: str, relevant_tools: Iterable[str]
    ) -> str:
        if task_id not in self.tasks:
            raise ValueError(f"unknown task: {task_id}")
        return "ACCEPT" if tool_name in set(relevant_tools) else "REJECT_ACTION_RESULT"

    def assess_progress(
        self, task_id: str, *, evidence_gain: bool, regression: bool = False
    ) -> str:
        task = self.tasks[task_id]
        if regression:
            task.progress_state = ProgressState.REGRESSION.value
        elif evidence_gain:
            task.progress_state = ProgressState.PROGRESS.value
        elif self.is_stagnating(task_id):
            task.progress_state = ProgressState.STAGNATION.value
        return task.progress_state or "unknown"

    def recovery_hint(self, task_id: str) -> str:
        failures = [item for item in self.failures if item.task_id == task_id]
        forbidden = [
            f"{item.tool_name}({json.dumps(item.arguments, sort_keys=True, ensure_ascii=False)})"
            for item in failures[-self.stagnation_threshold :]
        ]
        self.emit_event("RECOVERY_REQUESTED", task_id=task_id)
        return (
            "Continue the current task.\n"
            f"Do not repeat the same failed action: {', '.join(forbidden)}\n"
            "Choose a different read-only action that can add evidence."
        )

    def small_task_hint(self, task_id: str) -> str:
        task = self.tasks[task_id]
        goal = self.goals[task.goal_id]
        roots = [item for item in self.goals.values() if item.parent_goal_id is None]
        evidence = [self.evidence[item].summary for item in task.evidence_ids]
        failures = [self.failures_by_id(item).failure_code for item in task.failure_history]
        return "\n".join(
            [
                f"Final Goal: {roots[0].title if roots else goal.title}",
                f"Current Goal: {goal.title}",
                f"Current Task: {task.title}",
                "Completion Condition: " + "; ".join(task.completion_conditions),
                "Known Evidence: " + ("; ".join(evidence) or "none"),
                "Known Failures: " + ("; ".join(failures) or "none"),
                "Advance only the current task.",
            ]
        )

    def failures_by_id(self, failure_id: str) -> FailureRecord:
        return next(item for item in self.failures if item.failure_id == failure_id)

    def detect_tool_gap(
        self,
        task_id: str,
        required_capability: str,
        registry_tools: Iterable[Mapping[str, Any]],
        *,
        candidate_tool: str | None = None,
    ) -> ToolGapCandidate | None:
        if task_id not in self.tasks:
            raise ValueError(f"unknown task: {task_id}")
        needle = required_capability.casefold().strip()
        for tool in registry_tools:
            haystack = " ".join(
                [
                    str(tool.get("name") or ""),
                    str(tool.get("description") or ""),
                    " ".join(map(str, tool.get("keywords") or [])),
                ]
            ).casefold()
            if needle and needle in haystack:
                return None
        if needle in self.tool_gaps:
            gap = self.tool_gaps[needle]
            gap.occurrences += 1
            if gap.occurrences > 1:
                gap.status = "recommended"
            return gap
        gap = ToolGapCandidate(
            gap_id=f"TG-{len(self.tool_gaps) + 1:03d}",
            task_id=task_id,
            required_capability=required_capability,
            candidate_tool=candidate_tool,
            reason="No matching tool capability was found in the Registry.",
        )
        self.tool_gaps[needle] = gap
        return gap

    def record_confirmed_tool_gap(
        self,
        task_id: str,
        required_capability: str,
        *,
        registry_checked: bool,
        capability_index_checked: bool,
        existing_candidates: Iterable[str],
        rejected_candidates: Iterable[Mapping[str, str]],
        suggested_minimal_tool: str | None,
        evidence_ids: Iterable[str],
    ) -> ToolGapCandidate | None:
        refs = list(dict.fromkeys(evidence_ids))
        authoritative = bool(refs) and all(
            evidence_id in self.evidence
            and self.evidence[evidence_id].verified
            and self.evidence[evidence_id].certainty in AUTHORITATIVE_CERTAINTIES
            for evidence_id in refs
        )
        if not (registry_checked and capability_index_checked and authoritative):
            return None
        key = required_capability.casefold().strip()
        gap = ToolGapCandidate(
            gap_id=f"TG-{len(self.tool_gaps) + 1:03d}",
            task_id=task_id,
            required_capability=required_capability,
            candidate_tool=suggested_minimal_tool,
            reason="Capability Index and Registry contain no agent-available equivalent.",
            status="confirmed",
            registry_checked=True,
            capability_index_checked=True,
            existing_candidates=list(existing_candidates),
            rejected_candidates=[dict(item) for item in rejected_candidates],
            missing_capability=required_capability,
            suggested_minimal_tool=suggested_minimal_tool,
            evidence_ids=refs,
            certainty=InformationCertainty.CONFIRMED.value,
            requires_human_approval=True,
        )
        self.tool_gaps[key] = gap
        self.emit_event(
            "TOOL_GAP_CONFIRMED",
            task_id=task_id,
            required_capability=required_capability,
            evidence_ids=refs,
        )
        return gap

    def add_replan(self, record: ReplanRecord) -> None:
        if record.scope_goal_id not in self.goals:
            raise ValueError(f"unknown replan scope: {record.scope_goal_id}")
        self.replans.append(record)
        self.emit_event(
            "REPLAN_REQUESTED",
            replan_id=record.replan_id,
            scope_goal_id=record.scope_goal_id,
        )

    def replan_add_task(self, record: ReplanRecord, task: TaskRecord) -> None:
        """Apply an additive local replan without reopening completed work."""
        if task.goal_id != record.scope_goal_id:
            raise ValueError("replan task must belong to scope goal")
        self.add_task(task)
        if task.task_id not in record.added_task_ids:
            record.added_task_ids.append(task.task_id)
        self.add_replan(record)

    def final_synthesis_context(self, final_goal_id: str) -> dict[str, Any]:
        incomplete = [
            item.task_id
            for item in self.tasks.values()
            if item.status != TaskStatus.COMPLETE.value
        ]
        self.emit_event("FINAL_SYNTHESIS", goal_id=final_goal_id)
        return {
            "final_goal": asdict(self.goals[final_goal_id]),
            "completed_tasks": [
                asdict(item)
                for item in self.tasks.values()
                if item.status == TaskStatus.COMPLETE.value
            ],
            "evidence_summaries": [item.summary for item in self.evidence.values()],
            "unresolved_items": incomplete,
            "ready": not incomplete
            and self.goals[final_goal_id].status == GoalStatus.COMPLETE.value,
        }

    def observe_agent_runtime_event(self, event: Mapping[str, Any]) -> None:
        self.agent_runtime_events.append(dict(event))

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in (
            ("goal_tree.json", [asdict(item) for item in self.goals.values()]),
            ("tasks.json", [asdict(item) for item in self.tasks.values()]),
        ):
            (directory / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        for name, rows in (
            ("actions.jsonl", self.actions),
            ("evidence.jsonl", self.evidence.values()),
            ("claims.jsonl", self.claims),
            ("failures.jsonl", self.failures),
            ("replans.jsonl", self.replans),
            ("tool_gaps.jsonl", self.tool_gaps.values()),
            ("mutations.jsonl", self.mutations),
        ):
            text = "".join(
                json.dumps(asdict(row), ensure_ascii=False) + "\n" for row in rows
            )
            (directory / name).write_text(text, encoding="utf-8")
        (directory / "task_events.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in self.task_events),
            encoding="utf-8",
        )
        if self.sandbox_session is not None:
            (directory / "sandbox_session.json").write_text(
                json.dumps(self.sandbox_session.as_dict(), ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )

    @classmethod
    def load(cls, directory: Path, *, runtime_id: str = "loaded") -> "AgentTaskRuntime":
        runtime = cls(runtime_id)
        sandbox_path = directory / "sandbox_session.json"
        if sandbox_path.exists():
            runtime.attach_sandbox_session(
                SandboxSession(**json.loads(sandbox_path.read_text(encoding="utf-8")))
            )
        goals = json.loads((directory / "goal_tree.json").read_text(encoding="utf-8"))
        tasks = json.loads((directory / "tasks.json").read_text(encoding="utf-8"))
        runtime.goals = {item["goal_id"]: GoalNode(**item) for item in goals}
        runtime.tasks = {item["task_id"]: TaskRecord(**item) for item in tasks}
        for name, model, target in (
            ("actions.jsonl", ActionRecord, runtime.actions),
            ("claims.jsonl", ClaimRecord, runtime.claims),
            ("failures.jsonl", FailureRecord, runtime.failures),
            ("replans.jsonl", ReplanRecord, runtime.replans),
            ("mutations.jsonl", MutationRecord, runtime.mutations),
        ):
            path = directory / name
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line:
                    target.append(model(**json.loads(line)))
        for line in (directory / "tool_gaps.jsonl").read_text(encoding="utf-8").splitlines():
            if line:
                record = ToolGapCandidate(**json.loads(line))
                runtime.tool_gaps[record.required_capability.casefold().strip()] = record
        for line in (directory / "evidence.jsonl").read_text(encoding="utf-8").splitlines():
            if line:
                record = EvidenceRecord(**json.loads(line))
                runtime.evidence[record.evidence_id] = record
        for line in (directory / "task_events.jsonl").read_text(encoding="utf-8").splitlines():
            if line:
                runtime.task_events.append(json.loads(line))
        return runtime


__all__ = [
    "ActionRecord",
    "AgentTaskRuntime",
    "AUTHORITATIVE_CERTAINTIES",
    "CERTAINTY_PRIORITY",
    "ClaimRecord",
    "EvidenceRecord",
    "FailureRecord",
    "GoalNode",
    "GoalStatus",
    "InformationCertainty",
    "MutationRecord",
    "ProgressState",
    "ReplanRecord",
    "TaskRecord",
    "TaskStatus",
    "ToolGapCandidate",
    "SandboxSession",
]
