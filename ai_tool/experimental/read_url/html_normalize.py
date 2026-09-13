"""Deterministic HTML → main_text normalization for Web Evidence (no semantic inference)."""
from __future__ import annotations

import re
from html import unescape
from typing import Any

# Legacy region selectors — used only as fallback when paragraph-density yields nothing.
_LEGACY_SELECTORS = (
    r'(?is)<main\b[^>]*>(.*?)</main>',
    r'(?is)<article\b[^>]*>(.*?)</article>',
    r'(?is)<div\b[^>]*id=["\']content["\'][^>]*>(.*?)</div>',
    r'(?is)<div\b[^>]*id=["\']bodyContent["\'][^>]*>(.*?)</div>',
)

# Non-body metadata/boilerplate removed before region selection (generic HTML patterns).
_METADATA_PATTERNS: tuple[tuple[str, str], ...] = (
    ("infobox_table", r"(?is)<table\b[^>]*class=[^>]*infobox[^>]*>.*?</table>"),
    ("navbox_div", r"(?is)<div\b[^>]*class=[^>]*navbox[^>]*>.*?</div>"),
    ("navbox_table", r"(?is)<table\b[^>]*class=[^>]*navbox[^>]*>.*?</table>"),
    ("metadata_div", r"(?is)<div\b[^>]*class=[^>]*metadata[^>]*>.*?</div>"),
    ("reference_list", r"(?is)<div\b[^>]*class=[^>]*reflist[^>]*>.*?</div>"),
    ("toc", r"(?is)<div\b[^>]*id=[\"']toc[\"'][^>]*>.*?</div>"),
    ("typeof_span", r"(?is)<span\b[^>]*typeof=[^>]*>.*?</span>"),
    ("json_ld_script", r"(?is)<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>.*?</script>"),
)

_PARAGRAPH_REGION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?is)<article\b[^>]*>(.*?)</article>", "article"),
    (r"(?is)<main\b[^>]*>(.*?)</main>", "main"),
    (r"(?is)<div\b[^>]*id=[\"']mw-content-text[\"'][^>]*>(.*)", "mw-content-text"),
    (r"(?is)<body\b[^>]*>(.*?)</body>", "body"),
)

_STRIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "iframe",
        "svg",
    }
)

_MIN_FACT_READY_CHARS = 40
_MIN_PARAGRAPH_CHARS = 20


def _looks_like_boilerplate_or_metadata(text: str) -> bool:
    if not text:
        return True
    sample = text[:4000]
    if sample.count('"wt"') >= 3:
        return True
    if sample.count('{"') >= 5 and len(text.strip()) < 2500:
        return True
    nav_markers = ("メインメニュー", "jump to content", "sidebar", "vector-toc")
    hits = sum(1 for m in nav_markers if m.lower() in sample.lower())
    if hits >= 2 and len(text.strip()) < 600:
        return True
    return False


def _strip_noise_tags(html: str) -> str:
    work = html or ""
    for tag in _STRIP_TAGS:
        work = re.sub(rf"(?is)<{tag}\b[^>]*>.*?</{tag}>", " ", work)
    work = re.sub(r"(?is)<!--.*?-->", " ", work)
    return work


def _strip_metadata_regions(html: str) -> tuple[str, list[str]]:
    work = html
    removed: list[str] = []
    for name, pattern in _METADATA_PATTERNS:
        if re.search(pattern, work):
            work = re.sub(pattern, " ", work)
            removed.append(name)
    if '"wt"' in (html or ""):
        work = re.sub(r'(?is)\{"wt":', " ", work)
        if '"wt"' in html and '"wt"' not in work:
            removed.append("wikitext_json_fragments")
    return work, removed


