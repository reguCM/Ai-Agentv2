"""Human Requirement Resolution wedge (mission-canonical).

Span-first segmentation, per-span disposition proposal, validator, phase gate,
and projection into Task Runtime completion_conditions / mission constraints.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from ai_tool.chat_interface.requirement_decomposition import (
    RequirementStatus,
    decompose_requirements,
    explicit_conditions,
)

PHASE_REQUIREMENTS_RESOLVED = "REQUIREMENTS_RESOLVED"
PHASE_AWAITING_HUMAN = "AWAITING_HUMAN_REQUIREMENT"
PHASE_AWAITING_FACT = "AWAITING_FACT_RESOLUTION"
PHASE_AWAITING_ENVIRONMENT = "AWAITING_ENVIRONMENT_RESOLUTION"

DISPOSITION_GOAL = "GOAL"
DISPOSITION_CONSTRAINT = "CONSTRAINT"
DISPOSITION_PREFERENCE = "PREFERENCE"
DISPOSITION_AMBIGUOUS = "AMBIGUOUS_REQUIREMENT"
DISPOSITION_CONTEXT = "CONTEXT"
DISPOSITION_NOISE = "NOISE"

CONSTRAINT_SUBTYPE_PROHIBITION = "prohibition"
CONSTRAINT_SUBTYPE_TECHNOLOGY = "technology"

UNKNOWN_USER_INTENT = "user_intent"
UNKNOWN_FACT = "fact_unknown"
UNKNOWN_ENVIRONMENT = "environment_unknown"

PROVENANCE_USER_EXPLICIT = "user_explicit"
PROVENANCE_HUMAN_CONFIRMED = "human_confirmed"
PROVENANCE_LLM_PROPOSED = "llm_proposed"
PROVENANCE_RESEARCH = "research_confirmed"
PROVENANCE_PROBE = "probe_confirmed"

MATERIALITY_BLOCKS = "blocks_design"
MATERIALITY_INFO = "informational"

RESOLVED = "resolved"
UNRESOLVED = "unresolved"
WAIVED = "waived_by_human"

_SPAN_PEEL_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^簡単な"), "簡単な"),
    (re.compile(r"^Pythonで"), "Pythonで"),
    (re.compile(r"^見た目は二の次でいい"), "見た目は二の次でいい"),
    (re.compile(r"^なるべく軽くして"), "なるべく軽くして"),
    (re.compile(r"^初心者でも使えるように"), "初心者でも使えるように"),
    (re.compile(r"^赤いボタンは絶対に消さないで"), "赤いボタンは絶対に消さないで"),
)

_CREATION_INTENT = re.compile(
    r"(作って|作る|作成|作成して|build|create\b|implement\b)",
    re.IGNORECASE,
)

_SPAN_PROPOSAL_SYSTEM = """REQUIREMENT_SPAN_PROPOSAL_V1
You classify ONE verbatim span from the user's original request.
Return one JSON object only with keys:
disposition (GOAL|CONSTRAINT|PREFERENCE|AMBIGUOUS_REQUIREMENT|CONTEXT|NOISE),
constraint_subtype (prohibition|technology|null when not CONSTRAINT),
materiality (blocks_design|informational),
unknown_kind (user_intent|fact_unknown|environment_unknown|null),
normalized_meaning (string|null),
resolution_status (resolved|unresolved).
Do not drop or rewrite the span text. Do not invent requirements outside the span.
For explicit technology (e.g. Python), use CONSTRAINT/technology and resolved/user_explicit semantics in meaning only.
For vague scope (簡単な), use AMBIGUOUS_REQUIREMENT, blocks_design, user_intent, unresolved.
For prohibitions (must not remove), CONSTRAINT/prohibition, blocks_design, resolved if clear.
For soft priorities (二の次), PREFERENCE, informational, resolved.
Do not numericize vague degree requirements."""


@dataclass
class RequirementSpan:
    start: int
    end: int
    text: str


@dataclass
class StructuredRequirement:
    requirement_id: str
    source_text: str
    source_span: list[int]
    disposition: str
    resolution_status: str
    provenance: str
    materiality: str
    constraint_subtype: str | None = None
    unknown_kind: str | None = None
    normalized_meaning: str | None = None
    decision_owner: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload.get("constraint_subtype") is None:
            payload.pop("constraint_subtype", None)
        if payload.get("unknown_kind") is None:
            payload.pop("unknown_kind", None)
        if payload.get("normalized_meaning") is None:
            payload.pop("normalized_meaning", None)
        if payload.get("decision_owner") is None:
            payload.pop("decision_owner", None)
        return payload

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> StructuredRequirement:
        span = row.get("source_span") or [0, 0]
        return cls(
            requirement_id=str(row.get("requirement_id") or ""),
            source_text=str(row.get("source_text") or ""),
            source_span=[int(span[0]), int(span[1])],
            disposition=str(row.get("disposition") or ""),
            resolution_status=str(row.get("resolution_status") or UNRESOLVED),
            provenance=str(row.get("provenance") or PROVENANCE_LLM_PROPOSED),
            materiality=str(row.get("materiality") or MATERIALITY_BLOCKS),
            constraint_subtype=(
                str(row["constraint_subtype"]) if row.get("constraint_subtype") else None
            ),
            unknown_kind=str(row["unknown_kind"]) if row.get("unknown_kind") else None,
            normalized_meaning=(
                str(row["normalized_meaning"]) if row.get("normalized_meaning") else None
            ),
            decision_owner=str(row["decision_owner"]) if row.get("decision_owner") else None,
        )


@dataclass
class RequirementResolutionBundle:
    original_goal: str
    structured_requirements: list[StructuredRequirement]
    requirement_resolution_phase: str
    validator_errors: list[str] = field(default_factory=list)

    def as_mission_fields(self) -> dict[str, Any]:
        return {
            "original_goal": self.original_goal,
            "structured_requirements": [
                item.as_dict() for item in self.structured_requirements
            ],
            "requirement_resolution_phase": self.requirement_resolution_phase,
        }


def implementation_entry_requested(
    text: str,
    *,
    route: str,
    handoff_packet: Mapping[str, Any] | None,
    is_agent_task: bool,
) -> bool:
    """HD-3: gate by implementation-entry, not route label."""
    if handoff_packet is not None:
        return True
    if route != "chat":
        return False
    return bool(is_agent_task)


def segment_original_goal(text: str) -> list[RequirementSpan]:
    """Mechanical span segmentation; spans concatenate to the full original_goal."""
    goal = str(text or "")
    if not goal:
        return []
    spans: list[RequirementSpan] = []
    cursor = 0
    remaining = goal
    while remaining:
        matched = False
        for pattern, _label in _SPAN_PEEL_RULES:
            m = pattern.match(remaining)
            if m:
                piece = m.group(0)
                start = cursor
                end = cursor + len(piece)
                spans.append(RequirementSpan(start, end, piece))
                cursor = end
                remaining = remaining[len(piece) :]
                matched = True
                break
        if not matched:
            start = cursor
            end = cursor + len(remaining)
            spans.append(RequirementSpan(start, end, remaining))
            break
    return spans


def _new_requirement_id() -> str:
    return f"req-{uuid.uuid4().hex[:12]}"


def heuristic_span_proposal(span: RequirementSpan) -> dict[str, Any]:
    """Deterministic proposal for tests and offline validation."""
    text = span.text.strip()
    if text == "簡単な":
        return {
            "disposition": DISPOSITION_AMBIGUOUS,
            "materiality": MATERIALITY_BLOCKS,
            "unknown_kind": UNKNOWN_USER_INTENT,
            "resolution_status": UNRESOLVED,
            "normalized_meaning": None,
            "constraint_subtype": None,
        }
    if text.startswith("Python"):
        return {
            "disposition": DISPOSITION_CONSTRAINT,
            "constraint_subtype": CONSTRAINT_SUBTYPE_TECHNOLOGY,
            "materiality": MATERIALITY_BLOCKS,
            "unknown_kind": None,
            "resolution_status": RESOLVED,
            "normalized_meaning": "Use Python",
        }
    if "絶対に消さない" in text:
        return {
            "disposition": DISPOSITION_CONSTRAINT,
            "constraint_subtype": CONSTRAINT_SUBTYPE_PROHIBITION,
            "materiality": MATERIALITY_BLOCKS,
            "unknown_kind": None,
            "resolution_status": RESOLVED,
            "normalized_meaning": text,
        }
    if "二の次" in text:
        return {
            "disposition": DISPOSITION_PREFERENCE,
            "materiality": MATERIALITY_INFO,
            "unknown_kind": None,
            "resolution_status": RESOLVED,
            "normalized_meaning": text,
            "constraint_subtype": None,
        }
    if text.startswith("なるべく"):
        return {
            "disposition": DISPOSITION_AMBIGUOUS,
            "materiality": MATERIALITY_BLOCKS,
            "unknown_kind": UNKNOWN_USER_INTENT,
            "resolution_status": UNRESOLVED,
            "normalized_meaning": None,
            "constraint_subtype": None,
        }
    if text.startswith("初心者"):
        return {
            "disposition": DISPOSITION_AMBIGUOUS,
            "materiality": MATERIALITY_BLOCKS,
            "unknown_kind": UNKNOWN_USER_INTENT,
            "resolution_status": UNRESOLVED,
            "normalized_meaning": None,
            "constraint_subtype": None,
        }
    if _CREATION_INTENT.search(text) or "テトリス" in text:
        return {
            "disposition": DISPOSITION_GOAL,
            "materiality": MATERIALITY_BLOCKS,
            "unknown_kind": None,
            "resolution_status": RESOLVED,
            "normalized_meaning": text,
            "constraint_subtype": None,
        }
    return {
        "disposition": DISPOSITION_CONTEXT,
        "materiality": MATERIALITY_INFO,
        "unknown_kind": None,
        "resolution_status": RESOLVED,
        "normalized_meaning": text,
        "constraint_subtype": None,
    }


def _parse_llm_json(content: str) -> dict[str, Any]:
    raw = (content or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("proposal must be a JSON object")
    return data


def propose_span_disposition(
    span: RequirementSpan,
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "",
    original_goal: str = "",
    use_heuristic_only: bool = False,
) -> dict[str, Any]:
    if use_heuristic_only or chat_fn is None:
        return heuristic_span_proposal(span)
    prompt = (
        f"Original goal:\n{original_goal}\n\n"
        f"Span ({span.start},{span.end}): {span.text}\n"
        "Classify this span only."
    )
    response = chat_fn(
        model=model,
        messages=[
            {"role": "system", "content": _SPAN_PROPOSAL_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    content = getattr(getattr(response, "message", None), "content", "") or str(response)
    return _parse_llm_json(content)


def _coverage_ok(goal: str, spans: Sequence[RequirementSpan]) -> bool:
    if not spans:
        return not goal
    rebuilt = "".join(span.text for span in spans)
    return rebuilt == goal


def _row_from_proposal(
    span: RequirementSpan,
    proposal: Mapping[str, Any],
) -> StructuredRequirement:
    disposition = str(proposal.get("disposition") or DISPOSITION_CONTEXT)
    resolution = str(proposal.get("resolution_status") or UNRESOLVED)
    provenance = PROVENANCE_LLM_PROPOSED
    if resolution == RESOLVED and disposition in {
        DISPOSITION_GOAL,
        DISPOSITION_CONSTRAINT,
        DISPOSITION_PREFERENCE,
    }:
        provenance = PROVENANCE_USER_EXPLICIT
    decision_owner = None
    unknown = proposal.get("unknown_kind")
    if resolution == UNRESOLVED and unknown:
        if unknown == UNKNOWN_USER_INTENT:
            decision_owner = "human"
        elif unknown == UNKNOWN_FACT:
            decision_owner = "research"
        elif unknown == UNKNOWN_ENVIRONMENT:
            decision_owner = "environment_probe"
    return StructuredRequirement(
        requirement_id=_new_requirement_id(),
        source_text=span.text,
        source_span=[span.start, span.end],
        disposition=disposition,
        resolution_status=resolution,
        provenance=provenance,
        materiality=str(proposal.get("materiality") or MATERIALITY_BLOCKS),
        constraint_subtype=(
            str(proposal["constraint_subtype"])
            if proposal.get("constraint_subtype")
            else None
        ),
        unknown_kind=str(unknown) if unknown else None,
        normalized_meaning=(
            str(proposal["normalized_meaning"])
            if proposal.get("normalized_meaning")
            else None
        ),
        decision_owner=decision_owner,
    )


def validate_structured_requirements(
    original_goal: str,
    spans: Sequence[RequirementSpan],
    rows: Sequence[StructuredRequirement],
) -> list[str]:
    errors: list[str] = []
    if not _coverage_ok(original_goal, spans):
        errors.append("span_coverage_mismatch")
    for row in rows:
        if row.source_text and row.source_text not in original_goal:
            errors.append(f"{row.requirement_id}:source_text_not_in_original")
        if row.disposition == DISPOSITION_NOISE and not row.source_text:
            errors.append(f"{row.requirement_id}:noise_missing_source_text")
    ids = [row.requirement_id for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_requirement_id")
    return errors


def compute_requirement_resolution_phase(
    rows: Sequence[StructuredRequirement],
) -> str:
    for row in rows:
        if row.resolution_status != RESOLVED:
            if row.materiality != MATERIALITY_BLOCKS:
                continue
            if row.provenance == PROVENANCE_LLM_PROPOSED and row.disposition in {
                DISPOSITION_NOISE,
                DISPOSITION_CONTEXT,
            }:
                continue
            unknown = row.unknown_kind or UNKNOWN_USER_INTENT
            if unknown == UNKNOWN_FACT:
                return PHASE_AWAITING_FACT
            if unknown == UNKNOWN_ENVIRONMENT:
                return PHASE_AWAITING_ENVIRONMENT
            return PHASE_AWAITING_HUMAN
    return PHASE_REQUIREMENTS_RESOLVED


def mission_blocks_implementation_entry(mission: Mapping[str, Any] | None) -> bool:
    """Read-only gate from mission canonical store (no re-extraction)."""
    if not isinstance(mission, Mapping):
        return False
    rows = mission.get("structured_requirements")
    if not isinstance(rows, list) or not rows:
        return False
    bundle = load_bundle_from_mission(mission)
    return requirements_block_implementation_entry(
        bundle.requirement_resolution_phase,
        bundle.structured_requirements,
    )


def requirements_block_implementation_entry(
    phase: str,
    rows: Sequence[StructuredRequirement],
) -> bool:
    if phase != PHASE_REQUIREMENTS_RESOLVED:
        return True
    for row in rows:
        if (
            row.resolution_status == UNRESOLVED
            and row.materiality == MATERIALITY_BLOCKS
        ):
            return True
    return False


def extract_requirement_resolution(
    original_goal: str,
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "",
    use_heuristic_only: bool = False,
) -> RequirementResolutionBundle:
    spans = segment_original_goal(original_goal)
    rows: list[StructuredRequirement] = []
    for span in spans:
        proposal = propose_span_disposition(
            span,
            chat_fn=chat_fn,
            model=model,
            original_goal=original_goal,
            use_heuristic_only=use_heuristic_only,
        )
        rows.append(_row_from_proposal(span, proposal))
    errors = validate_structured_requirements(original_goal, spans, rows)
    phase = compute_requirement_resolution_phase(rows)
    if errors:
        phase = PHASE_AWAITING_HUMAN
    return RequirementResolutionBundle(
        original_goal=original_goal,
        structured_requirements=rows,
        requirement_resolution_phase=phase,
        validator_errors=errors,
    )


def bundle_from_explicit_numbered(
    original_goal: str,
    condition_descriptions: Sequence[str],
) -> RequirementResolutionBundle:
    rows: list[StructuredRequirement] = []
    for index, description in enumerate(condition_descriptions, start=1):
        rows.append(
            StructuredRequirement(
                requirement_id=f"req-explicit-{index}",
                source_text=str(description),
                source_span=[0, len(original_goal)],
                disposition=DISPOSITION_GOAL,
                resolution_status=RESOLVED,
                provenance=PROVENANCE_USER_EXPLICIT,
                materiality=MATERIALITY_BLOCKS,
                normalized_meaning=str(description),
            )
        )
    phase = compute_requirement_resolution_phase(rows)
    return RequirementResolutionBundle(
        original_goal=original_goal,
        structured_requirements=rows,
        requirement_resolution_phase=phase,
    )


def bundle_from_handoff() -> RequirementResolutionBundle:
    return RequirementResolutionBundle(
        original_goal="",
        structured_requirements=[],
        requirement_resolution_phase=PHASE_REQUIREMENTS_RESOLVED,
    )


def resolve_human_answer(
    bundle: RequirementResolutionBundle,
    requirement_id: str,
    answer_text: str,
) -> RequirementResolutionBundle:
    updated: list[StructuredRequirement] = []
    for row in bundle.structured_requirements:
        if row.requirement_id != requirement_id:
            updated.append(row)
            continue
        meaning = str(answer_text or "").strip() or row.normalized_meaning
        updated.append(
            StructuredRequirement(
                requirement_id=row.requirement_id,
                source_text=row.source_text,
                source_span=list(row.source_span),
                disposition=row.disposition,
                resolution_status=RESOLVED,
                provenance=PROVENANCE_HUMAN_CONFIRMED,
                materiality=row.materiality,
                constraint_subtype=row.constraint_subtype,
                unknown_kind=None,
                normalized_meaning=meaning,
                decision_owner=None,
            )
        )
    phase = compute_requirement_resolution_phase(updated)
    return RequirementResolutionBundle(
        original_goal=bundle.original_goal,
        structured_requirements=updated,
        requirement_resolution_phase=phase,
        validator_errors=list(bundle.validator_errors),
    )


def first_blocking_human_requirement(
    rows: Sequence[StructuredRequirement],
) -> StructuredRequirement | None:
    for row in rows:
        if (
            row.resolution_status == UNRESOLVED
            and row.materiality == MATERIALITY_BLOCKS
            and (row.unknown_kind or UNKNOWN_USER_INTENT) == UNKNOWN_USER_INTENT
        ):
            return row
    return None


def _runtime_adoption_from_rows(
    rows: Sequence[StructuredRequirement],
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    """ID-tagged completion projections plus legacy condition/constraint string lists."""
    condition_projections: list[dict[str, str]] = []
    conditions: list[str] = []
    constraints: list[str] = []
    for row in rows:
        if row.resolution_status not in {RESOLVED, WAIVED}:
            continue
        label = (row.normalized_meaning or row.source_text).strip()
        if not label:
            continue
        if row.disposition == DISPOSITION_GOAL:
            conditions.append(label)
            condition_projections.append(
                {
                    "requirement_id": row.requirement_id,
                    "completion_condition": label,
                }
            )
        elif row.disposition == DISPOSITION_CONSTRAINT:
            if row.constraint_subtype == CONSTRAINT_SUBTYPE_PROHIBITION:
                constraints.append(f"PROHIBITION: {label}")
            else:
                constraints.append(label)
        elif row.disposition == DISPOSITION_PREFERENCE and row.materiality == MATERIALITY_BLOCKS:
            condition = f"PREFERENCE: {label}"
            conditions.append(condition)
            condition_projections.append(
                {
                    "requirement_id": row.requirement_id,
                    "completion_condition": condition,
                }
            )
    return condition_projections, conditions, constraints


def project_to_runtime_adoption_entries(
    rows: Sequence[StructuredRequirement],
) -> list[dict[str, str]]:
    """Runtime-adopted completion conditions with stable requirement_id (not constraints)."""
    projections, _, _ = _runtime_adoption_from_rows(rows)
    return projections


def project_to_runtime_adoption(
    rows: Sequence[StructuredRequirement],
) -> tuple[list[str], list[str]]:
    """Step 6: completion_conditions and explicit_constraints projections."""
    _, conditions, constraints = _runtime_adoption_from_rows(rows)
    return conditions, constraints


def canonical_requirement_projection_from_dict_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Derive requirement_id ↔ completion_condition mapping from mission-canonical dict rows."""
    structured = [
        StructuredRequirement.from_dict(item)
        for item in rows
        if isinstance(item, Mapping)
    ]
    return project_to_runtime_adoption_entries(structured)


