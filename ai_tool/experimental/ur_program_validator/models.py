"""Result models — PASS/FAIL/WARNING/UNKNOWN, not boolean-only."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal

VerificationStatus = Literal["PASS", "FAIL", "WARNING", "UNKNOWN"]
SuggestionProvenance = Literal["officially_verified", "llm_suggestion", "unknown"]
CompareInterpretation = Literal[
    "expected",
    "possible_over_validation",
    "critical_miss",
    "unknown",
]


class IssueKind(str, Enum):
    SYNTAX = "syntax"
    UNKNOWN_FUNCTION = "unknown_function"
    ARG_COUNT = "arg_count"
    TYPE = "type"
    VERSION = "version"
    UNSUPPORTED = "unsupported"
    PYTHON_CONFUSION = "python_confusion"


@dataclass
class ValidationIssue:
    kind: IssueKind
    status: VerificationStatus
    message: str
    line: int = 0
    function: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class ValidationResult:
    status: VerificationStatus
    issues: list[ValidationIssue] = field(default_factory=list)
    version_context: dict[str, str] = field(default_factory=dict)
    provenance: list[dict[str, str]] = field(default_factory=list)
    not_validated: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "version_context": self.version_context,
            "provenance": self.provenance,
            "not_validated": self.not_validated,
        }


@dataclass
class URSimResult:
    status: VerificationStatus
    executed: bool
    mode: Literal["live", "stub", "manual", "unavailable"]
    message: str
    errors: list[str] = field(default_factory=list)
    automation_level: Literal["manual", "semi_auto", "auto", "none"] = "none"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompareResult:
    validator_status: VerificationStatus
    ur_sim_status: VerificationStatus
    interpretation: CompareInterpretation
    note: str
    test_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FixSuggestion:
    original: str
    suggestion: str
    provenance: SuggestionProvenance
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
