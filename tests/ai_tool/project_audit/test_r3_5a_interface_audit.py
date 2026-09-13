"""R3.5-A：窓口監査。Production と既定 Workflow は変えない。agent.py は import しない。"""
from __future__ import annotations

from pathlib import Path

from ai_tool.experimental.development_assistance.phase_r35a_interface_audit import (
    run_r35a_interface_audit,
)
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f


def test_default_workflow_still_off():
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )
    assert result.facet_discovery == "off"


def test_phase_f_still_adopt():
    result = run_phase_f(llm_enabled=False)
    assert result["decision"] == "ADOPT"
    assert result["core_discovery"]["c3_implemented"] == 0


def test_r35a_static_audit():
    result = run_r35a_interface_audit()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_changed"] is False
    assert result["judgment"] == "AUDIT_COMPLETE"
    assert result["agent_imports_tda"] is False
    assert result["agent_imports_research_record"] is False
    assert result["agent_imports_development_session"] is False
    assert result["r3_calls_real_llm"] is False
    assert result["standard_workflow_default_off"] is True
    assert result["ollama_client"] is True
    assert "search_web" in result["registry_visibility"]["agent"]
    assert "create_tool_proposal" not in result["registry_visibility"]["agent"]
    assert result["file_tools_in_agent_registry"] == []
    assert result["workspace_tools_on_disk"]["write_file.py"] is False
    assert result["html_at_repo_root"] == 0


def test_agent_py_is_not_imported_by_audit_module():
    import ai_tool.experimental.development_assistance.phase_r35a_interface_audit as audit_mod

    src = Path(audit_mod.__file__).read_text(encoding="utf-8")
    assert "import agent" not in src
    assert "from agent" not in src
