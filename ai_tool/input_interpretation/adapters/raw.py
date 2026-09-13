from __future__ import annotations
import time
from ..schema import AdapterExecution, CandidateType, InputEnvelope, InterpretationCandidate

class RawAdapter:
    adapter_id = "raw"
    def availability(self) -> tuple[str, str | None]: return "AVAILABLE", None
    def interpret(self, envelope: InputEnvelope) -> AdapterExecution:
        started = time.perf_counter()
        row = InterpretationCandidate(f"{envelope.input_id}:raw", self.adapter_id, envelope.raw_input, CandidateType.RAW.value, confidence=1.0, provenance={"input_id": envelope.input_id, "preserves_raw": True})
        return AdapterExecution(self.adapter_id, "AVAILABLE", [row], latency_ms=(time.perf_counter() - started) * 1000)