def _html_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<br\s*/?>", "\n", fragment)
    text = re.sub(r"(?is)<(?:p|div|li|h[1-6]|tr|td|th|section|blockquote)\b[^>]*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _paragraph_density_text(fragment: str) -> str:
    paras = re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", fragment)
    chunks = [_html_to_text(p) for p in paras if len(_html_to_text(p)) >= _MIN_PARAGRAPH_CHARS]
    if chunks:
        return "\n\n".join(chunks)
    return _html_to_text(fragment)


def _extract_body_segment_paragraph_density(html: str) -> tuple[str, str]:
    """Select main body via metadata strip + paragraph-density scoring."""
    cleaned = _strip_metadata_regions(_strip_noise_tags(html))[0]
    candidates: list[tuple[str, str, int]] = []
    for pattern, name in _PARAGRAPH_REGION_PATTERNS:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        fragment = match.group(1)
        para_text = _paragraph_density_text(fragment)
        para_count = len(re.findall(r"(?is)<p\b[^>]*>", fragment))
        score = len(para_text) + 30 * para_count
        candidates.append((para_text, f"paragraph_density_{name}", score))
    if candidates:
        text, method, _score = max(candidates, key=lambda x: x[2])
        if text.strip():
            return text, method
    return _extract_body_segment_legacy(cleaned)


def _extract_body_segment_legacy(html: str) -> tuple[str, str]:
    for pattern in _LEGACY_SELECTORS:
        match = re.search(pattern, html)
        if match:
            return _html_to_text(match.group(1)), "region_match_legacy"
    body = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", html)
    if body:
        return _html_to_text(body.group(1)), "body"
    return _html_to_text(html), "full_document"


def _extract_title(html: str) -> str | None:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    if not match:
        return None
    title = unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title or None


def normalize_html_to_evidence(
    html: str,
    *,
    max_main_text_chars: int = 32000,
    raw_fetch_truncated: bool = False,
) -> dict[str, Any]:
    """
    Convert HTML into LLM-readable main_text plus conservative quality flags.
    Does not interpret user questions or extract specific facts.
    """
    warnings: list[str] = []
    if not html or not str(html).strip():
        return {
            "main_text": "",
            "title": None,
            "quality": {
                "extraction_success": False,
                "body_reached": False,
                "truncated": False,
                "fact_ready": False,
                "warnings": ["empty_html"],
            },
        }

    segment, method = _extract_body_segment_paragraph_density(html)
    main_text = segment
    title = _extract_title(html)

    body_reached = (
        method.startswith("paragraph_density") or method in {"region_match_legacy", "body", "full_document"}
    ) and len(main_text) >= 20

    if raw_fetch_truncated and "</body>" not in (html or "").lower():
        substantial_article = (
            method.startswith("paragraph_density")
            and len(main_text.strip()) >= 500
            and not _looks_like_boilerplate_or_metadata(main_text)
        )
        if not substantial_article:
            body_reached = False

    if raw_fetch_truncated and not body_reached:
        warnings.append("raw_fetch_truncated_before_main_content")

    truncated = False
    if len(main_text) > max_main_text_chars:
        main_text = main_text[:max_main_text_chars]
        truncated = True
        warnings.append("main_text_truncated")

    extraction_success = bool(main_text.strip())
    fact_ready = (
        extraction_success
        and len(main_text.strip()) >= _MIN_FACT_READY_CHARS
        and body_reached
        and not (raw_fetch_truncated and not body_reached)
        and not _looks_like_boilerplate_or_metadata(main_text)
    )

    if not fact_ready and extraction_success and not body_reached:
        warnings.append("main_text_present_but_body_region_uncertain")
    if not fact_ready and extraction_success and _looks_like_boilerplate_or_metadata(main_text):
        warnings.append("main_text_looks_like_boilerplate_or_metadata")

    return {
        "main_text": main_text,
        "title": title,
        "quality": {
            "extraction_success": extraction_success,
            "body_reached": body_reached,
            "truncated": truncated,
            "fact_ready": fact_ready,
            "extraction_method": method,
            "warnings": warnings,
        },
    }