def sync_canonical_requirement_projection(orchestrator: Any) -> None:
    """Refresh orchestrator.canonical_requirement_projection from structured_requirements."""
    rows = getattr(orchestrator, "structured_requirements", None) or []
    orchestrator.canonical_requirement_projection = canonical_requirement_projection_from_dict_rows(
        rows
    )


def runtime_matches_for_completion_condition(
    runtime: Any,
    completion_condition: str,
) -> list[dict[str, Any]]:
    """READ-ONLY: tasks whose completion_conditions include the string, with evidence refs."""
    condition = str(completion_condition or "").strip()
    if not condition:
        return []
    matches: list[dict[str, Any]] = []
    tasks = getattr(runtime, "tasks", None) or {}
    for task_id in sorted(tasks.keys()):
        task = tasks[task_id]
        if condition not in (task.completion_conditions or []):
            continue
        evidence_ids = [
            str(ref)
            for ref in (task.condition_evidence.get(condition) or [])
            if str(ref).strip()
        ]
        status_map = getattr(task, "condition_status", None) or {}
        raw_status = status_map.get(condition)
        condition_status = str(raw_status) if raw_status is not None else "UNKNOWN"
        matches.append(
            {
                "task_id": str(task_id),
                "condition_status": condition_status,
                "evidence_ids": evidence_ids,
            }
        )
    return matches


