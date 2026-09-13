"""CURSOR_CONTROLLER verification for Phase 3-4. Not Project Agent capability."""
import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT, bootstrap_repo_root

bootstrap_repo_root()
ROOT = REPO_ROOT
import json
import inspect
from collections import Counter
from pathlib import Path


def create_ollama_tools(registry):
    tools = []
    for tool in registry["tools"]:
        if tool.get("visibility") != "agent":
            continue
        properties = {}
        required = []
        for name, parameter in tool.get("input", {}).items():
            param = dict(parameter)
            is_required = bool(param.pop("required", False))
            properties[name] = param
            if is_required:
                required.append(name)
        for name in tool.get("required") or []:
            if name not in required:
                required.append(name)
        parameters = {"type": "object", "properties": properties}
        if required:
            parameters["required"] = required
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": parameters,
                },
            }
        )
    return tools


def main():
    registry = json.loads(ROOT / "registry" / "tools.json".read_text(encoding="utf-8"))
    ollama_tools = create_ollama_tools(registry)
    agent_names = [t["function"]["name"] for t in ollama_tools]
    pipeline_names = [
        t["name"] for t in registry["tools"] if t.get("visibility") == "pipeline"
    ]

    print("===1 Registry visibility counts===")
    print(dict(Counter(t.get("visibility") for t in registry["tools"])))

    print("===2 Agent Ollama tools===")
    print(agent_names)

    print("===3 Pipeline not in Ollama===")
    leaked = [n for n in pipeline_names if n in agent_names]
    print("leaked:", leaked)
    print("pipeline_count:", len(pipeline_names))
    assert not leaked

    print("===4 search_web schema===")
    sw = next(t for t in ollama_tools if t["function"]["name"] == "search_web")
    print(json.dumps(sw["function"]["parameters"], ensure_ascii=False, indent=2))
    assert sw["function"]["parameters"]["required"] == ["query"]
    assert "required" not in sw["function"]["parameters"]["properties"]["query"]
    assert "実際にWeb検索を実行" in sw["function"]["description"]

    print("===5 path traversal===")
    from tools.file.workspace.list_files import list_files
    from tools.file.workspace.read_file import read_file
    from tools.file.workspace.search_files import search_files
    from tools.file.workspace._paths import workspace_root

    root = workspace_root()
    print("root:", root)
    r1 = list_files(path="..")
    r2 = read_file(path="C:/Windows/System32/drivers/etc/hosts")
    r3 = read_file(path="registry/tools.json", offset=1, limit=3)
    r4 = search_files(query="web_research", path="registry", glob="*.json")
    print("dotdot_ok?", r1.get("ok"), "error:", r1.get("error"))
    print("abs_out_ok?", r2.get("ok"), "error:", r2.get("error"))
    print("read_ok?", r3.get("ok"), "lines:", r3.get("returned_lines"))
    print("search_ok?", r4.get("ok"), "matches:", r4.get("match_count"))
    assert r1.get("ok") is False
    assert r2.get("ok") is False
    assert r3.get("ok") is True
    assert r4.get("ok") is True

    print("===6 existing search_web path===")
    from tools.system.tool_builder.research.web import search_web as core_search_web
    from tools.system.network.search_web import search_web as agent_search_web
    import tools.ai.tool_builder.web as web_mod

    sig = inspect.signature(web_mod.web_research)
    print("web_research params:", list(sig.parameters))
    empty = core_search_web("")
    print("core empty error:", empty.get("error"))
    net = agent_search_web(query="Windows CPU LoadPercentage", limit=3)
    print(
        "agent search backends:",
        net.get("backends_tried"),
        "hits:",
        len(net.get("hits") or []),
        "error:",
        net.get("error"),
    )

    print("===7 research/builder imports===")
    from tools.system.tool_builder.research.executor import research_executor  # noqa: F401
    from tools.ai.tool_builder.web import web_research

    materials = web_research(
        search_results=[
            {"title": "t", "snippet": "s", "url": "u", "backend": "x"}
        ],
        inventory={"available_commands": ["powershell"]},
    )
    assert "rules" in materials
    print("web_research materials keys ok")

    print("===8 required generation===")
    rf = next(t for t in ollama_tools if t["function"]["name"] == "read_file")
    sf = next(t for t in ollama_tools if t["function"]["name"] == "search_files")
    assert rf["function"]["parameters"]["required"] == ["path"]
    assert sf["function"]["parameters"]["required"] == ["query"]
    print("required ok for read_file/search_files")

    # Confirm agent.py create_ollama_tools source matches filter
    agent_src = ROOT / "agent.py".read_text(encoding="utf-8")
    assert 'visibility") != "agent"' in agent_src or "visibility\") != \"agent\"" in agent_src
    assert "parameters[\"required\"]" in agent_src or 'parameters["required"]' in agent_src

    expected = {
        "get_gpu_status",
        "get_gpu_processes",
        "cpu_status",
        "search_web",
        "list_files",
        "read_file",
        "search_files",
    }
    assert set(agent_names) == expected, agent_names
    assert "web_research" not in agent_names
    assert "create_tool_proposal" not in agent_names

    wr = next(t for t in registry["tools"] if t["name"] == "web_research")
    assert wr["visibility"] == "pipeline"
    assert "Web検索を実行するToolではない" in wr["description"]

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
