"""Dependency-light orchestration for comparing interpretation adapters."""
from __future__ import annotations

import re
import time
import uuid
from collections.abc import Sequence

from .adapters import LLMLinguaAdapter, RawAdapter, SafeNormalizerAdapter, SudachiAdapter
from .profiles import get_profile
from .schema import (
    Certainty, CompactionAction, CompactionDecision, InputEnvelope, InterpretationCandidate,
    InterpretationResult, ProtectedSpan, RequestIR, SemanticSelection,
)
from .tool_contract import SemanticComparator, validate_adapter_execution

_PROTECTED = re.compile(
    r"https?://[^\s]+|(?:[A-Za-z]:[\\/]|\.?\.?[\\/])[^\s\"'`]+|"
    r"[A-Za-z0-9_.-]+[/\\][A-Za-z0-9_./\\-]+|[A-Za-z0-9_.-]+\.(?:md|json|py|txt)|"
    r"`[^`]+`|\"[^\"]+\"|'[^']+'"
)


def detect_protected_spans(text: str) -> list[ProtectedSpan]:
    spans: list[ProtectedSpan] = []
    for match in _PROTECTED.finditer(text):
        value = match.group(0)
        kind = "url" if value.startswith(("http://", "https://")) else "quoted" if value[:1] in {'"', "'", "`"} else "path_or_id"
        spans.append(ProtectedSpan(match.start(), match.end(), value, kind))
    return spans


def _target_rows(text: str) -> list[dict[str, str]]:
    values = [m.group(0).strip("`\"'.,。") for m in _PROTECTED.finditer(text)]
    return [{"value": value, "type": "path" if ("/" in value or "\\" in value or "." in value) else "text"} for value in dict.fromkeys(values)]


class ConservativeComparator:
    """Deterministic v1 baseline. Its output is a semantic proposal, never an action."""

    def select(self, envelope: InputEnvelope, candidates: Sequence[InterpretationCandidate]) -> tuple[SemanticSelection, RequestIR]:
        preferred = next((c for c in candidates if c.source_tool == "safe_normalizer"), candidates[0])
        text = preferred.text
        targets = _target_rows(text)
        operations: list[str] = []
        # These broad stems are benchmark baselines, not production routing rules.
        if any(stem in text for stem in ("読", "よん", "よむ")):
            operations.append("READ")
        if "呼" in text and "文章" in text:
            operations.append("READ")
        if "呼" in text and "関数" in text:
            operations = [op for op in operations if op != "READ"] + ["CALL"]
        if any(stem in text for stem in ("削除しない", "変更しない", "実行しない")):
            negations = [part for part in re.split(r"[。\n]", text) if "ない" in part]
        else:
            negations = []
        order = operations.copy() if any(mark in text for mark in ("最初", "その後", "順")) else []
        constraints = [part.strip() for part in re.split(r"[。\n]", text) if any(mark in part for mark in ("ただし", "最初", "その後", "しない")) and part.strip()]
        output = ["SUMMARY"] if "要約" in text else []
        referential_ambiguity = any(word in text for word in ("それ", "そこ", "こっち", "そっち")) and len(targets) > 1
        provisional = referential_ambiguity and any(word in text for word in ("仮で", "仮に", "ひとまず"))
        ambiguities = (["referent_has_multiple_candidates"] if referential_ambiguity else []) or ([] if operations else ["operation_not_determined"])
        certainty = Certainty.PROVISIONAL.value if provisional else Certainty.AMBIGUOUS.value if referential_ambiguity else Certainty.KNOWN.value if operations else Certainty.UNKNOWN.value
        candidate_interpretations = [{"target": row["value"]} for row in targets] if referential_ambiguity else []
        assumptions = ([{"field": "targets", "value": targets[0]["value"], "source": "model_inference"}] if provisional and targets else [])
        selection = SemanticSelection(
            selected_candidate_ids=[preferred.candidate_id], interpreted_text=text,
            needs_clarification=(not operations or referential_ambiguity) and not provisional,
            confidence=0.5 if referential_ambiguity else 0.8 if operations else 0.3,
            ambiguities=ambiguities, certainty=certainty, assumptions=assumptions,
            provisional_fields=["targets"] if provisional else [],
            clarification_questions=["どの対象を指していますか？"] if referential_ambiguity and not provisional else [],
            candidate_interpretations=candidate_interpretations,
            ambiguity_reason="multiple targets for an anaphoric reference" if referential_ambiguity else None,
        )
        ir = RequestIR(
            intents=["workspace_observation"] if "READ" in operations else ["function_invocation"] if "CALL" in operations else [],
            targets=targets, operations=operations, operation_order=order,
            constraints=constraints, negations=negations, output_requirements=output,
            ambiguities=ambiguities,
            source_provenance={"input_id": envelope.input_id, "candidate_ids": selection.selected_candidate_ids, "semantic_proposal": True},
            certainty=certainty, assumptions=assumptions,
            provisional_fields=list(selection.provisional_fields),
            needs_clarification=selection.needs_clarification,
            clarification_questions=list(selection.clarification_questions),
            candidate_interpretations=candidate_interpretations,
            ambiguity_reason=selection.ambiguity_reason,
        )
        return selection, ir


