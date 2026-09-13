"""既存 observation Tool の合成。OS/API を直接取得しない。"""

from __future__ import annotations

from tools.system.cpu.get_cpu_status import get_cpu_status
from tools.system.gpu.gpu_status import get_gpu_status
from tools.system.memory.get_memory_status import get_memory_status
from tools.system.time.get_system_time import get_system_time

SECTIONS = ("time", "cpu", "memory", "gpu")


def _section_ok(result: object) -> bool:
    return isinstance(result, dict) and result.get("ok") is True


def get_system_summary() -> dict:
    """
    get_system_time / get_cpu_status / get_memory_status / get_gpu_status を呼ぶ。
    欠測を他セクションから補完しない。合成結果を observation_source=real とは書かない。
    """
    sections = {
        "time": get_system_time(),
        "cpu": get_cpu_status(),
        "memory": get_memory_status(),
        "gpu": get_gpu_status(),
    }
    ok_by_section = {name: _section_ok(sections[name]) for name in SECTIONS}
    successes = sum(1 for ok in ok_by_section.values() if ok)
    if successes == len(SECTIONS):
        status = "ok"
    elif successes == 0:
        status = "error"
    else:
        status = "partial"
    return {
        "status": status,
        "ok": status == "ok",
        "error": None if successes else "all_sections_failed",
        "observation_source": "composed",
        "source": "existing_observation_tools",
        "sections": sections,
        "derived": {"ok_by_section": ok_by_section},
    }
