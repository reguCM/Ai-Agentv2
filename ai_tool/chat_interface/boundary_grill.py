"""Production Boundary Grill for general SPEC_MEANING_GAP (Bridge-1/2).

Reuses GrillQuestionContract, Skill Applicability evaluation, and the
Conversation Grill resume pattern. Does not replace Goal Completion Human v0,
Conversation Grill, or Dev Skill Pipeline grills.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityId,
    GapKind,
    GapResolutionDecision,
    route_gap_resolution_from_orchestrator,
)
from ai_tool.grill_question_contract import (
    GRILL_REASON_BOUNDARY,
    SELECTION_POLICY_HUMAN_UI,
    GrillQuestionContract,
    GrillQuestionOption,
    validate_grill_question_contract,
)
from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    active_decision_for_key,
    decision_key_for_contract,
    decision_subject_for_key,
    new_decision_id,
    resolve_boundary_answer,
)
from ai_tool.skill_applicability import load_registry

BOUNDARY_GRILL_DIMENSIONS = (
    "goals",
    "acceptance",
    "boundaries",
    "alternatives",
    "assumptions",
)
BOUNDARY_GRILL_V0_REQUIRED = ("acceptance",)
_BOUNDARY_GRILL_OPTIONAL = ("behavior",)

_UNRESOLVED_SPEC_FORK = re.compile(
    r"(未決|未確定|どちらを(採用|選|使)|採用基準が|どちらか一方|いずれか一方|"
    r"複数.{0,12}妥当|2通り|二通り|両方.{0,8}妥当)",
    re.I,
)
_AB_LABELED_OPTIONS = re.compile(r"(?m)^\s*[AB][\)）.:：]\s+\S")
_MATERIAL_OUTCOME_TERMS = re.compile(
    r"(引用|要約|paragraph|summary|生成|削除|追加|改変|上書き|保存|報告)",
    re.I,
)


def boundary_grill_runtime_connected(registry: Mapping[str, Any] | None = None) -> bool:
    """True only when registry marks grill-me as production-connected."""
    catalog = registry or load_registry()
    for row in catalog.get("skills") or []:
        if str(row.get("id") or "") == "grill-me":
            return bool(row.get("runtime_connected"))
    return False


def request_has_material_spec_fork(request: str) -> bool:
    """True when multiple substantively different valid specs remain unresolved.

    Mere absence of explicit acceptance criteria is NOT sufficient.
    """
    text = str(request or "").strip()
    if not text:
        return False
    if not _UNRESOLVED_SPEC_FORK.search(text):
        return False
    has_ab_labels = bool(_AB_LABELED_OPTIONS.search(text)) or (
        bool(re.search(r"(?m)^\s*A\s*[:：]", text))
        and bool(re.search(r"(?m)^\s*B\s*[:：]", text))
    )
    if has_ab_labels:
        return True
    if re.search(r"(または|もしくは|あるいは)", text, re.I):
        return len(_MATERIAL_OUTCOME_TERMS.findall(text)) >= 2
    return False


def request_mentions_gui_fork(request: str) -> bool:
    text = str(request or "")
    return bool(re.search(r"\bGUI\b|gui|画面", text, re.I))


def boundary_grill_open_dimensions(orchestrator: Any) -> list[str]:
    resolved = set(getattr(orchestrator, "boundary_grill_resolved_dimensions", None) or [])
    required = list(BOUNDARY_GRILL_V0_REQUIRED)
    request = str(getattr(orchestrator, "request", "") or "")
    if "acceptance" in resolved and request_mentions_gui_fork(request):
        required.extend(_BOUNDARY_GRILL_OPTIONAL)
    return [item for item in required if item not in resolved]


def needs_boundary_spec_clarification(orchestrator: Any) -> bool:
    if orchestrator is None:
        return False
    if getattr(orchestrator, "needs_human_grill", lambda: False)():
        return False
    if getattr(orchestrator, "needs_goal_completion_human", lambda: False)():
        return False
    observation = getattr(getattr(orchestrator, "runtime", None), "tasks", {}).get("T1")
    if observation is None or getattr(observation, "status", None) != "complete":
        return False
    if not getattr(observation, "evidence_ids", None):
        return False
    if list(getattr(orchestrator, "user_explicit_conditions", None) or []):
        return False
    if not boundary_grill_open_dimensions(orchestrator):
        return False
    return request_has_material_spec_fork(str(getattr(orchestrator, "request", "") or ""))


def _next_boundary_dimension(orchestrator: Any) -> str | None:
    open_dims = boundary_grill_open_dimensions(orchestrator)
    return open_dims[0] if open_dims else None


def build_boundary_grill_contract(
    orchestrator: Any,
    *,
    dimension: str | None = None,
    round_index: int = 0,
) -> GrillQuestionContract:
    active_dimension = dimension or _next_boundary_dimension(orchestrator) or "acceptance"
    mission_id = str(getattr(orchestrator, "mission_id", "") or "mission")
    request = str(getattr(orchestrator, "request", "") or "")
    if active_dimension == "acceptance":
        question = (
            "観測は完了しましたが、Goal の完了条件（Acceptance）が一意に決まっていません。"
            "何をもって完了とみなすか、具体的な判定基準を指定してください。"
        )
        options = [
            GrillQuestionOption(
                id="acceptance_quote_first_lines",
                label="指定ファイルの先頭3行をそのまま引用できれば完了",
            ),
            GrillQuestionOption(
                id="acceptance_one_paragraph_summary",
                label="1段落の要約文を生成できれば完了",
            ),
        ]
        if re.search(r"\bJSON\b|json", request, re.I):
            options.insert(
                0,
                GrillQuestionOption(
                    id="acceptance_json_output",
                    label="JSON APIで出力",
                ),
            )
            recommended = "acceptance_json_output"
        else:
            recommended = "acceptance_quote_first_lines"
        reason = "観測済みの読取結果に対する完了判定が未固定"
    elif active_dimension == "behavior":
        question = (
            "GUI を含めるかどうかが未確定です。"
            "実装スコープに GUI 画面を含めますか。"
        )
        options = [
            GrillQuestionOption(id="behavior_gui_yes", label="GUIあり"),
            GrillQuestionOption(id="behavior_gui_no", label="GUIなし"),
        ]
        recommended = "behavior_gui_no"
        reason = "GUI inclusion remains unresolved"
    else:
        question = (
            f"仕様の曖昧さ（{active_dimension}）が残っています。"
            "この点について判断できる回答をください。"
        )
        options = [
            GrillQuestionOption(id=f"{active_dimension}_clarify", label="判断材料を補足する"),
        ]
        recommended = f"{active_dimension}_clarify"
        reason = f"boundary dimension {active_dimension} unresolved"
    if active_dimension == "acceptance":
        decision_key = "acceptance:output_format"
    elif active_dimension == "behavior":
        decision_key = "scope:gui"
    else:
        decision_key = f"{active_dimension}:general"
    contract = GrillQuestionContract(
        question_id=f"boundary_grill:{mission_id}:{active_dimension}:{round_index}",
        question=question,
        answer_type="single_choice",
        options=options,
        recommended_option_id=recommended,
        recommendation_reason=reason,
        grill_reason=GRILL_REASON_BOUNDARY,
        dimension=active_dimension,
        decision_key=decision_key,
        decision_subject=(
            "成果物の報告形式（Acceptance / Output Format）"
            if decision_key == "acceptance:output_format"
            else decision_key.replace(":", " / ")
        ),
    )
    errors = validate_grill_question_contract(contract)
    if errors:
        raise ValueError(f"invalid boundary grill contract: {errors}")
    return contract


def format_boundary_grill(contract: Mapping[str, Any] | GrillQuestionContract) -> str:
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


def boundary_grill_record(
    orchestrator: Any,
    contract: GrillQuestionContract,
) -> dict[str, Any]:
    return {
        "phase": "boundary_grill",
        "status": "AWAITING_HUMAN",
        "selection_policy": SELECTION_POLICY_HUMAN_UI,
        "contract": contract.as_dict(),
        "open_dimensions": boundary_grill_open_dimensions(orchestrator),
        "resolved_dimensions": sorted(
            set(getattr(orchestrator, "boundary_grill_resolved_dimensions", None) or [])
        ),
        "question": contract.question,
        "recommended_option_id": contract.recommended_option_id,
        "recommendation_reason": contract.recommendation_reason,
    }


def boundary_grill_state(orchestrator: Any, contract: GrillQuestionContract) -> dict[str, Any]:
    return {
        "original_request": str(getattr(orchestrator, "request", "") or ""),
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "mission_id": str(getattr(orchestrator, "mission_id", "") or ""),
        "execution_id": str(getattr(orchestrator, "execution_id", "") or ""),
        "boundary_grill_resolved_dimensions": sorted(
            set(getattr(orchestrator, "boundary_grill_resolved_dimensions", None) or [])
        ),
        "confirmed_clarifications": [
            dict(item)
            for item in (getattr(orchestrator, "confirmed_clarifications", None) or [])
        ],
        "user_explicit_conditions": list(
            getattr(orchestrator, "user_explicit_conditions", None) or []
        ),
        "boundary_grill_round": int(getattr(orchestrator, "boundary_grill_round", 0) or 0),
        "active_contract": contract.as_dict(),
        "open_dimensions": boundary_grill_open_dimensions(orchestrator),
    }


def restore_orchestrator_from_boundary_grill(
    runtime_id: str,
    state: Mapping[str, Any],
) -> Any:
    from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
    from ai_tool.mission_memory.chat_persist import bind_execution_identity
    from ai_tool.mission_memory.clarifications import restore_mission_clarifications
    from ai_tool.mission_memory.task_runtime import (
        apply_orchestrator_completion_runtime,
        resolve_canonical_completion_runtime,
    )

    orchestrator = ChatTaskOrchestrator(
        runtime_id,
        str(state.get("original_request") or ""),
    )
    mission_id = str(state.get("mission_id") or "")
    execution_id = str(state.get("execution_id") or "")
    bind_execution_identity(
        orchestrator,
        resume_mission_id=mission_id or None,
        new_execution=False,
    )
    if execution_id:
        orchestrator.execution_id = execution_id
    orchestrator.confirmed_clarifications = [
        dict(item) for item in (state.get("confirmed_clarifications") or [])
    ]
    restore_mission_clarifications(orchestrator)
    completion_runtime = resolve_canonical_completion_runtime(
        mission_id,
        state.get("completion_runtime") or {},
    )
    apply_orchestrator_completion_runtime(
        orchestrator,
        completion_runtime,
        replace_graph=ChatTaskOrchestrator.completion_runtime_requires_graph_restore(
            completion_runtime
        ),
    )
    orchestrator.boundary_grill_resolved_dimensions = list(
        state.get("boundary_grill_resolved_dimensions") or []
    )
    orchestrator.boundary_grill_round = int(state.get("boundary_grill_round") or 0)
    explicit_conditions = [
        str(item)
        for item in (state.get("user_explicit_conditions") or [])
        if str(item).strip()
    ]
    if not explicit_conditions:
        acceptance = active_decision_for_key(
            orchestrator.confirmed_clarifications,
            "acceptance:output_format",
        )
        if acceptance and str(acceptance.get("text") or "").strip():
            explicit_conditions = [str(acceptance.get("text") or "").strip()]
    orchestrator.user_explicit_conditions = explicit_conditions
    return orchestrator


def apply_boundary_grill_answer(
    orchestrator: Any,
    answer: str,
    contract: Mapping[str, Any],
    *,
    proposed: Mapping[str, Any] | None = None,
    supersede_prior_id: str | None = None,
) -> dict[str, Any]:
    """Persist confirmed Human decision without auto-completing Goal."""
    text = str(answer or "").strip()
    if not text and proposed is None:
        return {"applied": False, "reason": "empty_answer"}
    resolved = dict(proposed or resolve_boundary_answer(answer, contract))
    dimension = str(resolved.get("dimension") or contract.get("dimension") or "acceptance")
    selected_label = str(resolved.get("text") or text)
    from ai_tool.human_decision_premise import BOUNDARY_GRILL_SOURCE, normalize_decision_record

    record = normalize_decision_record(
        {
            "decision_id": new_decision_id(),
            "source": BOUNDARY_GRILL_SOURCE,
            "dimension": dimension,
            "decision_key": str(resolved.get("decision_key") or decision_key_for_contract(contract)),
            "decision_subject": str(
                resolved.get("decision_subject")
                or decision_subject_for_key(
                    str(resolved.get("decision_key") or decision_key_for_contract(contract))
                )
            ),
            "option_id": str(resolved.get("option_id") or ""),
            "text": selected_label,
            "question_id": str(contract.get("question_id") or ""),
            "human_confirmed": True,
            "auto_selected": False,
            "selection_policy": SELECTION_POLICY_HUMAN_UI,
            "status": DECISION_STATUS_CONFIRMED,
        }
    )
    if record is None:
        return {"applied": False, "reason": "invalid_decision_record"}
    if supersede_prior_id:
        from ai_tool.chat_interface.decision_change_gate import supersede_decision

        supersede_decision(
            orchestrator,
            supersede_prior_id,
            record,
            execution_id=str(getattr(orchestrator, "execution_id", "") or ""),
        )
    else:
        orchestrator.confirmed_clarifications.append(record)
    resolved = set(getattr(orchestrator, "boundary_grill_resolved_dimensions", None) or [])
    resolved.add(dimension)
    orchestrator.boundary_grill_resolved_dimensions = sorted(resolved)
    orchestrator.boundary_grill_round = int(getattr(orchestrator, "boundary_grill_round", 0) or 0) + 1
    if dimension == "acceptance" and selected_label.strip():
        orchestrator.user_explicit_conditions = [selected_label.strip()]
    payload = {
        "applied": True,
        "dimension": dimension,
        "decision_id": record["decision_id"],
        "decision_key": record["decision_key"],
        "selected_label": selected_label,
        "open_dimensions": boundary_grill_open_dimensions(orchestrator),
        "needs_more_boundary_grill": bool(boundary_grill_open_dimensions(orchestrator)),
    }
    if supersede_prior_id:
        payload["superseded_prior_id"] = str(supersede_prior_id)
    return payload


def should_launch_boundary_grill(
    decision: GapResolutionDecision | None,
    *,
    human_priority_blocked: bool,
    registry: Mapping[str, Any] | None = None,
) -> bool:
    if human_priority_blocked or decision is None:
        return False
    if decision.gap_kind != GapKind.SPEC_MEANING_GAP.value:
        return False
    if decision.winner != CapabilityId.SKILL_GRILL_ME.value:
        return False
    return boundary_grill_runtime_connected(registry)


def launch_boundary_grill(
    orchestrator: Any,
    decision: GapResolutionDecision,
) -> dict[str, Any]:
    contract = build_boundary_grill_contract(
        orchestrator,
        round_index=int(getattr(orchestrator, "boundary_grill_round", 0) or 0),
    )
    return {
        "contract": contract.as_dict(),
        "record": boundary_grill_record(orchestrator, contract),
        "state": boundary_grill_state(orchestrator, contract),
        "formatted": format_boundary_grill(contract),
        "gap_resolution": decision.as_dict(),
    }


def reroute_after_boundary_grill_answer(
    orchestrator: Any,
    *,
    stop_reason: str,
    answer_gate: Mapping[str, Any] | None,
) -> tuple[GapResolutionDecision, dict[str, Any]]:
    """Cross-check reuse: re-run existing Router after Human decision."""
    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason=stop_reason,
        answer_gate=answer_gate,
    )
    payload = {
        "gap_kind": decision.gap_kind,
        "gap_resolved": decision.gap_resolved,
        "winner": decision.winner,
        "open_dimensions": boundary_grill_open_dimensions(orchestrator),
    }
    return decision, payload