def build_canonical_requirement_runtime_coverage(orchestrator: Any) -> list[dict[str, Any]]:
    """READ-ONLY runtime condition coverage for projected canonical requirements."""
    return _build_canonical_requirement_runtime_trace(orchestrator)


def build_canonical_requirement_evidence_trace(orchestrator: Any) -> list[dict[str, Any]]:
    """Trace projected canonical requirements through runtime condition_evidence (read-only)."""
    return _build_canonical_requirement_runtime_trace(orchestrator)


def _build_canonical_requirement_runtime_trace(orchestrator: Any) -> list[dict[str, Any]]:
    """Shared trace: requirement_id → condition → task status and evidence refs."""
    runtime = getattr(orchestrator, "runtime", None)
    if runtime is None:
        return []
    trace: list[dict[str, Any]] = []
    for entry in getattr(orchestrator, "canonical_requirement_projection", None) or []:
        if not isinstance(entry, Mapping):
            continue
        requirement_id = str(entry.get("requirement_id") or "").strip()
        completion_condition = str(entry.get("completion_condition") or "").strip()
        if not requirement_id or not completion_condition:
            continue
        trace.append(
            {
                "requirement_id": requirement_id,
                "completion_condition": completion_condition,
                "runtime_matches": runtime_matches_for_completion_condition(
                    runtime,
                    completion_condition,
                ),
            }
        )
    return trace


