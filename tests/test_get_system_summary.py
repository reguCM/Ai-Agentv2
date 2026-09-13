"""get_system_summary — 既存 get_* の合成。OS/API を直接叩かない。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from tools.system.summary.get_system_summary import SECTIONS, get_system_summary

SRC = Path("tools/system/summary/get_system_summary.py").read_text(encoding="utf-8")


def _ok_section(**extra):
    row = {"ok": True, "status": "ok", "error": None, "observation_source": "real"}
    row.update(extra)
    return row


def _fail_section(*, status="error", error="mocked_failure"):
    return {
        "ok": False,
        "status": status,
        "error": error,
        "observation_source": "real",
        "source": "mock",
        "value": "unknown",
    }


def test_direct_call_returns_composed_sections():
    out = get_system_summary()
    assert out["observation_source"] == "composed"
    assert out["source"] == "existing_observation_tools"
    assert out["status"] in {"ok", "partial", "error"}
    assert set(out["sections"]) == set(SECTIONS)
    for name in SECTIONS:
        assert isinstance(out["sections"][name], dict)
        assert "ok" in out["sections"][name]
        assert name in out["derived"]["ok_by_section"]


def test_return_shape():
    out = get_system_summary()
    assert "status" in out
    assert "sections" in out
    assert "derived" in out
    assert "ok_by_section" in out["derived"]
    assert out["observation_source"] != "real"


def test_does_not_call_os_or_nvidia_directly():
    lowered = SRC.lower()
    assert "get-ciminstance" not in lowered
    assert "nvidia-smi" not in lowered
    assert "datetime.now" not in SRC
    assert "subprocess" not in SRC
    assert "from tools.system.time.get_system_time import get_system_time" in SRC
    assert "from tools.system.cpu.get_cpu_status import get_cpu_status" in SRC
    assert "from tools.system.memory.get_memory_status import get_memory_status" in SRC
    assert "from tools.system.gpu.gpu_status import get_gpu_status" in SRC
    assert "from tools.system.cpu.cpu_status" not in SRC
    assert "get_gpu_processes" not in SRC


def test_calls_existing_get_functions():
    time_out = _ok_section(datetime="2026-08-31T00:00:00+09:00")
    cpu_out = _ok_section(model="Test CPU")
    mem_out = _ok_section(total_mb=16)
    gpu_out = _ok_section(gpu="Test GPU")
    with (
        mock.patch("tools.system.summary.get_system_summary.get_system_time", return_value=time_out) as t,
        mock.patch("tools.system.summary.get_system_summary.get_cpu_status", return_value=cpu_out) as c,
        mock.patch("tools.system.summary.get_system_summary.get_memory_status", return_value=mem_out) as m,
        mock.patch("tools.system.summary.get_system_summary.get_gpu_status", return_value=gpu_out) as g,
    ):
        out = get_system_summary()
    assert t.called and c.called and m.called and g.called
    assert out["status"] == "ok"
    assert out["ok"] is True
    assert out["sections"]["time"] is time_out
    assert out["sections"]["cpu"] is cpu_out
    assert out["sections"]["memory"] is mem_out
    assert out["sections"]["gpu"] is gpu_out
    assert out["derived"]["ok_by_section"] == {"time": True, "cpu": True, "memory": True, "gpu": True}


def test_partial_keeps_other_sections_and_does_not_fill_gaps():
    time_out = _ok_section(datetime="kept")
    cpu_fail = _fail_section(error="cim_failed")
    mem_out = _ok_section(total_mb=8)
    gpu_out = _ok_section(temperature=40)
    with (
        mock.patch("tools.system.summary.get_system_summary.get_system_time", return_value=time_out),
        mock.patch("tools.system.summary.get_system_summary.get_cpu_status", return_value=cpu_fail),
        mock.patch("tools.system.summary.get_system_summary.get_memory_status", return_value=mem_out),
        mock.patch("tools.system.summary.get_system_summary.get_gpu_status", return_value=gpu_out),
    ):
        out = get_system_summary()
    assert out["status"] == "partial"
    assert out["ok"] is False
    assert out["sections"]["cpu"] is cpu_fail
    assert out["sections"]["cpu"]["error"] == "cim_failed"
    assert out["sections"]["time"]["datetime"] == "kept"
    assert out["derived"]["ok_by_section"]["cpu"] is False
    assert out["derived"]["ok_by_section"]["time"] is True
    assert out["sections"]["cpu"].get("model") is None
    assert "Test CPU" not in str(out["sections"]["cpu"])


def test_all_failed_is_error():
    fail = _fail_section()
    with (
        mock.patch("tools.system.summary.get_system_summary.get_system_time", return_value=fail),
        mock.patch("tools.system.summary.get_system_summary.get_cpu_status", return_value=fail),
        mock.patch("tools.system.summary.get_system_summary.get_memory_status", return_value=fail),
        mock.patch("tools.system.summary.get_system_summary.get_gpu_status", return_value=fail),
    ):
        out = get_system_summary()
    assert out["status"] == "error"
    assert out["ok"] is False
    assert out["error"] == "all_sections_failed"


def test_registry_entry_is_composed_not_real():
    registry = json.loads(
        (Path(__file__).resolve().parents[1] / "registry" / "tools.json").read_text(encoding="utf-8")
    )
    entry = next(t for t in registry["tools"] if t["name"] == "get_system_summary")
    assert entry["visibility"] == "agent"
    assert entry["module"] == "tools.system.summary.get_system_summary"
    assert entry["function"] == "get_system_summary"
    assert entry["input"] == {}
    assert entry.get("observation_source") != "real"
    names = [t["name"] for t in registry["tools"]]
    assert names.count("get_system_summary") == 1


def test_agent_visible_default_includes_summary_only_as_addition():
    from ai_tool.chat_interface.agent_turn import AGENT_VISIBLE_DEFAULT

    assert "get_system_summary" in AGENT_VISIBLE_DEFAULT
    assert AGENT_VISIBLE_DEFAULT == (
        "get_gpu_status",
        "get_gpu_processes",
        "cpu_status",
        "get_cpu_status",
        "get_system_summary",
        "search_web",
        "read_url_text",
    )


def test_does_not_alter_child_tool_modules():
    cpu = Path("tools/system/cpu/get_cpu_status.py").read_text(encoding="utf-8")
    mem = Path("tools/system/memory/get_memory_status.py").read_text(encoding="utf-8")
    assert "get_system_summary" not in cpu
    assert "get_system_summary" not in mem
