"""Experimental Evidence → LLM context packaging (investigation only).

NOT connected to Production Agent or enrich_web_tool_result.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai_tool.experimental.mechanical_verification.verifier import (
    MechanicalVerificationReport,
    verify_answer,
)
from ai_tool.web_tool_success_class_accuracy_evaluation import (
    ExpectedFact,
    _check_fact_in_text,
)

ContextFormat = Literal["A1_RAW", "A2_PASSAGE", "A3_SOURCE_GROUPED", "A4_CLAIM", "A5_VERIFY", "A6_HYBRID"]
VerificationMode = Literal["E1_NONE", "E2_FULL", "E3_MATCH_ONLY", "E4_ALL_VERDICTS"]


@dataclass
class EvidenceSource:
    url: str
    title: str
    main_text: str
    quality: dict[str, Any] = field(default_factory=dict)
    backend: str = "fixture"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceBundle:
    case_id: str
    user_request: str
    query: str
    sources: list[EvidenceSource]
    expected_facts: list[ExpectedFact]
    category: str = ""

    @property
    def raw_combined(self) -> str:
        return "\n\n---\n\n".join(s.main_text for s in self.sources if s.main_text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "user_request": self.user_request,
            "query": self.query,
            "category": self.category,
            "sources": [s.to_dict() for s in self.sources],
            "expected_facts": [f.to_dict() for f in self.expected_facts],
        }


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[一-龥ぁ-んァ-ン]{2,}|[A-Za-z]{3,}", query)
    return [t for t in terms if t.lower() not in ("the", "and", "what", "city")]


def _select_passages(text: str, query: str, *, max_paragraphs: int = 3) -> str:
    if not text.strip():
        return ""
    terms = _query_terms(query)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}|\n", text) if len(p.strip()) > 20]
    if not paragraphs:
        paragraphs = [text.strip()]
    scored: list[tuple[int, str]] = []
    for p in paragraphs:
        score = sum(1 for t in terms if t in p)
        scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    selected = [p for s, p in scored if s > 0][:max_paragraphs]
    if not selected:
        selected = [paragraphs[0]]
    return "\n\n".join(selected)


def _claim_candidates(text: str, facts: list[ExpectedFact]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for fact in facts:
        for pat in fact.evidence_patterns:
            m = re.search(pat, text, re.I)
            if m:
                claims.append(
                    {
                        "claim_id": fact.fact_id,
                        "claim_type": fact.fact_type,
                        "supporting_excerpt": m.group(0),
                        "confidence": "pattern_match",
                    }
                )
                break
    return claims


def build_context(
    fmt: ContextFormat,
    bundle: EvidenceBundle,
    *,
    verification_mode: VerificationMode = "E1_NONE",
    proxy_answer: str | None = None,
    include_verification: bool | None = None,
) -> str:
    raw = bundle.raw_combined
    parts: list[str] = []

    if fmt == "A1_RAW":
        parts.append(f"USER_REQUEST: {bundle.user_request}\n\nEVIDENCE:\n{raw}")

    elif fmt == "A2_PASSAGE":
        passages = "\n\n".join(_select_passages(s.main_text, bundle.query) for s in bundle.sources)
        parts.append(f"USER_REQUEST: {bundle.user_request}\n\nRELEVANT_PASSAGES:\n{passages}")

    elif fmt == "A3_SOURCE_GROUPED":
        grouped = []
        for s in bundle.sources:
            excerpt = _select_passages(s.main_text, bundle.query, max_paragraphs=2)
            grouped.append(
                {
                    "source": s.backend,
                    "title": s.title,
                    "url": s.url,
                    "excerpt": excerpt[:800],
                    "fact_ready": (s.quality or {}).get("fact_ready"),
                    "extraction_method": (s.quality or {}).get("extraction_method"),
                }
            )
        parts.append(
            f"USER_REQUEST: {bundle.user_request}\n\nSOURCES:\n"
            + json.dumps(grouped, ensure_ascii=False, indent=2)
        )

    elif fmt in ("A4_CLAIM", "A5_VERIFY", "A6_HYBRID"):
        claims = _claim_candidates(raw, bundle.expected_facts)
        if fmt == "A6_HYBRID":
            passages = _select_passages(raw, bundle.query)
            parts.append(f"PASSAGES:\n{passages}\n")
            for s in bundle.sources[:2]:
                parts.append(f"SOURCE: {s.title} ({s.url})\n")
        claim_block = {"claims": claims, "user_request": bundle.user_request}
        parts.append("CLAIM_ORIENTED:\n" + json.dumps(claim_block, ensure_ascii=False, indent=2))

    else:
        parts.append(raw)

    ctx = "\n".join(parts)

    add_verify = include_verification
    if add_verify is None:
        add_verify = fmt in ("A5_VERIFY", "A6_HYBRID") or verification_mode != "E1_NONE"

    if add_verify:
        mode = verification_mode if fmt not in ("A5_VERIFY", "A6_HYBRID") else "E4_ALL_VERDICTS"
        ctx += _verification_block(bundle, proxy_answer or "", raw, mode=mode)

    return ctx


def build_production_raw_context(bundle: EvidenceBundle) -> str:
    """Simulate Production enrich_web_tool_result JSON passed to LLM (investigation only)."""
    from tools.system.network.web_evidence import enrich_web_tool_result

    enriched_sources: list[dict[str, Any]] = []
    for s in bundle.sources:
        base: dict[str, Any] = {
            "ok": True,
            "url": s.url,
            "title": s.title,
            "main_text": s.main_text,
            "quality": dict(s.quality or {}),
        }
        enriched_sources.append(enrich_web_tool_result("read_url_text", base))

    if len(enriched_sources) == 1:
        payload: Any = enriched_sources[0]
    else:
        payload = {"read_url_text_results": enriched_sources}

    return (
        f"USER_REQUEST: {bundle.user_request}\n\n"
        f"TOOL_RESULT (read_url_text, production-shaped):\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_hybrid_context(bundle: EvidenceBundle, *, include_verification: bool = False) -> str:
    """Source + passage + combined evidence — shootout Format D (no claim-only)."""
    parts = [f"USER_REQUEST: {bundle.user_request}"]
    for s in bundle.sources:
        excerpt = _select_passages(s.main_text, bundle.query, max_paragraphs=2)
        parts.append(f"SOURCE: {s.title}\nURL: {s.url}\nEXCERPT:\n{excerpt}")
    parts.append(f"COMBINED_EVIDENCE:\n{bundle.raw_combined[:1500]}")
    ctx = "\n\n".join(parts)
    if include_verification:
        ctx += _verification_block(bundle, "", bundle.raw_combined, mode="E4_ALL_VERDICTS")
    return ctx


def _verification_block(
    bundle: EvidenceBundle,
    answer: str,
    evidence: str,
    *,
    mode: VerificationMode,
) -> str:
    if mode == "E1_NONE":
        return ""
    report: MechanicalVerificationReport = verify_answer(
        answer or "（未回答）",
        evidence,
        bundle.expected_facts,
    )
    results = report.results
    if mode == "E3_MATCH_ONLY":
        results = [r for r in results if r.verdict == "MATCH"]
    block = {
        "verification_overall": report.overall,
        "verification_results": [r.to_dict() for r in results],
        "instruction": "Use verification metadata as observation only; do not replace user-facing answer.",
    }
    return "\n\nVERIFICATION_METADATA:\n" + json.dumps(block, ensure_ascii=False, indent=2)


def fact_coverage_in_context(context: str, facts: list[ExpectedFact]) -> tuple[int, int]:
    met = sum(1 for f in facts if _check_fact_in_text(context, f))
    return met, len(facts)


def compress_context_levels(bundle: EvidenceBundle) -> dict[str, str]:
    """Investigation D — compression ladder."""
    raw = bundle.raw_combined
    return {
        "full": build_context("A1_RAW", bundle),
        "passage": build_context("A2_PASSAGE", bundle),
        "claim": build_context("A4_CLAIM", bundle),
        "source_summary": build_context("A3_SOURCE_GROUPED", bundle),
    }


__all__ = [
    "ContextFormat",
    "EvidenceBundle",
    "EvidenceSource",
    "VerificationMode",
    "build_context",
    "build_hybrid_context",
    "build_production_raw_context",
    "compress_context_levels",
    "fact_coverage_in_context",
]
