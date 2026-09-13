"""TDA パイプライン結果を ResearchRecord として保存する。Experimental。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.facet_records_from_facts import (
    derive_facet_records,
    enrich_environment_from_candidates,
)
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.phase_r2_research_sources import core_specs
from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore


def ingest_spec(store: ResearchStore, spec: Any, *, label: str, research_id: str) -> dict[str, Any]:
    """run_tda_case → add_from_run。facet_records が空なら機械的に導出する。"""
    run = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    run["requirement"] = spec.user_requirement
    before = ResearchStore()
    rec_before = before.add_from_run(run, checked_at=datetime.now(timezone.utc).isoformat())
    facets_before = len(rec_before.facet_records or [])
    rec = store.add_from_run(run, checked_at=datetime.now(timezone.utc).isoformat())
    rec.research_id = research_id
    rec.environment_facts = {**(rec.environment_facts or {}), "label": label}
    rec.provenance = "tda_pipeline"
    enrich_environment_from_candidates(rec)
    derived = derive_facet_records(rec)
    return {
        "research_id": rec.research_id,
        "label": label,
        "pipeline_pass": bool(run.get("pass")),
        "candidates": len(run.get("candidates") or []),
        "queries": list(run.get("queries") or []),
        "environment_facts": dict(rec.environment_facts or {}),
        "license_facts": list(rec.license_facts or []),
        "sources": list(rec.sources or []),
        "facet_count_before_derive": facets_before,
        "facet_count_after_derive": len(rec.facet_records or []),
        "derived_ids": [d["facet_id"] for d in derived],
        "facet_ids": [str(f.get("facet_id")) for f in (rec.facet_records or [])],
        "live_network": False,
        "ingestion": "run_tda_case + add_from_run",
    }


def ingest_core_store() -> tuple[ResearchStore, list[dict[str, Any]]]:
    store = ResearchStore()
    reports: list[dict[str, Any]] = []
    labels = [("A", "RR-A"), ("B", "RR-B"), ("C", "RR-C"), ("D", "RR-D"), ("E", "RR-E")]
    for spec, (label, rid) in zip(core_specs(), labels):
        reports.append(ingest_spec(store, spec, label=label, research_id=rid))
    return store, reports


def add_noise_records(store: ResearchStore, n: int) -> int:
    """スケール用。add_from_run の envelope で無関係記憶を足す。HTML 再実行はしない。"""
    added = 0
    for i in range(n):
        name = f"N{i:03d}"
        run = {
            "requirement": f"{name}について調べて。",
            "queries": [name],
            "candidates": [
                {
                    "name": f"Lib{name}",
                    "type": "Library",
                    "license": "BSD",
                    "environment": {"python": "Python 3.10", "os": "Linux", "cuda": "CUDA 11.8"},
                    "url": f"https://fixture.local/r2/{name.lower()}",
                    "source_title": f"{name} docs",
                    "source_category": "Other",
                    "description": f"unrelated noise {name}",
                }
            ],
            "conflicts": [],
        }
        rec = store.add_from_run(run, checked_at=datetime.now(timezone.utc).isoformat())
        rec.research_id = f"RR-{name}"
        rec.environment_facts = {**(rec.environment_facts or {}), "label": name}
        rec.provenance = "r2_noise_ingest"
        rec.facet_records.append(
            {
                "facet_id": "noise",
                "family": "noise",
                "aliases": [name.lower()],
                "evidence": [name],
                "unknown": [],
                "conflicts": [],
            }
        )
        derive_facet_records(rec)
        added += 1
    return added


def scaled_ingested_store(n: int) -> tuple[ResearchStore, list[dict[str, Any]]]:
    store, reports = ingest_core_store()
    extra = max(0, n - len(store.records))
    if extra:
        add_noise_records(store, extra)
    return store, reports
