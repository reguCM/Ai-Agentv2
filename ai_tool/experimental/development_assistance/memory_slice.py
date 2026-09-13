"""Mechanical memory slice — bind / diff / select. Not a Reasoning Core.

Compares dumping every ResearchRecord Facet into LLM material vs
passing only the bound record's needed Facets. Does not ask an LLM
to organize memory.
"""
from __future__ import annotations

import re
from typing import Any

from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore

# Must not appear on a bound-A slice.
FOREIGN_ON_A = frozenset(
    {"ursim", "ros", "nodejs", "control_authority", "dashboard", "docker"}
)


def iter_memory_facets(store: ResearchStore) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rec in store.records:
        for f in rec.facet_records or []:
            fid = str(f.get("facet_id") or "")
            if not fid:
                continue
            rows.append(
                {
                    "research_id": rec.research_id,
                    "label": str((rec.environment_facts or {}).get("label") or ""),
                    "facet_id": fid,
                }
            )
    return rows


def dump_all_for_llm(store: ResearchStore) -> dict[str, Any]:
    """Path A: every stored Facet. Not recommended; measured as baseline."""
    rows = iter_memory_facets(store)
    ids = [f"{r['research_id']}:{r['facet_id']}" for r in rows]
    return {
        "mode": "dump_all",
        "facet_rows": rows,
        "facet_count": len(rows),
        "record_count": len(store.records),
        "ids": ids,
        "note": "All memory. LLM is not asked to sort this.",
    }


def select_bound_facets(
    store: ResearchStore,
    *,
    bound_research_id: str,
    session_facet_ids: list[str],
    missing_facet_ids: list[str],
) -> dict[str, Any]:
    """Path B: only the bound record, and only named session / missing Facets."""
    wanted = list(dict.fromkeys([*session_facet_ids, *missing_facet_ids]))
    selected: list[dict[str, str]] = [
        {"research_id": bound_research_id, "facet_id": fid} for fid in wanted if fid
    ]
    foreign = [s["facet_id"] for s in selected if s["facet_id"] in FOREIGN_ON_A]
    other_records = [
        r.research_id for r in store.records if r.research_id != bound_research_id
    ]
    leaked = [
        row
        for row in iter_memory_facets(store)
        if row["research_id"] != bound_research_id and row["facet_id"] in {s["facet_id"] for s in selected}
        and row["facet_id"] in FOREIGN_ON_A
    ]
    return {
        "mode": "mechanical_slice",
        "bound_research_id": bound_research_id,
        "selected": selected,
        "facet_count": len(selected),
        "foreign_on_a": foreign,
        "other_record_ids": other_records,
        "cross_record_foreign_leak": leaked,
        "guessed": False,
    }


def compare_llm_payloads(
    store: ResearchStore,
    *,
    bound_research_id: str,
    session_facet_ids: list[str],
    missing_facet_ids: list[str],
    expected_ids: list[str] | None = None,
) -> dict[str, Any]:
    dumped = dump_all_for_llm(store)
    sliced = select_bound_facets(
        store,
        bound_research_id=bound_research_id,
        session_facet_ids=session_facet_ids,
        missing_facet_ids=missing_facet_ids,
    )
    selected_ids = [s["facet_id"] for s in sliced["selected"]]
    expected = list(expected_ids or session_facet_ids)
    recall = (len(set(expected) & set(selected_ids)) / len(expected)) if expected else 1.0
    all_n = dumped["facet_count"] or 1
    return {
        "all_memory_facet_count": dumped["facet_count"],
        "all_memory_record_count": dumped["record_count"],
        "llm_dump_all_facet_count": dumped["facet_count"],
        "llm_slice_facet_count": sliced["facet_count"],
        "reduction": round(1.0 - (sliced["facet_count"] / all_n), 4),
        "relevant_facet_recall": recall,
        "irrelevant_suppression": 1.0 if not sliced["foreign_on_a"] else 0.0,
        "cross_record_contamination": len(sliced["cross_record_foreign_leak"]),
        "dump_all": dumped,
        "slice": sliced,
        "selected_ids": selected_ids,
        "design_note": (
            "Memory all → mechanical bind → Facet diff → select → "
            "only the small set to LLM. Not a new Core."
        ),
    }


def hydrate_session_slots(rec: ResearchRecord) -> dict[str, str]:
    """Copy this record's named env only. Do not merge other records."""
    env = rec.environment_facts or {}
    out: dict[str, str] = {}
    py = str(env.get("python") or "")
    m = re.search(r"3\.\d+", py)
    if m:
        out["python_version"] = m.group(0)
    if env.get("os"):
        out["os"] = str(env["os"]).lower()
    cuda = str(env.get("cuda") or "")
    cm = re.search(r"12(?:\.\d+)?", cuda)
    if cm:
        out["cuda"] = cm.group(0)
    if rec.license_facts:
        out["license"] = str(rec.license_facts[0])
    return out
