from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_tool.mission_memory.validate import (
    schema_version,
    validate_bundle,
    validate_evidence,
    validate_execution,
    validate_mission,
)


def _mission(**overrides: Any) -> dict[str, Any]:
    record = {
        "schema_version": schema_version(),
        "mission_id": "m1",
        "original_goal": "このPCで動くテトリスを作りたい",
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
    }
    record.update(overrides)
    return record


def _execution(**overrides: Any) -> dict[str, Any]:
    record = {
        "schema_version": schema_version(),
        "execution_id": "x1",
        "mission_id": "m1",
        "execution_sequence": 1,
        "result_determination": "determined",
        "determined_result": "paused for grill",
        "execution_end_state_judgment": "judged",
        "execution_end_state": "paused",
        "goal_achievement_performed": False,
        "stop_reason": "HUMAN_GRILL",
        "unresolved_items": [],
        "evidence_refs": [],
    }
    record.update(overrides)
    return record


def _evidence(**overrides: Any) -> dict[str, Any]:
    record = {
        "schema_version": schema_version(),
        "persistent_evidence_id": "pe1",
        "created_in_mission_id": "m1",
        "created_by_execution_id": "x1",
        "source_type": "file",
        "source": "docs/example.md",
        "summary": "ファイルを読んだ要約",
        "observed_at": "2026-09-10T02:00:00Z",
    }
    record.update(overrides)
    return record


def test_schema_version_comes_from_schema_file() -> None:
    assert schema_version() == "1"


def test_mission_accepts_optional_completion_runtime() -> None:
    mission = _mission(
        completion_runtime={
            "current_goal_id": "G1",
            "current_task_id": "gh-T2",
            "goals": [{"goal_id": "G1", "title": "Goal", "status": "open", "task_ids": ["gh-T2"], "evidence_ids": []}],
            "tasks": [
                {
                    "task_id": "gh-T2",
                    "goal_id": "G1",
                    "source": "goal_handoff",
                    "decision_premises": [
                        {
                            "decision_key": "acceptance:output_format",
                            "derived_from_decision_id": "d1",
                            "validated_against_decision_id": "d2",
                        }
                    ],
                    "revalidation": {
                        "needs_revalidation": False,
                        "premise_revalidation": {
                            "outcome": "still_valid",
                            "reason": "ok",
                            "evaluated_against_decision_ids": {
                                "acceptance:output_format": "d2",
                            },
                        },
                    },
                }
            ],
        }
    )
    assert validate_mission(mission).verdict == "ACCEPT"


def test_valid_mission_execution_evidence_accept() -> None:
    assert validate_mission(_mission()).verdict == "ACCEPT"
    assert validate_execution(_execution()).verdict == "ACCEPT"
    assert validate_evidence(_evidence()).verdict == "ACCEPT"


def test_undetermined_omits_determined_result() -> None:
    record = _execution()
    record["result_determination"] = "undetermined"
    del record["determined_result"]
    assert validate_execution(record).verdict == "ACCEPT"


def test_determined_empty_result_is_not_missing() -> None:
    record = _execution(determined_result="")
    assert validate_execution(record).verdict == "ACCEPT"


def test_undetermined_with_determined_result_rejects() -> None:
    record = _execution(result_determination="undetermined")
    result = validate_execution(record)
    assert result.verdict == "REJECT"
    assert result.schema_errors


def test_determined_without_determined_result_rejects() -> None:
    record = _execution()
    del record["determined_result"]
    result = validate_execution(record)
    assert result.verdict == "REJECT"
    assert result.schema_errors


def test_not_judged_omits_execution_end_state() -> None:
    record = _execution()
    record["execution_end_state_judgment"] = "not_judged"
    del record["execution_end_state"]
    assert validate_execution(record).verdict == "ACCEPT"


def test_not_judged_with_execution_end_state_rejects() -> None:
    record = _execution(execution_end_state_judgment="not_judged")
    result = validate_execution(record)
    assert result.verdict == "REJECT"


