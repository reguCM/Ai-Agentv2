"""Technology Candidate builder from Web Evidence (experimental PoC)."""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from ai_tool.experimental.conversation_resolution.candidate_builder import (
    build_candidates_from_sources,
    classify_candidate_relation,
    choose_presentation_mode,
    difference_note,
)
from ai_tool.experimental.conversation_resolution.models import Candidate
from ai_tool.experimental.evidence_context.packager import EvidenceSource

CandidateType = Literal[
    "OSS",
    "Library",
    "API",
    "SDK",
    "Framework",
    "Service",
    "Existing Tool",
    "Custom Build",
    "Unknown",
]

SourceCategory = Literal[
    "Official Documentation",
    "Official GitHub",
    "API Reference",
    "Official Example",
    "Technical Documentation",
    "Other",
]

_VERSION_RE = re.compile(r"(?:v(?:ersion)?\s*)?(\d+\.\d+(?:\.\d+)?)", re.I)
_PYTHON_RE = re.compile(r"python\s*(3\.\d+(?:\.\d+)?)?", re.I)
_LICENSE_RE = re.compile(r"\b(MIT|Apache(?:\s*2\.0)?|GPL(?:v?\d+)?|BSD|ISC)\b", re.I)
_CUDA_RE = re.compile(r"\b(CUDA\s*\d+(?:\.\d+)?|cuda)\b", re.I)
_DOCKER_RE = re.compile(r"\bdocker\b", re.I)
_GPU_RE = re.compile(r"\b(GPU|VRAM|CUDA)\b", re.I)


def _infer_source_category(url: str, title: str) -> SourceCategory:
    u = url.lower()
    t = title.lower()
    if "github.com" in u:
        return "Official GitHub"
    if "api" in u or "api reference" in t or "reference" in t:
        return "API Reference"
    if "example" in t or "tutorial" in t:
        return "Official Example"
    if "docs." in u or "documentation" in t or "manual" in t or "universal-robots.com" in u:
        return "Official Documentation"
    if "wiki" in u:
        return "Technical Documentation"
    return "Other"


def _infer_candidate_type(url: str, title: str, text: str) -> CandidateType:
    blob = f"{url} {title} {text}".lower()
    if "api." in url or " api " in blob or "rest api" in blob:
        return "API"
    if "sdk" in blob:
        return "SDK"
    if "github.com" in url:
        return "OSS"
    if "framework" in blob:
        return "Framework"
    if "service" in blob or "cloud" in blob:
        return "Service"
    if "library" in blob or "pip install" in blob:
        return "Library"
    return "Unknown"


