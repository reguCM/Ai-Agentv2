"""Pytest fixtures for experimental scoped read tests."""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_tool.experimental.scoped_read.config import load_scoped_read_config


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_web: Real public URL smoke test (network-dependent; not part of deterministic gate)",
    )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """Isolated miniature repository with experimental allowlist layout."""
    (tmp_path / "registry").mkdir()
    (tmp_path / "registry" / "tools.json").write_text('{"tools":[]}', encoding="utf-8")

    allowed = tmp_path / "docs" / "ai_tool"
    specs = tmp_path / "docs" / "ai_tool" / "tool_creation" / "specs"
    runs = tmp_path / "runs" / "ai_tool"
    outside = tmp_path / "outside"
    evil = tmp_path / "docs" / "ai_tool_evil"

    for d in (allowed, specs, runs, outside, evil):
        d.mkdir(parents=True, exist_ok=True)

    (allowed / "sample.txt").write_text("hello\nworld\n", encoding="utf-8")
    (allowed / "unicode.txt").write_text("日本語テスト\n", encoding="utf-8")
    (allowed / "empty.txt").write_text("", encoding="utf-8")
    (allowed / "sample.md").write_text("# Title\n\nbody\n", encoding="utf-8")
    (allowed / "sample.json").write_text('{"a": 1}\n', encoding="utf-8")
    (specs / "spec.json").write_text('{"tool_id":"test"}\n', encoding="utf-8")
    (outside / "secret.txt").write_text("SECRET\n", encoding="utf-8")
    (evil / "trap.txt").write_text("trap\n", encoding="utf-8")
    (allowed / "subdir").mkdir()
    (allowed / "subdir" / "nested.txt").write_text("nested\n", encoding="utf-8")
    (allowed / "dir_only").mkdir()

    config = {
        "version": 1,
        "status": "experimental",
        "tool_id": "local:workspace_read_text_scoped",
        "roots": [
            {"id": "ai_tool_docs", "path": "docs/ai_tool", "description": "docs"},
            {"id": "ai_tool_runs", "path": "runs/ai_tool", "description": "runs"},
            {
                "id": "tool_creation_specs",
                "path": "docs/ai_tool/tool_creation/specs",
                "description": "specs",
            },
        ],
        "explicit_denies": [],
        "limits": {
            "max_bytes": 65536,
            "max_lines_default": 500,
            "encoding": "utf-8",
            "encoding_errors": "replace",
        },
        "path_rules": {
            "reject_parent_segments": True,
            "reject_absolute_outside_repo": True,
            "reject_symlink_escape": True,
            "allow_directories": False,
        },
    }
    config_path = tmp_path / "allowlist.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    (tmp_path / "_config_path.txt").write_text(str(config_path), encoding="utf-8")
    return tmp_path


@pytest.fixture
def mini_config(mini_repo: Path) -> object:
    config_path = Path((mini_repo / "_config_path.txt").read_text(encoding="utf-8"))
    return load_scoped_read_config(repo_root=mini_repo, config_path=config_path)


@pytest.fixture
def mini_config_path(mini_repo: Path) -> Path:
    return Path((mini_repo / "_config_path.txt").read_text(encoding="utf-8"))


@pytest.fixture
def symlink_escape(mini_repo: Path) -> Path | None:
    """Symlink inside allowlist pointing outside. None if OS cannot create symlink."""
    link = mini_repo / "docs" / "ai_tool" / "link.txt"
    target = mini_repo / "outside" / "secret.txt"
    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        return None
    return link


class _LocalHttpHandler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, dict[str, str], bytes]] = {}

    def log_message(self, format, *args):  # noqa: A003
        return

    def do_GET(self):  # noqa: N802
        route = self.routes.get(self.path)
        if route is None:
            self.send_error(404)
            return
        status, headers, body = route
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if status not in (301, 302, 303, 307, 308):
            self.wfile.write(body)


@pytest.fixture
def local_http_server():
    """127.0.0.1 server for http_client redirect tests (validate patched in test)."""
    server = HTTPServer(("127.0.0.1", 0), _LocalHttpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base, _LocalHttpHandler
    finally:
        server.shutdown()
        thread.join(timeout=2)