def test_judged_without_execution_end_state_rejects() -> None:
    record = _execution()
    del record["execution_end_state"]
    result = validate_execution(record)
    assert result.verdict == "REJECT"


def test_fifth_execution_end_state_rejects() -> None:
    record = _execution(execution_end_state="not_judged")
    result = validate_execution(record)
    assert result.verdict == "REJECT"


def test_goal_achievement_not_performed_omits_result() -> None:
    record = _execution(goal_achievement_performed=False)
    assert "goal_achievement_result" not in record
    assert validate_execution(record).verdict == "ACCEPT"


def test_goal_achievement_performed_requires_result() -> None:
    record = _execution(goal_achievement_performed=True)
    result = validate_execution(record)
    assert result.verdict == "REJECT"
    record["goal_achievement_result"] = "not_achieved"
    assert validate_execution(record).verdict == "ACCEPT"


def test_goal_achievement_not_performed_with_result_rejects() -> None:
    record = _execution(
        goal_achievement_performed=False,
        goal_achievement_result="achieved",
    )
    result = validate_execution(record)
    assert result.verdict == "REJECT"


def test_empty_lists_are_known_zero_not_missing() -> None:
    mission = _mission(
        explicit_conditions=[],
        explicit_constraints=[],
        user_confirmed_supplements=[],
    )
    execution = _execution(unresolved_items=[], evidence_refs=[])
    assert validate_mission(mission).verdict == "ACCEPT"
    assert validate_execution(execution).verdict == "ACCEPT"


def test_missing_required_list_rejects() -> None:
    mission = _mission()
    del mission["explicit_conditions"]
    result = validate_mission(mission)
    assert result.verdict == "REJECT"


def test_empty_mission_id_rejects() -> None:
    result = validate_mission(_mission(mission_id=""))
    assert result.verdict == "REJECT"


def test_supplement_source_grill_or_goal_completion() -> None:
    mission = _mission(
        user_confirmed_supplements=[{"text": "規模は小さく", "source": "chat"}]
    )
    result = validate_mission(mission)
    assert result.verdict == "REJECT"
    mission["user_confirmed_supplements"] = [
        {"text": "規模は小さく", "source": "grill"}
    ]
    assert validate_mission(mission).verdict == "ACCEPT"
    mission["user_confirmed_supplements"] = [
        {
            "text": "指名したファイルが無いことを確認し、それを報告できれば Goal は完了",
            "source": "goal_completion",
        }
    ]
    assert validate_mission(mission).verdict == "ACCEPT"


def test_effective_goal_field_is_rejected() -> None:
    mission = _mission()
    mission["effective_goal"] = "合成文"
    result = validate_mission(mission)
    assert result.verdict == "REJECT"


def test_artifact_refs_and_implementation_path_fields_rejected() -> None:
    extra = _execution()
    extra["artifact_refs"] = []
    assert validate_execution(extra).verdict == "REJECT"
    extra = _execution()
    extra["determination_block"] = "passed"
    assert validate_execution(extra).verdict == "REJECT"
    extra = _execution()
    extra["resume_bridge"] = "connected"
    assert validate_execution(extra).verdict == "REJECT"


def test_runtime_evidence_id_is_not_canonical_field() -> None:
    record = _evidence()
    record["evidence_id"] = "E1"
    result = validate_evidence(record)
    assert result.verdict == "REJECT"


def test_unknown_source_type_without_locator_accepts() -> None:
    record = _evidence(source_type="unknown.tool-output")
    assert "source_locator" not in record
    assert validate_evidence(record).verdict == "ACCEPT"


def test_source_locator_allows_type_specific_keys() -> None:
    record = _evidence(
        source_locator={"path": "docs/example.md", "git_revision": "abc123"}
    )
    assert validate_evidence(record).verdict == "ACCEPT"


