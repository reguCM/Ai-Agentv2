"""Relevant Facet Router — experimental orchestration, not a Reasoning Core.

Selects stored facet_records whose aliases appear in the requirement and
forwards value / evidence / unknown / conflict / version / provenance.
Does not judge truth of the requirement.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai_tool.experimental.development_assistance.decision_factors import DecisionFactor
from ai_tool.experimental.development_assistance.research_record import ResearchRecord

RoutingMode = Literal["off", "full", "relevant"]


@dataclass
class FacetSliceItem:
    facet_id: str
    family: str
    reason: str
    matched_aliases: list[str]
    value: str
    evidence: list[str]
    unknown: list[str]
    conflicts: list[str]
    version: str
    provenance: str
    pulled_with: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RelevantSlice:
    mode: RoutingMode
    requirement: str
    facet_ids: list[str]
    items: list[FacetSliceItem] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "requirement": self.requirement,
            "facet_ids": list(self.facet_ids),
            "items": [i.to_dict() for i in self.items],
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


def select_relevant_facets(
    requirement: str,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Alias overlap against stored facet metadata. No inference."""
    req = requirement
    req_l = requirement.lower()
    selected: list[dict[str, Any]] = []
    by_id = {str(f.get("facet_id")): f for f in catalog}
    seen: set[str] = set()
    for facet in catalog:
        hits: list[str] = []
        for alias in facet.get("aliases") or []:
            a = str(alias)
            if not a:
                continue
            if a.isascii() and len(a) < 3:
                continue
            if a.lower() in req_l or a in req:
                hits.append(a)
        if not hits:
            continue
        fid = str(facet.get("facet_id") or "")
        if fid in seen:
            continue
        seen.add(fid)
        selected.append({**facet, "matched_aliases": hits, "pulled_with": ""})
        for companion in facet.get("pull_with") or []:
            cid = str(companion)
            if cid in seen or cid not in by_id:
                continue
            seen.add(cid)
            selected.append(
                {
                    **by_id[cid],
                    "matched_aliases": [],
                    "pulled_with": fid,
                }
            )
    return selected


def _value_for(facet_id: str, record: ResearchRecord) -> str:
    env = record.environment_facts or {}
    if facet_id in env:
        return str(env[facet_id])
    aliases = {
        "ursim": "ursim_version",
        "version": "ursim_version",
        "network_ports": "network_ports",
        "python_version": "python",
    }
    key = aliases.get(facet_id, facet_id)
    return str(env.get(key) or "")


def build_slice_items(
    selected: list[dict[str, Any]],
    records: list[ResearchRecord],
) -> list[FacetSliceItem]:
    rec = records[0] if records else None
    provenance = rec.provenance if rec else ""
    items: list[FacetSliceItem] = []
    for facet in selected:
        fid = str(facet.get("facet_id") or "")
        hits = list(facet.get("matched_aliases") or [])
        pulled = str(facet.get("pulled_with") or "")
        if pulled:
            reason = f"stored companion of {pulled} (routing, not a truth claim)"
        else:
            reason = "requirement contains stored alias: " + ", ".join(hits[:4])
        items.append(
            FacetSliceItem(
                facet_id=fid,
                family=str(facet.get("family") or ""),
                reason=reason,
                matched_aliases=hits,
                value=_value_for(fid, rec) if rec else "",
                evidence=[str(x) for x in (facet.get("evidence") or [])],
                unknown=[str(x) for x in (facet.get("unknown") or [])],
                conflicts=[str(x) for x in (facet.get("conflicts") or [])],
                version=str(facet.get("version") or (rec.environment_facts.get("ursim_version") if rec else "")),
                provenance=provenance,
                pulled_with=pulled,
            )
        )
    return items


def slice_to_decision_factors(items: list[FacetSliceItem]) -> list[DecisionFactor]:
    factors: list[DecisionFactor] = []
    for item in items:
        if item.unknown:
            status: str = "unknown"
            detail = "; ".join(item.unknown)
        elif item.conflicts:
            status = "conflict"
            detail = "; ".join(item.conflicts)
        elif item.evidence:
            status = "match"
            detail = "; ".join(item.evidence[:3])
        else:
            status = "partial"
            detail = item.reason
        if item.value:
            detail = f"value={item.value}; {detail}"
        factors.append(
            DecisionFactor(
                factor=item.facet_id,
                status=status,  # type: ignore[arg-type]
                detail=detail,
                candidate_id="relevant_slice",
            )
        )
    return factors


def items_from_dicts(raws: list[dict[str, Any]]) -> list[FacetSliceItem]:
    names = FacetSliceItem.__dataclass_fields__
    return [FacetSliceItem(**{k: v for k, v in raw.items() if k in names}) for raw in raws]


def format_slice_material(slice_: RelevantSlice) -> str:
    if slice_.skipped or not slice_.items:
        return ""
    lines = ["Relevant Research Slice (routing, not a verdict):"]
    for item in slice_.items:
        lines.append(
            f"- {item.facet_id}: value={item.value or '(none)'} | "
            f"evidence={len(item.evidence)} unknown={len(item.unknown)} "
            f"conflict={len(item.conflicts)} | {item.reason}"
        )
    return "\n".join(lines)


def route_relevant_facets(
    requirement: str,
    records: list[ResearchRecord],
    *,
    mode: RoutingMode,
    needed_facet_ids: list[str] | None = None,
) -> RelevantSlice:
    if mode == "off":
        return RelevantSlice(mode="off", requirement=requirement, facet_ids=[], skipped=True, skip_reason="off")
    catalog: list[dict[str, Any]] = []
    for rec in records:
        catalog.extend(list(rec.facet_records or []))
    if not catalog:
        return RelevantSlice(mode=mode, requirement=requirement, facet_ids=[], skipped=True, skip_reason="no_facet_records")
    if mode == "full":
        selected = [{**f, "matched_aliases": ["*"], "pulled_with": ""} for f in catalog]
    elif needed_facet_ids:
        wanted = {str(x) for x in needed_facet_ids}
        by_id = {str(f.get("facet_id")): f for f in catalog}
        selected = []
        seen: set[str] = set()
        for fid in wanted:
            if fid in seen or fid not in by_id:
                continue
            seen.add(fid)
            selected.append({**by_id[fid], "matched_aliases": ["discovery"], "pulled_with": "facet_discovery"})
            for companion in by_id[fid].get("pull_with") or []:
                cid = str(companion)
                if cid in seen or cid not in by_id:
                    continue
                seen.add(cid)
                selected.append({**by_id[cid], "matched_aliases": [], "pulled_with": fid})
    else:
        selected = select_relevant_facets(requirement, catalog)
    items = build_slice_items(selected, records)
    return RelevantSlice(
        mode=mode,
        requirement=requirement,
        facet_ids=[i.facet_id for i in items],
        items=items,
    )