class InputInterpretationPlayground:
    def __init__(self, *, adapters=None, comparator: SemanticComparator | None = None) -> None:
        self.adapters = adapters or {a.adapter_id: a for a in (RawAdapter(), SafeNormalizerAdapter(), SudachiAdapter(), LLMLinguaAdapter())}
        self.comparator = comparator or ConservativeComparator()

    def interpret(self, raw_input: str, *, profile_id: str = "all", input_id: str | None = None, metadata=None, adapter_ids: Sequence[str] | None = None) -> InterpretationResult:
        started = time.perf_counter()
        envelope = InputEnvelope(input_id or f"ii-{uuid.uuid4().hex[:12]}", raw_input, profile_ids=[profile_id], protected_spans=detect_protected_spans(raw_input), metadata=dict(metadata or {}))
        executions, candidates, compact = [], [], []
        selected_adapters = tuple(adapter_ids) if adapter_ids is not None else get_profile(profile_id).adapter_ids
        for adapter_id in selected_adapters:
            execution = self.adapters[adapter_id].interpret(envelope)
            validate_adapter_execution(envelope, execution)
            executions.append(execution); candidates.extend(execution.candidates); compact.extend(execution.compaction)
        if not candidates:
            raise RuntimeError("no interpretation candidate was produced")
        selection, request_ir = self.comparator.select(envelope, candidates)
        known_ids = {row.candidate_id for row in candidates}
        if any(row not in known_ids for row in selection.selected_candidate_ids):
            raise ValueError("semantic comparator selected an unknown candidate")
        if not selection.none_of_the_above and not selection.selected_candidate_ids:
            raise ValueError("selection must select, fuse, or explicitly choose none")
        working = selection.interpreted_text
        metrics = {
            "raw_characters": len(raw_input), "working_characters": len(working),
            "raw_tokens_estimated": max(1, len(raw_input) // 3), "working_tokens_estimated": max(1, len(working) // 3),
            "reduction_ratio": 0.0 if not raw_input else round(1 - len(working) / len(raw_input), 4),
            "processing_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        return InterpretationResult(envelope, executions, candidates, compact, selection, request_ir, metrics)


def conservative_compaction_candidates(text: str, *, input_id: str) -> list[CompactionDecision]:
    """Diagnose obvious redundancy without applying destructive compression."""
    rows, seen, result = [row.strip() for row in text.splitlines() if row.strip()], set(), []
    for row in rows:
        action = CompactionAction.SUPPRESS.value if row in seen else CompactionAction.KEEP.value
        result.append(CompactionDecision(row, action, "exact duplicate" if row in seen else "meaning-bearing or first occurrence", {"input_id": input_id}))
        seen.add(row)
    return result
