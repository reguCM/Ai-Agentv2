"""
Deterministic Safety / Contract Tests for local:read_url_text.

Uses mock fetch_fn or local HTTP fixtures only.
Does NOT hit the public internet.

Real public URL checks live in test_read_url_text_smoke.py (@pytest.mark.real_web).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_tool.experimental.read_url.reader import read_url_text


def _mock_fetch(status, headers, body, final_url):
    def fn(url, **kwargs):
        return status, headers, body, final_url

    return fn


# --- Normal (mock) ---


def test_normal_https_text() -> None:
    r = read_url_text(
        "https://example.com/page",
        fetch_fn=_mock_fetch(200, {"content-type": "text/plain"}, b"Hello World", "https://example.com/page"),
    )
    assert r["ok"] is True
    assert r["content"] == "Hello World"
    assert r["status_code"] == 200


def test_normal_http_text() -> None:
    r = read_url_text(
        "http://example.org/",
        fetch_fn=_mock_fetch(200, {"content-type": "text/html; charset=utf-8"}, b"<p>ok</p>", "http://example.org/"),
    )
    assert r["ok"] is True


# --- Boundary (mock) ---


def test_boundary_max_bytes_truncated() -> None:
    body = b"x" * 100
    r = read_url_text(
        "https://example.com/big",
        max_bytes=50,
        fetch_fn=_mock_fetch(200, {"content-type": "text/plain"}, body, "https://example.com/big"),
    )
    assert r["ok"] is True
    assert r["truncated"] is True
    assert r["size_bytes"] == 50


def test_boundary_empty_body() -> None:
    r = read_url_text(
        "https://example.com/empty",
        fetch_fn=_mock_fetch(200, {"content-type": "text/plain"}, b"", "https://example.com/empty"),
    )
    assert r["ok"] is True
    assert r["content"] == ""


def test_boundary_long_url() -> None:
    long_path = "a" * 2000
    url = f"https://example.com/{long_path}"
    r = read_url_text(url, fetch_fn=_mock_fetch(200, {"content-type": "text/plain"}, b"ok", url))
    assert r["ok"] is True


# --- Invalid ---


def test_invalid_empty_url() -> None:
    r = read_url_text("")
    assert r["ok"] is False
    assert "empty" in r["error"]


def test_invalid_malformed_url() -> None:
    r = read_url_text("not-a-url")
    assert r["ok"] is False


def test_invalid_unsupported_scheme() -> None:
    r = read_url_text("ftp://example.com/file.txt")
    assert r["ok"] is False
    assert "unsupported scheme" in r["error"]


def test_invalid_file_scheme() -> None:
    r = read_url_text("file:///etc/passwd")
    assert r["ok"] is False


# --- Safety / SSRF ---


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://[::1]/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/",
        "http://metadata.google.internal/",
    ],
)
def test_safety_ssrf_blocked(url: str) -> None:
    r = read_url_text(url)
    assert r["ok"] is False
    assert "ssrf" in r["error"].lower() or "blocked" in r["error"].lower()


def test_safety_userinfo_rejected() -> None:
    r = read_url_text("http://user:pass@example.com/")
    assert r["ok"] is False


def test_safety_no_real_fetch_on_blocked() -> None:
    called = False

    def fetch(*a, **k):
        nonlocal called
        called = True
        return 200, {}, b"", "x"

    r = read_url_text("http://127.0.0.1/secret", fetch_fn=fetch)
    assert r["ok"] is False
    assert called is False


# --- Failure (mock) ---


def test_failure_http_404() -> None:
    r = read_url_text(
        "https://example.com/missing",
        fetch_fn=_mock_fetch(404, {"content-type": "text/plain"}, b"not found", "https://example.com/missing"),
    )
    assert r["ok"] is False
    assert "http error" in r["error"]


def test_failure_http_500() -> None:
    r = read_url_text(
        "https://example.com/err",
        fetch_fn=_mock_fetch(500, {}, b"", "https://example.com/err"),
    )
    assert r["ok"] is False


def test_failure_timeout() -> None:
    def fetch(*a, **k):
        raise TimeoutError("timeout")

    r = read_url_text("https://example.com/slow", fetch_fn=fetch)
    assert r["ok"] is False
    assert r["error"] == "timeout"


def test_failure_connection() -> None:
    def fetch(*a, **k):
        raise ConnectionError("connection failure: refused")

    r = read_url_text("https://example.com/down", fetch_fn=fetch)
    assert r["ok"] is False
    assert "connection failure" in r["error"]


def test_failure_binary_content_type() -> None:
    r = read_url_text(
        "https://example.com/image",
        fetch_fn=_mock_fetch(200, {"content-type": "image/png"}, b"\x89PNG", "https://example.com/image"),
    )
    assert r["ok"] is False
    assert "binary" in r["error"]


def test_failure_binary_sniff() -> None:
    r = read_url_text(
        "https://example.com/bin",
        fetch_fn=_mock_fetch(200, {"content-type": "text/plain"}, b"\x00\x01\x02", "https://example.com/bin"),
    )
    assert r["ok"] is False


def test_failure_redirect_to_private() -> None:
    def fetch(*a, **k):
        raise ValueError("ssrf blocked: private or loopback IP")

    r = read_url_text("https://example.com/redir", fetch_fn=fetch)
    assert r["ok"] is False


# --- Output contract (mock) ---


def test_output_contract_keys() -> None:
    r = read_url_text(
        "https://example.com/",
        fetch_fn=_mock_fetch(200, {"content-type": "text/plain"}, b"x", "https://example.com/"),
    )
    for key in (
        "ok",
        "url",
        "final_url",
        "status_code",
        "content_type",
        "size_bytes",
        "content",
        "main_text",
        "title",
        "quality",
        "truncated",
        "error",
    ):
        assert key in r


def test_output_error_includes_url() -> None:
    r = read_url_text("http://127.0.0.1/")
    assert r["url"] == "http://127.0.0.1/"
    assert r["ok"] is False


# --- HTTP client redirect (local server fixture) ---


def test_redirect_revalidates_private_target(local_http_server) -> None:
    from ai_tool.experimental.read_url import http_client

    base, handler = local_http_server
    private_target = "http://127.0.0.1:9999/private"
    handler.routes = {
        "/redirect": (302, {"Location": private_target}, b""),
    }
    start_url = f"{base}/redirect"

    def validate_side(u: str):
        if u == private_target:
            return None, "ssrf blocked: private or loopback IP"
        return u, None

    with patch.object(http_client, "validate_url", side_effect=validate_side):
        with pytest.raises(ValueError, match="ssrf blocked"):
            http_client.default_http_get(
                start_url,
                timeout_seconds=2,
                max_bytes=1024,
                max_redirects=5,
            )
