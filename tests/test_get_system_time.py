"""get_system_time — 直接実行の契約と実測。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from tools.system.time.get_system_time import get_system_time

REQUIRED = ("datetime", "timezone", "formatted")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def test_direct_call_returns_current_local_time():
    before = datetime.now().astimezone()
    out = get_system_time()
    after = datetime.now().astimezone()
    assert out["ok"] is True
    assert out["status"] == "ok"
    assert out["error"] is None
    parsed = datetime.fromisoformat(out["datetime"])
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=before.tzinfo)
    assert before - timedelta(seconds=2) <= parsed <= after + timedelta(seconds=2)


def test_return_shape():
    out = get_system_time()
    for key in REQUIRED:
        assert key in out
        assert isinstance(out[key], str)
        assert out[key].strip()
    assert ISO_RE.match(out["datetime"])
    assert out["observation_source"] == "real"
    assert out["source"] == "datetime.now_astimezone"


def test_registry_entry_matches_observation_tools():
    registry = json.loads(
        (Path(__file__).resolve().parents[1] / "registry" / "tools.json").read_text(encoding="utf-8")
    )
    entry = next(t for t in registry["tools"] if t["name"] == "get_system_time")
    assert entry["visibility"] == "agent"
    assert entry["observation_source"] == "real"
    assert entry["module"] == "tools.system.time.get_system_time"
    assert entry["function"] == "get_system_time"
    assert entry["input"] == {}
    names = [t["name"] for t in registry["tools"]]
    assert names.count("get_system_time") == 1
    assert "get_cpu_status" in names
    assert "get_gpu_status" in names


def test_does_not_alter_existing_cpu_module():
    src = Path("tools/system/cpu/get_cpu_status.py").read_text(encoding="utf-8")
    assert "get_system_time" not in src
