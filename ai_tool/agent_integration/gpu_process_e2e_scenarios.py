"""GPU process Agent E2E scenarios — deterministic + live LLM prompts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ExpectedTool = str  # registry tool name


@dataclass
class GpuProcessE2EScenario:
    scenario_id: str
    user_request: str
    expected_tool: ExpectedTool
    routing_note: str
    mock_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    mock_final_answer: str = ""
    live: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "user_request": self.user_request,
            "expected_tool": self.expected_tool,
            "routing_note": self.routing_note,
            "mock_tool_calls": self.mock_tool_calls,
            "mock_final_answer": self.mock_final_answer,
            "live": self.live,
        }


# --- Phase 2: Deterministic Agent Bridge ---

DET_CASE1_GPU_PROCESSES = GpuProcessE2EScenario(
    scenario_id="det_case1_gpu_process_list",
    user_request="現在GPUを使っているプロセスを確認したい",
    expected_tool="get_gpu_processes",
    routing_note="GPUプロセス一覧 → get_gpu_processes",
    mock_tool_calls=[{"name": "get_gpu_processes", "arguments": {}}],
    mock_final_answer="GPU使用中プロセスを確認しました（deterministic mock）。",
)

DET_CASE2_GPU_VRAM = GpuProcessE2EScenario(
    scenario_id="det_case2_gpu_process_vram",
    user_request="GPUプロセスのVRAM使用量を確認したい",
    expected_tool="get_gpu_processes",
    routing_note="プロセス別VRAM → get_gpu_processes",
    mock_tool_calls=[{"name": "get_gpu_processes", "arguments": {}}],
    mock_final_answer="各プロセスのVRAM使用量を確認しました（deterministic mock）。",
)

DET_CASE3_CPU_NOT_GPU_PROC = GpuProcessE2EScenario(
    scenario_id="det_case3_cpu_not_gpu_processes",
    user_request="CPUの状態を確認したい",
    expected_tool="cpu_status",
    routing_note="CPU要求 → cpu_status（get_gpu_processes 不可）",
    mock_tool_calls=[{"name": "cpu_status", "arguments": {}}],
    mock_final_answer="CPU状態を確認しました（deterministic mock）。",
)

DET_CASE4_GPU_STATUS = GpuProcessE2EScenario(
    scenario_id="det_case4_gpu_overall_status",
    user_request="GPUモデルやGPU全体の使用率を確認したい",
    expected_tool="get_gpu_status",
    routing_note="GPU全体メトリクス → get_gpu_status",
    mock_tool_calls=[{"name": "get_gpu_status", "arguments": {}}],
    mock_final_answer="GPU全体の状態を確認しました（deterministic mock）。",
)

DET_CASE5_CPU_STRUCTURED = GpuProcessE2EScenario(
    scenario_id="det_case5_cpu_structured",
    user_request="CPUのモデル名とコア数を教えて",
    expected_tool="get_cpu_status",
    routing_note="構造化CPU情報 → get_cpu_status",
    mock_tool_calls=[{"name": "get_cpu_status", "arguments": {}}],
    mock_final_answer="CPUモデルとコア数を確認しました（deterministic mock）。",
)

DETERMINISTIC_SCENARIOS = [
    DET_CASE1_GPU_PROCESSES,
    DET_CASE2_GPU_VRAM,
    DET_CASE3_CPU_NOT_GPU_PROC,
    DET_CASE4_GPU_STATUS,
    DET_CASE5_CPU_STRUCTURED,
]

# --- Phase 3: Real Ollama LLM (prompts only — selection validated at runtime) ---

LIVE_SCENARIO_A = GpuProcessE2EScenario(
    scenario_id="live_a_gpu_process_list",
    user_request="今このPCでGPUを使っているプロセスを確認してください。",
    expected_tool="get_gpu_processes",
    routing_note="Real LLM — GPUプロセス確認",
    live=True,
)

LIVE_SCENARIO_B = GpuProcessE2EScenario(
    scenario_id="live_b_gpu_process_vram",
    user_request="現在GPUを使っているプロセスと、それぞれのVRAM使用量を教えてください。",
    expected_tool="get_gpu_processes",
    routing_note="Real LLM — VRAM per process; unknown must not be fabricated",
    live=True,
)

LIVE_SCENARIO_C = GpuProcessE2EScenario(
    scenario_id="live_c_gpu_overall_status",
    user_request="GPU全体の使用率や温度など、現在のGPU状態を確認してください。",
    expected_tool="get_gpu_status",
    routing_note="Real LLM — must not pick get_gpu_processes",
    live=True,
)

LIVE_SCENARIO_D = GpuProcessE2EScenario(
    scenario_id="live_d_gpu_process_explain",
    user_request="GPUを使っているプロセスを確認したうえで、どのプロセスがVRAMを多く使っているか説明してください。",
    expected_tool="get_gpu_processes",
    routing_note="Real LLM — tool result utilization in answer",
    live=True,
)

LIVE_SCENARIO_E = GpuProcessE2EScenario(
    scenario_id="live_e_cpu_structured",
    user_request="CPUのモデル名、コア数、スレッド数を確認してください。",
    expected_tool="get_cpu_status",
    routing_note="Real LLM — structured CPU metrics",
    live=True,
)

LIVE_SCENARIOS = [
    LIVE_SCENARIO_A,
    LIVE_SCENARIO_B,
    LIVE_SCENARIO_C,
    LIVE_SCENARIO_D,
    LIVE_SCENARIO_E,
]
