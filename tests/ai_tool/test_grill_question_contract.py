from __future__ import annotations

import pytest

from ai_tool.grill_question_contract import (
    ANSWER_TYPE_SINGLE_CHOICE,
    GRILL_REASON_GOAL_COMPLETION_HUMAN,
    GRILL_REASON_INITIAL,
    RESPONSE_KIND_HUMAN_UI,
    RESPONSE_KIND_SIMULATED_HUMAN,
    SELECTION_POLICY_HUMAN_UI,
    SELECTION_POLICY_TEST_AUTO,
    apply_selection_policy,
    normalize_goal_completion_human_packet,
    normalize_grill_question_payload,
    validate_grill_question_contract_dict,
    validate_grill_selection_result_dict,
)
from ai_tool.grill_me_loop import run_grill_me_loop


def test_normalize_recommended_answer_only_payload() -> None:
    contract = normalize_grill_question_payload(
        {
            "question": "Where should implementation happen?",
            "recommended_answer": "Dedicated Sandbox",
            "dimension": "boundaries",
            "rationale": "isolate production repo",
        },
        question_id="initial_grill:r1",
        grill_reason=GRILL_REASON_INITIAL,
        dimension="boundaries",
    )
    assert contract.question == "Where should implementation happen?"
    assert contract.answer_type == "freeform_with_recommendation"
    assert len(contract.options) == 1
    assert contract.options[0].id == "opt_recommended"
    assert contract.options[0].label == "Dedicated Sandbox"
    assert contract.recommended_option_id == "opt_recommended"
    assert contract.recommendation_reason == "isolate production repo"
    assert contract.grill_reason == GRILL_REASON_INITIAL


def test_normalize_explicit_options_payload() -> None:
    contract = normalize_grill_question_payload(
        {
            "question": "Which runtime?",
            "options": [
                {"id": "sandbox", "label": "Dedicated Sandbox"},
                {"id": "worktree", "label": "Dev worktree"},
            ],
            "recommended_option_id": "sandbox",
            "recommendation_reason": "mutation isolation",
        },
        question_id="boundary_grill:r2",
        grill_reason="boundary_grill",
    )
    assert contract.answer_type == ANSWER_TYPE_SINGLE_CHOICE
    assert contract.recommended_option_id == "sandbox"
    assert [item.id for item in contract.options] == ["sandbox", "worktree"]


def test_test_auto_policy_selects_recommended_option() -> None:
    contract = normalize_grill_question_payload(
        {
            "question": "Where?",
            "recommended_answer": "Sandbox",
            "rationale": "safe",
        },
        question_id="initial_grill:r1",
        grill_reason=GRILL_REASON_INITIAL,
    )
    selection = apply_selection_policy(contract, SELECTION_POLICY_TEST_AUTO)
    assert selection.auto_selected is True
    assert selection.selected_option_id == "opt_recommended"
    assert selection.selected_label == "Sandbox"
    assert selection.human_response_kind == RESPONSE_KIND_SIMULATED_HUMAN


def test_human_ui_policy_does_not_auto_select() -> None:
    contract = normalize_grill_question_payload(
        {
            "question": "Where?",
            "recommended_answer": "Sandbox",
            "rationale": "safe",
        },
        question_id="initial_grill:r1",
        grill_reason=GRILL_REASON_INITIAL,
    )
    selection = apply_selection_policy(contract, SELECTION_POLICY_HUMAN_UI)
    assert selection.auto_selected is False
    assert selection.selected_option_id is None
    assert selection.selected_label is None
    assert selection.human_response_kind == RESPONSE_KIND_HUMAN_UI


def test_goal_completion_human_packet_maps_to_same_contract() -> None:
    contract = normalize_goal_completion_human_packet(
        {
            "question": "この Goal では何をもって完了としますか。",
            "goal_meaning_options": [
                {"id": "absence_confirmed_completes_goal", "label": "不在確認で完了"},
                {"id": "content_report_required", "label": "中身報告が必須"},
            ],
            "recommended": {
                "id": None,
                "text": "完了条件が不在確認なら不在確認で完了",
            },
        },
        question_id="goal_completion_human:readme",
    )
    assert contract.grill_reason == GRILL_REASON_GOAL_COMPLETION_HUMAN
    assert contract.answer_type == ANSWER_TYPE_SINGLE_CHOICE
    assert len(contract.options) == 2
    assert contract.recommended_option_id == ""
    assert "不在確認" in contract.recommendation_reason


