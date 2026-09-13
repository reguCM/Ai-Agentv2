"""Grill bridge for Human Requirement Resolution wedge."""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.chat_interface.requirement_resolution import (
    RequirementResolutionBundle,
    StructuredRequirement,
    UNKNOWN_USER_INTENT,
    first_blocking_human_requirement,
    load_bundle_from_mission,
    merge_mission_requirement_fields,
    resolve_human_answer,
)
from ai_tool.grill_question_contract import (
    ANSWER_TYPE_FREEFORM_WITH_RECOMMENDATION,
    GRILL_REASON_REQUIREMENT_RESOLUTION,
    GrillQuestionContract,
    GrillQuestionOption,
    SELECTION_POLICY_HUMAN_UI,
    validate_grill_question_contract,
)

SOURCE_REQUIREMENT_RESOLUTION = "requirement_resolution"


def build_requirement_resolution_contract(
    row: StructuredRequirement,
    *,
    original_goal: str,
) -> GrillQuestionContract:
    question = (
        f"依頼の「{row.source_text}」について、実装の前提を確定してください。\n"
        f"原文: {original_goal}"
    )
    contract = GrillQuestionContract(
        question_id=f"req-res-{row.requirement_id}",
        question=question,
        answer_type=ANSWER_TYPE_FREEFORM_WITH_RECOMMENDATION,
        options=[
            GrillQuestionOption(
                id="opt_freeform",
                label="回答をテキストで入力してください",
            )
        ],
        recommended_option_id="opt_freeform",
        recommendation_reason="Human intent clarification",
        grill_reason=GRILL_REASON_REQUIREMENT_RESOLUTION,
        dimension="requirements",
        decision_key=f"requirement:{row.requirement_id}",
        decision_subject=row.source_text,
    )
    errors = validate_grill_question_contract(contract)
    if errors:
        raise ValueError("; ".join(errors))
    return contract


def format_requirement_resolution_grill(contract: GrillQuestionContract) -> str:
    return contract.question


def launch_requirement_resolution_grill(
    *,
    mission_id: str,
    original_request: str,
    bundle: RequirementResolutionBundle,
) -> dict[str, Any] | None:
    row = first_blocking_human_requirement(bundle.structured_requirements)
    if row is None:
        return None
    contract = build_requirement_resolution_contract(
        row, original_goal=original_request
    )
    state = {
        "mission_id": mission_id,
        "original_request": original_request,
        "active_contract": contract.as_dict(),
        "pending_requirement_id": row.requirement_id,
        "structured_requirements": [
            item.as_dict() for item in bundle.structured_requirements
        ],
        "requirement_resolution_phase": bundle.requirement_resolution_phase,
    }
    return {
        "record": contract.as_dict(),
        "state": state,
        "formatted": format_requirement_resolution_grill(contract),
        "pending_requirement_id": row.requirement_id,
    }


def apply_requirement_resolution_grill_answer(
    mission: Mapping[str, Any],
    state: Mapping[str, Any],
    user_text: str,
) -> tuple[dict[str, Any], RequirementResolutionBundle]:
    bundle = load_bundle_from_mission(mission)
    if not bundle.structured_requirements and state.get("structured_requirements"):
        bundle = RequirementResolutionBundle(
            original_goal=str(state.get("original_request") or mission.get("original_goal") or ""),
            structured_requirements=[
                StructuredRequirement.from_dict(item)
                for item in state.get("structured_requirements") or []
                if isinstance(item, dict)
            ],
            requirement_resolution_phase=str(
                state.get("requirement_resolution_phase") or bundle.requirement_resolution_phase
            ),
        )
    pending_id = str(state.get("pending_requirement_id") or "")
    if not pending_id:
        row = first_blocking_human_requirement(bundle.structured_requirements)
        pending_id = row.requirement_id if row else ""
    updated_bundle = resolve_human_answer(bundle, pending_id, user_text)
    mission_dict = merge_mission_requirement_fields(dict(mission), updated_bundle)
    supplement = {
        "text": str(user_text or "").strip(),
        "source": SOURCE_REQUIREMENT_RESOLUTION,
        "decision_key": f"requirement:{pending_id}",
        "dimension": "requirements",
    }
    supplements = list(mission_dict.get("user_confirmed_supplements") or [])
    supplements.append(supplement)
    mission_dict["user_confirmed_supplements"] = supplements
    return mission_dict, updated_bundle


__all__ = [
    "SOURCE_REQUIREMENT_RESOLUTION",
    "launch_requirement_resolution_grill",
    "apply_requirement_resolution_grill_answer",
    "build_requirement_resolution_contract",
]