def test_persisted_at_is_separate_optional_field() -> None:
    record = _evidence()
    assert "persisted_at" not in record
    assert validate_evidence(record).verdict == "ACCEPT"
    record["persisted_at"] = "2026-09-10T02:01:00Z"
    assert validate_evidence(record).verdict == "ACCEPT"


def test_optional_correlation_id() -> None:
    record = _execution()
    assert "correlation_id" not in record
    assert validate_execution(record).verdict == "ACCEPT"
    record["correlation_id"] = "turn-1"
    assert validate_execution(record).verdict == "ACCEPT"


def test_bundle_rejects_execution_from_other_mission_when_mission_present() -> None:
    mission = _mission()
    other = _execution(mission_id="m-other")
    result = validate_bundle(mission=mission, executions=[other])
    assert result.verdict == "REJECT"
    assert any("EXECUTION_MISSION_MISMATCH" in item for item in result.join_errors)


def test_bundle_accepts_cross_mission_evidence_ref() -> None:
    execution = _execution(evidence_refs=["pe-other"])
    other = _evidence(
        persistent_evidence_id="pe-other",
        created_in_mission_id="m-other",
        created_by_execution_id="x-other",
    )
    creator = _execution(
        execution_id="x-other",
        mission_id="m-other",
        execution_sequence=1,
        evidence_refs=[],
    )
    creator["execution_end_state_judgment"] = "not_judged"
    del creator["execution_end_state"]
    result = validate_bundle(executions=[execution, creator], evidence=[other])
    assert result.verdict == "ACCEPT", result.to_dict()


def test_bundle_provenance_mission_must_match_creating_execution() -> None:
    execution = _execution()
    evidence = _evidence(created_in_mission_id="m-wrong")
    result = validate_bundle(executions=[execution], evidence=[evidence])
    assert result.verdict == "REJECT"
    assert any(
        "EVIDENCE_PROVENANCE_MISSION_MISMATCH" in item for item in result.join_errors
    )


def test_bundle_dangling_evidence_ref_rejects_when_evidence_set_provided() -> None:
    execution = _execution(evidence_refs=["pe-missing"])
    result = validate_bundle(executions=[execution], evidence=[])
    assert result.verdict == "REJECT"
    assert any("EVIDENCE_REF_UNRESOLVED" in item for item in result.join_errors)


def test_execution_alone_does_not_require_evidence_resolution() -> None:
    execution = _execution(evidence_refs=["pe-missing"])
    result = validate_bundle(executions=[execution])
    assert result.verdict == "ACCEPT"


def test_duplicate_execution_sequence_same_mission_rejects() -> None:
    first = _execution(execution_id="x1", execution_sequence=1)
    second = _execution(execution_id="x2", execution_sequence=1)
    result = validate_bundle(executions=[first, second])
    assert result.verdict == "REJECT"
    assert any("EXECUTION_SEQUENCE_DUPLICATE" in item for item in result.join_errors)


def test_missing_creating_execution_rejects_when_executions_provided() -> None:
    result = validate_bundle(executions=[], evidence=[_evidence()])
    assert result.verdict == "REJECT"
    assert any(
        "EVIDENCE_CREATED_BY_EXECUTION_MISSING" in item for item in result.join_errors
    )


def test_happy_bundle_accepts() -> None:
    result = validate_bundle(
        mission=_mission(),
        executions=[_execution(evidence_refs=["pe1"])],
        evidence=[_evidence()],
    )
    assert result.verdict == "ACCEPT", result.to_dict()


def test_bundle_does_not_mutate_inputs() -> None:
    mission = _mission()
    execution = _execution()
    evidence = _evidence()
    snapshot = (deepcopy(mission), deepcopy(execution), deepcopy(evidence))
    result = validate_bundle(
        mission=mission,
        executions=[execution],
        evidence=[evidence],
    )
    assert result.verdict == "ACCEPT"
    assert (mission, execution, evidence) == snapshot
