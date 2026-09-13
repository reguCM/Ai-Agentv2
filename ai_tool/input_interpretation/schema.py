"""Canonical, serialization-friendly interpretation contracts."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

class CandidateType(str, Enum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    ANALYSIS = "ANALYSIS"
    COMPRESSED = "COMPRESSED"

class CompactionAction(str, Enum):
    KEEP = "KEEP"
    SUPPRESS = "SUPPRESS"
    MERGE = "MERGE"
    REPLACE = "REPLACE"
    UNCERTAIN = "UNCERTAIN"

class Certainty(str, Enum):
    KNOWN = "KNOWN"
    LIKELY = "LIKELY"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    PROVISIONAL = "PROVISIONAL"

class EvaluationType(str, Enum):
    HARD_GOLD = "HARD_GOLD"
    ACCEPTABLE_SET = "ACCEPTABLE_SET"
    RUBRIC = "RUBRIC"
    HUMAN_ADJUDICATED = "HUMAN_ADJUDICATED"

class RequirementImportance(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    OPTIONAL = "OPTIONAL"

@dataclass(frozen=True)
class ProtectedSpan:
    start: int
    end: int
    text: str
    kind: str
    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start or not self.text:
            raise ValueError("protected span must have a valid non-empty range")

@dataclass
class InputEnvelope:
    input_id: str
    raw_input: str
    input_mode: str = "text"
    profile_ids: list[str] = field(default_factory=list)
    protected_spans: list[ProtectedSpan] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        if not self.input_id or not isinstance(self.raw_input, str):
            raise ValueError("input_id and raw_input are required")

@dataclass
class InterpretationCandidate:
    candidate_id: str
    source_tool: str
    text: str
    candidate_type: str
    corrections: list[dict[str, Any]] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    confidence: float | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

@dataclass
class CompactionDecision:
    target_span: str
    action: str
    reason: str
    provenance: dict[str, Any] = field(default_factory=dict)

@dataclass
class SemanticSelection:
    selected_candidate_ids: list[str] = field(default_factory=list)
    interpreted_text: str = ""
    fusion_used: bool = False
    none_of_the_above: bool = False
    needs_clarification: bool = False
    confidence: float | None = None
    ambiguities: list[str] = field(default_factory=list)
    certainty: str = Certainty.UNKNOWN.value
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    provisional_fields: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    candidate_interpretations: list[dict[str, Any]] = field(default_factory=list)
    ambiguity_reason: str | None = None

@dataclass
class RequestIR:
    intents: list[str] = field(default_factory=list)
    targets: list[dict[str, Any]] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    operation_order: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    negations: list[str] = field(default_factory=list)
    output_requirements: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    source_provenance: dict[str, Any] = field(default_factory=dict)
    certainty: str = Certainty.UNKNOWN.value
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    provisional_fields: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: list[str] = field(default_factory=list)
    candidate_interpretations: list[dict[str, Any]] = field(default_factory=list)
    ambiguity_reason: str | None = None

@dataclass
class RubricRequirement:
    field: str
    expected: Any
    importance: str
    weight: float

@dataclass
class BenchmarkCase:
    case_id: str
    level: str
    evaluation_type: str
    input: str
    expected_request_ir: dict[str, Any] = field(default_factory=dict)
    acceptable_interpretations: list[dict[str, Any]] = field(default_factory=list)
    forbidden_interpretations: list[dict[str, Any]] = field(default_factory=list)
    critical_requirements: list[RubricRequirement] = field(default_factory=list)
    rubric: list[RubricRequirement] = field(default_factory=list)
    clarification_expected: bool | None = None
    provisional_expected: bool | None = None
    pair_id: str | None = None

@dataclass
class AdapterExecution:
    adapter_id: str
    availability: str
    candidates: list[InterpretationCandidate] = field(default_factory=list)
    compaction: list[CompactionDecision] = field(default_factory=list)
    latency_ms: float = 0.0
    detail: str | None = None

@dataclass
class InterpretationResult:
    envelope: InputEnvelope
    adapter_executions: list[AdapterExecution]
    candidates: list[InterpretationCandidate]
    compaction: list[CompactionDecision]
    semantic_selection: SemanticSelection
    request_ir: RequestIR
    metrics: dict[str, Any] = field(default_factory=dict)
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