def _extract_environment(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    py = _PYTHON_RE.search(text)
    if py:
        env["python"] = py.group(0)
    cuda = _CUDA_RE.search(text)
    if cuda:
        env["cuda"] = cuda.group(0)
    if _DOCKER_RE.search(text):
        env["docker"] = "mentioned"
    if _GPU_RE.search(text):
        env["gpu"] = "mentioned"
    if "windows" in text.lower():
        env["os"] = "Windows"
    elif "linux" in text.lower():
        env["os"] = "Linux"
    return env


def _extract_versions(text: str) -> list[str]:
    return list(dict.fromkeys(_VERSION_RE.findall(text)))[:5]


def _extract_name(title: str, url: str) -> str:
    if title and title != url:
        return title[:120]
    path = urlparse(url).path.strip("/")
    if path:
        return path.split("/")[-1][:120]
    return url[:120]


@dataclass
class TechnologyCandidate:
    candidate_id: str
    name: str
    type: CandidateType
    description: str
    source_ids: list[str]
    url: str
    source_title: str
    source_category: SourceCategory
    version: str = "UNKNOWN"
    environment: dict[str, str] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    license: str = "UNKNOWN"
    unknowns: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    claim: str = ""
    evidence_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_technology_candidates(
    sources: list[EvidenceSource],
    *,
    topic: str = "",
) -> list[TechnologyCandidate]:
    """Build technology candidates from evidence — no fabricated fields."""
    base = build_candidates_from_sources(sources, topic=topic)
    tech: list[TechnologyCandidate] = []
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for i, (src, cand) in enumerate(zip(sources, base)):
        text = src.main_text
        sid = f"S{i + 1}"
        versions = _extract_versions(text)
        env = _extract_environment(text)
        lic = _LICENSE_RE.search(text)
        ctype = _infer_candidate_type(src.url, src.title, text)
        scat = _infer_source_category(src.url, src.title)

        caps: list[str] = []
        lims: list[str] = []
        unknowns: list[str] = []

        if ctype in ("OSS", "Library"):
            caps.append("Installable library/component")
        if ctype == "API":
            caps.append("Remote API integration")
            lims.append("External service dependency")
        if not versions:
            unknowns.append("version")
        if not env:
            unknowns.append("environment")
        if not lic:
            unknowns.append("license")

        tech.append(
            TechnologyCandidate(
                candidate_id=f"TC{labels[i]}",
                name=_extract_name(src.title, src.url),
                type=ctype,
                description=cand.claim or text[:200],
                source_ids=[sid],
                url=src.url,
                source_title=src.title,
                source_category=scat,
                version=versions[0] if versions else "UNKNOWN",
                environment=env,
                capabilities=caps,
                limitations=lims,
                license=lic.group(0) if lic else "UNKNOWN",
                unknowns=unknowns,
                claim=cand.claim,
                evidence_id=f"E{i + 1}",
                metadata={
                    "backend": src.backend,
                    "all_versions": versions,
                    "fact_ready": (src.quality or {}).get("fact_ready"),
                },
            )
        )
    return tech


def add_custom_build_candidate(
    candidates: list[TechnologyCandidate],
    *,
    requirement: str,
) -> TechnologyCandidate:
    """Add Custom Build as a non-web candidate option."""
    cid = f"TC{chr(ord('A') + len(candidates))}"
    custom = TechnologyCandidate(
        candidate_id=cid,
        name="Custom Build",
        type="Custom Build",
        description=f"Self-built Tool for: {requirement[:100]}",
        source_ids=[],
        url="",
        source_title="(no external source — design option)",
        source_category="Other",
        version="UNKNOWN",
        capabilities=["Full control", "No external dependency (if feasible)"],
        limitations=["Higher development cost", "Maintenance burden"],
        unknowns=["implementation effort", "long-term maintenance"],
        metadata={"synthetic": True},
    )
    candidates.append(custom)
    return custom


def detect_conflicts(candidates: list[TechnologyCandidate]) -> list[dict[str, Any]]:
    """Detect version/environment conflicts across candidates — do not resolve."""
    conflicts: list[dict[str, Any]] = []
    versions = [(c.candidate_id, c.version) for c in candidates if c.version != "UNKNOWN"]
    if len(set(v for _, v in versions)) >= 2 and len(versions) >= 2:
        conflicts.append(
            {
                "conflict_type": "version_requirement",
                "sources": [c for c, _ in versions],
                "details": dict(versions),
            }
        )
    py_versions: list[tuple[str, str]] = []
    for c in candidates:
        py = c.environment.get("python")
        if py:
            py_versions.append((c.candidate_id, py))
    if len(set(v for _, v in py_versions)) >= 2:
        conflicts.append(
            {
                "conflict_type": "python_version",
                "sources": [c for c, _ in py_versions],
                "details": dict(py_versions),
            }
        )
    for c in candidates:
        c.conflicts = [x for x in conflicts if c.candidate_id in x.get("sources", [])]
    return conflicts


def tech_candidates_to_envelope(
    candidates: list[TechnologyCandidate],
    *,
    user_request: str,
    relation: str | None = None,
) -> dict[str, Any]:
    """Envelope for LLM proposal."""
    web_cands = [c for c in candidates if c.type != "Custom Build"]
    proxy: list[Candidate] = [
        Candidate(
            candidate_id=c.candidate_id,
            label=c.candidate_id,
            claim=c.description,
            evidence_id=c.evidence_id or "",
            source_id=c.source_ids[0] if c.source_ids else "",
            url=c.url,
            source_title=c.source_title,
            definition_label=c.version if c.version != "UNKNOWN" else "unspecified",
            years=[int(c.version.split(".")[0])] if c.version != "UNKNOWN" and c.version[0].isdigit() else [],
            metadata={"type": c.type},
        )
        for c in web_cands
    ]

    rel = relation
    if rel is None and len(proxy) >= 2:
        rel = classify_candidate_relation(proxy)
    elif rel is None:
        rel = "SINGLE"

    mode = choose_presentation_mode(rel)  # type: ignore[arg-type]
    if any(c.type == "Custom Build" for c in candidates) and len(candidates) >= 2:
        mode = "MULTI"

    conflicts = detect_conflicts(web_cands)
    diff = difference_note(proxy, rel) if len(proxy) >= 2 else ""  # type: ignore[arg-type]

    return {
        "candidates": [c.to_dict() for c in candidates],
        "technology_candidates": [c.to_dict() for c in candidates],
        "relation": rel,
        "presentation_mode": mode,
        "difference_note": diff,
        "conflicts": conflicts,
        "user_request": user_request,
    }
