"""Research reuse matching — full / partial / no reuse without Mechanical Answer."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore

ReuseMode = Literal["full_reuse", "partial_reuse", "no_reuse"]
FreshnessLabel = Literal["fresh", "possibly_stale", "unknown", "needs_revalidation"]

_PYTHON_RE = re.compile(r"python\s*(3\.\d+(?:\.\d+)?)?", re.I)
_CUDA_RE = re.compile(r"cuda\s*(12(?:\.\d+)?|11(?:\.\d+)?)?", re.I)
_TECH_NAMES = (
    "polars", "pytorch", "pdfplumber", "pypdf", "toolx", "urscript", "dataframe", "pandas", "json",
)
_TECH_RE = re.compile(
    r"\b(polars|pytorch|pdfplumber|pypdf|toolx|urscript|dataframe|json|pandas)\b",
    re.I,
)


@dataclass
class RequirementFacets:
    requirement: str
    technologies: list[str] = field(default_factory=list)
    python: str = ""
    cuda: str = ""
    os: str = ""
    license_preference: str = ""
    topic_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_requirement_facets(
    requirement: str,
    *,
    user_constraints: dict[str, str] | None = None,
) -> RequirementFacets:
    """Metadata-based facet extraction — no embedding."""
    lower = requirement.lower()
    techs = [n for n in _TECH_NAMES if n in lower]
    techs.extend(_TECH_RE.findall(requirement))
    techs = list(dict.fromkeys(techs))
    py = _PYTHON_RE.search(requirement)
    cuda = _CUDA_RE.search(requirement)
    constraints = user_constraints or {}
    tokens = [t for t in re.split(r"[\s、。]+", requirement) if len(t) > 2][:8]
    return RequirementFacets(
        requirement=requirement,
        technologies=techs,
        python=constraints.get("python") or (py.group(0) if py else ""),
        cuda=constraints.get("cuda") or (cuda.group(0) if cuda else ""),
        os=constraints.get("os", ""),
        license_preference=constraints.get("license_preference", ""),
        topic_tokens=tokens,
    )


def _facet_overlap(facets: RequirementFacets, record: ResearchRecord) -> dict[str, Any]:
    """Which facets are covered by past research vs missing."""
    reusable: list[str] = []
    missing: list[str] = []

    rec_techs = [n.lower() for n in record.technology_names]
    req_techs = [t.lower() for t in facets.technologies]
    tech_match = bool(req_techs) and any(
        any(rt in rt_full or rt_full in rt for rt_full in rec_techs) for rt in req_techs
    )
    topic_match = any(
        t.lower() in record.requirement.lower() or t.lower() in record.topic.lower()
        for t in facets.topic_tokens[:4]
    )
    req_similar = (
        facets.requirement.strip() == record.requirement.strip()
        or facets.requirement[:40] in record.requirement
        or record.requirement[:40] in facets.requirement
    )

    if not tech_match and not topic_match and not req_similar:
        return {"relevant": False, "reusable": [], "missing": ["technology", "topic"]}

    if record.license_facts:
        reusable.append("license")
    else:
        missing.append("license")

    env = record.environment_facts
    if facets.python:
        past_py = env.get("python", "")
        if facets.python.lower().replace("python ", "") in past_py.lower().replace("python ", ""):
            reusable.append("python")
        elif past_py and past_py != "UNKNOWN":
            missing.append("python")  # different version requested
        else:
            missing.append("python")
    elif env.get("python"):
        reusable.append("python")

    if facets.cuda:
        past_cuda = env.get("cuda", "")
        if facets.cuda.lower() in past_cuda.lower():
            reusable.append("cuda")
        elif past_cuda:
            missing.append("cuda")
        else:
            missing.append("cuda")
    elif env.get("cuda") or env.get("gpu"):
        reusable.append("cuda")

    if record.version_facts:
        reusable.append("version")
    else:
        missing.append("version")

    if record.sources:
        reusable.append("source")
    if record.unknowns:
        reusable.append("known_unknowns")

    return {
        "relevant": True,
        "reusable": sorted(set(reusable)),
        "missing": sorted(set(missing)),
        "tech_match": tech_match,
        "topic_match": topic_match,
        "requirement_similar": req_similar,
    }


def assess_freshness(record: ResearchRecord) -> FreshnessLabel:
    """Observed freshness — no fixed 30-day rule."""
    try:
        checked = datetime.fromisoformat(record.checked_at.replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - checked).days
        if age_days <= 7:
            return "fresh"
        if age_days <= 90:
            return "possibly_stale"
        return "needs_revalidation"
    except (ValueError, TypeError):
        return "unknown"


@dataclass
class ReuseAssessment:
    mode: ReuseMode
    matched_research_id: str
    relevance: dict[str, Any]
    reusable_fields: list[str]
    missing_fields: list[str]
    freshness: FreshnessLabel
    web_searches_without_reuse: int
    web_searches_with_reuse: int
    searches_saved: int
    past_material_summary: str
    safety_note: str = "Past research is material for conversation — not ground truth."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_best_match(
    facets: RequirementFacets,
    store: ResearchStore,
) -> ResearchRecord | None:
    candidates: list[tuple[int, ResearchRecord]] = []
    for rec in store.records:
        overlap = _facet_overlap(facets, rec)
        if not overlap.get("relevant"):
            continue
        score = len(overlap.get("reusable") or [])
        if overlap.get("tech_match"):
            score += 3
        candidates.append((score, rec))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def assess_reuse(
    facets: RequirementFacets,
    store: ResearchStore,
    *,
    baseline_searches: int = 2,
) -> ReuseAssessment:
    """Determine full / partial / no reuse and search reduction estimate."""
    match = find_best_match(facets, store)
    if not match:
        return ReuseAssessment(
            mode="no_reuse",
            matched_research_id="",
            relevance={"relevant": False},
            reusable_fields=[],
            missing_fields=["all"],
            freshness="unknown",
            web_searches_without_reuse=baseline_searches,
            web_searches_with_reuse=baseline_searches,
            searches_saved=0,
            past_material_summary="No matching past research.",
        )

    overlap = _facet_overlap(facets, match)
    missing = overlap.get("missing") or []
    reusable = overlap.get("reusable") or []
    req_similar = bool(overlap.get("requirement_similar"))
    freshness = assess_freshness(match)

    if not missing or (req_similar and set(missing) <= {"license", "known_unknowns"}):
        mode: ReuseMode = "full_reuse"
        searches_with = 0
    elif missing:
        mode = "partial_reuse"
        searches_with = min(baseline_searches, max(1, len(missing)))
    else:
        mode = "full_reuse"
        searches_with = 0

    summary = (
        f"Past research {match.research_id} ({match.checked_at[:10]}): "
        f"reusable={', '.join(reusable) or 'none'}; missing={', '.join(missing) or 'none'}; "
        f"freshness={freshness}"
    )

    return ReuseAssessment(
        mode=mode,
        matched_research_id=match.research_id,
        relevance=overlap,
        reusable_fields=reusable,
        missing_fields=missing,
        freshness=freshness,
        web_searches_without_reuse=baseline_searches,
        web_searches_with_reuse=searches_with,
        searches_saved=baseline_searches - searches_with,
        past_material_summary=summary,
    )


def merge_past_and_new_material(
    assessment: ReuseAssessment,
    store: ResearchStore,
    new_run: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine past record with optional new evidence — label provenance."""
    past = next((r for r in store.records if r.research_id == assessment.matched_research_id), None)
    past_dict = past.to_dict() if past else {}
    new_candidates = (new_run or {}).get("candidates") or []
    return {
        "from_past_research": {
            "research_id": assessment.matched_research_id,
            "candidates": past_dict.get("technology_candidates") or [],
            "version_facts": past_dict.get("version_facts") or [],
            "sources": past_dict.get("sources") or [],
            "unknowns": past_dict.get("unknowns") or [],
            "conflicts": past_dict.get("conflicts") or [],
            "checked_at": past_dict.get("checked_at"),
            "freshness": assessment.freshness,
        },
        "from_new_research": {
            "candidates": new_candidates,
            "queries": (new_run or {}).get("queries") or [],
        },
        "missing_fields_addressed": assessment.missing_fields,
        "safety_note": assessment.safety_note,
    }


def reuse_conversation_material(assessment: ReuseAssessment, store: ResearchStore) -> str:
    """LLM-facing summary — past info as material, not truth."""
    if assessment.mode == "no_reuse":
        return "過去の調査記録に該当する情報はありません。新規Web Researchが必要です。"
    past = next((r for r in store.records if r.research_id == assessment.matched_research_id), None)
    if not past:
        return assessment.past_material_summary
    lines = [
        f"以前の調査（{assessment.matched_research_id}、{past.checked_at[:10]}）の材料:",
    ]
    for vf in past.version_facts[:2]:
        lines.append(
            f"  - {vf.get('technology')}: Python={vf.get('python')}, CUDA={vf.get('cuda')}, "
            f"License={vf.get('license')} (出典: {vf.get('source_category')})"
        )
    if assessment.missing_fields:
        lines.append(f"不足（過去調査に無い/不一致）: {', '.join(assessment.missing_fields)}")
    lines.append(f"鮮度: {assessment.freshness} — 無条件に最新とは扱いません。")
    if past.unknowns:
        lines.append(f"既知の不明点: {', '.join(past.unknowns[:5])}")
    return "\n".join(lines)
