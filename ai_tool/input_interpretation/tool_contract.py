from __future__ import annotations
from typing import Protocol, Sequence
from .schema import AdapterExecution, InputEnvelope, InterpretationCandidate, RequestIR, SemanticSelection

class InterpretationAdapter(Protocol):
    adapter_id: str
    def availability(self) -> tuple[str, str | None]: ...
    def interpret(self, envelope: InputEnvelope) -> AdapterExecution: ...

class SemanticComparator(Protocol):
    def select(self, envelope: InputEnvelope, candidates: Sequence[InterpretationCandidate]) -> tuple[SemanticSelection, RequestIR]: ...

def validate_adapter_execution(envelope: InputEnvelope, execution: AdapterExecution) -> None:
    if execution.availability not in {"AVAILABLE", "UNAVAILABLE", "ERROR"}:
        raise ValueError("invalid adapter availability")
    for candidate in execution.candidates:
        if candidate.source_tool != execution.adapter_id:
            raise ValueError("candidate source_tool does not match adapter")
        if candidate.provenance.get("input_id") != envelope.input_id:
            raise ValueError("candidate provenance must reference the input envelope")
