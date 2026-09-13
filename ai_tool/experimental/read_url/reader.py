from __future__ import annotations

import re
from typing import Any, Callable

from ai_tool.experimental.read_url.config import (
    ALLOWED_CONTENT_TYPE_PREFIXES,
    DEFAULT_LIMITS,
    FetchLimits,
)
from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.experimental.read_url.http_client import FetchFn, default_http_get
from ai_tool.experimental.read_url.ssrf import validate_url

BINARY_SNIFF_BYTES = 8192


def _error(*, url: str, error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "url": url,
        "final_url": None,
        "status_code": None,
        "content_type": None,
        "size_bytes": None,
        "content": None,
        "main_text": None,
        "title": None,
        "quality": None,
        "truncated": False,
        "error": error,
    }


def _plain_text_quality(text: str, *, truncated: bool) -> dict[str, Any]:
    stripped = (text or "").strip()
    extraction_success = bool(stripped)
    fact_ready = extraction_success and len(stripped) >= 40 and not truncated
    warnings: list[str] = []
    if truncated:
        warnings.append("raw_fetch_truncated")
    if extraction_success and not fact_ready:
        warnings.append("plain_text_too_short_or_truncated")
    return {
        "extraction_success": extraction_success,
        "body_reached": extraction_success,
        "truncated": truncated,
        "fact_ready": fact_ready,
        "extraction_method": "plain_text",
        "warnings": warnings,
    }


def _success(
    *,
    url: str,
    final_url: str,
    status_code: int,
    content_type: str | None,
    size_bytes: int,
    main_text: str,
    title: str | None,
    quality: dict[str, Any],
    raw_truncated: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "content": main_text,
        "main_text": main_text,
        "title": title,
        "quality": quality,
        "truncated": raw_truncated or bool(quality.get("truncated")),
        "error": None,
    }


def _is_probably_binary(data: bytes) -> bool:
    chunk = data[:BINARY_SNIFF_BYTES]
    if b"\x00" in chunk:
        return True
    if not chunk:
        return False
    textish = sum(1 for b in chunk if b in (9, 10, 13) or 32 <= b <= 126 or b >= 128)
    return (textish / len(chunk)) < 0.85


def _content_type_allowed(content_type: str | None) -> bool:
    if not content_type:
        return True
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime.startswith(("image/", "video/", "audio/")):
        return False
    if mime in ("application/octet-stream", "application/pdf"):
        return False
    for prefix in ALLOWED_CONTENT_TYPE_PREFIXES:
        if prefix.endswith("/"):
            if mime.startswith(prefix):
                return True
        elif mime == prefix or mime.startswith(prefix):
            return True
    return False


def _is_html_content(content_type: str | None, text: str) -> bool:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime in ("text/html", "application/xhtml+xml"):
        return True
    head = (text or "")[:500].lower()
    return "<html" in head or "<body" in head or "<!doctype html" in head


def _decode_body(body: bytes, content_type: str | None) -> tuple[str | None, str | None]:
    charset = "utf-8"
    if content_type and "charset=" in content_type.lower():
        match = re.search(r"charset=([^\s;]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip("\"'")
    try:
        return body.decode(charset), None
    except (LookupError, UnicodeDecodeError):
        try:
            return body.decode("utf-8", errors="replace"), None
        except Exception as exc:  # noqa: BLE001
            return None, f"encoding error: {exc}"


def read_url_text(
    url: str | None = None,
    max_bytes: int | None = None,
    timeout_seconds: float | None = None,
    *,
    limits: FetchLimits | None = None,
    fetch_fn: FetchFn | None = None,
) -> dict[str, Any]:
    """
    Read-only HTTP GET fetch with SSRF validation and deterministic evidence normalization.
    Returns main_text + quality for LLM grounding (no semantic inference inside the tool).
    """
    requested = "" if url is None else str(url).strip()
    cfg = limits or DEFAULT_LIMITS
    effective_max = int(max_bytes) if max_bytes is not None else cfg.max_bytes
    effective_timeout = float(timeout_seconds) if timeout_seconds is not None else cfg.timeout_seconds
    effective_max = min(max(effective_max, 1), 262144)
    effective_timeout = min(max(effective_timeout, 1.0), 60.0)

    if not requested:
        return _error(url=requested, error="malformed url: empty")

    normalized, err = validate_url(requested)
    if err:
        return _error(url=requested, error=err)

    assert normalized is not None
    getter = fetch_fn or default_http_get

    try:
        status, headers, body, final_url = getter(
            normalized,
            timeout_seconds=effective_timeout,
            max_bytes=effective_max,
            max_redirects=cfg.max_redirects,
        )
    except TimeoutError:
        return _error(url=requested, error="timeout")
    except ConnectionError as exc:
        return _error(url=requested, error=str(exc))
    except ValueError as exc:
        msg = str(exc)
        if "redirect" in msg:
            return _error(url=requested, error=msg)
        if "ssrf" in msg:
            return _error(url=requested, error=msg)
        return _error(url=requested, error=msg)

    final = final_url or normalized
    content_type = headers.get("content-type")

    if status >= 400:
        return _error(url=requested, error=f"http error: {status}")

    raw_truncated = len(body) > effective_max
    body = body[:effective_max]

    if not _content_type_allowed(content_type):
        return _error(url=requested, error="binary response: content-type not allowed")

    if _is_probably_binary(body):
        return _error(url=requested, error="binary response")

    text, enc_err = _decode_body(body, content_type)
    if enc_err:
        return _error(url=requested, error=enc_err)

    decoded = text or ""
    if _is_html_content(content_type, decoded):
        evidence = normalize_html_to_evidence(
            decoded,
            max_main_text_chars=cfg.max_main_text_chars,
            raw_fetch_truncated=raw_truncated,
        )
        main_text = str(evidence.get("main_text") or "")
        title = evidence.get("title")
        quality = dict(evidence.get("quality") or {})
    else:
        main_text = decoded
        title = None
        quality = _plain_text_quality(main_text, truncated=raw_truncated)

    return _success(
        url=requested,
        final_url=final,
        status_code=status,
        content_type=content_type,
        size_bytes=len(body),
        main_text=main_text,
        title=title,
        quality=quality,
        raw_truncated=raw_truncated,
    )
