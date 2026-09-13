"""Phase N+1 fixtures — generalized TDA facets (not UR-only, not a Core)."""
from __future__ import annotations

from typing import Any

from ai_tool.experimental.development_assistance.research_record import ResearchRecord

# Domain-agnostic catalog tags. Routing retrieves envelopes; discovery does not judge.
GENERAL_TDA_CATALOG: list[dict[str, Any]] = [
    {"facet_id": "python_version", "family": "environment", "aliases": ["python", "3.12", "3.13"], "evidence": ["Python version fact"], "unknown": [], "conflicts": ["3.12 vs 3.13"]},
    {"facet_id": "cuda", "family": "dependency", "aliases": ["cuda", "12.3"], "evidence": ["CUDA 12.3 recorded"], "unknown": [], "conflicts": []},
    {"facet_id": "license", "family": "license", "aliases": ["license", "ライセンス", "mit", "gpl"], "evidence": ["License Y"], "unknown": [], "conflicts": []},
    {"facet_id": "docker", "family": "container", "aliases": ["docker", "container"], "evidence": [], "unknown": ["Docker runtime not recorded on A"], "conflicts": []},
    {"facet_id": "storage", "family": "container", "aliases": ["storage", "volume"], "evidence": [], "unknown": [], "conflicts": []},
    {"facet_id": "os", "family": "environment", "aliases": ["windows", "linux", "os"], "evidence": ["Windows"], "unknown": [], "conflicts": []},
    {"facet_id": "hardware", "family": "environment", "aliases": ["rtx", "3060", "gpu"], "evidence": ["RTX 3060"], "unknown": [], "conflicts": []},
    {"facet_id": "vram", "family": "environment", "aliases": ["12gb", "vram", "12GB"], "evidence": ["12GB"], "unknown": [], "conflicts": []},
    {"facet_id": "runtime", "family": "environment", "aliases": ["runtime"], "evidence": [], "unknown": [], "conflicts": []},
    {"facet_id": "dependencies", "family": "dependency", "aliases": ["dependency", "依存"], "evidence": ["NumPy", "PyTorch"], "unknown": [], "conflicts": []},
    {"facet_id": "gpu_passthrough", "family": "container", "aliases": ["passthrough", "nvidia-docker"], "evidence": [], "unknown": ["GPU passthrough not measured"], "conflicts": []},
    {"facet_id": "version", "family": "version", "aliases": ["version", "5.15", "5.17"], "evidence": ["A version X"], "unknown": [], "conflicts": ["5.17 must not apply to 5.15"]},
    {"facet_id": "conflict", "family": "meta", "aliases": ["conflict", "競合"], "evidence": [], "unknown": [], "conflicts": ["version isolation"]},
    {"facet_id": "api_availability", "family": "api", "aliases": ["api", "available"], "evidence": [], "unknown": ["Whether API exists on current A"], "conflicts": []},
    {"facet_id": "source", "family": "meta", "aliases": ["source", "出典"], "evidence": ["official docs"], "unknown": [], "conflicts": []},
    {"facet_id": "currentness", "family": "meta", "aliases": ["current", "最新"], "evidence": [], "unknown": ["API currentness not dated"], "conflicts": []},
    {"facet_id": "distribution", "family": "license", "aliases": ["distribution", "配布"], "evidence": [], "unknown": ["Distribution terms not extracted"], "conflicts": []},
    {"facet_id": "modification", "family": "license", "aliases": ["modification", "改変"], "evidence": [], "unknown": ["Modification terms not extracted"], "conflicts": []},
    {"facet_id": "performance", "family": "performance", "aliases": ["performance", "vram"], "evidence": [], "unknown": ["Runtime performance not measured"], "conflicts": []},
    {"facet_id": "numpy", "family": "noise", "aliases": ["numpy"], "evidence": ["NumPy present"], "unknown": [], "conflicts": []},
]


def record_a(*, python: str = "Python 3.13", extra_python_versions: tuple[str, ...] = ("3.12", "3.13")) -> dict[str, Any]:
    vfs = [{"technology": "Python", "version": v} for v in extra_python_versions]
    vfs.append({"technology": "CUDA", "version": "12.3", "cuda": "12.3"})
    vfs.append({"technology": "PyTorch", "version": "X", "python": python, "cuda": "CUDA 12.3"})
    return {
        "research_id": "RR-A",
        "requirement": "Aについて調べて。",
        "topic": "A PyTorch / NumPy stack",
        "technology_candidates": [
            {
                "candidate_id": "A",
                "name": "LibA",
                "type": "OSS library",
                "version": "X",
                "license": "Y",
                "environment": {
                    "python": python,
                    "cuda": "CUDA 12.3",
                    "os": "Windows",
                    "gpu": "RTX 3060",
                    "vram": "12GB",
                },
            }
        ],
        "version_facts": vfs,
        "environment_facts": {
            "python": python,
            "cuda": "CUDA 12.3",
            "os": "Windows",
            "gpu": "RTX 3060",
            "vram": "12GB",
            "label": "A",
        },
        "license_facts": ["Y"],
        "api_observations": [],
        "sources": [{"title": "A docs", "url": "https://example.invalid/a", "category": "official"}],
        "unknowns": ["GPU passthrough not measured"],
        "conflicts": [{"id": "py-312-vs-313", "summary": "Python 3.12 evidence is not 3.13 evidence."}],
        "queries": ["A pytorch"],
        "checked_at": "2026-08-30T09:00:00+00:00",
        "provenance": "phase_n1_fixture",
        "facet_records": list(GENERAL_TDA_CATALOG),
    }


def record_b() -> dict[str, Any]:
    payload = record_a(python="Python 3.12")
    payload["research_id"] = "RR-B"
    payload["requirement"] = "Bについて調べて。"
    payload["topic"] = "B alternative library"
    payload["environment_facts"]["label"] = "B"
    payload["technology_candidates"][0]["candidate_id"] = "B"
    payload["technology_candidates"][0]["name"] = "LibB"
    payload["license_facts"] = ["Z"]
    return payload


def record_a_515_517() -> dict[str, Any]:
    return {
        "research_id": "RR-A-VER",
        "requirement": "A 5.15 vs notes that mention 5.17",
        "topic": "A version isolation",
        "technology_candidates": [{"name": "A", "version": "5.15", "license": "Y"}],
        "version_facts": [
            {"technology": "A", "version": "5.15", "applies_to": "5.15"},
            {"technology": "A", "version": "5.17", "does_not_apply": "do not apply 5.17 to 5.15"},
        ],
        "environment_facts": {"label": "A", "product_version": "5.15"},
        "license_facts": ["Y"],
        "api_observations": [],
        "sources": [],
        "unknowns": ["5.17 behavior on 5.15 unknown"],
        "conflicts": [{"id": "v517-vs-v515", "summary": "5.17 must not apply to 5.15"}],
        "queries": [],
        "checked_at": "2026-08-30T09:00:00+00:00",
        "provenance": "phase_n1_fixture",
        "facet_records": [f for f in GENERAL_TDA_CATALOG if f["facet_id"] in {"version", "conflict"}],
    }


def typed_record(payload: dict[str, Any]) -> ResearchRecord:
    from dataclasses import fields

    names = {f.name for f in fields(ResearchRecord)}
    return ResearchRecord(**{k: v for k, v in payload.items() if k in names})