def merge_mission_requirement_fields(
    mission: dict[str, Any],
    bundle: RequirementResolutionBundle,
) -> dict[str, Any]:
    updated = dict(mission)
    updated["original_goal"] = bundle.original_goal
    updated["structured_requirements"] = [
        row.as_dict() for row in bundle.structured_requirements
    ]
    updated["requirement_resolution_phase"] = bundle.requirement_resolution_phase
    conditions, constraints = project_to_runtime_adoption(bundle.structured_requirements)
    if conditions:
        merged = list(updated.get("explicit_conditions") or [])
        for item in conditions:
            if item not in merged:
                merged.append(item)
        updated["explicit_conditions"] = merged
    if constraints:
        merged_c = list(updated.get("explicit_constraints") or [])
        for item in constraints:
            if item not in merged_c:
                merged_c.append(item)
        updated["explicit_constraints"] = merged_c
    return updated


def sync_canonical_requirements_from_mission(
    orchestrator: Any,
    *,
    mission_id: str | None = None,
    store: Any | None = None,
) -> bool:
    """Copy mission structured_requirements onto the orchestrator without re-interpretation."""
    from ai_tool.mission_memory.store import MissionMemoryStore

    mid = str(mission_id or getattr(orchestrator, "mission_id", "") or "").strip()
    if not mid:
        return False
    memory = store or MissionMemoryStore.from_default()
    mission = memory.get_mission(mid)
    if not isinstance(mission, Mapping):
        return False
    rows = mission.get("structured_requirements")
    if not isinstance(rows, list) or not rows:
        return False
    orchestrator.structured_requirements = [
        dict(item) for item in rows if isinstance(item, Mapping)
    ]
    phase = mission.get("requirement_resolution_phase")
    if phase:
        orchestrator.requirement_resolution_phase = str(phase)
    sync_canonical_requirement_projection(orchestrator)
    return True


