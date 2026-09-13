"""Query Generator — Requirement to 1–3 search queries (experimental PoC)."""
from __future__ import annotations

import re
from typing import Any


def _extract_topic(requirement: str) -> str:
    req = requirement.strip()
    patterns = [
        r"(?:Tool|ツール).*?(?:作|創|build|create)",
        r"(.+?)(?:するTool|ツール|Tool)",
        r"(.+?)(?:を|で).*?(?:解析|処理|変換|制御)",
    ]
    for pat in patterns:
        m = re.search(pat, req, re.I)
        if m and m.lastindex and m.lastindex >= 1:
            topic = m.group(1).strip()
            if len(topic) >= 3:
                return topic[:80]
    return req[:80]


def generate_search_queries(
    user_requirement: str,
    *,
    max_queries: int = 3,
    extra_terms: list[str] | None = None,
) -> list[str]:
    """Generate up to 3 search queries from requirement. No autonomous bulk search."""
    topic = _extract_topic(user_requirement)
    terms = list(extra_terms or [])
    lower = user_requirement.lower()

    queries: list[str] = []

    if "ur" in lower or "urscript" in lower or "universal robot" in lower:
        queries.extend([
            "Universal Robots URScript official documentation",
            "URScript command reference PolyScope",
            "Universal Robots SDK API documentation",
        ])
    elif "pdf" in lower:
        queries.extend([
            f"{topic} Python library official documentation",
            "PDF parsing Python library GitHub",
            "PDF API service documentation",
        ])
    elif "pytorch" in lower or "cuda" in lower or "gpu" in lower:
        queries.extend([
            f"{topic} PyTorch CUDA requirements official",
            "PyTorch GPU installation Python version",
            f"{topic} Docker GPU documentation",
        ])
    elif "polars" in lower or "dataframe" in lower:
        queries.extend([
            f"Polars Python library official documentation",
            f"{topic} Python data processing library",
            f"Polars GitHub SDK",
        ])
    else:
        queries.extend([
            f"{topic} official documentation",
            f"{topic} Python library GitHub",
            f"{topic} API SDK",
        ])

    for t in terms:
        q = f"{topic} {t}".strip()
        if q not in queries:
            queries.append(q)

    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        qn = q.strip()
        if qn and qn not in seen:
            seen.add(qn)
            out.append(qn)
        if len(out) >= max_queries:
            break
    return out[:max_queries]
