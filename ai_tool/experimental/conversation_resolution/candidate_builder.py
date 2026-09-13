"""Build Candidate structures from Web Evidence sources (experimental)."""
from __future__ import annotations

import re
from typing import Any

from ai_tool.experimental.conversation_resolution.models import (
    Candidate,
    CandidateRelation,
    EvidenceRecord,
    PresentationMode,
    SourceRecord,
    VerificationObservation,
)
from ai_tool.experimental.evidence_context.packager import EvidenceSource
from ai_tool.experimental.mechanical_verification.verifier import (
    extract_heuristic_evidence_facts,
    verify_answer,
)
from ai_tool.web_tool_success_class_accuracy_evaluation import (
    ExpectedFact,
    extract_population_numeric_values,
)

YEAR_RE = re.compile(r"(20\d{2}|19\d{2})")
POP_RE = re.compile(
    r"(?:約|およそ|推計)?\s*([0-9]{1,3}(?:[,，][0-9]{3})*(?:\.[0-9]+)?)\s*(万(?:人)?|人)?",
    re.I,
)
AREA_RE = re.compile(
    r"([0-9]{1,3}(?:[,，][0-9]{3})*(?:\.[0-9]+)?)\s*(?:平方キロ|km²|km2|平方km)",
    re.I,
)
DEFINITION_HINTS = (
    ("国勢調査", "census"),
    ("推計", "estimate"),
    (" census", "census"),
    ("estimate", "estimate"),
    ("現在", "current"),
)


def _definition_label(text: str) -> str:
    for hint, label in DEFINITION_HINTS:
        if hint.lower() in text.lower():
            return label
    years = YEAR_RE.findall(text)
    if years:
        return f"year_{years[0]}"
    return "unspecified"


def _extract_claim(text: str, *, topic: str = "") -> str:
    text = text.strip()
    if not text:
        return ""
    sentences = re.split(r"[。\n]", text)
    for s in sentences:
        s = s.strip()
        if len(s) < 8:
            continue
        if topic and any(t in s for t in topic.split() if len(t) >= 2):
            return s
    return sentences[0].strip() if sentences else text[:200]


def _numeric_values(text: str) -> list[float]:
    if "人口" in text or "population" in text.lower():
        pop = extract_population_numeric_values(text)
        if pop:
            return pop
    facts = extract_heuristic_evidence_facts(text)
    return list(facts.get("all_numerics") or [])


def source_records_from_bundle(sources: list[EvidenceSource]) -> tuple[list[SourceRecord], list[EvidenceRecord]]:
    srcs: list[SourceRecord] = []
    evs: list[EvidenceRecord] = []
    for i, s in enumerate(sources):
        sid = f"S{i + 1}"
        srcs.append(
            SourceRecord(
                source_id=sid,
                url=s.url,
                title=s.title,
                backend=s.backend,
                source_type=(s.quality or {}).get("source_type") or "web",
            )
        )
        evs.append(
            EvidenceRecord(
                evidence_id=f"E{i + 1}",
                source_id=sid,
                excerpt=_extract_claim(s.main_text),
                main_text=s.main_text,
                fact_ready=(s.quality or {}).get("fact_ready"),
            )
        )
    return srcs, evs


def build_candidates_from_sources(
    sources: list[EvidenceSource],
    *,
    topic: str = "",
    expected_facts: list[ExpectedFact] | None = None,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, s in enumerate(sources):
        claim = _extract_claim(s.main_text, topic=topic)
        years = [int(y) for y in YEAR_RE.findall(s.main_text)]
        nums = _numeric_values(s.main_text)
        cid = f"C{labels[i]}"
        verification: list[VerificationObservation] = []
        if expected_facts:
            report = verify_answer(claim, s.main_text, expected_facts)
            for r in report.results[:3]:
                verification.append(
                    VerificationObservation(
                        claim_id=r.claim_id,
                        verdict=r.verdict,
                        method=r.method,
                    )
                )
        candidates.append(
            Candidate(
                candidate_id=cid,
                label=cid,
                claim=claim,
                evidence_id=f"E{i + 1}",
                source_id=f"S{i + 1}",
                url=s.url,
                source_title=s.title,
                definition_label=_definition_label(s.main_text),
                numeric_values=nums,
                years=years,
                verification=verification,
                metadata={"backend": s.backend, "fact_ready": (s.quality or {}).get("fact_ready")},
            )
        )
    return candidates


def _numeric_near(a: float, b: float, *, rel: float = 0.02) -> bool:
    if a == 0 and b == 0:
        return True
    base = max(abs(a), abs(b), 1.0)
    return abs(a - b) / base <= rel


def classify_candidate_relation(candidates: list[Candidate]) -> CandidateRelation:
    if len(candidates) <= 1:
        return "SINGLE"

    claims_norm = [re.sub(r"\s+", "", c.claim.lower()) for c in candidates]
    if len(set(claims_norm)) == 1:
        return "AGREEMENT"

    defs = {c.definition_label for c in candidates if c.definition_label != "unspecified"}
    years = {y for c in candidates for y in c.years}
    if len(defs) >= 2 or (len(years) >= 2 and all(c.numeric_values for c in candidates)):
        if len(defs) >= 2 or (max(years) - min(years) >= 1 if years else False):
            return "DEFINITION_DIFF"

    nums = [c.numeric_values[0] for c in candidates if c.numeric_values]
    if len(nums) >= 2:
        same_year = years and len(set(years)) == 1
        if same_year and not _numeric_near(nums[0], nums[1], rel=0.015):
            return "TRUE_CONFLICT"
        if all(_numeric_near(nums[0], n, rel=0.015) for n in nums[1:]):
            return "NUMERIC_NEAR"

    return "DEFINITION_DIFF" if len(candidates) >= 2 else "SINGLE"


def choose_presentation_mode(relation: CandidateRelation) -> PresentationMode:
    if relation in ("SINGLE", "AGREEMENT"):
        return "SINGLE"
    if relation == "NUMERIC_NEAR":
        return "MERGED"
    if relation == "DEFINITION_DIFF":
        return "MULTI"
    if relation == "TRUE_CONFLICT":
        return "UNRESOLVED"
    return "SINGLE"


def difference_note(candidates: list[Candidate], relation: CandidateRelation) -> str:
    if relation == "AGREEMENT":
        return "複数ソースで内容は一致しています。"
    if relation == "NUMERIC_NEAR":
        return "数値表記に差がありますが、実質的に近い値です。"
    if relation == "DEFINITION_DIFF":
        parts = []
        for c in candidates:
            yr = f"{c.years[0]}年" if c.years else "年度不明"
            parts.append(f"{c.label}は{c.source_title}（{yr}、{c.definition_label}）")
        return "定義・時点の違い: " + " / ".join(parts)
    if relation == "TRUE_CONFLICT":
        return "同一条件について異なる数値が報告されています。自動では一方に固定しません。"
    return ""


def build_envelope(
    sources: list[EvidenceSource],
    *,
    user_request: str,
    topic: str = "",
    expected_facts: list[ExpectedFact] | None = None,
) -> dict[str, Any]:
    src_records, ev_records = source_records_from_bundle(sources)
    candidates = build_candidates_from_sources(sources, topic=topic, expected_facts=expected_facts)
    relation = classify_candidate_relation(candidates)
    mode = choose_presentation_mode(relation)
    return {
        "sources": [s.to_dict() for s in src_records],
        "evidence": [e.to_dict() for e in ev_records],
        "candidates": [c.to_dict() for c in candidates],
        "relation": relation,
        "presentation_mode": mode,
        "difference_note": difference_note(candidates, relation),
        "user_request": user_request,
    }
