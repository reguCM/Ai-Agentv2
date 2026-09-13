import json

from ai_tool.chat_interface.requirement_decomposition import (
    RequirementCondition,
    RequirementStatus,
    decompose_requirements,
    explicit_conditions,
    validate_conditions,
)


def test_a_clear_request_is_ready_with_small_conditions():
    called = False

    def chat(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unenumerated requests must not call the extractor")

    result = decompose_requirements(
        "contractを確認して要点を報告",
        chat_fn=chat,
        model="fake", available_tools=["read_file"],
    )
    assert result.status == RequirementStatus.READY.value
    assert result.source == "not_enumerated"
    assert result.conditions == []
    assert not called


def test_system_prompt_forbids_invented_and_counted_conditions():
    from ai_tool.chat_interface.requirement_decomposition import _SYSTEM

    assert "Prefer 3-5 conditions" not in _SYSTEM
    assert "Do not add conditions from general knowledge" in _SYSTEM
    assert "Do not invent extra conditions to reach a count" in _SYSTEM
    assert "依頼に書かれていない項目を一般常識や推測で追加しないこと。" in _SYSTEM


def test_b_missing_input_does_not_become_ready():
    result = validate_conditions([
        RequirementCondition("C1", "対象ファイルを読む", ambiguity="missing_input")
    ])
    assert result.status == "MISSING_INPUT"
    assert result.clarification


def test_c_vague_condition_requires_clarification():
    result = validate_conditions([RequirementCondition("C1", "十分に確認する")])
    assert result.status == "AMBIGUOUS"
    assert "十分に確認する" in result.clarification


def test_d_human_decision_is_not_executed_as_ready():
    result = validate_conditions([
        RequirementCondition("C1", "採用案を決定する", ambiguity="human_decision")
    ])
    assert result.status == "NEEDS_HUMAN_DECISION"


def test_e_explicit_conditions_are_preserved_without_llm_rewrite():
    request = "Completion Condition:\n1. fieldを取得する\n2. statusを確認する"
    called = False

    def chat(**_kwargs):
        nonlocal called
        called = True

    result = decompose_requirements(
        request, chat_fn=chat, model="fake", available_tools=["read_file"]
    )
    assert [row.description for row in result.conditions] == [
        "fieldを取得する", "statusを確認する"
    ]
    assert result.source == "explicit"
    assert not called


def test_validator_detects_duplicates_and_tool_gap():
    duplicate = validate_conditions([
        RequirementCondition("C1", "fileを読む"),
        RequirementCondition("C2", "fileを読む"),
    ], available_tools=["read_file"])
    assert duplicate.status == "AMBIGUOUS"
    gap = validate_conditions([
        RequirementCondition(
            "C1", "正本を読む", source_hint="read_file", source_hint_certainty="CONFIRMED"
        )
    ], available_tools=[])
    assert gap.status == "TOOL_GAP"


def test_source_path_hint_is_validated_as_read_file_capability():
    result = validate_conditions([
        RequirementCondition("C1", "契約を読む", source_hint="docs/contract.md")
    ], available_tools=["read_file"])
    assert result.status == "READY"


def test_action_like_tool_condition_is_detected_and_normalized():
    result = validate_conditions([
        RequirementCondition("C1", "Toolで仕様を確認する")
    ], available_tools=["read_file"])
    assert result.status == "READY"
    assert result.conditions[0].description == "仕様が確認できている"
    assert result.conditions[0].action_like is True
    assert result.conditions[0].action_hint == "Toolで確認"
    assert result.conditions[0].original_description == "Toolで仕様を確認する"


def test_outcome_condition_is_preserved():
    text = "仕様の必須fieldが確認できている"
    result = validate_conditions([RequirementCondition("C1", text)])
    assert result.status == "READY"
    assert result.conditions[0].description == text
    assert result.conditions[0].action_like is False


def test_read_file_method_is_separated_from_partial_outcome():
    result = validate_conditions([
        RequirementCondition("C1", "read_fileでpartial条件を確認する")
    ], available_tools=["read_file"])
    condition = result.conditions[0]
    assert condition.description == "partial条件が確認できている"
    assert condition.action_hint == "read_fileで確認"
    assert condition.action_like is True


def test_action_only_conditions_do_not_become_ready():
    result = validate_conditions([
        RequirementCondition("C1", "ファイルを読む"),
        RequirementCondition("C2", "テストを実行する"),
    ])
    assert result.status == "UNSUPPORTED"
    assert result.conditions == []
    assert len(result.rejected_conditions) == 2


def test_explicit_completion_condition_is_not_rewritten_by_validator():
    text = "read_fileでpartial条件を確認する"
    result = validate_conditions(
        [RequirementCondition("C1", text)],
        available_tools=["read_file"],
        source="explicit",
    )
    assert result.conditions[0].description == text
    assert result.conditions[0].original_description is None


def test_explicit_parser_ignores_non_numbered_prose():
    rows = explicit_conditions("条件:\n1. Aを確認\n2. Bを確認\n補足です")
    assert [row.description for row in rows] == ["Aを確認", "Bを確認"]


def test_validator_rejects_effective_duplicate_and_unknown_dependency():
    duplicate = validate_conditions([
        RequirementCondition("C1", "statusの許可値を確認する"),
        RequirementCondition("C2", "statusの許可値を確認"),
    ])
    assert duplicate.status == "AMBIGUOUS"
    dependency = validate_conditions([
        RequirementCondition("C1", "結果を報告する", dependencies=["C9"])
    ])
    assert dependency.status == "UNSUPPORTED"


def test_local_extraction_rejects_unrequested_standard_and_format_constraints():
    from ai_tool.chat_interface.requirement_decomposition import (
        _drop_unrequested_named_constraints,
        _parse_conditions,
    )

    payload = json.dumps(
        {
            "conditions": [
                {"condition_id": "C1", "description": "現在時刻が実測されている"},
                {"condition_id": "C2", "description": "日時がYYYY-MM-DD HH:MM:SS形式である"},
                {"condition_id": "C3", "description": "タイムゾーンがIANA準拠である"},
            ]
        },
        ensure_ascii=False,
    )
    request = "現在時刻とタイムゾーンを実測する"
    conditions, unrequested = _drop_unrequested_named_constraints(
        request, _parse_conditions(payload)
    )
    result = validate_conditions(conditions, available_tools=["get_system_time"])
    result.rejected_conditions.extend(unrequested)

    assert result.status == "READY"
    assert [row.description for row in result.conditions] == ["現在時刻が実測されている"]
    assert {row.condition_id for row in result.rejected_conditions} == {"C2", "C3"}
