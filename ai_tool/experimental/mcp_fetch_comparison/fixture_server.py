"""Deterministic local HTTP fixture server for MCP Fetch comparison (experiment only)."""
from __future__ import annotations

import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "MCPFetchFixture/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send(self, status: int, body: bytes, content_type: str = "text/plain") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        cfg = self.server.fixture_config  # type: ignore[attr-defined]

        if path == "/plain":
            self._send(200, b"hello plain fixture\n", "text/plain; charset=utf-8")
            return
        if path == "/html":
            body = b"<html><head><title>Fixture</title></head><body><p>Hello HTML</p></body></html>"
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path == "/small":
            self._send(200, b"x" * 64, "text/plain")
            return
        if path == "/near_max":
            size = int(cfg.get("near_max_bytes", 65000))
            self._send(200, (b"a" * size), "text/plain")
            return
        if path == "/large":
            size = int(cfg.get("large_bytes", 120000))
            self._send(200, (b"b" * size), "text/plain")
            return
        if path == "/redirect":
            port = self.server.server_address[1]  # type: ignore[attr-defined]
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{port}/plain")
            self.end_headers()
            return
        if path == "/redirect_private":
            port = self.server.server_address[1]  # type: ignore[attr-defined]
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{port}/private_target")
            self.end_headers()
            return
        if path == "/private_target":
            self._send(200, b"private after redirect\n", "text/plain")
            return
        if path == "/404":
            self._send(404, b"not found fixture\n", "text/plain")
            return
        if path == "/500":
            self._send(500, b"server error fixture\n", "text/plain")
            return
        if path == "/slow":
            delay = float(cfg.get("slow_seconds", 15.0))
            time.sleep(delay)
            self._send(200, b"slow response\n", "text/plain")
            return
        self._send(404, b"unknown fixture path\n", "text/plain")


class FixtureServer:
    def __init__(self, *, near_max_bytes: int = 65000, large_bytes: int = 120000, slow_seconds: float = 15.0) -> None:
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._config = {
            "near_max_bytes": near_max_bytes,
            "large_bytes": large_bytes,
            "slow_seconds": slow_seconds,
        }

    @property
    def base_url(self) -> str:
        if not self._httpd:
            raise RuntimeError("fixture server not started")
        host, port = self._httpd.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._httpd = HTTPServer(("127.0.0.1", 0), FixtureHandler)
        self._httpd.fixture_config = self._config  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def fixture_response_for_path(
    path: str, *, base_url: str, timeout_seconds: float = 30.0
) -> tuple[int, dict[str, str], bytes, str | None]:
    """Return HTTP response tuple for a fixture path (experiment harness replay)."""
    import urllib.error
    import urllib.request

    url = f"{base_url.rstrip('/')}{path}"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "MCPFetchComparison/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers, body, resp.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return exc.code, headers, body, exc.geturl()
    except TimeoutError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise TimeoutError(str(exc)) from exc
