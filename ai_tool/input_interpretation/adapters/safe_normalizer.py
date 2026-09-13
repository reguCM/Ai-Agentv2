from __future__ import annotations
import time
import unicodedata
from ..schema import AdapterExecution, CandidateType, InputEnvelope, InterpretationCandidate

def normalize_unprotected(envelope: InputEnvelope) -> str:
    output, cursor = [], 0
    for span in sorted(envelope.protected_spans, key=lambda row: row.start):
        if span.start < cursor or envelope.raw_input[span.start:span.end] != span.text:
            raise ValueError("protected span does not match raw input")
        output.extend((unicodedata.normalize("NFKC", envelope.raw_input[cursor:span.start]), span.text))
        cursor = span.end
    output.append(unicodedata.normalize("NFKC", envelope.raw_input[cursor:]))
    return "".join(output)

class SafeNormalizerAdapter:
    adapter_id = "safe_normalizer"
    def availability(self) -> tuple[str, str | None]: return "AVAILABLE", None
    def interpret(self, envelope: InputEnvelope) -> AdapterExecution:
        started = time.perf_counter(); normalized = normalize_unprotected(envelope)
        corrections = [] if normalized == envelope.raw_input else [{"kind": "unicode_nfkc", "safe": True}]
        row = InterpretationCandidate(f"{envelope.input_id}:normalized", self.adapter_id, normalized, CandidateType.NORMALIZED.value, corrections=corrections, confidence=1.0, provenance={"input_id": envelope.input_id, "protected_spans_preserved": True})
        return AdapterExecution(self.adapter_id, "AVAILABLE", [row], latency_ms=(time.perf_counter() - started) * 1000)
