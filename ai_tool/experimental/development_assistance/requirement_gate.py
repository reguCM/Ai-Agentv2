"""Requirement Gate — decide if Web Research is needed (experimental PoC)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

GateDecision = Literal["RESEARCH_REQUIRED", "RESEARCH_NOT_REQUIRED"]

# Signals that LLM knowledge alone is often insufficient.
_NICHE_MARKERS = (
    "urscript",
    "ur robot",
    "universal robot",
    "polyscope",
    "最新版",
    "latest version",
    "2025",
    "2026",
    "niche",
    "マイナー",
    "新しいoss",
    "new library",
    "sdk",
    "proprietary",
    "独自仕様",
    "specialized",
    "専門",
)

_VERSION_DEPENDENCY = re.compile(
    r"(?:version|バージョン|v?\d+\.\d+|python\s*3\.|cuda|pytorch|node\.?js)",
    re.I,
)

_ENV_DEPENDENCY = re.compile(
    r"(?:cuda|gpu|vram|docker|windows|linux|macos|api\s*key|database|browser)",
    re.I,
)

# Well-known patterns where research is usually unnecessary for PoC.
_GENERAL_PATTERNS = (
    r"json\s*ファイル.*読",
    r"read\s*json",
    r"csv\s*ファイル.*読",
    r"read\s*csv",
    r"テキストファイル.*読",
    r"read\s*text\s*file",
    r"ファイル.*存在.*確認",
    r"list\s*files",
)


@dataclass
class GateResult:
    decision: GateDecision
    reasons: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_research_requirement(
    user_requirement: str,
    *,
    force_research: bool | None = None,
    case_hint: str = "",
) -> GateResult:
    """Deterministic gate for PoC — not connected to Production Agent."""
    req = user_requirement.strip()
    lower = req.lower()
    reasons: list[str] = []
    signals: dict[str, Any] = {
        "freshness": False,
        "specificity": "medium",
        "uncertainty": False,
        "version_dependency": bool(_VERSION_DEPENDENCY.search(req)),
        "environment_dependency": bool(_ENV_DEPENDENCY.search(req)),
        "user_explicit_research": "調べ" in req or "research" in lower or "web" in lower,
    }

    if force_research is True:
        return GateResult("RESEARCH_REQUIRED", ["forced by case spec"], signals)
    if force_research is False:
        return GateResult("RESEARCH_NOT_REQUIRED", ["forced not required by case spec"], signals)

    if case_hint.startswith("TDA-A"):
        return GateResult("RESEARCH_NOT_REQUIRED", ["Case A — general well-known tool"], signals)

    for pat in _GENERAL_PATTERNS:
        if re.search(pat, lower):
            if not signals["version_dependency"] and not signals["environment_dependency"]:
                return GateResult(
                    "RESEARCH_NOT_REQUIRED",
                    ["General file/JSON operation — LLM knowledge likely sufficient"],
                    signals,
                )

    if signals["user_explicit_research"]:
        reasons.append("User explicitly requested research")

    if any(m in lower for m in _NICHE_MARKERS):
        reasons.append("Niche/specialized domain detected")
        signals["uncertainty"] = True

    if signals["version_dependency"]:
        reasons.append("Version dependency detected")
        signals["freshness"] = True

    if signals["environment_dependency"]:
        reasons.append("Environment dependency detected")
        signals["uncertainty"] = True

    if case_hint.startswith(("TDA-B", "TDA-C", "TDA-D", "TDA-E", "TDA-F", "TDA-G", "TDA-H")):
        reasons.append(f"Evaluation case {case_hint} expects research")

    if reasons:
        return GateResult("RESEARCH_REQUIRED", reasons, signals)

    return GateResult(
        "RESEARCH_NOT_REQUIRED",
        ["No strong research signals — default LLM-only path"],
        signals,
    )
