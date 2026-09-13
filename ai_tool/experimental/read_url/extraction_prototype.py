"""Experimental HTML extraction strategies — NOT Production.

Compares multiple normalization approaches without modifying html_normalize.py.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from html import unescape
from typing import Any, Callable

from ai_tool.experimental.read_url.html_normalize import (
    _extract_title,
    _looks_like_boilerplate_or_metadata,
    normalize_html_to_evidence,
)

StrategyId = str

_STRIP_TAGS = frozenset(
    {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg"}
)

_METADATA_PATTERNS: tuple[tuple[str, str], ...] = (
    ("infobox_table", r"(?is)<table\b[^>]*class=[^>]*infobox[^>]*>.*?</table>"),
    ("navbox", r"(?is)<div\b[^>]*class=[^>]*navbox[^>]*>.*?</div>"),
    ("metadata_div", r"(?is)<div\b[^>]*class=[^>]*metadata[^>]*>.*?</div>"),
    ("reference", r"(?is)<div\b[^>]*class=[^>]*reflist[^>]*>.*?</div>"),
    ("toc", r"(?is)<div\b[^>]*id=[\"']toc[\"'][^>]*>.*?</div>"),
    ("navbox_inner", r"(?is)<table\b[^>]*class=[^>]*navbox[^>]*>.*?</table>"),
    ("typeof_span", r"(?is)<span\b[^>]*typeof=[^>]*>.*?</span>"),
    ("json_ld_script", r"(?is)<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>.*?</script>"),
    ("inline_wikidata_json", r"(?is)\{[^{}]*\"@context\"[^{}]*\}"),
)

_WIKI_HOST_MARKERS = ("wikipedia.org", "wikimedia.org")


@dataclass
class ExtractionPrototypeResult:
    strategy_id: StrategyId
    strategy_label: str
    url: str | None
    main_text: str
    title: str | None
    extraction_method: str
    warnings: list[str]
    body_reached: bool
    fact_ready: bool
    fact_ready_reason: str
    removed_regions: list[str]
    diagnostics: dict[str, Any] = field(default_factory=dict)
    evidence_presence: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _strip_noise_tags(html: str) -> str:
    work = html or ""
    for tag in _STRIP_TAGS:
        work = re.sub(rf"(?is)<{tag}\b[^>]*>.*?</{tag}>", " ", work)
    work = re.sub(r"(?is)<!--.*?-->", " ", work)
    return work


def _html_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<br\s*/?>", "\n", fragment)
    text = re.sub(r"(?is)<(?:p|div|li|h[1-6]|tr|td|th|section|blockquote)\b[^>]*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fact_ready_reason(quality: dict[str, Any], main_text: str) -> str:
    if not quality.get("extraction_success"):
        return "extraction_failed"
    if not quality.get("body_reached"):
        return "body_not_reached"
    if quality.get("truncated"):
        return "main_text_truncated"
    warns = quality.get("warnings") or []
    if "main_text_looks_like_boilerplate_or_metadata" in warns:
        return "boilerplate_or_metadata_heuristic"
    if quality.get("fact_ready"):
        return "fact_ready_true"
    if len(main_text.strip()) < 40:
        return "main_text_too_short"
    return "heuristic_false_other"


def _build_quality(main_text: str, *, method: str, body_reached: bool, warnings: list[str]) -> dict[str, Any]:
    extraction_success = bool(main_text.strip())
    fact_ready = (
        extraction_success
        and len(main_text.strip()) >= 40
        and body_reached
        and not _looks_like_boilerplate_or_metadata(main_text)
    )
    if not fact_ready and extraction_success and _looks_like_boilerplate_or_metadata(main_text):
        if "main_text_looks_like_boilerplate_or_metadata" not in warnings:
            warnings.append("main_text_looks_like_boilerplate_or_metadata")
    if not fact_ready and extraction_success and not body_reached:
        if "main_text_present_but_body_region_uncertain" not in warnings:
            warnings.append("main_text_present_but_body_region_uncertain")
    return {
        "extraction_success": extraction_success,
        "body_reached": body_reached,
        "truncated": False,
        "fact_ready": fact_ready,
        "extraction_method": method,
        "warnings": warnings,
    }


def _extract_region(html: str, pattern: str, *, method: str) -> tuple[str, bool]:
    match = re.search(pattern, html)
    if match:
        return _html_to_text(match.group(1)), True
    body = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", html)
    if body:
        return _html_to_text(body.group(1)), True
    return _html_to_text(html), False


def _strip_metadata(html: str) -> tuple[str, list[str]]:
    work = html
    removed: list[str] = []
    for name, pat in _METADATA_PATTERNS:
        if re.search(pat, work):
            work = re.sub(pat, " ", work)
            removed.append(name)
    work = re.sub(r'(?is)\{"wt":', " ", work)
    if '"wt"' in html and '"wt"' not in work:
        removed.append("wikitext_json_fragments")
    return work, removed


def _evidence_presence(main_text: str, *, expect: str) -> dict[str, bool]:
    blob = main_text or ""
    pop_patterns = (
        r"人口",
        r"population",
        r"[0-9]{1,3}[,，][0-9]{3,}",
        r"[0-9]{3,}\s*人",
        r"[0-9]{1,4}\s*万\s*人",
    )
    cap_patterns = (r"東京", r"とうきょう", r"Tokyo", r"首都")
    nav_only_markers = ('"wt"', "jump to content", "メインメニュー", "sidebar")
    return {
        "population": any(re.search(p, blob, re.I) for p in pop_patterns),
        "capital": any(re.search(p, blob, re.I) for p in cap_patterns),
        "wikidata_boilerplate": blob.count('"wt"') >= 3,
        "navigation_only": sum(1 for m in nav_only_markers if m.lower() in blob.lower()) >= 2
        and len(blob.strip()) < 800,
        "non_empty": bool(blob.strip()),
    }


def _finalize(
    strategy_id: StrategyId,
    label: str,
    *,
    url: str | None,
    main_text: str,
    title: str | None,
    method: str,
    body_reached: bool,
    warnings: list[str],
    removed_regions: list[str],
    diagnostics: dict[str, Any],
    expect: str,
) -> ExtractionPrototypeResult:
    quality = _build_quality(main_text, method=method, body_reached=body_reached, warnings=list(warnings))
    return ExtractionPrototypeResult(
        strategy_id=strategy_id,
        strategy_label=label,
        url=url,
        main_text=main_text,
        title=title,
        extraction_method=method,
        warnings=list(quality.get("warnings") or []),
        body_reached=body_reached,
        fact_ready=bool(quality.get("fact_ready")),
        fact_ready_reason=_fact_ready_reason(quality, main_text),
        removed_regions=removed_regions,
        diagnostics=diagnostics,
        evidence_presence=_evidence_presence(main_text, expect=expect),
    )


def strategy_s0_production(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    evidence = normalize_html_to_evidence(html)
    quality = evidence.get("quality") or {}
    main_text = str(evidence.get("main_text") or "")
    return _finalize(
        "S0_PRODUCTION",
        "Production normalize_html_to_evidence",
        url=url,
        main_text=main_text,
        title=evidence.get("title"),
        method=str(quality.get("extraction_method") or "production"),
        body_reached=bool(quality.get("body_reached")),
        warnings=list(quality.get("warnings") or []),
        removed_regions=[],
        diagnostics={"source": "production_module"},
        expect=expect,
    )


def strategy_s1_mw_content_text(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    cleaned = _strip_noise_tags(html)
    text, reached = _extract_region(
        cleaned,
        r'(?is)<div\b[^>]*id=["\']mw-content-text["\'][^>]*>(.*?)(?=</div>\s*(?:<noscript|$)|\Z)',
        method="mw-content-text",
    )
    if len(text) < 100:
        text, reached = _extract_region(
            cleaned,
            r'(?is)<div\b[^>]*id=["\']mw-content-text["\'][^>]*>(.*)',
            method="mw-content-text_greedy",
        )
    return _finalize(
        "S1_MW_CONTENT",
        "#mw-content-text region",
        url=url,
        main_text=text,
        title=_extract_title(html),
        method="mw-content-text",
        body_reached=reached,
        warnings=[],
        removed_regions=[],
        diagnostics={},
        expect=expect,
    )


def strategy_s2_mw_parser_first(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    cleaned = _strip_noise_tags(html)
    text, reached = _extract_region(
        cleaned,
        r'(?is)<div\b[^>]*class=["\'][^"\']*mw-parser-output[^"\']*["\'][^>]*>(.*?)</div>',
        method="mw-parser-output_first",
    )
    return _finalize(
        "S2_MW_PARSER_FIRST",
        "First mw-parser-output match (baseline failure mode)",
        url=url,
        main_text=text,
        title=_extract_title(html),
        method="mw-parser-output_first",
        body_reached=reached,
        warnings=["first_parser_match_may_be_infobox"],
        removed_regions=[],
        diagnostics={},
        expect=expect,
    )


def strategy_s3_metadata_strip_content(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    cleaned = _strip_noise_tags(html)
    stripped, removed = _strip_metadata(cleaned)
    text, reached = _extract_region(
        stripped,
        r'(?is)<div\b[^>]*id=["\']mw-content-text["\'][^>]*>(.*)',
        method="metadata_strip_mw-content-text",
    )
    return _finalize(
        "S3_METADATA_STRIP",
        "Metadata strip + mw-content-text (investigation A4 class)",
        url=url,
        main_text=text,
        title=_extract_title(html),
        method="metadata_strip_mw-content-text",
        body_reached=reached,
        warnings=[],
        removed_regions=removed,
        diagnostics={"removed_count": len(removed)},
        expect=expect,
    )


def strategy_s4_paragraph_density(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    cleaned = _strip_noise_tags(html)
    stripped, removed = _strip_metadata(cleaned)
    candidates: list[tuple[str, str, int]] = []
    for pat, name in (
        (r"(?is)<article\b[^>]*>(.*?)</article>", "article"),
        (r"(?is)<main\b[^>]*>(.*?)</main>", "main"),
        (r"(?is)<div\b[^>]*id=[\"']mw-content-text[\"'][^>]*>(.*)", "mw-content-text"),
        (r"(?is)<body\b[^>]*>(.*?)</body>", "body"),
    ):
        m = re.search(pat, stripped)
        if not m:
            continue
        fragment = m.group(1)
        paras = re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", fragment)
        para_text = "\n\n".join(_html_to_text(p) for p in paras if len(_html_to_text(p)) > 20)
        score = len(para_text) + 30 * len(paras)
        candidates.append((para_text or _html_to_text(fragment), f"paragraph_density_{name}", score))
    if not candidates:
        candidates = [(_html_to_text(stripped), "paragraph_density_full", 0)]
    text, method, _score = max(candidates, key=lambda x: x[2])
    return _finalize(
        "S4_PARAGRAPH_DENSITY",
        "Paragraph-density in semantic/article regions",
        url=url,
        main_text=text,
        title=_extract_title(html),
        method=method,
        body_reached=bool(text.strip()),
        warnings=[],
        removed_regions=removed,
        diagnostics={"candidate_count": len(candidates)},
        expect=expect,
    )


def strategy_s5_semantic_html(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    cleaned = _strip_noise_tags(html)
    stripped, removed = _strip_metadata(cleaned)
    for pat, name in (
        (r"(?is)<main\b[^>]*>(.*?)</main>", "semantic_main"),
        (r"(?is)<article\b[^>]*>(.*?)</article>", "semantic_article"),
        (r"(?is)<div\b[^>]*role=[\"']main[\"'][^>]*>(.*?)</div>", "role_main"),
    ):
        m = re.search(pat, stripped)
        if m:
            text = _html_to_text(m.group(1))
            return _finalize(
                "S5_SEMANTIC",
                "Semantic HTML main/article",
                url=url,
                main_text=text,
                title=_extract_title(html),
                method=name,
                body_reached=True,
                warnings=[],
                removed_regions=removed,
                diagnostics={},
                expect=expect,
            )
    return strategy_s4_paragraph_density(html, url=url, expect=expect)


def strategy_s6_wiki_post_infobox(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    """Wikipedia-specific: remove infobox then merge all mw-parser-output siblings."""
    cleaned = _strip_noise_tags(html)
    stripped, removed = _strip_metadata(cleaned)
    blocks = re.findall(
        r'(?is)<div\b[^>]*class=["\'][^"\']*mw-parser-output[^"\']*["\'][^>]*>(.*?)</div>',
        stripped,
    )
    merged = "\n\n".join(_html_to_text(b) for b in blocks if _html_to_text(b))
    method = "wiki_merged_parser_outputs"
    if not merged.strip():
        return strategy_s3_metadata_strip_content(html, url=url, expect=expect)
    return _finalize(
        "S6_WIKI_MERGED",
        "Wikipedia: merged mw-parser-output after infobox removal",
        url=url,
        main_text=merged,
        title=_extract_title(html),
        method=method,
        body_reached=True,
        warnings=["wikipedia_specific_merge"],
        removed_regions=removed,
        diagnostics={"parser_block_count": len(blocks)},
        expect=expect,
    )


def strategy_s7_largest_text_block(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    """Generic: pick largest text block among div/section candidates after metadata strip."""
    cleaned = _strip_noise_tags(html)
    stripped, removed = _strip_metadata(cleaned)
    candidates: list[tuple[str, str, int]] = []
    for m in re.finditer(r"(?is)<(div|section)\b[^>]*>(.*?)</\1>", stripped):
        text = _html_to_text(m.group(2))
        if len(text) >= 80:
            candidates.append((text, f"largest_{m.group(1)}", len(text)))
    if not candidates:
        candidates = [(_html_to_text(stripped), "largest_full", len(stripped))]
    text, method, _ = max(candidates, key=lambda x: x[2])
    return _finalize(
        "S7_LARGEST_BLOCK",
        "Generic largest text block after metadata strip",
        url=url,
        main_text=text,
        title=_extract_title(html),
        method=method,
        body_reached=True,
        warnings=[],
        removed_regions=removed,
        diagnostics={"block_candidates": len(candidates)},
        expect=expect,
    )


def strategy_s8_prestrip_production(html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    """Metadata strip then run production normalize on cleaned HTML."""
    cleaned = _strip_noise_tags(html)
    stripped, removed = _strip_metadata(cleaned)
    evidence = normalize_html_to_evidence(stripped)
    quality = evidence.get("quality") or {}
    main_text = str(evidence.get("main_text") or "")
    return _finalize(
        "S8_PRESTRIP_PRODUCTION",
        "Metadata strip then production selectors",
        url=url,
        main_text=main_text,
        title=evidence.get("title") or _extract_title(html),
        method=f"prestrip_{quality.get('extraction_method')}",
        body_reached=bool(quality.get("body_reached")),
        warnings=list(quality.get("warnings") or []),
        removed_regions=removed,
        diagnostics={"production_after_strip": True},
        expect=expect,
    )


STRATEGIES: dict[StrategyId, Callable[..., ExtractionPrototypeResult]] = {
    "S0_PRODUCTION": strategy_s0_production,
    "S1_MW_CONTENT": strategy_s1_mw_content_text,
    "S2_MW_PARSER_FIRST": strategy_s2_mw_parser_first,
    "S3_METADATA_STRIP": strategy_s3_metadata_strip_content,
    "S4_PARAGRAPH_DENSITY": strategy_s4_paragraph_density,
    "S5_SEMANTIC": strategy_s5_semantic_html,
    "S6_WIKI_MERGED": strategy_s6_wiki_post_infobox,
    "S7_LARGEST_BLOCK": strategy_s7_largest_text_block,
    "S8_PRESTRIP_PRODUCTION": strategy_s8_prestrip_production,
}


def is_wikipedia_url(url: str | None) -> bool:
    u = (url or "").lower()
    return any(m in u for m in _WIKI_HOST_MARKERS)


def run_strategy(strategy_id: StrategyId, html: str, *, url: str | None = None, expect: str = "any") -> ExtractionPrototypeResult:
    fn = STRATEGIES[strategy_id]
    return fn(html, url=url, expect=expect)


def run_all_strategies(html: str, *, url: str | None = None, expect: str = "any") -> list[ExtractionPrototypeResult]:
    return [run_strategy(sid, html, url=url, expect=expect) for sid in STRATEGIES]
