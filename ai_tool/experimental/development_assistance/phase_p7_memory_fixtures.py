"""P-7 memory fixtures — distributed ResearchRecords, not one giant record.

Not a Knowledge Base. Each record keeps its own facet_records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore


def _ts() -> str:
    return datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc).isoformat()


def _rec(
    *,
    research_id: str,
    label: str,
    name: str,
    requirement: str,
    topic: str,
    env: dict[str, str],
    license_facts: list[str],
    version_facts: list[dict[str, Any]],
    facet_records: list[dict[str, Any]],
    unknowns: list[str] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    env = {**env, "label": label}
    return {
        "research_id": research_id,
        "requirement": requirement,
        "topic": topic,
        "technology_candidates": [
            {
                "candidate_id": label,
                "name": name,
                "type": "OSS library",
                "version": env.get("product_version") or "X",
                "license": license_facts[0] if license_facts else "UNKNOWN",
                "environment": dict(env),
            }
        ],
        "version_facts": version_facts,
        "environment_facts": env,
        "license_facts": license_facts,
        "api_observations": [],
        "sources": [{"title": f"{label} docs", "url": f"https://example.invalid/{label.lower()}", "category": "official"}],
        "unknowns": list(unknowns or []),
        "conflicts": list(conflicts or []),
        "queries": [requirement],
        "checked_at": _ts(),
        "provenance": "phase_p7_fixture",
        "facet_records": facet_records,
    }


def record_a_mem() -> dict[str, Any]:
    return _rec(
        research_id="RR-A",
        label="A",
        name="LibA",
        requirement="Aについて調べて。",
        topic="A library",
        env={"python": "Python 3.12", "os": "Windows", "cuda": "CUDA 12.3"},
        license_facts=["Y"],
        version_facts=[
            {"technology": "Python", "version": "3.12"},
            {"technology": "CUDA", "version": "12.3", "cuda": "12.3"},
        ],
        facet_records=[
            {"facet_id": "python_version", "family": "environment", "aliases": ["python", "3.12"], "evidence": ["Python 3.12"], "unknown": [], "conflicts": ["3.12 vs 3.13"]},
            {"facet_id": "os", "family": "environment", "aliases": ["windows"], "evidence": ["Windows"], "unknown": [], "conflicts": []},
            {"facet_id": "cuda", "family": "dependency", "aliases": ["cuda", "12.3"], "evidence": ["CUDA 12.3"], "unknown": [], "conflicts": []},
            {"facet_id": "license", "family": "license", "aliases": ["license", "Y"], "evidence": ["License Y"], "unknown": [], "conflicts": []},
        ],
        conflicts=[{"id": "py-312-vs-313", "summary": "Python 3.12 evidence is not 3.13 evidence."}],
        unknowns=["Python 3.13: no official information"],
    )


def record_b_mem() -> dict[str, Any]:
    return _rec(
        research_id="RR-B",
        label="B",
        name="LibB",
        requirement="Bについて調べて。",
        topic="B library",
        env={"python": "Python 3.13", "os": "Linux", "cuda": "CUDA 12.4"},
        license_facts=["Z"],
        version_facts=[
            {"technology": "Python", "version": "3.13"},
            {"technology": "CUDA", "version": "12.4", "cuda": "12.4"},
        ],
        facet_records=[
            {"facet_id": "python_version", "family": "environment", "aliases": ["python", "3.13"], "evidence": ["Python 3.13"], "unknown": [], "conflicts": []},
            {"facet_id": "os", "family": "environment", "aliases": ["linux"], "evidence": ["Linux"], "unknown": [], "conflicts": []},
            {"facet_id": "cuda", "family": "dependency", "aliases": ["cuda", "12.4"], "evidence": ["CUDA 12.4"], "unknown": [], "conflicts": []},
            {"facet_id": "license", "family": "license", "aliases": ["license", "Z"], "evidence": ["License Z"], "unknown": [], "conflicts": []},
        ],
    )


def record_c_mem() -> dict[str, Any]:
    return _rec(
        research_id="RR-C",
        label="C",
        name="LibC",
        requirement="Cについて調べて。",
        topic="C container ROS",
        env={"os": "Ubuntu", "docker": "docker", "ros": "ROS"},
        license_facts=["X"],
        version_facts=[],
        facet_records=[
            {"facet_id": "docker", "family": "container", "aliases": ["docker"], "evidence": ["Docker"], "unknown": [], "conflicts": []},
            {"facet_id": "os", "family": "environment", "aliases": ["ubuntu", "linux"], "evidence": ["Ubuntu"], "unknown": [], "conflicts": []},
            {"facet_id": "ros", "family": "middleware", "aliases": ["ros"], "evidence": ["ROS"], "unknown": [], "conflicts": []},
            {"facet_id": "license", "family": "license", "aliases": ["license", "X"], "evidence": ["License X"], "unknown": [], "conflicts": []},
        ],
    )


def record_d_mem() -> dict[str, Any]:
    return _rec(
        research_id="RR-D",
        label="D",
        name="URSim",
        requirement="URSimについて調べて。",
        topic="URSim 5.15.2",
        env={"ursim_version": "5.15.2", "product": "UR", "dashboard": "Dashboard"},
        license_facts=["UR"],
        version_facts=[{"technology": "URSim", "version": "5.15.2", "applies_to": "5.15.2"}],
        facet_records=[
            {"facet_id": "ursim", "family": "runtime", "aliases": ["ursim", "5.15.2"], "evidence": ["URSim 5.15.2"], "unknown": [], "conflicts": ["do not apply 5.17 to 5.15.2"]},
            {"facet_id": "version", "family": "version", "aliases": ["5.15.2", "ur"], "evidence": ["5.15.2"], "unknown": [], "conflicts": []},
            {"facet_id": "dashboard", "family": "api", "aliases": ["dashboard"], "evidence": ["Dashboard"], "unknown": [], "conflicts": []},
            {"facet_id": "control_authority", "family": "ops", "aliases": ["control authority"], "evidence": [], "unknown": ["not asserted"], "conflicts": []},
        ],
        unknowns=["5.17 behavior on 5.15.2 unknown"],
    )


def record_e_mem() -> dict[str, Any]:
    return _rec(
        research_id="RR-E",
        label="E",
        name="LibE",
        requirement="Eについて調べて。",
        topic="E Node.js",
        env={"os": "Windows", "runtime": "Node.js"},
        license_facts=["Y"],
        version_facts=[{"technology": "Node.js", "version": "UNKNOWN"}],
        facet_records=[
            {"facet_id": "nodejs", "family": "runtime", "aliases": ["node.js", "nodejs"], "evidence": ["Node.js"], "unknown": [], "conflicts": []},
            {"facet_id": "os", "family": "environment", "aliases": ["windows"], "evidence": ["Windows"], "unknown": [], "conflicts": []},
            {"facet_id": "license", "family": "license", "aliases": ["license", "Y"], "evidence": ["License Y"], "unknown": [], "conflicts": []},
        ],
    )


def record_win_py(research_id: str, label: str, python: str, os_name: str) -> dict[str, Any]:
    return _rec(
        research_id=research_id,
        label=label,
        name=f"Lib{label}",
        requirement=f"{label}について調べて。",
        topic=f"{label} {os_name} {python}",
        env={"python": python, "os": os_name},
        license_facts=["Y"],
        version_facts=[{"technology": "Python", "version": python.replace("Python ", "")}],
        facet_records=[
            {"facet_id": "python_version", "family": "environment", "aliases": ["python", python.replace("Python ", "")], "evidence": [python], "unknown": [], "conflicts": []},
            {"facet_id": "os", "family": "environment", "aliases": [os_name.lower()], "evidence": [os_name], "unknown": [], "conflicts": []},
        ],
    )


def typed(payload: dict[str, Any]) -> ResearchRecord:
    from dataclasses import fields

    names = {f.name for f in fields(ResearchRecord)}
    return ResearchRecord(**{k: v for k, v in payload.items() if k in names})


def multi_record_store() -> ResearchStore:
    store = ResearchStore()
    for fn in (record_a_mem, record_b_mem, record_c_mem, record_d_mem, record_e_mem):
        store.add(typed(fn()))
    return store


def overlap_store() -> ResearchStore:
    """Same Facet on several records: Windows+3.12 / Windows+3.13 / Linux+3.12."""
    store = ResearchStore()
    store.add(typed(record_win_py("RR-WA", "WA", "Python 3.12", "Windows")))
    store.add(typed(record_win_py("RR-WB", "WB", "Python 3.13", "Windows")))
    store.add(typed(record_win_py("RR-LC", "LC", "Python 3.12", "Linux")))
    return store


def _filler(i: int) -> dict[str, Any]:
    n = f"N{i:03d}"
    return _rec(
        research_id=f"RR-{n}",
        label=n,
        name=f"Lib{n}",
        requirement=f"{n}について調べて。",
        topic=f"noise {n}",
        env={"python": "Python 3.10", "os": "Linux", "cuda": "CUDA 11.8"},
        license_facts=["N"],
        version_facts=[{"technology": "Python", "version": "3.10"}],
        facet_records=[
            {"facet_id": "python_version", "family": "environment", "aliases": ["python", "3.10"], "evidence": ["3.10"], "unknown": [], "conflicts": []},
            {"facet_id": "os", "family": "environment", "aliases": ["linux"], "evidence": ["Linux"], "unknown": [], "conflicts": []},
            {"facet_id": "noise", "family": "noise", "aliases": [n.lower()], "evidence": [n], "unknown": [], "conflicts": []},
        ],
    )


def scaled_store(n: int) -> ResearchStore:
    """5 / 20 / 50 / 100 Record 相当。A は RR-A のまま。追加分は無関係な記憶。"""
    store = multi_record_store()
    extra = max(0, n - len(store.records))
    for i in range(extra):
        store.add(typed(_filler(i)))
    return store
