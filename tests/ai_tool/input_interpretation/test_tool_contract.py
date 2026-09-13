import pytest
from ai_tool.input_interpretation.schema import AdapterExecution, InputEnvelope, InterpretationCandidate
from ai_tool.input_interpretation.tool_contract import validate_adapter_execution

def test_contract_requires_candidate_provenance():
    envelope = InputEnvelope("i1", "text")
    execution = AdapterExecution("raw", "AVAILABLE", [InterpretationCandidate("c1", "raw", "text", "RAW")])
    with pytest.raises(ValueError, match="provenance"):
        validate_adapter_execution(envelope, execution)

def test_contract_accepts_unavailable_without_candidates():
    validate_adapter_execution(InputEnvelope("i1", "text"), AdapterExecution("optional", "UNAVAILABLE"))
