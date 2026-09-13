"""Normalized grill question contract for Chat UI and E2E harnesses.

Shared across Initial Grill, future Boundary Grill, and Goal-meaning grills.
Not used for Human Approval / confirmed tool-gap approval flows.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

CONTRACT_VERSION = "0.1"

ANSWER_TYPE_SINGLE_CHOICE = "single_choice"
ANSWER_TYPE_FREEFORM_WITH_RECOMMENDATION = "freeform_with_recommendation"

GRILL_REASON_INITIAL = "initial_grill"
GRILL_REASON_BOUNDARY = "boundary_grill"
GRILL_REASON_GOAL_GAP = "goal_gap_grill"
GRILL_REASON_GOAL_COMPLETION_HUMAN = "goal_completion_human"
GRILL_REASON_DECISION_CHANGE = "decision_change_confirmation"
GRILL_REASON_REQUIREMENT_RESOLUTION = "requirement_resolution"

SELECTION_POLICY_TEST_AUTO = "test_auto_recommendation"
SELECTION_POLICY_HUMAN_UI = "human_ui"

RESPONSE_KIND_SIMULATED_HUMAN = "simulated_human"
RESPONSE_KIND_HUMAN_UI = "human_ui"

DEFAULT_RECOMMENDED_OPTION_ID = "opt_recommended"

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "registry" / "schema" / "grill_question_contract.schema.json"

FORBIDDEN_GRILL_REASONS = frozenset(
    {
        "human_approval",
        "approval_required",
        "confirmed_tool_gap",
        "tool_gap_approval",
    }
)
FORBIDDEN_CONTRACT_KEYS = frozenset(
    {
        "human_approval",
        "requires_human_approval",
        "confirmed_tool_gap",
        "approval_required",
        "missing_capability",
        "suggested_minimal_tool",
    }
)


@dataclass(frozen=True)
class GrillQuestionOption:
    id: str
    label: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label}


@dataclass
class GrillQuestionContract:
    contract_version: str = CONTRACT_VERSION
    question_id: str = ""
    question: str = ""
    answer_type: str = ANSWER_TYPE_SINGLE_CHOICE
    options: list[GrillQuestionOption] = field(default_factory=list)
    recommended_option_id: str = ""
    recommendation_reason: str = ""
    grill_reason: str = ""
    dimension: str | None = None
    decision_key: str | None = None
    decision_subject: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["options"] = [item.as_dict() for item in self.options]
        return payload

    def option_by_id(self, option_id: str) -> GrillQuestionOption | None:
        for item in self.options:
            if item.id == option_id:
                return item
        return None

    def has_recommended_option(self) -> bool:
        return bool(self.recommended_option_id) and self.option_by_id(
            self.recommended_option_id
        ) is not None

    def recommended_option(self) -> GrillQuestionOption | None:
        if not self.recommended_option_id:
            return None
        return self.option_by_id(self.recommended_option_id)


@dataclass
class GrillSelectionResult:
    question_id: str
    selected_option_id: str | None
    selected_label: str | None
    selection_policy: str
    human_response_kind: str
    auto_selected: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _semantic_contract_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in FORBIDDEN_CONTRACT_KEYS:
        if key in payload:
            errors.append(f"forbidden human_approval field present: {key}")
    grill_reason = str(payload.get("grill_reason") or "")
    if grill_reason in FORBIDDEN_GRILL_REASONS:
        errors.append(f"grill_reason must not be human approval: {grill_reason}")
    options = payload.get("options") or []
    option_ids = [str(item.get("id") or "") for item in options if isinstance(item, Mapping)]
    if len(option_ids) != len(set(option_ids)):
        errors.append("options.id must be unique")
    recommended_option_id = str(payload.get("recommended_option_id") or "")
    if recommended_option_id and recommended_option_id not in set(option_ids):
        errors.append("recommended_option_id must reference an options.id")
    return errors


def _semantic_selection_errors(
    contract: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if str(contract.get("question_id") or "") != str(selection.get("question_id") or ""):
        errors.append("selection.question_id must match contract.question_id")
    policy = str(selection.get("selection_policy") or "")
    auto_selected = bool(selection.get("auto_selected"))
    selected_option_id = selection.get("selected_option_id")
    recommended_option_id = str(contract.get("recommended_option_id") or "")
    option_ids = {
        str(item.get("id") or "")
        for item in (contract.get("options") or [])
        if isinstance(item, Mapping)
    }
    has_recommended = bool(
        recommended_option_id and recommended_option_id in option_ids
    )
    if policy == SELECTION_POLICY_HUMAN_UI:
        if auto_selected:
            errors.append("human_ui must not auto_select")
        if selected_option_id is not None:
            errors.append("human_ui must leave selected_option_id null")
    if policy == SELECTION_POLICY_TEST_AUTO:
        if not has_recommended:
            errors.append(
                "test_auto_recommendation requires a valid recommended_option_id"
            )
        elif not auto_selected or selected_option_id != recommended_option_id:
            errors.append(
                "test_auto_recommendation must auto_select the recommended_option_id"
            )
    return errors


def validate_grill_question_contract_dict(payload: Mapping[str, Any]) -> list[str]:
    """Validate contract JSON against schema and semantic grill rules."""
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(error.message for error in validator.iter_errors(dict(payload)))
    errors.extend(_semantic_contract_errors(payload))
    return errors


def validate_grill_selection_result_dict(
    contract: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> list[str]:
    """Validate selection result against schema and policy semantics."""
    schema = _load_schema()
    selection_schema = {
        **schema,
        "required": list(schema["$defs"]["selection_result"]["required"]),
        "properties": schema["$defs"]["selection_result"]["properties"],
        "additionalProperties": False,
    }
    validator = Draft202012Validator(selection_schema)
    errors = sorted(error.message for error in validator.iter_errors(dict(selection)))
    errors.extend(_semantic_selection_errors(contract, selection))
    return errors


def validate_grill_question_contract(contract: GrillQuestionContract) -> list[str]:
    return validate_grill_question_contract_dict(contract.as_dict())


def validate_grill_selection_result(
    contract: GrillQuestionContract,
    selection: GrillSelectionResult,
) -> list[str]:
    return validate_grill_selection_result_dict(contract.as_dict(), selection.as_dict())


def _coerce_options(raw_options: Any, recommended_answer: str) -> list[GrillQuestionOption]:
    options: list[GrillQuestionOption] = []
    if isinstance(raw_options, list):
        for index, item in enumerate(raw_options):
            if not isinstance(item, Mapping):
                continue
            option_id = str(item.get("id") or f"opt_{index + 1}").strip()
            label = str(item.get("label") or item.get("text") or "").strip()
            if option_id and label:
                options.append(GrillQuestionOption(id=option_id, label=label))
    if options:
        return options
    answer = str(recommended_answer or "").strip()
    if not answer:
        return []
    return [GrillQuestionOption(id=DEFAULT_RECOMMENDED_OPTION_ID, label=answer)]


def normalize_grill_question_payload(
    payload: Mapping[str, Any],
    *,
    question_id: str,
    grill_reason: str,
    dimension: str | None = None,
) -> GrillQuestionContract:
    """Normalize LLM or adapter payload into the shared grill question contract."""
    question = str(payload.get("question") or "").strip()
    recommended_answer = str(payload.get("recommended_answer") or "").strip()
    options = _coerce_options(payload.get("options"), recommended_answer)
    if not question:
        raise ValueError("question is required")
    if not options:
        raise ValueError("options or recommended_answer is required")

    recommended_option_id = str(
        payload.get("recommended_option_id")
        or payload.get("recommended_id")
        or DEFAULT_RECOMMENDED_OPTION_ID
    ).strip()
    if recommended_option_id not in {item.id for item in options}:
        recommended_option_id = options[0].id

    recommendation_reason = str(
        payload.get("recommendation_reason")
        or payload.get("rationale")
        or payload.get("recommended_reason")
        or ""
    ).strip()

    answer_type = str(payload.get("answer_type") or "").strip()
    if not answer_type:
        answer_type = (
            ANSWER_TYPE_SINGLE_CHOICE
            if len(options) > 1
            else ANSWER_TYPE_FREEFORM_WITH_RECOMMENDATION
        )

    contract = GrillQuestionContract(
        question_id=question_id,
        question=question,
        answer_type=answer_type,
        options=options,
        recommended_option_id=recommended_option_id,
        recommendation_reason=recommendation_reason,
        grill_reason=grill_reason,
        dimension=str(dimension or payload.get("dimension") or "").strip() or None,
    )
    errors = validate_grill_question_contract(contract)
    if errors:
        raise ValueError("; ".join(errors))
    return contract


def normalize_goal_completion_human_packet(
    packet: Mapping[str, Any],
    *,
    question_id: str,
) -> GrillQuestionContract:
    """Map Goal Completion Human v0 packet into the same UI contract."""
    options = [
        GrillQuestionOption(
            id=str(item.get("id") or ""),
            label=str(item.get("label") or ""),
        )
        for item in (packet.get("goal_meaning_options") or [])
        if isinstance(item, Mapping)
        if str(item.get("id") or "").strip() and str(item.get("label") or "").strip()
    ]
    recommended = dict(packet.get("recommended") or {})
    recommended_option_id = str(recommended.get("id") or "").strip()
    if recommended_option_id and recommended_option_id not in {item.id for item in options}:
        recommended_option_id = ""
    contract = GrillQuestionContract(
        question_id=question_id,
        question=str(packet.get("question") or "").strip(),
        answer_type=ANSWER_TYPE_SINGLE_CHOICE if len(options) > 1 else ANSWER_TYPE_FREEFORM_WITH_RECOMMENDATION,
        options=options,
        recommended_option_id=recommended_option_id,
        recommendation_reason=str(recommended.get("text") or "").strip(),
        grill_reason=GRILL_REASON_GOAL_COMPLETION_HUMAN,
    )
    errors = validate_grill_question_contract(contract)
    if errors:
        raise ValueError("; ".join(errors))
    return contract


def apply_selection_policy(
    contract: GrillQuestionContract,
    selection_policy: str,
) -> GrillSelectionResult:
    """Resolve selection for harness vs future Human UI on the same contract."""
    if selection_policy in {SELECTION_POLICY_TEST_AUTO, "recommended"}:
        if not contract.has_recommended_option():
            raise ValueError(
                f"recommended option missing for question_id={contract.question_id}"
            )
        option = contract.recommended_option()
        if option is None:
            raise ValueError(
                f"recommended option missing for question_id={contract.question_id}"
            )
        selection = GrillSelectionResult(
            question_id=contract.question_id,
            selected_option_id=option.id,
            selected_label=option.label,
            selection_policy=SELECTION_POLICY_TEST_AUTO,
            human_response_kind=RESPONSE_KIND_SIMULATED_HUMAN,
            auto_selected=True,
        )
    elif selection_policy == SELECTION_POLICY_HUMAN_UI:
        selection = GrillSelectionResult(
            question_id=contract.question_id,
            selected_option_id=None,
            selected_label=None,
            selection_policy=SELECTION_POLICY_HUMAN_UI,
            human_response_kind=RESPONSE_KIND_HUMAN_UI,
            auto_selected=False,
        )
    else:
        raise ValueError(f"unsupported selection_policy: {selection_policy}")
    errors = validate_grill_selection_result(contract, selection)
    if errors:
        raise ValueError("; ".join(errors))
    return selection
