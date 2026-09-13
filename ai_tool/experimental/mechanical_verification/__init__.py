"""Mechanical Verification — experimental capability (Production-independent).

Verifies LLM claims against Evidence using deterministic rules.
Does NOT replace LLM answers or connect to Production main path.
"""
from __future__ import annotations

from ai_tool.experimental.mechanical_verification.verifier import (
    MechanicalVerificationReport,
    VerificationResult,
    VerificationVerdict,
    extract_heuristic_evidence_facts,
    verify_answer,
)

__all__ = [
    "MechanicalVerificationReport",
    "VerificationResult",
    "VerificationVerdict",
    "extract_heuristic_evidence_facts",
    "verify_answer",
]
