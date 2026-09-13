"""Ollama semantic comparator for the isolated playground."""
from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any, Callable

from .schema import Certainty, InputEnvelope, InterpretationCandidate, RequestIR, SemanticSelection

_CERTAINTY = [row.value for row in Certainty]
COMPARATOR_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["semantic_selection", "request_ir"],
    "properties": {
        "semantic_selection": {
            "type": "object",
            "required": ["selected_candidate_ids", "interpreted_text", "fusion_used", "none_of_the_above", "needs_clarification", "certainty", "ambiguities", "assumptions", "unknowns", "provisional_fields", "clarification_questions", "candidate_interpretations"],
            "properties": {
                "selected_candidate_ids": {"type": "array", "items": {"type": "string"}},
                "interpreted_text": {"type": "string"}, "fusion_used": {"type": "boolean"},
                "none_of_the_above": {"type": "boolean"}, "needs_clarification": {"type": "boolean"},
                "certainty": {"type": "string", "enum": _CERTAINTY},
                "confidence": {"type": ["number", "null"]},
                "ambiguities": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "object"}},
                "unknowns": {"type": "array", "items": {"type": "string"}},
                "provisional_fields": {"type": "array", "items": {"type": "string"}},
                "clarification_questions": {"type": "array", "items": {"type": "string"}},
                "candidate_interpretations": {"type": "array", "items": {"type": "object"}},
                "ambiguity_reason": {"type": ["string", "null"]},
            },
        },
        "request_ir": {
            "type": "object",
            "required": ["intents", "targets", "operations", "operation_order", "constraints", "conditions", "negations", "output_requirements", "ambiguities", "certainty", "assumptions", "unknowns", "provisional_fields", "needs_clarification", "clarification_questions", "candidate_interpretations"],
            "properties": {
                "intents": {"type": "array", "items": {"type": "string"}},
                "targets": {"type": "array", "items": {"type": "object"}},
                "operations": {"type": "array", "items": {"type": "string"}},
                "operation_order": {"type": "array", "items": {"type": "string"}},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "conditions": {"type": "array", "items": {"type": "string"}},
                "negations": {"type": "array", "items": {"type": "string"}},
                "output_requirements": {"type": "array", "items": {"type": "string"}},
                "ambiguities": {"type": "array", "items": {"type": "string"}},
                "certainty": {"type": "string", "enum": _CERTAINTY},
                "assumptions": {"type": "array", "items": {"type": "object"}},
                "unknowns": {"type": "array", "items": {"type": "string"}},
                "provisional_fields": {"type": "array", "items": {"type": "string"}},
                "needs_clarification": {"type": "boolean"},
                "clarification_questions": {"type": "array", "items": {"type": "string"}},
                "candidate_interpretations": {"type": "array", "items": {"type": "object"}},
                "ambiguity_reason": {"type": ["string", "null"]},
            },
        },
    },
}

_SYSTEM = """You compare alternative views of one Japanese user input and propose a RequestIR.
The RAW candidate is always preserved and is authoritative for what the user actually wrote. Other candidates are diagnostic proposals, never truth.
Do not invent a unique intent when the input is ambiguous. Use AMBIGUOUS or UNKNOWN and needs_clarification=true.
If the user explicitly permits a temporary assumption, use PROVISIONAL, record the assumption and its source, and never label it KNOWN.
Preserve targets, paths, code, URLs, negation, prohibitions, permissions, conditions, operation order, and output requirements.
You may select candidates, fuse them, or choose none_of_the_above. Return only the specified JSON object. RequestIR is a semantic proposal, not an execution command."""


class OllamaSemanticComparator:
    def __init__(self, *, chat_fn: Callable[..., Any], model: str, view_id: str, candidate_diagnostics: dict[str, Any] | None = None) -> None:
        self.chat_fn = chat_fn; self.model = model; self.view_id = view_id
        self.candidate_diagnostics = candidate_diagnostics or {}; self.calls: list[dict[str, Any]] = []

    def select(self, envelope: InputEnvelope, candidates: Sequence[InterpretationCandidate]) -> tuple[SemanticSelection, RequestIR]:
        packet = {
            "input_id": envelope.input_id, "input_view": self.view_id,
            "raw_input": envelope.raw_input,
            "protected_spans": [vars(row) for row in envelope.protected_spans],
            "candidates": [{"candidate_id": row.candidate_id, "source_tool": row.source_tool, "candidate_type": row.candidate_type, "text": row.text, "uncertainties": row.uncertainties, "provenance": row.provenance} for row in candidates],
            "candidate_diagnostics": self.candidate_diagnostics.get(envelope.input_id, {}),
        }
        started = time.perf_counter()
        response = self.chat_fn(model=self.model, messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}], tools=[], format=COMPARATOR_OUTPUT_SCHEMA, execution_profile="structured_output", options={"temperature": 0, "num_predict": 1800})
        elapsed = (time.perf_counter() - started) * 1000
        message = getattr(response, "message", None); content = getattr(message, "content", None)
        if not content: raise ValueError("LLM comparator returned empty content")
        payload = json.loads(str(content)); selection_data = payload["semantic_selection"]; ir_data = payload["request_ir"]
        known = {row.candidate_id for row in candidates}; selected = list(selection_data.get("selected_candidate_ids") or [])
        if any(row not in known for row in selected): raise ValueError("LLM comparator selected an unknown candidate")
        if not selected and not selection_data.get("none_of_the_above"): raise ValueError("LLM comparator must select, fuse, or choose none")
        certainty = str(selection_data.get("certainty") or "UNKNOWN")
        if certainty not in _CERTAINTY or str(ir_data.get("certainty") or "UNKNOWN") not in _CERTAINTY: raise ValueError("invalid certainty")
        if certainty == "PROVISIONAL" and (not selection_data.get("assumptions") or not selection_data.get("provisional_fields")): raise ValueError("PROVISIONAL requires assumptions and provisional_fields")
        selection = SemanticSelection(**{key: selection_data.get(key) for key in SemanticSelection.__dataclass_fields__ if key in selection_data})
        ir_data["source_provenance"] = {"input_id": envelope.input_id, "candidate_ids": selected, "semantic_proposal": True, "model": self.model, "view_id": self.view_id}
        request_ir = RequestIR(**{key: ir_data.get(key) for key in RequestIR.__dataclass_fields__ if key in ir_data})
        prompt_chars = len(_SYSTEM) + len(json.dumps(packet, ensure_ascii=False))
        self.calls.append({"input_id": envelope.input_id, "model": self.model, "view_id": self.view_id, "elapsed_ms": round(elapsed, 3), "input_characters": prompt_chars, "input_tokens_estimated": max(1, prompt_chars // 3), "output_characters": len(str(content)), "output_tokens_estimated": max(1, len(str(content)) // 3), "selected_candidate_sources": [row.source_tool for row in candidates if row.candidate_id in selected], "none_of_the_above": bool(selection.none_of_the_above), "needs_clarification": bool(selection.needs_clarification)})
        return selection, request_ir
