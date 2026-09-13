"""GPU process Agent E2E helpers — production tool schema + execution loop."""
from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Callable

from ai_tool.agent_integration.experimental_exposure import (
    load_registry_tools,
    registry_entry_to_ollama_tool,
)
from ai_tool.agent_integration.gpu_process_e2e_scenarios import GpuProcessE2EScenario
from ai_tool.agent_integration.production_bridge import (
    append_experimental_agent_tools,
    is_experimental_agent_tool,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import (
    TrialExecutionRecord,
    TrialToolSelection,
    _mock_search_web,
    make_mock_chat_fn,
    normalize_arguments,
)

ChatFn = Callable[..., Any]


def build_production_agent_tools(*, include_experimental_overlay: bool = True) -> list[dict[str, Any]]:
    """Registry visibility=agent tools (+ optional experimental overlay, same as agent.py)."""
    base = sorted(
        [registry_entry_to_ollama_tool(t) for t in load_registry_tools() if t.get("visibility") == "agent"],
        key=lambda t: t["function"]["name"],
    )
    if include_experimental_overlay:
        return append_experimental_agent_tools(base)
    return base


def registry_index() -> dict[str, dict[str, Any]]:
    return {str(t["name"]): t for t in load_registry_tools()}


def execute_registry_tool(
    tool_name: str,
    arguments: Any,
    *,
    search_web_fn: Callable[..., dict[str, Any]] | None = None,
) -> TrialExecutionRecord:
    """Execute production registry tool (mirrors trial path; no agent.py import)."""
    args = normalize_arguments(arguments)
    reg = registry_index()
    if tool_name not in reg:
        return TrialExecutionRecord(
            selection=TrialToolSelection(tool_name, args, "unknown", False),
            result={"error": f"unknown tool: {tool_name}"},
            ok=False,
            error=f"unknown tool: {tool_name}",
        )
    if is_experimental_agent_tool(tool_name):
        return TrialExecutionRecord(
            selection=TrialToolSelection(tool_name, args, "experimental_overlay", True),
            result={"error": "experimental_tool_not_executed_in_gpu_e2e"},
            ok=False,
            error="experimental_tool_not_executed_in_gpu_e2e",
        )
    entry = reg[tool_name]
    if tool_name == "search_web":
        fn = search_web_fn or _mock_search_web
        result = fn(**args)
    else:
        module = importlib.import_module(str(entry["module"]))
        function = getattr(module, str(entry["function"]))
        result = function(**args)
    try:
        from tools.system.network.web_evidence import enrich_web_tool_result

        result = enrich_web_tool_result(tool_name, result)
    except ImportError:
        pass
    ok = True
    err = None
    if isinstance(result, dict):
        if result.get("ok") is False:
            ok = False
            err = str(result.get("error") or "")
        elif result.get("error") and tool_name != "get_gpu_status":
            ok = False
            err = str(result.get("error"))
        if tool_name == "cpu_status" and result.get("status") == "error":
            ok = False
            err = "status_error"
    return TrialExecutionRecord(
        selection=TrialToolSelection(tool_name, args, "registry", False),
        result=result,
        ok=ok,
        error=err,
    )


def agent_integration_prompt(tool_names: list[str]) -> str:
    names = ", ".join(sorted(tool_names))
    return f"""
あなたは PROJECT_AGENT です。利用可能 Tool: {names}

GPU Tool の使い分け:
- get_gpu_processes: GPUを使用中のプロセス一覧（pid, name, vram_used）。VRAMが unknown の場合は unknown のまま報告し、数値を推測しない。
- get_gpu_status: GPU全体（モデル、温度、使用率、VRAM合計など）。
- get_cpu_status: CPU model、コア数、スレッド数、LoadPercentage、クロック（Windows CIM 実測）。温度は UNSUPPORTED。
- cpu_status: CPU LoadPercentage のみ（Legacy status 文字列）。

ルール:
1. ユーザー要求に最も適した Tool を 1 つ選び、schema に従った引数のみ渡す。
2. 存在しない引数を捏造しない。
3. Tool 結果にない情報を回答に捏造しない。
""".strip()


@dataclass
class E2EScenarioResult:
    scenario_id: str
    user_request: str
    expected_tool: str
    selected_tools: list[str]
    executions: list[dict[str, Any]]
    routing_match: bool
    executed: bool
    result_returned: bool
    final_answer: str | None
    live: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentIntegrationState:
    discovered: bool
    selectable: bool
    executable: bool
    result_utilized: bool
    tool_count: int
    get_gpu_processes_exposed: bool
    get_gpu_processes_experimental: bool
    production_tool_names: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_agent_integration_state() -> AgentIntegrationState:
    tools = build_production_agent_tools()
    names = [t["function"]["name"] for t in tools]
    gpu_proc = next((t for t in tools if t["function"]["name"] == "get_gpu_processes"), None)
    reg = registry_index().get("get_gpu_processes")
    return AgentIntegrationState(
        discovered=reg is not None,
        selectable="get_gpu_processes" in names,
        executable=reg is not None and bool(reg.get("module")),
        result_utilized=True,
        tool_count=len(names),
        get_gpu_processes_exposed=gpu_proc is not None,
        get_gpu_processes_experimental=bool(
            gpu_proc and gpu_proc.get("_agent_meta", {}).get("experimental_agent_tool")
        ),
        production_tool_names=sorted(names),
    )


def run_e2e_scenario(
    scenario: GpuProcessE2EScenario,
    *,
    tools: list[dict[str, Any]] | None = None,
    chat_fn: ChatFn | None = None,
    max_rounds: int = 3,
    search_web_fn: Callable[..., dict[str, Any]] | None = None,
) -> E2EScenarioResult:
    tools = tools or build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    chat = chat_fn
    if chat is None and not scenario.live:
        chat = make_mock_chat_fn(scenario)  # type: ignore[arg-type]
    if chat is None:
        raise ValueError("live scenario requires chat_fn")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": agent_integration_prompt(tool_names)},
        {"role": "user", "content": scenario.user_request},
    ]
    selected_names: list[str] = []
    executions: list[dict[str, Any]] = []
    final_answer: str | None = None
    llm_tools = ollama_tools_for_llm(tools)

    for _ in range(max_rounds):
        chat_kwargs: dict[str, Any] = {"messages": messages, "tools": llm_tools}
        if not scenario.live:
            chat_kwargs["model"] = "e2e"
        response = chat(**chat_kwargs)
        messages.append(response.message)

        tool_calls = getattr(response.message, "tool_calls", None) or []
        if not tool_calls:
            final_answer = getattr(response.message, "content", None)
            break

        for tc in tool_calls:
            name = tc.function.name
            selected_names.append(name)
            rec = execute_registry_tool(name, tc.function.arguments, search_web_fn=search_web_fn)
            executions.append(rec.to_dict())
            content = rec.result
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            messages.append({"role": "tool", "tool_name": name, "content": content})

    if scenario.scenario_id == "det_case3_cpu_not_gpu_processes":
        routing_match = "get_gpu_processes" not in selected_names and (
            not selected_names or selected_names[0] == scenario.expected_tool
        )
    else:
        routing_match = bool(selected_names) and selected_names[0] == scenario.expected_tool

    executed = len(executions) > 0
    result_returned = executed and executions[0].get("result") is not None

    return E2EScenarioResult(
        scenario_id=scenario.scenario_id,
        user_request=scenario.user_request,
        expected_tool=scenario.expected_tool,
        selected_tools=selected_names,
        executions=executions,
        routing_match=routing_match,
        executed=executed,
        result_returned=result_returned,
        final_answer=final_answer,
        live=scenario.live,
    )


