"""Decision Change Confirmation Gate (Phase 1: Boundary Grill).

Confirms with Human before a new answer supersedes an active confirmed Decision
for the same decision_key. Not a Grill Engine — reuses GrillQuestionContract
for Human UI only.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Literal, Mapping

from ai_tool.grill_question_contract import (
    GRILL_REASON_DECISION_CHANGE,
    SELECTION_POLICY_HUMAN_UI,
    GrillQuestionContract,
    GrillQuestionOption,
    validate_grill_question_contract,
)

ConflictClass = Literal[
    "no_prior",
    "duplicate",
    "additional_info",
    "concretization",
    "compatible",
    "replacement",
]

DECISION_STATUS_CONFIRMED = "confirmed"
DECISION_STATUS_SUPERSEDED = "superseded"

OPTION_CONFIRM_CHANGE = "confirm_change"
OPTION_KEEP_PRIOR = "keep_prior"
OPTION_DEFER_CHANGE = "defer_change"

_BOUNDARY_DECISION_KEY_BY_DIMENSION: dict[str, str] = {
    "acceptance": "acceptance:output_format",
    "behavior": "scope:gui",
}

_CONCRETIZATION_MARKERS = re.compile(r"(先頭\d+行|1行|一行|原文|引用)", re.I)


def new_decision_id() -> str:
    return "d" + uuid.uuid4().hex


def ensure_decision_id(record: Mapping[str, Any]) -> str:
    existing = str(record.get("decision_id") or "").strip()
    if existing:
        return existing
    return new_decision_id()


def decision_status(record: Mapping[str, Any] | None) -> str:
    if not isinstance(record, Mapping):
        return DECISION_STATUS_CONFIRMED
    status = str(record.get("status") or DECISION_STATUS_CONFIRMED).strip()
    return status or DECISION_STATUS_CONFIRMED


def is_active_confirmed(record: Mapping[str, Any] | None) -> bool:
    return isinstance(record, Mapping) and decision_status(record) == DECISION_STATUS_CONFIRMED


def decision_key_for_contract(contract: Mapping[str, Any]) -> str:
    explicit = str(contract.get("decision_key") or "").strip()
    if explicit:
        return explicit
    dimension = str(contract.get("dimension") or "acceptance").strip() or "acceptance"
    return _BOUNDARY_DECISION_KEY_BY_DIMENSION.get(dimension, f"{dimension}:general")


def decision_subject_for_key(decision_key: str) -> str:
    subjects = {
        "acceptance:output_format": "成果物の報告形式（Acceptance / Output Format）",
        "acceptance:line_count": "報告する行数（Acceptance / Line Count）",
        "behavior:focus_loss": "フォーカス喪失時の挙動（Behavior / Focus Loss）",
    }
    return subjects.get(decision_key, decision_key.replace(":", " / "))


def resolve_boundary_answer(
    answer: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize a Boundary Grill answer into a proposed Decision payload."""
    text = str(answer or "").strip()
    dimension = str(contract.get("dimension") or "acceptance")
    decision_key = decision_key_for_contract(contract)
    selected_label = text
    option_id = ""
    for row in contract.get("options") or []:
        if not isinstance(row, Mapping):
            continue
        row_id = str(row.get("id") or "")
        row_label = str(row.get("label") or "")
        if text in {row_id, row_label}:
            option_id = row_id
            selected_label = row_label or text
            break
    return {
        "source": "boundary_grill",
        "dimension": dimension,
        "decision_key": decision_key,
        "decision_subject": decision_subject_for_key(decision_key),
        "option_id": option_id,
        "text": selected_label,
        "question_id": str(contract.get("question_id") or ""),
        "human_confirmed": True,
        "auto_selected": False,
        "selection_policy": SELECTION_POLICY_HUMAN_UI,
        "status": DECISION_STATUS_CONFIRMED,
    }


def active_decision_for_key(
    clarifications: list[dict[str, Any]] | None,
    decision_key: str,
) -> dict[str, Any] | None:
    if not decision_key:
        return None
    active: dict[str, Any] | None = None
    for row in clarifications or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("decision_key") or "") != decision_key:
            continue
        if not is_active_confirmed(row):
            continue
        active = dict(row)
    return active


