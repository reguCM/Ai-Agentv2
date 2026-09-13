"""API existence observation — FOUND/NOT_FOUND/UNKNOWN, not mechanical correctness."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

ObservedStatus = Literal["FOUND", "NOT_FOUND", "UNKNOWN"]


@dataclass
class APIObservation:
    api_name: str
    source: str
    version: str
    document_section: str
    observed_status: ObservedStatus
    unknown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def observe_api_in_text(
    api_name: str,
    text: str,
    *,
    source: str = "",
    version: str = "UNKNOWN",
    section: str = "",
) -> APIObservation:
    """Check if API name appears in source text — presence ≠ correctness."""
    pattern = re.compile(re.escape(api_name), re.I)
    if pattern.search(text):
        return APIObservation(
            api_name=api_name,
            source=source,
            version=version,
            document_section=section or "body",
            observed_status="FOUND",
        )
    return APIObservation(
        api_name=api_name,
        source=source,
        version=version,
        document_section=section or "body",
        observed_status="NOT_FOUND",
        unknown="Not observed in provided source excerpt",
    )


def observe_apis_from_sources(
    api_names: list[str],
    sources: list[dict[str, Any]],
) -> list[APIObservation]:
    """Observe multiple API names across evidence sources."""
    out: list[APIObservation] = []
    for name in api_names:
        found = False
        for src in sources:
            text = str(src.get("main_text") or src.get("text") or "")
            obs = observe_api_in_text(
                name,
                text,
                source=str(src.get("url") or src.get("title") or ""),
                version=str(src.get("version") or "UNKNOWN"),
            )
            if obs.observed_status == "FOUND":
                out.append(obs)
                found = True
                break
        if not found:
            out.append(
                APIObservation(
                    api_name=name,
                    source="",
                    version="UNKNOWN",
                    document_section="",
                    observed_status="UNKNOWN",
                    unknown="No source contained this API name",
                )
            )
    return out
