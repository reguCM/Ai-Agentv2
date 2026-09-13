from __future__ import annotations
import importlib.util
import time
from ..schema import AdapterExecution, CandidateType, CompactionDecision, InputEnvelope, InterpretationCandidate

class LLMLinguaAdapter:
    adapter_id = "llmlingua"
    def __init__(self, compressor=None, *, rate: float = 0.7, model_name: str | None = None, device: str = "cpu") -> None:
        self.compressor = compressor
        self.rate = rate
        self.model_name = model_name
        self.device = device
    def availability(self) -> tuple[str, str | None]:
        if self.compressor is not None: return "AVAILABLE", None
        if not importlib.util.find_spec("llmlingua"): return "UNAVAILABLE", "LLMLingua is not installed"
        return "UNAVAILABLE", "library detected; compressor model is not configured"
    def interpret(self, envelope: InputEnvelope) -> AdapterExecution:
        started = time.perf_counter(); status, detail = self.availability()
        if status != "AVAILABLE":
            return AdapterExecution(self.adapter_id, status, latency_ms=(time.perf_counter() - started) * 1000, detail=detail)
        try:
            payload = self.compressor.compress_prompt(
                [envelope.raw_input], rate=self.rate,
                force_tokens=[span.text for span in envelope.protected_spans],
                strict_preserve_uncompressed=True,
            )
            compressed = str(payload.get("compressed_prompt") or "")
            candidate = InterpretationCandidate(
                candidate_id=f"{envelope.input_id}:llmlingua",
                source_tool=self.adapter_id, text=compressed,
                candidate_type=CandidateType.COMPRESSED.value,
                uncertainties=[] if compressed else ["empty_compression_output"],
                confidence=None,
                provenance={
                    "input_id": envelope.input_id, "canonical": False,
                    "model_name": self.model_name, "device": self.device,
                    "rate": self.rate, "origin_tokens": payload.get("origin_tokens"),
                    "compressed_tokens": payload.get("compressed_tokens"),
                    "library_payload": {key: value for key, value in payload.items() if key not in {"compressed_prompt", "compressed_prompt_list"}},
                },
            )
            decision = CompactionDecision(envelope.raw_input, "UNCERTAIN", "external compression candidate; semantic preservation requires evaluation", {"input_id": envelope.input_id, "candidate_id": candidate.candidate_id})
            return AdapterExecution(self.adapter_id, "AVAILABLE", [candidate], [decision], (time.perf_counter() - started) * 1000)
        except Exception as exc:
            return AdapterExecution(self.adapter_id, "ERROR", latency_ms=(time.perf_counter() - started) * 1000, detail=f"{type(exc).__name__}: {exc}")