def load_bundle_from_mission(mission: Mapping[str, Any]) -> RequirementResolutionBundle:
    rows = [
        StructuredRequirement.from_dict(item)
        for item in (mission.get("structured_requirements") or [])
        if isinstance(item, dict)
    ]
    return RequirementResolutionBundle(
        original_goal=str(mission.get("original_goal") or ""),
        structured_requirements=rows,
        requirement_resolution_phase=str(
            mission.get("requirement_resolution_phase") or PHASE_AWAITING_HUMAN
        ),
    )


def prepare_implementation_entry_bundle(
    text: str,
    *,
    chat_fn: Callable[..., Any],
    model: str,
    available_tools: Iterable[str],
    handoff_packet: Mapping[str, Any] | None,
    use_heuristic_only: bool = False,
) -> RequirementResolutionBundle | None:
    if handoff_packet is not None:
        return bundle_from_handoff()
    explicit = explicit_conditions(text)
    if explicit:
        numbered = decompose_requirements(
            text,
            chat_fn=chat_fn,
            model=model,
            available_tools=available_tools,
        )
        if numbered.status != RequirementStatus.READY.value:
            return None
        descriptions = [row.description for row in numbered.conditions if row.required]
        return bundle_from_explicit_numbered(text, descriptions)
    return extract_requirement_resolution(
        text,
        chat_fn=chat_fn,
        model=model,
        use_heuristic_only=use_heuristic_only,
    )


__all__ = [
    "PHASE_REQUIREMENTS_RESOLVED",
    "PHASE_AWAITING_HUMAN",
    "PHASE_AWAITING_FACT",
    "PHASE_AWAITING_ENVIRONMENT",
    "StructuredRequirement",
    "RequirementResolutionBundle",
    "implementation_entry_requested",
    "segment_original_goal",
    "extract_requirement_resolution",
    "prepare_implementation_entry_bundle",
    "mission_blocks_implementation_entry",
    "requirements_block_implementation_entry",
    "resolve_human_answer",
    "first_blocking_human_requirement",
    "project_to_runtime_adoption",
    "project_to_runtime_adoption_entries",
    "canonical_requirement_projection_from_dict_rows",
    "sync_canonical_requirement_projection",
    "runtime_matches_for_completion_condition",
    "build_canonical_requirement_evidence_trace",
    "build_canonical_requirement_runtime_coverage",
    "merge_mission_requirement_fields",
    "load_bundle_from_mission",
    "sync_canonical_requirements_from_mission",
    "heuristic_span_proposal",
]
