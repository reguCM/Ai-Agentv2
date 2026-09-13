from ai_tool.input_interpretation.adapters.safe_normalizer import normalize_unprotected
from ai_tool.input_interpretation.adapters.llmlingua_adapter import LLMLinguaAdapter
from ai_tool.input_interpretation.playground import InputInterpretationPlayground, detect_protected_spans
from ai_tool.input_interpretation.schema import InputEnvelope, InterpretationCandidate, RequestIR, SemanticSelection

def test_protected_path_is_not_normalized():
    raw = "次は `Ａ／Ｂ.md` を読んで"
    spans = detect_protected_spans(raw)
    envelope = InputEnvelope("i1", raw, protected_spans=spans)
    assert "`Ａ／Ｂ.md`" in normalize_unprotected(envelope)

def test_all_adapters_share_one_harness_and_optional_adapters_fail_closed():
    result = InputInterpretationPlayground().interpret("A.mdを読んで", input_id="i1")
    availability = {row.adapter_id: row.availability for row in result.adapter_executions}
    assert availability["raw"] == availability["safe_normalizer"] == "AVAILABLE"
    assert availability["sudachi"] in {"AVAILABLE", "UNAVAILABLE", "ERROR"}
    assert availability["llmlingua"] == "UNAVAILABLE"
    assert result.envelope.raw_input == "A.mdを読んで"

class NoneComparator:
    def select(self, envelope, candidates):
        return SemanticSelection(none_of_the_above=True, needs_clarification=True), RequestIR(ambiguities=["none"])

def test_comparator_can_choose_none_of_the_above():
    result = InputInterpretationPlayground(comparator=NoneComparator()).interpret("???", profile_id="baseline")
    assert result.semantic_selection.none_of_the_above is True
    assert result.request_ir.ambiguities == ["none"]

class InvalidComparator:
    def select(self, envelope, candidates):
        return SemanticSelection(selected_candidate_ids=["fabricated"]), RequestIR()

def test_comparator_cannot_fabricate_candidate_identity():
    import pytest
    with pytest.raises(ValueError, match="unknown candidate"):
        InputInterpretationPlayground(comparator=InvalidComparator()).interpret("text", profile_id="baseline")

class FakeCompressor:
    def compress_prompt(self, context, **kwargs):
        assert kwargs["strict_preserve_uncompressed"] is True
        return {"compressed_prompt": "A.mdを読む", "origin_tokens": 10, "compressed_tokens": 5, "rate": "50%"}

def test_llmlingua_configured_output_is_candidate_not_canonical():
    adapter = LLMLinguaAdapter(FakeCompressor(), model_name="fake", device="cpu")
    # Dependency discovery is deliberately replaced for deterministic testing.
    adapter.availability = lambda: ("AVAILABLE", None)
    result = adapter.interpret(InputEnvelope("i1", "A.mdを実際に読んで"))
    assert result.availability == "AVAILABLE"
    assert result.candidates[0].text == "A.mdを読む"
    assert result.candidates[0].provenance["canonical"] is False
    assert result.compaction[0].action == "UNCERTAIN"