def test_validator_rejects_duplicate_option_ids() -> None:
    errors = validate_grill_question_contract_dict(
        {
            "contract_version": "0.1",
            "question_id": "initial_grill:r1",
            "question": "Where?",
            "answer_type": "single_choice",
            "options": [
                {"id": "sandbox", "label": "Sandbox"},
                {"id": "sandbox", "label": "Duplicate"},
            ],
            "recommended_option_id": "sandbox",
            "recommendation_reason": "safe",
            "grill_reason": GRILL_REASON_INITIAL,
        }
    )
    assert any("unique" in item for item in errors)


def test_validator_rejects_human_approval_grill_reason() -> None:
    errors = validate_grill_question_contract_dict(
        {
            "contract_version": "0.1",
            "question_id": "initial_grill:r1",
            "question": "Approve tool?",
            "answer_type": "freeform_with_recommendation",
            "options": [{"id": "opt_recommended", "label": "Approve"}],
            "recommended_option_id": "opt_recommended",
            "recommendation_reason": "approval",
            "grill_reason": "human_approval",
        }
    )
    assert errors


def test_test_auto_requires_recommended_option_for_goal_completion_human() -> None:
    contract = normalize_goal_completion_human_packet(
        {
            "question": "この Goal では何をもって完了としますか。",
            "goal_meaning_options": [
                {"id": "absence_confirmed_completes_goal", "label": "不在確認で完了"},
                {"id": "content_report_required", "label": "中身報告が必須"},
            ],
            "recommended": {"id": None, "text": "推奨のみ"},
        },
        question_id="goal_completion_human:readme",
    )
    with pytest.raises(ValueError, match="recommended option missing"):
        apply_selection_policy(contract, SELECTION_POLICY_TEST_AUTO)


def test_human_ui_selection_validator_enforces_no_auto_select() -> None:
    contract = normalize_grill_question_payload(
        {
            "question": "Where?",
            "recommended_answer": "Sandbox",
            "rationale": "safe",
        },
        question_id="initial_grill:r1",
        grill_reason=GRILL_REASON_INITIAL,
    )
    selection = apply_selection_policy(contract, SELECTION_POLICY_HUMAN_UI)
    assert validate_grill_selection_result_dict(contract.as_dict(), selection.as_dict()) == []


def test_grill_loop_transcript_includes_normalized_contract() -> None:
    def chat(**kwargs):
        user = str((kwargs.get("messages") or [])[-1]["content"])
        if "Ask the next highest-value unresolved question" in user:
            payload = {
                "question": "Where?",
                "recommended_answer": "Sandbox",
                "dimension": "boundaries",
                "rationale": "isolate",
            }
        else:
            payload = {
                "dimensions": {
                    "goals": 0.25,
                    "acceptance": 0.25,
                    "boundaries": 0.0,
                    "alternatives": 0.25,
                    "assumptions": 0.25,
                },
                "aggregate": 0.2,
                "weakest": [],
                "ready_to_exit": True,
                "aligned_spec": {"title": "Tetris", "summary": "sandbox"},
            }
        import json

        return type(
            "Resp",
            (),
            {"message": type("Msg", (), {"content": json.dumps(payload)})()},
        )()

    result = run_grill_me_loop(
        "テトリスを作って",
        model="mock",
        max_rounds=3,
        min_rounds_before_score=1,
        chat_fn=chat,
    )
    assert result.transcript
    turn = result.transcript[0]
    contract = turn.question_contract
    assert contract["question_id"] == "initial_grill:r1"
    assert contract["grill_reason"] == GRILL_REASON_INITIAL
    assert contract["recommended_option_id"] == "opt_recommended"
    assert turn.selection_result["selection_policy"] == SELECTION_POLICY_TEST_AUTO
    assert turn.selection_result["human_response_kind"] == RESPONSE_KIND_SIMULATED_HUMAN
