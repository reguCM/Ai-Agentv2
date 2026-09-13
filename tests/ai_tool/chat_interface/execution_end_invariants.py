"""Cross-cutting Execution end-state invariant contracts and evaluator.

Contracts are derived from existing specs/code only. Fields marked NOT_CONNECTED
or UNDECIDED are not guessed — tests record those statuses instead of passing
silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal

CheckStatus = Literal["PASS", "FAIL", "NOT_CONNECTED", "UNDECIDED", "N/A"]


class FieldContract(str, Enum):
    REQUIRED = "REQUIRED"
    NOT_CONNECTED = "NOT_CONNECTED"
    UNDECIDED = "UNDECIDED"
    NOT_APPLICABLE = "N/A"


@dataclass(frozen=True)
class EndBranchContract:
    branch_id: str
    spec_source: str
    entry: str
    answer: FieldContract = FieldContract.REQUIRED
    mission_persist: FieldContract = FieldContract.REQUIRED
    expected_stop_reason: str | None = None
    expected_judgment: str | None = None
    expected_end_state: str | None = None
    expected_goal_achievement_performed: bool | None = None
    next_action_or_terminal: FieldContract = FieldContract.UNDECIDED
    resume: FieldContract = FieldContract.NOT_APPLICABLE
    anti_silent_end: FieldContract = FieldContract.REQUIRED
    notes: str = ""


@dataclass
class InvariantCheck:
    field: str
    contract: FieldContract
    status: CheckStatus
    detail: str


@dataclass
class ScenarioRun:
    contract: EndBranchContract
    run: Callable[..., tuple[dict[str, Any], dict[str, Any]]]


def _mission_record(result: dict[str, Any]) -> dict[str, Any] | None:
    recorded = result.get("mission_memory")
    if not isinstance(recorded, dict) or not recorded.get("ok"):
        return None
    return recorded


def execution_stop_reason_from_result(result: dict[str, Any]) -> str | None:
    """Persisted execution stop_reason when mission_memory write succeeded."""
    execution = _execution_from_store(result)
    if execution is None:
        return None
    token = str(execution.get("stop_reason") or "").strip()
    return token or None


def _execution_from_store(result: dict[str, Any]) -> dict[str, Any] | None:
    recorded = _mission_record(result)
    if recorded is None:
        return None
    try:
        from ai_tool.mission_memory.store import MissionMemoryStore

        store = MissionMemoryStore.from_default()
        return store.get_execution(
            str(recorded["mission_id"]),
            str(recorded["execution_id"]),
        )
    except Exception:
        return None


def _has_resume(session: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    if result.get("goal_completion_resume"):
        return True, "result.goal_completion_resume"
    if session.get("goal_completion_resume"):
        return True, "session.goal_completion_resume"
    if result.get("conversation_grill") or session.get("conversation_grill_state"):
        return True, "conversation_grill_state"
    return False, "none"


def _has_next_action_or_terminal(result: dict[str, Any]) -> tuple[bool, str]:
    if str(result.get("route") or "") == "help" or str(result.get("intent") or "") == "help":
        return True, "help_response"
    requirement = result.get("requirement_decomposition")
    if isinstance(requirement, dict):
        status = str(requirement.get("status") or "")
        if status and status != "READY":
            return True, f"requirement_decomposition.status={status}"
    if (
        result.get("awaiting_goal_completion_human")
        or result.get("awaiting_human_grill")
        or result.get("awaiting_human_review")
    ):
        return True, "human_wait_flag"
    report = result.get("runtime_status_report") or {}
    next_actions = report.get("next_actions") or []
    if next_actions:
        return True, "runtime_status_report.next_actions"
    reason_code = str(report.get("reason_code") or "").strip()
    if reason_code:
        return True, f"runtime_status_report.reason_code={reason_code}"
    markdown = str(report.get("markdown") or "")
    if markdown and "次に可能な対応" in markdown:
        return True, "runtime_status_report.markdown"
    gate = result.get("answer_gate") or {}
    gate_reason = str(gate.get("reason") or "").strip()
    if gate_reason in {
        "awaiting_human_grill",
        "awaiting_goal_completion_human",
        "closed_unresolved_goal_target",
        "provisional_user_variable_target",
    }:
        return True, f"answer_gate.reason={gate_reason}"
    if result.get("goal_completion_judgment"):
        return True, "goal_completion_judgment"
    answer = str(result.get("answer") or "")
    terminal_markers = (
        "Mission 状態:",
        "未対応として停止",
        "Human Approvalが必要",
        "返信で指定してください",
        "この Goal では何をもって完了としますか",
        "処理を開始できませんでした",
        "処理状態:",
        "停止理由:",
    )
    for marker in terminal_markers:
        if marker in answer:
            return True, f"answer.contains:{marker}"
    if result.get("is_error") and str(result.get("user_error") or "").strip():
        return True, "user_error"
    return False, "none"


def evaluate_execution_end_invariants(
    result: dict[str, Any],
    session: dict[str, Any],
    contract: EndBranchContract,
) -> list[InvariantCheck]:
    checks: list[InvariantCheck] = []
    answer = str(result.get("answer") or "").strip()
    recorded = _mission_record(result)
    execution = _execution_from_store(result)

    def add(
        field: str,
        field_contract: FieldContract,
        ok: bool,
        detail: str,
        *,
        not_connected_ok: bool = False,
    ) -> None:
        if field_contract == FieldContract.NOT_APPLICABLE:
            checks.append(InvariantCheck(field, field_contract, "N/A", detail))
            return
        if field_contract == FieldContract.UNDECIDED:
            checks.append(
                InvariantCheck(field, field_contract, "UNDECIDED", detail)
            )
            return
        if field_contract == FieldContract.NOT_CONNECTED:
            status: CheckStatus = (
                "NOT_CONNECTED" if not_connected_ok or not ok else "FAIL"
            )
            if ok:
                status = "NOT_CONNECTED"
            checks.append(InvariantCheck(field, field_contract, status, detail))
            return
        checks.append(
            InvariantCheck(
                field,
                field_contract,
                "PASS" if ok else "FAIL",
                detail,
            )
        )

    add(
        "user_facing_answer",
        contract.answer,
        bool(answer),
        f"len={len(answer)}",
    )

    if contract.mission_persist == FieldContract.NOT_CONNECTED:
        add(
            "mission_persist",
            contract.mission_persist,
            recorded is None,
            "mission_memory absent as spec expects",
            not_connected_ok=True,
        )
    elif contract.mission_persist == FieldContract.NOT_APPLICABLE:
        add("mission_persist", contract.mission_persist, True, "n/a")
    elif contract.mission_persist == FieldContract.UNDECIDED:
        add(
            "mission_persist",
            contract.mission_persist,
            True,
            f"UNDECIDED; recorded={bool(recorded)}",
        )
    else:
        add(
            "mission_persist",
            contract.mission_persist,
            recorded is not None,
            f"mission_memory={recorded}",
        )

    if contract.expected_stop_reason is not None and execution is not None:
        actual = str(execution.get("stop_reason") or "")
        add(
            "execution.stop_reason",
            FieldContract.REQUIRED,
            actual == contract.expected_stop_reason,
            f"expected={contract.expected_stop_reason} actual={actual}",
        )
    elif contract.expected_stop_reason is not None:
        add(
            "execution.stop_reason",
            FieldContract.REQUIRED,
            False,
            "execution record missing",
        )

    if contract.expected_judgment is not None and execution is not None:
        actual = str(execution.get("execution_end_state_judgment") or "")
        add(
            "execution.execution_end_state_judgment",
            FieldContract.REQUIRED,
            actual == contract.expected_judgment,
            f"expected={contract.expected_judgment} actual={actual}",
        )

    if contract.expected_end_state is not None and execution is not None:
        actual = execution.get("execution_end_state")
        add(
            "execution.execution_end_state",
            FieldContract.REQUIRED,
            actual == contract.expected_end_state,
            f"expected={contract.expected_end_state} actual={actual}",
        )

    if contract.expected_goal_achievement_performed is not None and execution is not None:
        actual = bool(execution.get("goal_achievement_performed"))
        add(
            "execution.goal_achievement_performed",
            FieldContract.REQUIRED,
            actual == contract.expected_goal_achievement_performed,
            f"expected={contract.expected_goal_achievement_performed} actual={actual}",
        )

    has_terminal, terminal_detail = _has_next_action_or_terminal(result)
    if contract.next_action_or_terminal == FieldContract.NOT_CONNECTED:
        add(
            "next_action_or_terminal",
            contract.next_action_or_terminal,
            not has_terminal,
            f"spec NOT_CONNECTED; observed={terminal_detail}",
            not_connected_ok=True,
        )
    elif contract.next_action_or_terminal == FieldContract.UNDECIDED:
        add(
            "next_action_or_terminal",
            contract.next_action_or_terminal,
            True,
            f"UNDECIDED; observed={terminal_detail}",
        )
    else:
        add(
            "next_action_or_terminal",
            contract.next_action_or_terminal,
            has_terminal,
            terminal_detail,
        )

    if contract.resume == FieldContract.NOT_APPLICABLE:
        add("resume_info", contract.resume, True, "n/a")
    elif contract.resume == FieldContract.NOT_CONNECTED:
        has_resume, resume_detail = _has_resume(session, result)
        add(
            "resume_info",
            contract.resume,
            not has_resume,
            f"spec NOT_CONNECTED; observed={resume_detail}",
            not_connected_ok=True,
        )
    else:
        has_resume, resume_detail = _has_resume(session, result)
        add(
            "resume_info",
            contract.resume,
            has_resume,
            resume_detail,
        )

    if contract.anti_silent_end == FieldContract.NOT_APPLICABLE:
        add("anti_silent_end", contract.anti_silent_end, True, "n/a")
    elif contract.anti_silent_end == FieldContract.NOT_CONNECTED:
        add(
            "anti_silent_end",
            contract.anti_silent_end,
            True,
            contract.notes or "NOT_CONNECTED by spec",
        )
    elif contract.anti_silent_end == FieldContract.UNDECIDED:
        add(
            "anti_silent_end",
            contract.anti_silent_end,
            True,
            f"UNDECIDED; answer_present={bool(answer)} terminal={terminal_detail}",
        )
    else:
        non_mission_path = contract.mission_persist in {
            FieldContract.NOT_CONNECTED,
            FieldContract.NOT_APPLICABLE,
        }
        if not answer:
            silent = not (
                result.get("is_error")
                and str(result.get("user_error") or "").strip()
            )
        elif non_mission_path:
            silent = False
        elif has_terminal:
            silent = False
        elif contract.next_action_or_terminal == FieldContract.NOT_CONNECTED:
            silent = True
        else:
            silent = True
        add(
            "anti_silent_end",
            contract.anti_silent_end,
            not silent,
            f"answer_present={bool(answer)} terminal={terminal_detail}",
        )

    return checks


def format_invariant_report(
    contract: EndBranchContract,
    checks: list[InvariantCheck],
) -> str:
    lines = [
        f"branch={contract.branch_id}",
        f"entry={contract.entry}",
        f"spec={contract.spec_source}",
    ]
    if contract.notes:
        lines.append(f"notes={contract.notes}")
    for item in checks:
        lines.append(
            f"  {item.field}: {item.status} ({item.contract.value}) — {item.detail}"
        )
    failures = [item for item in checks if item.status == "FAIL"]
    lines.append(f"FAIL count={len(failures)}")
    return "\n".join(lines)


def collect_failures(checks: list[InvariantCheck]) -> list[InvariantCheck]:
    return [item for item in checks if item.status == "FAIL"]
