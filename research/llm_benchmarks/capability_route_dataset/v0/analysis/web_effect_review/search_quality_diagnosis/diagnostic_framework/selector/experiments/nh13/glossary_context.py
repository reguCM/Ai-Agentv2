"""NH13 glossary context builders — mechanical, no LLM term selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parents[2]
GLOSSARY_DIR = FRAMEWORK / "knowledge_base" / "glossary"
GLOSSARY_JSON = GLOSSARY_DIR / "glossary.json"

# Mechanical per-case relevant terms (Condition D). LLM does not choose.
CASE_RELEVANT_TERMS: dict[str, list[str]] = {
    "NH5-A": [
        "Observation", "Fingerprint", "Mechanical Mapping", "Ranking", "Filter", "Route",
        "stdout", "Evidence", "UNKNOWN", "Small LLM", "Selector",
    ],
    "NH5-B": [
        "Observation", "stdout", "LLM handoff", "Ranking", "Filter", "Route",
        "Mechanical Mapping", "Evidence", "UNKNOWN",
    ],
    "NH5-C": [
        "State", "ACTIVE", "SUPERSEDED", "Goal", "Claim", "Hypothesis",
        "Validator", "Evidence", "UNKNOWN", "Change Request",
    ],
    "NH5-D": [
        "State", "REOPEN", "ACTIVE", "SUPERSEDED", "Evidence", "Validator",
        "Goal", "Claim", "UNKNOWN",
    ],
    "NH5-E": [
        "State", "REOPEN", "Evidence", "Validator", "Claim", "Hypothesis",
        "INFERENCE", "UNKNOWN", "False Accept",
    ],
    "NH5-F": [
        "State", "ACTIVE", "SUPERSEDED", "Goal", "Validator", "Evidence",
        "UNKNOWN", "False Accept",
    ],
    "NH5-G": [
        "State", "Goal", "ACTIVE", "SUPERSEDED", "Validator", "Evidence",
        "UNKNOWN", "Claim",
    ],
    "NH5-H": [
        "Observation", "UNKNOWN", "Evidence", "INFERENCE", "stdout",
        "Small LLM", "Gate", "HUMAN_REVIEW",
    ],
    "NH5-I": [
        "Observation", "stdout", "LLM handoff", "Small LLM", "UNKNOWN",
        "Evidence", "INFERENCE", "Safety", "Accuracy",
    ],
    "NH5-J": [
        "Observation", "LLM handoff", "stdout", "Ranking", "Filter",
        "Small LLM", "Large LLM", "Gate", "UNKNOWN", "Safety",
    ],
}

ROLE_CONTEXT_ENTRIES: list[dict[str, str]] = [
    {
        "term": "Observation",
        "generates": "fixed observation slots from materials",
        "consumes": "problem materials (log, code, summary)",
        "must_not": "generate Fingerprint, select methods, or auto-fix",
    },
    {
        "term": "Fingerprint",
        "generates": "feature dict for Selector (mechanical only)",
        "consumes": "Observation slots via Mechanical Mapping",
        "must_not": "be output directly by Small LLM",
    },
    {
        "term": "Selector",
        "generates": "diagnostic method ID",
        "consumes": "Fingerprint features",
        "must_not": "observe materials or validate safety alone",
    },
    {
        "term": "Gate",
        "generates": "escalation level (LOW/HIGH/UNKNOWN)",
        "consumes": "slots + materials hints",
        "must_not": "be decided by LLM; not the same as Validator",
    },
    {
        "term": "Validator",
        "generates": "pass/fail on state transitions and evidence",
        "consumes": "State change requests + evidence objects",
        "must_not": "select diagnostic methods or replace Gate",
    },
    {
        "term": "Small LLM",
        "generates": "Observation slots only",
        "consumes": "materials + optional glossary context",
        "must_not": "run full diagnosis, Large LLM tasks, or production fixes",
    },
    {
        "term": "Large LLM",
        "generates": "corrections for HIGH slots only",
        "consumes": "materials + small slots + allowed slot list",
        "must_not": "full re-diagnosis or Fingerprint generation",
    },
    {
        "term": "HUMAN_REVIEW",
        "generates": "safety stop signal",
        "consumes": "remaining HIGH uncertainty",
        "must_not": "be treated as failure or auto-bypassed",
    },
    {
        "term": "Evidence",
        "generates": "citation or 4-class label",
        "consumes": "material quotes",
        "must_not": "be invented without material support",
    },
    {
        "term": "Mechanical Mapping",
        "generates": "Fingerprint features",
        "consumes": "Observation slots",
        "must_not": "use LLM inference",
    },
]


def load_glossary() -> dict[str, Any]:
    return json.loads(GLOSSARY_JSON.read_text(encoding="utf-8"))


def terms_by_name(glossary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["term"]: t for t in glossary.get("terms", [])}


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def glossary_block_for_terms(terms: list[str], glossary: dict[str, Any] | None = None) -> str:
    by_name = terms_by_name(glossary or load_glossary())
    lines = ["## Project glossary (relevant terms)\n"]
    for name in terms:
        t = by_name.get(name)
        if not t:
            continue
        ja = (t.get("aliases") or [""])[0]
        lines.append(f"### {t['term']} ({ja})")
        lines.append(t.get("human_definition", ""))
        lines.append("")
    return "\n".join(lines)


def build_definition_only(glossary: dict[str, Any] | None = None) -> str:
    glossary = glossary or load_glossary()
    lines = ["## Project term definitions (definition + role only)\n"]
    for t in glossary.get("terms", []):
        ja = (t.get("aliases") or [""])[0]
        lines.append(f"TERM: {t['term']}")
        lines.append(f"日本語名: {ja}")
        lines.append(f"DEFINITION: {t.get('human_definition', '')}")
        lines.append(f"ROLE: {t.get('role', '')}")
        lines.append("")
    return "\n".join(lines)


def build_boundary_do_not(glossary: dict[str, Any] | None = None) -> str:
    glossary = glossary or load_glossary()
    lines = ["## Project boundaries (DO / DO NOT)\n"]
    for t in glossary.get("terms", []):
        lines.append(f"TERM: {t['term']}")
        lines.append(f"DEFINITION: {t.get('llm_definition') or t.get('human_definition', '')}")
        lines.append(f"ROLE: {t.get('role', '')}")
        dist = t.get("distinguish_from") or []
        if dist:
            lines.append(f"DISTINGUISH FROM: {', '.join(dist)}")
        lines.append("DO: follow project-specific meaning above")
        lines.append("DO NOT: confuse with general English meaning or related terms listed")
        lines.append("")
    lines.extend(
        [
            "## Critical boundaries",
            "Observation ≠ Fingerprint — slots only, not features dict",
            "Gate ≠ Validator — escalation vs safety check",
            "Evidence ≠ Inference — material-backed vs guessed",
            "Safety ≠ Accuracy — safe HUMAN_REVIEW is not failure",
            "SUPPORTED (experiment) ≠ ACTIVE (state)",
            "stdout ≠ LLM handoff — display text vs messages JSON",
            "exists ≠ content — count vs snippet body",
        ]
    )
    return "\n".join(lines)


def build_role_context() -> str:
    lines = ["## Role structure (who does what)\n"]
    for e in ROLE_CONTEXT_ENTRIES:
        lines.append(f"{e['term']}:")
        lines.append(f"  generates: {e['generates']}")
        lines.append(f"  consumes: {e['consumes']}")
        lines.append(f"  must NOT: {e['must_not']}")
        lines.append("")
    return "\n".join(lines)


def build_context(
    condition: str,
    case_id: str | None = None,
    glossary: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (appendix_text, manifest_dict). condition A returns empty appendix."""
    glossary = glossary or load_glossary()
    manifest: dict[str, Any] = {
        "condition": condition,
        "case_id": case_id,
        "glossary_source": None,
        "term_count": 0,
        "char_count": 0,
        "approx_tokens": 0,
    }
    if condition == "A":
        return "", manifest
    if condition == "B":
        path = GLOSSARY_DIR / "llm" / "LLM_CONTEXT_GLOSSARY.md"
        text = path.read_text(encoding="utf-8")
        manifest["glossary_source"] = str(path.relative_to(FRAMEWORK))
        manifest["term_count"] = len(glossary.get("terms", []))
    elif condition == "C":
        path = GLOSSARY_DIR / "llm" / "LLM_QUICK_REFERENCE.md"
        text = path.read_text(encoding="utf-8")
        manifest["glossary_source"] = str(path.relative_to(FRAMEWORK))
        manifest["term_count"] = len(glossary.get("terms", []))
    elif condition == "D":
        if not case_id:
            raise ValueError("case_id required for condition D")
        terms = CASE_RELEVANT_TERMS.get(case_id, [])
        text = glossary_block_for_terms(terms, glossary)
        manifest["glossary_source"] = "mechanical CASE_RELEVANT_TERMS"
        manifest["term_count"] = len(terms)
        manifest["terms"] = terms
    elif condition == "E":
        text = build_definition_only(glossary)
        manifest["glossary_source"] = "glossary.json definition_only"
        manifest["term_count"] = len(glossary.get("terms", []))
    elif condition == "F":
        text = build_boundary_do_not(glossary)
        manifest["glossary_source"] = "glossary.json boundary_do_not"
        manifest["term_count"] = len(glossary.get("terms", []))
    elif condition == "G":
        text = build_role_context()
        manifest["glossary_source"] = "nh13 ROLE_CONTEXT_ENTRIES"
        manifest["term_count"] = len(ROLE_CONTEXT_ENTRIES)
    else:
        raise ValueError(f"unknown condition {condition}")
    manifest["char_count"] = len(text)
    manifest["approx_tokens"] = approx_tokens(text)
    return f"\n\n---\n# Glossary context ({condition})\n\n{text}", manifest
