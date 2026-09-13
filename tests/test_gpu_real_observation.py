"""GPU REAL 観測 Tool（固定値フォールバック禁止）のテスト。"""

import inspect
import json
import unittest
from pathlib import Path
from unittest import mock

from tools.ai.tool_builder.proposal import PROJECT_CONVENTIONS, create_tool_proposal
from tools.system.gpu import gpu_processes, gpu_status
from tools.system.gpu.nvidia_smi import query_gpu_status


CASES_DIR = Path(__file__).resolve().parents[1] / "research" / "llm_benchmarks" / "cases"
FIVE_CASES = (
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
)


class GpuRealObservationTests(unittest.TestCase):
    def test_status_success_not_hardcoded_fake(self):
        fake = {
            "gpu": "RTX 3060",
            "temperature": 60,
            "utilization": 50,
            "vram_used": 6000,
            "vram_total": 12288,
        }
        with mock.patch(
            "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
            return_value={
                "ok": True,
                "error": None,
                "status": "ok",
                "rows": [["GeForce TEST", "41", "7", "1234", "8192"]],
                "source": "nvidia-smi",
            },
        ), mock.patch(
            "tools.system.gpu.nvidia_smi.nvidia_smi_path",
            return_value="nvidia-smi",
        ):
            out = get_gpu_status_via_module()
        self.assertTrue(out["ok"])
        self.assertEqual(out["gpu"], "GeForce TEST")
        self.assertEqual(out["temperature"], 41.0)
        self.assertEqual(out["utilization"], 7.0)
        self.assertEqual(out["vram_used"], 1234)
        self.assertEqual(out["vram_total"], 8192)
        self.assertEqual(out["observation_source"], "real")
        for key, value in fake.items():
            self.assertNotEqual(out.get(key), value)

    def test_status_failure_no_rtx_fallback(self):
        with mock.patch(
            "tools.system.gpu.nvidia_smi.nvidia_smi_path",
            return_value=None,
        ):
            out = query_gpu_status()
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["gpu"], "unknown")
        self.assertNotEqual(out["gpu"], "RTX 3060")
        self.assertEqual(out["temperature"], "unknown")
        tool = gpu_status.get_gpu_status()
        self.assertNotEqual(tool.get("gpu"), "RTX 3060")
        self.assertEqual(tool.get("observation_source"), "real")

    def test_processes_not_fixed_ollama_python(self):
        with mock.patch(
            "tools.system.gpu.nvidia_smi.nvidia_smi_path",
            return_value="nvidia-smi",
        ), mock.patch(
            "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
            return_value={
                "ok": True,
                "error": None,
                "status": "ok",
                "rows": [["111", "chrome.exe", "200"]],
                "source": "nvidia-smi",
            },
        ):
            out = gpu_processes.get_gpu_processes()
        names = [p["name"] for p in out["processes"]]
        self.assertEqual(names, ["chrome.exe"])
        self.assertNotIn("ollama", names)
        self.assertNotIn("python.exe", names)

        with mock.patch(
            "tools.system.gpu.nvidia_smi.nvidia_smi_path",
            return_value=None,
        ):
            failed = gpu_processes.get_gpu_processes()
        self.assertEqual(failed["processes"], [])
        self.assertFalse(failed["ok"])
        self.assertNotEqual(
            failed["processes"],
            [{"name": "ollama", "vram_used": 4500}, {"name": "python.exe", "vram_used": 1200}],
        )

    def test_source_has_no_hardcoded_rtx_fallback(self):
        src = (
            inspect.getsource(gpu_status)
            + inspect.getsource(gpu_processes)
            + inspect.getsource(query_gpu_status)
        )
        self.assertNotIn("RTX 3060", src)
        self.assertNotIn("vram_used\": 6000", src.replace(" ", ""))
        self.assertNotIn('"ollama"', src)

    def test_bench_fixtures_load_and_marked(self):
        for case_id in FIVE_CASES:
            path = CASES_DIR / f"{case_id}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["id"], case_id)
            self.assertEqual(data["fixture_kind"], "BENCH_FIXTURE_NOT_LIVE_SENSOR")
            self.assertEqual(data["observation_source"], "fixture")
            self.assertIn("state", data)
            self.assertIn("request", data)

    def test_tool_builder_does_not_treat_fake_gpu_as_sensor_example(self):
        materials = create_tool_proposal("CPU状態を取る")
        rules = "\n".join(materials["rules"])
        self.assertIn("固定値・架空値", rules)
        self.assertIn("nvidia_smi", rules)
        self.assertNotEqual(
            PROJECT_CONVENTIONS["module_example"],
            "tools.system.gpu.gpu_status",
        )
        self.assertEqual(
            PROJECT_CONVENTIONS["module_example"],
            "tools.system.cpu.cpu_status",
        )
        # 旧 FAKE 数値を正しい例として載せない
        blob = json.dumps(materials, ensure_ascii=False)
        self.assertNotIn("RTX 3060", blob)
        self.assertNotIn('"temperature": 60', blob)

    def test_registry_marks_gpu_tools_real(self):
        registry = json.loads(
            (Path(__file__).resolve().parents[1] / "registry" / "tools.json").read_text(
                encoding="utf-8"
            )
        )
        by_name = {t["name"]: t for t in registry["tools"]}
        self.assertEqual(by_name["get_gpu_status"]["observation_source"], "real")
        self.assertEqual(by_name["get_gpu_processes"]["observation_source"], "real")
        self.assertEqual(by_name["get_cpu_status"]["visibility"], "agent")
        self.assertEqual(by_name["get_cpu_status"]["observation_source"], "real")


def get_gpu_status_via_module():
    return gpu_status.get_gpu_status()


if __name__ == "__main__":
    unittest.main()
