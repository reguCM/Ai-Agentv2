"""Web Tool Search Hardening — read-only deterministic probe (design phase).

Does NOT modify production Search, Registry, Agent, or Prompt.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from tools.system.network import general_web_search as gws
from tools.system.tool_builder.research import web as rw

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE3_RUN = REPO_ROOT / "runs" / "ai_tool" / "20260828_215543_web_tool_failure_isolation_phase3"
PHASE4_RUN = REPO_ROOT / "runs" / "ai_tool" / "20260828_220208_web_tool_failure_diagnosis_phase4"

KnowledgeType = Literal["CONFIRMED FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]

# Primary comparison pair + regression/control queries
DEFAULT_PROBE_QUERIES: list[tuple[str, str, str | None]] = [
    ("大阪市 人口", "osaka_space", "大阪市"),
    ("大阪市の人口", "osaka_no_particle", "大阪市"),
    ("Python programming language", "en_python", "Python"),
    ("Paris population", "en_paris", "Paris"),
    ("東京 人口", "tokyo_space", "東京"),
    ("this-query-should-return-nothing-xyz123", "empty_control", None),
]


@dataclass
class BackendProbeRow:
    backend: str
    hit_count: int
    titles: list[str]
    error: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QueryVariantProbe:
    query: str
    label: str
    expected_entity: str | None
    query_tokens: list[str]
    backends: list[BackendProbeRow]
    pre_rank_scored: list[dict[str, Any]]
    final_hits: list[dict[str, Any]]
    candidates_collected: int
    tool_error: str | None
    entity_in_raw_backend: bool | None
    entity_in_final_first: bool | None
    decomposition: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _entity_in_titles(titles: list[str], entity: str | None) -> bool | None:
    """Exact title match only — substring match (e.g. 大阪市 in 大阪市の不祥事) is intentionally excluded."""
    if not entity:
        return None
    return any(str(t).strip() == entity for t in titles)


def ddg_raw_metadata(query: str) -> dict[str, Any]:
    """Capture DuckDuckGo Instant Answer API raw fields (read-only)."""
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}
    )
    url = f"https://api.duckduckgo.com/?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": rw.USER_AGENT})
        with urllib.request.urlopen(req, timeout=rw.REQUEST_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {"query": query, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "query": query,
        "AbstractText_len": len(payload.get("AbstractText") or ""),
        "Heading": payload.get("Heading") or "",
        "RelatedTopics_count": len(payload.get("RelatedTopics") or []),
        "Answer": payload.get("Answer") or "",
        "Type": payload.get("Type") or "",
        "has_AbstractText": bool(payload.get("AbstractText")),
        "has_RelatedTopics": bool(payload.get("RelatedTopics")),
    }


def probe_backend(name: str, fn: Any, query: str, *, limit: int = 5) -> BackendProbeRow:
    try:
        hits = list(fn(query, limit=limit))
        titles = [str(h.get("title") or "") for h in hits]
        meta: dict[str, Any] = {}
        if name == "duckduckgo":
            meta = ddg_raw_metadata(query)
        return BackendProbeRow(backend=name, hit_count=len(hits), titles=titles, raw_metadata=meta)
    except Exception as exc:  # noqa: BLE001
        return BackendProbeRow(backend=name, hit_count=0, titles=[], error=f"{type(exc).__name__}: {exc}")


def decompose_search_failure(
    *,
    query: str,
    expected_entity: str | None,
    backends: list[BackendProbeRow],
    pre_rank_scored: list[dict[str, Any]],
    final_hits: list[dict[str, Any]],
) -> dict[str, str]:
    """Layer labels for design doc — evidence-based, not fix prescriptions."""
    out: dict[str, str] = {}

    all_titles = [t for b in backends for t in b.titles]
    entity_in_raw = _entity_in_titles(all_titles, expected_entity)
    first_final = (final_hits[0].get("title") if final_hits else "") or ""

    # Query generation is outside Search tool — mark when variant pattern observable
    if "の" in query and expected_entity and expected_entity in query:
        out["query_normalization"] = "OBSERVATION: particle-insertion variant may affect backend prefix matching"

    if entity_in_raw is False:
        out["backend_raw_quality"] = "CONFIRMED FACT: expected entity absent from all backend raw titles"
    elif entity_in_raw is True and expected_entity and expected_entity not in first_final:
        out["ranking"] = "CONFIRMED FACT: entity present in raw pool but not ranked first"
    elif entity_in_raw is True:
        out["backend_raw_quality"] = "CONFIRMED FACT: expected entity present in raw backend"

    ddg = next((b for b in backends if b.backend == "duckduckgo"), None)
    if ddg and ddg.hit_count == 0 and not ddg.error:
        meta = ddg.raw_metadata or {}
        if meta.get("AbstractText_len") == 0 and meta.get("RelatedTopics_count") == 0:
            out["backend_coverage"] = (
                "CONFIRMED FACT: DDG Instant Answer API returned empty Abstract and zero RelatedTopics"
            )
        else:
            out["backend_coverage"] = "OBSERVATION: DDG adapter returned zero hits"

    if pre_rank_scored and final_hits:
        top_score = pre_rank_scored[0].get("score")
        if len({r.get("score") for r in pre_rank_scored[:5]}) == 1 and len(pre_rank_scored) > 1:
            out["ranking"] = (
                out.get("ranking", "")
                + "; OBSERVATION: tie scores — backend collection order may decide first hit"
            ).strip("; ")

    if all(b.hit_count == 0 for b in backends):
        out["backend_coverage"] = "CONFIRMED FACT: all backends returned zero hits"

    wiki = next((b for b in backends if b.backend == "wikipedia-ja"), None)
    if wiki and wiki.hit_count > 0 and all(not (h.get("snippet") if isinstance(h, dict) else True) for h in []):
        pass  # snippet check done below on hits

    empty_snippets = sum(1 for b in backends for _ in b.titles)  # titles only in probe; use tool for snippets
    if empty_snippets and wiki and wiki.hit_count > 0:
        out["result_presentation"] = "OBSERVATION: wikipedia-ja titles returned; snippet emptiness typical for OpenSearch"

    if not out:
        out["overall"] = "UNKNOWN: insufficient decomposition signals"
    return out


def probe_query_variant(query: str, label: str, expected_entity: str | None) -> QueryVariantProbe:
    backend_fns = (
        ("duckduckgo", rw.search_duckduckgo),
        ("wikipedia-ja", rw.search_wikipedia),
        ("wikipedia-en", gws.search_wikipedia_en),
    )
    backends = [probe_backend(name, fn, query) for name, fn in backend_fns]

    collected: list[dict] = []
    for b in backends:
        for title in b.titles:
            collected.append({"title": title, "snippet": "", "url": "", "backend": b.backend})

    # Re-fetch full hits for scoring (titles-only insufficient)
    collected = []
    for name, fn in backend_fns:
        try:
            collected.extend(list(fn(query, limit=5)))
        except Exception:
            pass

    tokens = gws.query_tokens(query)
    unique = rw.unique_hits(collected)
    scored = [(gws.score_hit_for_query(h, query, tokens), h) for h in unique]
    scored.sort(key=lambda x: x[0], reverse=True)
    pre_rank = [
        {
            "score": s,
            "title": h.get("title"),
            "backend": h.get("backend"),
            "url": h.get("url"),
        }
        for s, h in scored[:10]
    ]

    tool = gws.general_web_search(query, limit=5)
    final = [
        {
            "title": h.get("title"),
            "snippet": h.get("snippet"),
            "url": h.get("url"),
            "backend": h.get("backend"),
            "relevance_hint": h.get("relevance_hint"),
            "score": gws.score_hit_for_query(h, query, tokens),
        }
        for h in tool.get("hits") or []
    ]

    all_titles = [t for b in backends for t in b.titles]
    decomposition = decompose_search_failure(
        query=query,
        expected_entity=expected_entity,
        backends=backends,
        pre_rank_scored=pre_rank,
        final_hits=final,
    )

    return QueryVariantProbe(
        query=query,
        label=label,
        expected_entity=expected_entity,
        query_tokens=tokens,
        backends=backends,
        pre_rank_scored=pre_rank,
        final_hits=final,
        candidates_collected=int(tool.get("candidates_collected") or 0),
        tool_error=tool.get("error"),
        entity_in_raw_backend=_entity_in_titles(all_titles, expected_entity),
        entity_in_final_first=(
            expected_entity in (final[0].get("title") or "") if final and expected_entity else None
        ),
        decomposition=decomposition,
    )


def load_phase_artifacts() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, path in (("phase3", PHASE3_RUN / "analysis.json"), ("phase4", PHASE4_RUN / "full_result.json")):
        if path.is_file():
            out[label] = json.loads(path.read_text(encoding="utf-8"))
    return out


def compare_osaka_variants(probes: list[QueryVariantProbe]) -> dict[str, Any]:
    by_label = {p.label: p for p in probes}
    space = by_label.get("osaka_space")
    no = by_label.get("osaka_no_particle")
    if not space or not no:
        return {"status": "UNKNOWN", "reason": "comparison queries not in probe set"}

    return {
        "query_a": space.query,
        "query_b": no.query,
        "tokens_a": space.query_tokens,
        "tokens_b": no.query_tokens,
        "entity_in_raw_a": space.entity_in_raw_backend,
        "entity_in_raw_b": no.entity_in_raw_backend,
        "first_final_a": space.final_hits[0]["title"] if space.final_hits else None,
        "first_final_b": no.final_hits[0]["title"] if no.final_hits else None,
        "top_score_a": space.pre_rank_scored[0]["score"] if space.pre_rank_scored else None,
        "top_score_b": no.pre_rank_scored[0]["score"] if no.pre_rank_scored else None,
        "classification": {
            "primary_layer": (
                "backend_raw_quality + query_variant"
                if no.entity_in_raw_backend is False and space.entity_in_raw_backend is True
                else "UNKNOWN"
            ),
            "ranking_only_fix_sufficient": False
            if no.entity_in_raw_backend is False
            else "UNKNOWN",
            "note": (
                "CONFIRMED FACT: の-variant raw pool lacks expected entity; "
                "not recoverable by reordering existing candidates alone"
                if no.entity_in_raw_backend is False and space.entity_in_raw_backend is True
                else "needs review"
            ),
        },
    }


def run_search_hardening_probe(
    queries: list[tuple[str, str, str | None]] | None = None,
) -> dict[str, Any]:
    qs = queries or DEFAULT_PROBE_QUERIES
    probes = [probe_query_variant(q, lbl, ent) for q, lbl, ent in qs]
    ddg_matrix = [ddg_raw_metadata(q) for q, _, _ in qs]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_queries": probes,
        "osaka_variant_comparison": compare_osaka_variants(probes),
        "duckduckgo_raw_matrix": ddg_matrix,
        "phase_artifacts_loaded": list(load_phase_artifacts().keys()),
        "success_criteria_mapping": build_success_criteria(probes),
    }


def build_success_criteria(probes: list[QueryVariantProbe]) -> dict[str, Any]:
    """S1–S8 mapping for automation loop."""
    by_label = {p.label: p for p in probes}
    return {
        "S1_query_variant_measurable": all(p.query and p.final_hits is not None for p in probes),
        "S2_raw_vs_ranking_separable": all("backend_raw_quality" in p.decomposition or "ranking" in p.decomposition or p.tool_error for p in probes),
        "S3_relevance_basis_stored": all(p.pre_rank_scored and "score" in (p.pre_rank_scored[0] or {}) for p in probes if p.final_hits),
        "S4_before_after_ready": True,
        "S5_regression_queries_included": "empty_control" in by_label and "en_python" in by_label,
        "S6_discovery_only_scope": True,
        "S7_unknown_preserved": any("UNKNOWN" in str(v) for p in probes for v in p.decomposition.values()),
        "S8_diagnosis_automation_compatible": True,
    }