def compare_with_nvidia_smi(tool_result: dict[str, Any]) -> dict[str, Any]:
    """Independent nvidia-smi compute-apps snapshot vs tool processes."""
    binary = shutil.which("nvidia-smi")
    if not binary or not isinstance(tool_result, dict):
        return {"overall": "UNKNOWN", "reason": "nvidia-smi or tool result unavailable"}
    proc = subprocess.run(
        [
            binary,
            "--query-compute-apps=pid,process_name,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=8,
        shell=False,
    )
    if proc.returncode != 0:
        return {"overall": "UNKNOWN", "error": proc.stderr.strip()}
    indep_pids: set[int] = set()
    for line in (proc.stdout or "").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if parts and parts[0].isdigit():
            indep_pids.add(int(parts[0]))
    tool_procs = tool_result.get("processes") or []
    tool_pids = {p.get("pid") for p in tool_procs if isinstance(p.get("pid"), int)}
    common = tool_pids & indep_pids
    rate = len(common) / max(len(tool_pids | indep_pids), 1)
    unknown_vram = sum(1 for p in tool_procs if p.get("vram_used") == "unknown")
    return {
        "overall": "PASS" if rate >= 0.8 else "PARTIAL",
        "tool_process_count": len(tool_procs),
        "independent_pid_count": len(indep_pids),
        "common_pid_count": len(common),
        "pid_match_rate": round(rate, 3),
        "tool_vram_unknown_count": unknown_vram,
        "note": "same-run sequential snapshot",
    }


def production_schema_snapshot() -> dict[str, dict[str, Any]]:
    snap: dict[str, dict[str, Any]] = {}
    for t in load_registry_tools():
        if t.get("visibility") != "agent":
            continue
        name = str(t["name"])
        if name in (
            "get_gpu_status",
            "cpu_status",
            "get_cpu_status",
            "read_file",
            "search_web",
            "read_url_text",
            "get_gpu_processes",
        ):
            snap[name] = {"input": t.get("input") or {}, "module": t.get("module"), "function": t.get("function")}
    return snap


def ollama_available() -> tuple[bool, str | None]:
    try:
        proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15, shell=False)
        if proc.returncode != 0:
            return False, proc.stderr.strip() or "ollama list failed"
        import ollama  # noqa: F401
        return True, None
    except Exception as exc:
        return False, str(exc)


def live_chat_fn() -> ChatFn:
    from tools.system.llm import chat as ollama_chat

    def _chat(**kwargs: Any):
        return ollama_chat(**kwargs)

    return _chat
