from __future__ import annotations
import importlib.util
import time
from ..schema import AdapterExecution, CandidateType, InputEnvelope, InterpretationCandidate

class SudachiAdapter:
    adapter_id = "sudachi"
    def availability(self) -> tuple[str, str | None]:
        return ("AVAILABLE", None) if importlib.util.find_spec("sudachipy") else ("UNAVAILABLE", "SudachiPy is not installed")
    def interpret(self, envelope: InputEnvelope) -> AdapterExecution:
        started = time.perf_counter(); status, detail = self.availability()
        if status != "AVAILABLE": return AdapterExecution(self.adapter_id, status, latency_ms=(time.perf_counter() - started) * 1000, detail=detail)
        try:
            from sudachipy import Dictionary  # type: ignore[import-not-found]
            analysis = [{"surface": t.surface(), "lemma": t.dictionary_form(), "reading": t.reading_form(), "normalized": t.normalized_form()} for t in Dictionary().create().tokenize(envelope.raw_input)]
            row = InterpretationCandidate(f"{envelope.input_id}:sudachi", self.adapter_id, envelope.raw_input, CandidateType.ANALYSIS.value, provenance={"input_id": envelope.input_id, "analysis": analysis, "rewrites_raw": False})
            return AdapterExecution(self.adapter_id, "AVAILABLE", [row], latency_ms=(time.perf_counter() - started) * 1000)
        except Exception as exc:
            return AdapterExecution(self.adapter_id, "ERROR", latency_ms=(time.perf_counter() - started) * 1000, detail=f"{type(exc).__name__}: {exc}")
