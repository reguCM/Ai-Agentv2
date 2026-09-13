import json
from types import SimpleNamespace

import pytest

from ai_tool.input_interpretation.llm_comparator import COMPARATOR_OUTPUT_SCHEMA, OllamaSemanticComparator
from ai_tool.input_interpretation.playground import InputInterpretationPlayground


def response(payload):
    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))


def valid_payload(candidate_id="i1:raw", *, certainty="KNOWN"):
    return {
        "semantic_selection": {
            "selected_candidate_ids": [candidate_id], "interpreted_text": "A.mdを読んで", "fusion_used": False,
            "none_of_the_above": False, "needs_clarification": False, "certainty": certainty, "confidence": 0.9,
            "ambiguities": [], "assumptions": [], "unknowns": [], "provisional_fields": [],
            "clarification_questions": [], "candidate_interpretations": [], "ambiguity_reason": None,
        },
        "request_ir": {
            "intents": ["workspace_observation"], "targets": [{"value": "A.md", "type": "path"}],
            "operations": ["READ"], "operation_order": [], "constraints": [], "conditions": [], "negations": [],
            "output_requirements": [], "ambiguities": [], "certainty": certainty, "assumptions": [], "unknowns": [],
            "provisional_fields": [], "needs_clarification": False, "clarification_questions": [],
            "candidate_interpretations": [], "ambiguity_reason": None,
        },
    }


def test_real_comparator_contract_uses_structured_output_and_keeps_proposal_boundary():
    observed = {}
    def fake_chat(**kwargs):
        observed.update(kwargs)
        return response(valid_payload())
    comparator = OllamaSemanticComparator(chat_fn=fake_chat, model="fake", view_id="RAW")
    result = InputInterpretationPlayground(comparator=comparator).interpret("A.mdを読んで", profile_id="baseline", input_id="i1", adapter_ids=("raw",))
    assert observed["format"] == COMPARATOR_OUTPUT_SCHEMA
    assert observed["execution_profile"] == "structured_output" and observed["tools"] == []
    assert result.request_ir.source_provenance["semantic_proposal"] is True
    assert result.request_ir.source_provenance["view_id"] == "RAW"
    assert comparator.calls[0]["selected_candidate_sources"] == ["raw"]


def test_comparator_rejects_fabricated_candidate():
    comparator = OllamaSemanticComparator(chat_fn=lambda **_: response(valid_payload("fake-id")), model="fake", view_id="RAW")
    with pytest.raises(ValueError, match="unknown candidate"):
        InputInterpretationPlayground(comparator=comparator).interpret("A.mdを読んで", input_id="i1", adapter_ids=("raw",))


def test_provisional_requires_assumption_and_provisional_field():
    payload = valid_payload(certainty="PROVISIONAL")
    comparator = OllamaSemanticComparator(chat_fn=lambda **_: response(payload), model="fake", view_id="RAW")
    with pytest.raises(ValueError, match="PROVISIONAL"):
        InputInterpretationPlayground(comparator=comparator).interpret("仮にA.md", input_id="i1", adapter_ids=("raw",))


def test_none_of_the_above_is_allowed_without_selected_candidate():
    payload = valid_payload(); payload["semantic_selection"].update(selected_candidate_ids=[], none_of_the_above=True, certainty="UNKNOWN", needs_clarification=True)
    payload["request_ir"].update(certainty="UNKNOWN", needs_clarification=True)
    comparator = OllamaSemanticComparator(chat_fn=lambda **_: response(payload), model="fake", view_id="RAW")
    result = InputInterpretationPlayground(comparator=comparator).interpret("不明", input_id="i1", adapter_ids=("raw",))
    assert result.semantic_selection.none_of_the_above is True
