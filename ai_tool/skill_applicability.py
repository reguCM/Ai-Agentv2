"""Dev Skill applicability resolution (Phase 0).

Separates two judgments:
- usability: whether the skill *can* be used in the current context
- value: whether using the skill is *worth it* when usable

Registry canonical source: registry/skills.json
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

RETRYABLE_SKILL_IDS = frozenset({"grill-me", "write-prd"})
# grill-me は単体呼び出し・判定対象外。write-prd 内部 invoke は別経路。
VALUE_LOOP_EXCLUDED_SKILL_IDS = frozenset({"grill-me"})


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "registry" / "skills.json"


class UsabilityVerdict(str, Enum):
    USABLE = "USABLE"
    BLOCKED = "BLOCKED"
    DEFER = "DEFER"


class ValueVerdict(str, Enum):
    USE = "USE"
    SKIP = "SKIP"
    REDUNDANT = "REDUNDANT"
    DEFER = "DEFER"


OPTIONAL_INPUTS = frozenset({"knowledge_map"})

ARTIFACT_BY_SKILL_OUTPUT: dict[str, list[str]] = {
    "grill-me": ["ambiguity_report"],
    "write-prd": ["prd"],
    "graph-engineering": ["knowledge_map"],
    "tech-spec": ["tech_spec"],
    "planning-and-task-breakdown": ["implementation_plan", "task_list"],
    "goal-handoff": ["goal_handoff_packet"],
    "session-start": ["session_sync_report"],
}

_NUMBERED_CONDITION = re.compile(r"(?m)^\s*\d+[.)．]\s+\S")
_VAGUE_REQUEST = re.compile(
    r"(作って|作る|build|create|implement|して$|したい)",
    re.I,
)
_SINGLE_FILE_SANDBOX = re.compile(
    r"(sandbox|単一|1ファイル|one file|tetris/main\.py)",
    re.I,
)
_RESUME_HINT = re.compile(
    r"(再開|resume|続き|worktree|branch|session start|同期)",
    re.I,
)


@dataclass
class GapContext:
    """Boundary-router context for skill value resolution at execution end."""

    kind: str
    facts_sufficient: bool = False
    gap_resolved: bool = False


@dataclass
class SkillArtifacts:
    """Upstream artifact kinds already available."""

    kinds: set[str] = field(default_factory=set)

    def has(self, kind: str) -> bool:
        return kind in self.kinds

    def add_outputs(self, skill_id: str) -> None:
        for kind in ARTIFACT_BY_SKILL_OUTPUT.get(skill_id, []):
            self.kinds.add(kind)

    def as_list(self) -> list[str]:
        return sorted(self.kinds)


@dataclass
class SkillApplicabilityItem:
    skill_id: str
    usability: str
    usability_reasons: list[str] = field(default_factory=list)
    value: str = ValueVerdict.DEFER.value
    value_reasons: list[str] = field(default_factory=list)
    execute: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkillStepOutcome:
    """Observed result from one skill execution attempt."""

    status: str
    gate_passed: bool | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class SkillStepAttempt:
    attempt: int
    active_skill_id: str
    snapshot: list[SkillApplicabilityItem]
    outcome: SkillStepOutcome

    @property
    def applicability(self) -> SkillApplicabilityItem:
        for item in self.snapshot:
            if item.skill_id == self.active_skill_id:
                return item
        raise KeyError(f"active skill missing from snapshot: {self.active_skill_id}")


@dataclass
class CompositionStepRun:
    skill_id: str
    attempts: list[SkillStepAttempt] = field(default_factory=list)

    @property
    def final_status(self) -> str:
        if not self.attempts:
            return "skipped"
        return self.attempts[-1].outcome.status

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


@dataclass
class ValueConsumptionExecution:
    skill_id: str
    outcome: SkillStepOutcome


@dataclass
class ValueConsumptionRound:
    round_index: int
    snapshot: list[SkillApplicabilityItem] = field(default_factory=list)
    executions: list[ValueConsumptionExecution] = field(default_factory=list)

    @property
    def executed_skill_ids(self) -> list[str]:
        return [row.skill_id for row in self.executions]


@dataclass
class SkillValueConsumptionReport:
    request_excerpt: str
    consumer: str
    composition_id: str
    excluded_skill_ids: list[str] = field(default_factory=list)
    rounds: list[ValueConsumptionRound] = field(default_factory=list)
    final_artifacts: SkillArtifacts = field(default_factory=SkillArtifacts)

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    def all_executed_skill_ids(self) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for round_row in self.rounds:
            for skill_id in round_row.executed_skill_ids:
                if skill_id not in seen:
                    ordered.append(skill_id)
                    seen.add(skill_id)
        return ordered

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_excerpt": self.request_excerpt,
            "consumer": self.consumer,
            "composition_id": self.composition_id,
            "excluded_skill_ids": self.excluded_skill_ids,
            "round_count": self.round_count,
            "executed_skill_ids": self.all_executed_skill_ids(),
            "final_artifacts": self.final_artifacts.as_list(),
            "rounds": [
                {
                    "round_index": round_row.round_index,
                    "snapshot": [item.as_dict() for item in round_row.snapshot],
                    "executions": [
                        {
                            "skill_id": row.skill_id,
                            "outcome": asdict(row.outcome),
                        }
                        for row in round_row.executions
                    ],
                }
                for round_row in self.rounds
            ],
        }


@dataclass
class CompositionWalkReport:
    request_excerpt: str
    consumer: str
    composition_id: str
    step_runs: list[CompositionStepRun] = field(default_factory=list)
    final_artifacts: SkillArtifacts = field(default_factory=SkillArtifacts)

    def executed_skill_ids(self) -> list[str]:
        return [
            run.skill_id
            for run in self.step_runs
            if run.attempts
            and run.attempts[-1].outcome.status in {"done", "partial"}
            and run.attempts[-1].applicability.execute
        ]


@dataclass
class SkillApplicabilityReport:
    request_excerpt: str
    consumer: str
    composition_id: str
    items: list[SkillApplicabilityItem] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_excerpt": self.request_excerpt,
            "consumer": self.consumer,
            "composition_id": self.composition_id,
            "items": [item.as_dict() for item in self.items],
            "executed_skill_ids": self.executed_skill_ids(),
        }

    def executed_skill_ids(self) -> list[str]:
        return [item.skill_id for item in self.items if item.execute]


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def composition_steps(
    composition_id: str,
    registry: Mapping[str, Any] | None = None,
) -> list[str]:
    catalog = registry or load_registry()
    for composition in catalog.get("compositions") or []:
        if composition.get("id") == composition_id:
            return list(composition.get("steps") or [])
    raise KeyError(f"Unknown composition id: {composition_id}")


def _skill_index(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(skill["id"]): dict(skill) for skill in (registry.get("skills") or [])}


def _consumer_compatible(skill: Mapping[str, Any], consumer: str) -> bool:
    consumers = {str(item) for item in (skill.get("consumers") or [])}
    if consumer in consumers:
        return True
    if consumer == "local_agent":
        return bool(consumers & {"cursor", "codex"})
    return False


def _missing_inputs(skill: Mapping[str, Any], artifacts: SkillArtifacts) -> list[str]:
    missing: list[str] = []
    for kind in skill.get("inputs") or []:
        required = str(kind)
        if required in OPTIONAL_INPUTS:
            continue
        if required == "prd" and not artifacts.has("prd"):
            missing.append(required)
        elif required == "tech_spec" and not artifacts.has("tech_spec"):
            missing.append(required)
        elif required in {"implementation_plan", "task_list"}:
            if not (artifacts.has("implementation_plan") or artifacts.has("task_list")):
                missing.append(required)
    return missing


def _request_is_ambiguous(request: str) -> bool:
    text = str(request or "").strip()
    if not text:
        return True
    if _NUMBERED_CONDITION.search(text):
        return False
    if len(text) <= 24 and _VAGUE_REQUEST.search(text):
        return True
    vague_markers = ("適切に", "いい感じ", "よしなに", "maybe", "perhaps")
    return any(marker in text.casefold() for marker in vague_markers)


def _scope_is_small(request: str) -> bool:
    text = str(request or "")
    return bool(_SINGLE_FILE_SANDBOX.search(text))


def _resume_context(request: str, *, resume_session: bool) -> bool:
    return resume_session or bool(_RESUME_HINT.search(request))


def _redundant_with_invoker(
    skill_id: str,
    composition_steps: list[str],
    skills: Mapping[str, Mapping[str, Any]],
) -> str | None:
    """Mark redundant only when an earlier composition step already invokes this skill."""
    try:
        skill_index = composition_steps.index(skill_id)
    except ValueError:
        return None
    for index, step in enumerate(composition_steps):
        if index >= skill_index:
            break
        entry = skills.get(step) or {}
        invokes = {str(item) for item in (entry.get("invokes") or [])}
        if skill_id in invokes:
            return step
    return None


def _grill_already_satisfied(artifacts: SkillArtifacts) -> bool:
    return artifacts.has("ambiguity_report")


def build_artifacts_from_router_input(inp: Any) -> SkillArtifacts:
    """Map router observation to artifact kinds without implying gap resolution."""
    artifacts = SkillArtifacts(set(getattr(inp, "artifact_kinds", None) or []))
    return artifacts


def _resolve_boundary_grill_me(
    item: SkillApplicabilityItem,
    entry: Mapping[str, Any],
    gap_context: GapContext,
    *,
    request: str,
) -> SkillApplicabilityItem:
    if gap_context.gap_resolved:
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("gap_resolved_by_confirmed_spec_or_human_decision")
        return item
    if gap_context.kind != "spec_meaning_gap":
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append(f"gap_kind_not_spec_meaning:{gap_context.kind}")
        return item
    if not gap_context.facts_sufficient:
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("facts_insufficient_use_recovery_first")
        return item
    if not entry.get("runtime_connected"):
        item.usability = UsabilityVerdict.BLOCKED.value
        item.usability_reasons.append("runtime_not_connected")
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("runtime_not_connected")
        return item
    from ai_tool.chat_interface.boundary_grill import request_has_material_spec_fork

    if not request_has_material_spec_fork(str(request or "")):
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("no_material_spec_fork")
        return item
    item.value = ValueVerdict.USE.value
    item.value_reasons.append("boundary_spec_ambiguity_unresolved")
    return item


def resolve_skill_applicability(
    skill_id: str,
    *,
    request: str,
    consumer: str,
    artifacts: SkillArtifacts,
    composition_steps: list[str],
    registry: Mapping[str, Any] | None = None,
    resume_session: bool = False,
    gap_context: GapContext | None = None,
) -> SkillApplicabilityItem:
    """Resolve usability and value for one skill in the current context."""
    catalog = registry or load_registry()
    skills = _skill_index(catalog)
    entry = skills.get(skill_id)
    item = SkillApplicabilityItem(skill_id=skill_id, usability=UsabilityVerdict.DEFER.value)

    if entry is None:
        item.usability = UsabilityVerdict.BLOCKED.value
        item.usability_reasons.append("unknown_skill_id")
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("not_in_registry")
        return item

    skill_path = REPO_ROOT / str(entry.get("path") or "")
    if not skill_path.is_file():
        item.usability = UsabilityVerdict.BLOCKED.value
        item.usability_reasons.append("skill_body_missing")
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("skill_body_missing")
        return item

    if str(entry.get("status") or "") == "retired":
        item.usability = UsabilityVerdict.BLOCKED.value
        item.usability_reasons.append("skill_retired")
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("skill_retired")
        return item

    if not _consumer_compatible(entry, consumer):
        item.usability = UsabilityVerdict.BLOCKED.value
        item.usability_reasons.append(f"consumer_not_supported:{consumer}")
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("wrong_consumer")
        return item

    missing = _missing_inputs(entry, artifacts)
    if missing:
        item.usability = UsabilityVerdict.BLOCKED.value
        item.usability_reasons.append("missing_inputs:" + ",".join(missing))
        item.value = ValueVerdict.DEFER.value
        item.value_reasons.append("blocked_by_missing_inputs")
        return item

    outputs = [str(kind) for kind in (entry.get("outputs") or [])]
    boundary_grill = skill_id == "grill-me" and gap_context is not None
    if (
        outputs
        and all(artifacts.has(kind) for kind in outputs)
        and not boundary_grill
    ):
        item.usability = UsabilityVerdict.USABLE.value
        item.usability_reasons.append("outputs_already_present")
        item.value = ValueVerdict.SKIP.value
        item.value_reasons.append("artifact_already_satisfied")
        return item

    item.usability = UsabilityVerdict.USABLE.value
    item.usability_reasons.append("registry_and_inputs_satisfied")

    invoker = _redundant_with_invoker(skill_id, composition_steps, skills)
    if invoker:
        item.value = ValueVerdict.REDUNDANT.value
        item.value_reasons.append(f"invoked_by:{invoker}")
        return item

    if skill_id == "grill-me":
        if gap_context is not None:
            return _resolve_boundary_grill_me(item, entry, gap_context, request=request)
        if _request_is_ambiguous(request):
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("request_ambiguous")
        else:
            item.value = ValueVerdict.SKIP.value
            item.value_reasons.append("request_already_specific")
        return item

    if skill_id == "graph-engineering":
        if _scope_is_small(request):
            item.value = ValueVerdict.SKIP.value
            item.value_reasons.append("scope_single_file_or_sandbox")
        else:
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("multi_component_or_unfamiliar_scope")
        return item

    if skill_id == "write-prd":
        if artifacts.has("prd"):
            item.value = ValueVerdict.SKIP.value
            item.value_reasons.append("prd_already_present")
        elif _grill_already_satisfied(artifacts):
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("needs_prd_from_prior_grill")
        elif _request_is_ambiguous(request):
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("needs_grounded_prd")
        else:
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("spec_still_beneficial")
        return item

    if skill_id == "tech-spec":
        if artifacts.has("tech_spec"):
            item.value = ValueVerdict.SKIP.value
            item.value_reasons.append("tech_spec_already_present")
        elif _scope_is_small(request):
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("sandbox_constraints_need_spec")
        else:
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("implementation_order_benefits_from_spec")
        return item

    if skill_id == "planning-and-task-breakdown":
        if artifacts.has("implementation_plan") and artifacts.has("task_list"):
            item.value = ValueVerdict.SKIP.value
            item.value_reasons.append("plan_and_tasks_already_present")
        elif _scope_is_small(request):
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("verifiable_tasks_still_useful")
        else:
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("multi_step_planning_beneficial")
        return item

    if skill_id == "goal-handoff":
        if artifacts.has("goal_handoff_packet"):
            item.value = ValueVerdict.SKIP.value
            item.value_reasons.append("handoff_already_present")
        else:
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("bridge_to_implementation_session")
        return item

    if skill_id == "session-start":
        if _resume_context(request, resume_session=resume_session):
            item.value = ValueVerdict.USE.value
            item.value_reasons.append("resume_or_resync_context")
        else:
            item.value = ValueVerdict.SKIP.value
            item.value_reasons.append("fresh_work_not_session_resume")
        return item

    item.value = ValueVerdict.USE.value
    item.value_reasons.append("default_use_when_usable")
    return item


def should_execute(item: SkillApplicabilityItem) -> bool:
    return (
        item.usability == UsabilityVerdict.USABLE.value
        and item.value == ValueVerdict.USE.value
    )


def skill_outcome_satisfied(skill_id: str, outcome: SkillStepOutcome) -> bool:
    """Return True when a retryable skill no longer needs another attempt."""
    if outcome.status == "error":
        return False
    if outcome.status == "skipped":
        return True
    if skill_id in RETRYABLE_SKILL_IDS:
        return outcome.gate_passed is True
    return outcome.status == "done"


def build_applicability_snapshot(
    *,
    steps: list[str],
    active_skill_id: str,
    request: str,
    consumer: str,
    artifacts: SkillArtifacts,
    registry: Mapping[str, Any],
    resume_session: bool = False,
) -> list[SkillApplicabilityItem]:
    """Resolve the full composition but allow execute on only the active step."""
    active_index = steps.index(active_skill_id)
    snapshot: list[SkillApplicabilityItem] = []
    for index, skill_id in enumerate(steps):
        item = resolve_skill_applicability(
            skill_id,
            request=request,
            consumer=consumer,
            artifacts=artifacts,
            composition_steps=steps,
            registry=registry,
            resume_session=resume_session,
        )
        if index < active_index:
            item.execute = False
            if item.value == ValueVerdict.USE.value:
                item.value = ValueVerdict.SKIP.value
                item.value_reasons.append("prior_step_completed_in_walk")
        elif index == active_index:
            item.execute = should_execute(item)
        else:
            item.value = ValueVerdict.DEFER.value
            item.value_reasons.append(f"awaiting_active_step:{active_skill_id}")
            item.execute = False
        snapshot.append(item)
    return snapshot


def count_execute_true(snapshot: list[SkillApplicabilityItem]) -> int:
    return sum(1 for item in snapshot if item.execute)


def should_retry_skill_execution(
    skill_id: str,
    *,
    next_attempt: int,
    outcome: SkillStepOutcome,
    max_attempts: int,
) -> bool:
    """Retry when usefulness remains (gate not passed) and budget remains."""
    if skill_id not in RETRYABLE_SKILL_IDS:
        return False
    if outcome.status == "error":
        return False
    if next_attempt >= max_attempts:
        return False
    return not skill_outcome_satisfied(skill_id, outcome)


def judgment_target_steps(
    steps: list[str],
    excluded_skill_ids: frozenset[str] = VALUE_LOOP_EXCLUDED_SKILL_IDS,
) -> list[str]:
    """Skills that participate in value-loop judgment and execution."""
    return [skill_id for skill_id in steps if skill_id not in excluded_skill_ids]


def run_skill_value_consumption_loop(
    *,
    request: str,
    composition_id: str,
    executor: Callable[[str], SkillStepOutcome],
    consumer: str = "local_agent",
    registry: Mapping[str, Any] | None = None,
    resume_session: bool = False,
    initial_artifacts: SkillArtifacts | None = None,
    excluded_skill_ids: frozenset[str] = VALUE_LOOP_EXCLUDED_SKILL_IDS,
    max_rounds: int = 20,
) -> SkillValueConsumptionReport:
    """Consume valuable skills from a blank state until no USE remains.

    grill-me is neither judged nor executed here (standalone grill is out of scope).
    All other composition steps are judgment targets each round. USE skills run in
    composition order within the round. Outputs register only when satisfied.
    Rounds repeat until a round performs zero executions.
    """
    catalog = registry or load_registry()
    steps = composition_steps(composition_id, catalog)
    targets = judgment_target_steps(steps, excluded_skill_ids)
    artifacts = initial_artifacts or SkillArtifacts()
    report = SkillValueConsumptionReport(
        request_excerpt=str(request or "")[:240],
        consumer=consumer,
        composition_id=composition_id,
        excluded_skill_ids=sorted(excluded_skill_ids),
    )

    for round_index in range(max_rounds):
        round_row = ValueConsumptionRound(round_index=round_index)
        round_had_execution = False

        for skill_id in targets:
            item = resolve_skill_applicability(
                skill_id,
                request=request,
                consumer=consumer,
                artifacts=artifacts,
                composition_steps=steps,
                registry=catalog,
                resume_session=resume_session,
            )
            item.execute = should_execute(item)
            round_row.snapshot.append(item)

            if not item.execute:
                continue

            outcome = executor(skill_id)
            round_row.executions.append(
                ValueConsumptionExecution(skill_id=skill_id, outcome=outcome)
            )
            round_had_execution = True

            if skill_outcome_satisfied(skill_id, outcome):
                artifacts.add_outputs(skill_id)

        report.rounds.append(round_row)
        if not round_had_execution:
            break

    report.final_artifacts = artifacts
    return report


def walk_composition_with_retry(
    *,
    request: str,
    composition_id: str,
    executor: Callable[[str, int], SkillStepOutcome],
    consumer: str = "local_agent",
    registry: Mapping[str, Any] | None = None,
    resume_session: bool = False,
    initial_artifacts: SkillArtifacts | None = None,
    max_attempts_per_skill: int = 3,
) -> CompositionWalkReport:
    """Walk a composition, executing skills and retrying while usefulness remains.

    For retryable skills (`grill-me`, `write-prd`), an attempt with
    `gate_passed=False` does not register outputs. The next loop iteration
    re-resolves applicability; while artifacts are missing the skill stays USE.
    """
    catalog = registry or load_registry()
    steps = composition_steps(composition_id, catalog)
    artifacts = initial_artifacts or SkillArtifacts()
    report = CompositionWalkReport(
        request_excerpt=str(request or "")[:240],
        consumer=consumer,
        composition_id=composition_id,
    )

    for skill_id in steps:
        attempt = 0
        step_run = CompositionStepRun(skill_id=skill_id)
        while True:
            snapshot = build_applicability_snapshot(
                steps=steps,
                active_skill_id=skill_id,
                request=request,
                consumer=consumer,
                artifacts=artifacts,
                registry=catalog,
                resume_session=resume_session,
            )
            item = next(row for row in snapshot if row.skill_id == skill_id)

            if not item.execute:
                step_run.attempts.append(
                    SkillStepAttempt(
                        attempt=attempt,
                        active_skill_id=skill_id,
                        snapshot=snapshot,
                        outcome=SkillStepOutcome(status="skipped"),
                    )
                )
                break

            outcome = executor(skill_id, attempt)
            step_run.attempts.append(
                SkillStepAttempt(
                    attempt=attempt,
                    active_skill_id=skill_id,
                    snapshot=snapshot,
                    outcome=outcome,
                )
            )

            if skill_outcome_satisfied(skill_id, outcome):
                if outcome.status != "skipped":
                    artifacts.add_outputs(skill_id)
                break

            if not should_retry_skill_execution(
                skill_id,
                next_attempt=attempt + 1,
                outcome=outcome,
                max_attempts=max_attempts_per_skill,
            ):
                break

            attempt += 1

        report.step_runs.append(step_run)

    report.final_artifacts = artifacts
    return report


def resolve_composition_applicability(
    *,
    request: str,
    composition_id: str,
    consumer: str = "local_agent",
    registry: Mapping[str, Any] | None = None,
    resume_session: bool = False,
    initial_artifacts: SkillArtifacts | None = None,
) -> SkillApplicabilityReport:
    """Walk a composition in order and resolve per-step usability/value."""
    catalog = registry or load_registry()
    steps = composition_steps(composition_id, catalog)
    artifacts = initial_artifacts or SkillArtifacts()
    report = SkillApplicabilityReport(
        request_excerpt=str(request or "")[:240],
        consumer=consumer,
        composition_id=composition_id,
    )

    for skill_id in steps:
        item = resolve_skill_applicability(
            skill_id,
            request=request,
            consumer=consumer,
            artifacts=artifacts,
            composition_steps=steps,
            registry=catalog,
            resume_session=resume_session,
        )
        item.execute = should_execute(item)
        report.items.append(item)
        if item.execute:
            artifacts.add_outputs(skill_id)
    return report


__all__ = [
    "CompositionStepRun",
    "CompositionWalkReport",
    "RETRYABLE_SKILL_IDS",
    "VALUE_LOOP_EXCLUDED_SKILL_IDS",
    "ValueConsumptionExecution",
    "ValueConsumptionRound",
    "SkillValueConsumptionReport",
    "build_applicability_snapshot",
    "count_execute_true",
    "judgment_target_steps",
    "run_skill_value_consumption_loop",
    "SkillApplicabilityItem",
    "SkillApplicabilityReport",
    "SkillArtifacts",
    "SkillStepAttempt",
    "SkillStepOutcome",
    "UsabilityVerdict",
    "ValueVerdict",
    "composition_steps",
    "load_registry",
    "resolve_composition_applicability",
    "resolve_skill_applicability",
    "should_execute",
    "should_retry_skill_execution",
    "skill_outcome_satisfied",
    "walk_composition_with_retry",
]
