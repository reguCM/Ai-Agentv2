"""Real Web Smoke Tests for local:read_url_text (network-dependent, separate from deterministic tests)."""
from __future__ import annotations

import os

import pytest

from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.experimental.read_url.smoke_targets import REAL_WEB_SMOKE_TARGETS

pytestmark = pytest.mark.real_web


@pytest.fixture(scope="module")
def skip_real_web() -> None:
    if os.environ.get("READ_URL_SKIP_REAL_WEB", "").lower() in ("1", "true", "yes"):
        pytest.skip("READ_URL_SKIP_REAL_WEB set")


@pytest.mark.parametrize("target", REAL_WEB_SMOKE_TARGETS, ids=lambda t: t.case_id)
def test_real_web_fetch_success(target, skip_real_web) -> None:
    """Confirm live DNS/HTTP fetch against a stable public URL (no golden body match)."""
    r = read_url_text(target.url, max_bytes=65536, timeout_seconds=20)
    assert r["url"] == target.url
    assert r["ok"] is True, r.get("error")
    assert r["status_code"] == 200
    assert r["content"]
    assert (r["size_bytes"] or 0) > 0
    ctype = (r["content_type"] or "").lower()
    if target.content_kind == "html":
        assert "html" in ctype or "<" in r["content"][:300]
    else:
        assert "text/" in ctype or "plain" in ctype


def test_real_web_max_bytes_applied(skip_real_web) -> None:
    url = REAL_WEB_SMOKE_TARGETS[0].url
    r = read_url_text(url, max_bytes=256, timeout_seconds=20)
    assert r["url"] == url
    assert r["ok"] is True, r.get("error")
    assert (r["size_bytes"] or 0) <= 256
    assert r["truncated"] is True


def test_real_web_timeout_parameter_accepted(skip_real_web) -> None:
    url = REAL_WEB_SMOKE_TARGETS[1].url
    r = read_url_text(url, max_bytes=4096, timeout_seconds=20)
    assert r["ok"] is True, r.get("error")
    assert r["final_url"]
