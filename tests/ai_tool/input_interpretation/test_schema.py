import pytest
from ai_tool.input_interpretation.schema import Certainty, EvaluationType, InputEnvelope, ProtectedSpan, RequestIR

def test_input_envelope_keeps_raw_input_verbatim():
    raw = "A.mdをｙｐんで"
    envelope = InputEnvelope("i1", raw)
    assert envelope.raw_input == raw

def test_invalid_protected_span_is_rejected():
    with pytest.raises(ValueError):
        ProtectedSpan(2, 2, "x", "path")

def test_uncertainty_and_evaluation_contracts_are_explicit():
    assert set(Certainty) == {Certainty.KNOWN, Certainty.LIKELY, Certainty.AMBIGUOUS, Certainty.UNKNOWN, Certainty.PROVISIONAL}
    assert set(EvaluationType) == {EvaluationType.HARD_GOLD, EvaluationType.ACCEPTABLE_SET, EvaluationType.RUBRIC, EvaluationType.HUMAN_ADJUDICATED}
    ir = RequestIR(certainty="PROVISIONAL", assumptions=[{"source": "model_inference"}], provisional_fields=["targets"])
    assert ir.certainty != "KNOWN"
    assert ir.assumptions[0]["source"] == "model_inference"