def _normalize_label(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").casefold())


def classify_answer_vs_prior(
    prior: Mapping[str, Any] | None,
    proposed: Mapping[str, Any],
) -> ConflictClass:
    if not is_active_confirmed(prior):
        return "no_prior"
    prior_key = str(prior.get("decision_key") or "")
    proposed_key = str(proposed.get("decision_key") or "")
    if prior_key != proposed_key:
        return "additional_info"
    prior_option = str(prior.get("option_id") or "").strip()
    proposed_option = str(proposed.get("option_id") or "").strip()
    if prior_option and proposed_option and prior_option == proposed_option:
        return "duplicate"
    prior_text = _normalize_label(str(prior.get("text") or ""))
    proposed_text = _normalize_label(str(proposed.get("text") or ""))
    if prior_text and proposed_text and prior_text == proposed_text:
        return "duplicate"
    if prior_option and proposed_option and prior_option != proposed_option:
        return "replacement"
    if prior_text and proposed_text:
        if proposed_text in prior_text or prior_text in proposed_text:
            return "concretization"
        if _CONCRETIZATION_MARKERS.search(str(proposed.get("text") or "")) and (
            _CONCRETIZATION_MARKERS.search(str(prior.get("text") or ""))
            or "引用" in str(prior.get("text") or "")
            or "原文" in str(prior.get("text") or "")
        ):
            if proposed_option == prior_option or not proposed_option or not prior_option:
                return "concretization"
    if prior_text and proposed_text and prior_text != proposed_text:
        return "replacement"
    return "compatible"


def needs_decision_change_confirmation(conflict_class: ConflictClass) -> bool:
    return conflict_class == "replacement"


def prepare_boundary_grill_answer(
    orchestrator: Any,
    answer: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    proposed = resolve_boundary_answer(answer, contract)
    clarifications = list(getattr(orchestrator, "confirmed_clarifications", None) or [])
    prior = active_decision_for_key(clarifications, proposed["decision_key"])
    conflict_class = classify_answer_vs_prior(prior, proposed)
    return {
        "proposed": proposed,
        "prior": dict(prior) if prior else None,
        "prior_decision_id": str((prior or {}).get("decision_id") or ""),
        "conflict_class": conflict_class,
        "needs_confirmation": needs_decision_change_confirmation(conflict_class),
        "decision_key": proposed["decision_key"],
    }


def build_decision_change_contract(
    prior: Mapping[str, Any],
    proposed: Mapping[str, Any],
    *,
    mission_id: str,
    round_index: int = 0,
) -> GrillQuestionContract:
    prior_label = str(prior.get("text") or "")
    proposed_label = str(proposed.get("text") or "")
    decision_key = str(proposed.get("decision_key") or prior.get("decision_key") or "")
    subject = str(proposed.get("decision_subject") or decision_subject_for_key(decision_key))
    question = (
        f"以前は「{prior_label}」と確定しています（{subject}）。\n"
        f"今回は「{proposed_label}」へ変更してよいですか？"
    )
    contract = GrillQuestionContract(
        question_id=f"decision_change:{mission_id}:{decision_key}:{round_index}",
        question=question,
        answer_type="single_choice",
        options=[
            GrillQuestionOption(
                id=OPTION_CONFIRM_CHANGE,
                label="はい、変更を確定します",
            ),
            GrillQuestionOption(
                id=OPTION_KEEP_PRIOR,
                label="いいえ、以前の判断を維持します",
            ),
            GrillQuestionOption(
                id=OPTION_DEFER_CHANGE,
                label="保留（今回は変更しません）",
            ),
        ],
        recommended_option_id=OPTION_KEEP_PRIOR,
        recommendation_reason="既決仕様の変更は明示確認が必要",
        grill_reason=GRILL_REASON_DECISION_CHANGE,
        dimension=str(proposed.get("dimension") or prior.get("dimension") or "acceptance"),
    )
    errors = validate_grill_question_contract(contract)
    if errors:
        raise ValueError(f"invalid decision change contract: {errors}")
    return contract


def format_decision_change_confirmation(contract: Mapping[str, Any] | GrillQuestionContract) -> str:
    payload = contract.as_dict() if isinstance(contract, GrillQuestionContract) else dict(contract)
    lines = [
        str(payload.get("question") or ""),
        "",
        "Human UI policy: 推奨案は参考表示のみです。自動確定しません。",
        "返信で判断を指定してください。",
    ]
    recommended_id = str(payload.get("recommended_option_id") or "")
    for row in payload.get("options") or []:
        if not isinstance(row, Mapping):
            continue
        option_id = str(row.get("id") or "")
        prefix = "（推奨・参考）" if option_id and option_id == recommended_id else "-"
        lines.append(f"{prefix} {row.get('label')}")
    return "\n".join(lines)


def decision_change_confirmation_state(
    *,
    mission_id: str,
    execution_id: str,
    consumer: str,
    resume_packet: Mapping[str, Any],
    pending_application: Mapping[str, Any],
    contract: GrillQuestionContract,
) -> dict[str, Any]:
    return {
        "phase": "decision_change_confirmation",
        "status": "AWAITING_HUMAN",
        "mission_id": mission_id,
        "execution_id": execution_id,
        "consumer": consumer,
        "resume_packet": dict(resume_packet),
        "pending_application": dict(pending_application),
        "active_contract": contract.as_dict(),
        "selection_policy": SELECTION_POLICY_HUMAN_UI,
    }


def launch_decision_change_confirmation(
    orchestrator: Any,
    *,
    resume_packet: Mapping[str, Any],
    pending_application: Mapping[str, Any],
    prior: Mapping[str, Any],
    proposed: Mapping[str, Any],
) -> dict[str, Any]:
    mission_id = str(getattr(orchestrator, "mission_id", "") or "mission")
    contract = build_decision_change_contract(
        prior,
        proposed,
        mission_id=mission_id,
        round_index=int(getattr(orchestrator, "boundary_grill_round", 0) or 0),
    )
    state = decision_change_confirmation_state(
        mission_id=mission_id,
        execution_id=str(getattr(orchestrator, "execution_id", "") or ""),
        consumer="boundary_grill",
        resume_packet=resume_packet,
        pending_application=pending_application,
        contract=contract,
    )
    return {
        "contract": contract.as_dict(),
        "state": state,
        "formatted": format_decision_change_confirmation(contract),
    }


def interpret_decision_change_answer(answer: str) -> str:
    text = str(answer or "").strip()
    lower = text.casefold()
    if text in {OPTION_CONFIRM_CHANGE, "はい、変更を確定します", "変更を確定", "変更します"}:
        return OPTION_CONFIRM_CHANGE
    if text in {OPTION_KEEP_PRIOR, "いいえ、以前の判断を維持します", "以前の判断を維持", "維持"}:
        return OPTION_KEEP_PRIOR
    if text in {OPTION_DEFER_CHANGE, "保留", "今回は変更しません"}:
        return OPTION_DEFER_CHANGE
    if any(token in lower for token in ("変更", "confirm", "yes", "はい")):
        if any(token in lower for token in ("維持", "keep", "いいえ", "no")):
            return OPTION_KEEP_PRIOR
        return OPTION_CONFIRM_CHANGE
    if any(token in lower for token in ("維持", "keep", "いいえ", "no")):
        return OPTION_KEEP_PRIOR
    if any(token in lower for token in ("保留", "defer", "cancel")):
        return OPTION_DEFER_CHANGE
    return OPTION_KEEP_PRIOR


def supersede_decision(
    orchestrator: Any,
    prior_decision_id: str,
    new_record: dict[str, Any],
    *,
    execution_id: str,
    chat_fn: Any | None = None,
    model: str = "fake",
    run_premise_revalidation: bool = False,
) -> dict[str, Any] | None:
    prior_row: dict[str, Any] | None = None
    new_id = ensure_decision_id(new_record)
    new_record["decision_id"] = new_id
    new_record["status"] = DECISION_STATUS_CONFIRMED
    new_record["supersedes"] = prior_decision_id or None
    for row in getattr(orchestrator, "confirmed_clarifications", None) or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("decision_id") or "") != prior_decision_id:
            continue
        if not row.get("decision_id"):
            row["decision_id"] = prior_decision_id
        row["status"] = DECISION_STATUS_SUPERSEDED
        row["superseded_by"] = new_id
        row["superseded_at_execution_id"] = execution_id
        prior_row = dict(row)
    clarifications = list(getattr(orchestrator, "confirmed_clarifications", None) or [])
    clarifications.append(new_record)
    orchestrator.confirmed_clarifications = clarifications
    from ai_tool.human_decision_premise import refresh_task_revalidation

    refresh_task_revalidation(orchestrator)
    if run_premise_revalidation and chat_fn is not None:
        from ai_tool.decision_premise_revalidation import run_premise_revalidations

        run_premise_revalidations(orchestrator, chat_fn=chat_fn, model=model)
    return prior_row


def active_confirmed_clarifications(
    clarifications: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in (clarifications or [])
        if isinstance(item, dict) and is_active_confirmed(item)
    ]
