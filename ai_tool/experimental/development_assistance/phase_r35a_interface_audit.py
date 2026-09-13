"""R3.5-A 経路監査（読み取りのみ。Production / Workflow は変更しない）。

agent.py は import しない（実行ループが走るため）。ソースと JSON を読む。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]


def _visibility_counts(registry: dict[str, Any]) -> dict[str, Any]:
    tools = registry.get("tools") or []
    agent = [t["name"] for t in tools if t.get("visibility") == "agent"]
    pipeline = [t["name"] for t in tools if t.get("visibility") == "pipeline"]
    unspecified = [t["name"] for t in tools if "visibility" not in t]
    return {
        "agent": agent,
        "pipeline": pipeline,
        "unspecified": unspecified,
        "agent_count": len(agent),
        "pipeline_count": len(pipeline),
        "unspecified_count": len(unspecified),
        "total": len(tools),
    }


def _workspace_tools_on_disk() -> dict[str, bool]:
    ws = _REPO / "tools" / "file" / "workspace"
    return {
        "list_files.py": (ws / "list_files.py").is_file(),
        "read_file.py": (ws / "read_file.py").is_file(),
        "search_files.py": (ws / "search_files.py").is_file(),
        "write_file.py": (ws / "write_file.py").is_file(),
    }


def run_r35a_interface_audit() -> dict[str, Any]:
    agent_src = (_REPO / "agent.py").read_text(encoding="utf-8")
    registry = json.loads((_REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    vis = _visibility_counts(registry)
    ws_files = _workspace_tools_on_disk()
    llm_py = (_REPO / "tools" / "system" / "llm.py").read_text(encoding="utf-8")
    r3_src = (
        _REPO / "ai_tool" / "experimental" / "development_assistance" / "phase_r3_min_loop_harness.py"
    ).read_text(encoding="utf-8")
    wf_src = (
        _REPO / "ai_tool" / "experimental" / "development_assistance" / "standard_workflow.py"
    ).read_text(encoding="utf-8")
    bridge_src = (_REPO / "ai_tool" / "agent_integration" / "production_bridge.py").read_text(
        encoding="utf-8"
    )
    pointer_src = (
        _REPO / "ai_tool" / "experimental" / "development_assistance" / "pointer_resolution.py"
    ).read_text(encoding="utf-8")

    html_count = len(list(_REPO.glob("*.html")))
    ui_framework_hits = []
    for name in ("streamlit", "flask", "fastapi", "gradio", "django"):
        if name in agent_src.lower():
            ui_framework_hits.append(name)

    agent_mentions_file_tools = all(
        name in agent_src for name in ("list_files", "read_file", "search_files")
    )
    file_tools_in_registry = [
        n for n in ("list_files", "read_file", "search_files", "write_file") if n in vis["agent"]
    ]

    problems = [
        {
            "発見した問題": "SYSTEM_PROMPT と IDENTITY_SMOKE は list_files / read_file / search_files を前提にするが、現行 registry/tools.json に同名 Tool が無い。",
            "影響": "LLM がファイル Tool を選ぶと execute_tool が失敗する。IDENTITY_SMOKE も失敗し得る。「hello.py を作る」は Agent 経路では成立しない。",
            "修正案": "Registry と Prompt を一致させる。または Prompt / smoke から未登録名を外す。write_file はコード自体が無い。今回は未修正。",
        },
        {
            "発見した問題": "create_tool_proposal に visibility=agent が無い。Ollama 公開集合に入らない。",
            "影響": "通常の Agent ループから Tool 作成は始まらない。execute_tool の特殊分岐は呼べない。",
            "修正案": "意図的なら Prompt にも「作れない」と書く。公開するなら visibility と Gate を設計する。今回は未修正。",
        },
        {
            "発見した問題": "agent.py は TDA（run_standard_workflow / ResearchRecord / DevelopmentSession）を import しない。",
            "影響": "R1〜R3 の bind / diff / select は Local Agent の会話ループに接続していない。",
            "修正案": "experimental フラグでのみ接続。既定は off。今回は未修正。",
        },
        {
            "発見した問題": "ユーザー入力は対話ループではなく AI_AGENT_USER_REQUEST または起動時の既定1件。",
            "影響": "毎日使う Chat 窓口は無い。Follow-up は同一プロセスの第2メッセージとしては来ない。",
            "修正案": "Chat 入口を別 Phase で足す。今回は未修正。",
        },
        {
            "発見した問題": "production_bridge の experimental overlay ID 集合は空。",
            "影響": "Registry 外の experimental Tool は現在 Agent に追加されない。",
            "修正案": "必要な Tool は Registry 正式登録で扱う。今回は未修正。",
        },
    ]

    classification = {
        "Chat入口_CLI": "実装あり",
        "Chat入口_UI": "実装なし",
        "Ollama接続_agent.py": "実装あり",
        "Ollama接続_今回起動確認": "未確認",
        "TDA_bind_diff_select": "fixtureのみ",
        "DevelopmentSession": "fixtureのみ",
        "実LLM_R3ループ": "実装なし",
        "実LLM_agent.py": "実装あり",
        "File変更_Agent_Tool": "実装なし",
        "File読取_コード": "実装あり",
        "File読取_Registry公開": "実装なし",
        "Test_Agent自動実行": "実装なし",
        "Test_R3_fixture": "fixtureのみ",
        "Cursor_API": "実装なし",
        "UI": "実装なし",
        "Avatar": "実装なし",
        "create_tool_proposal_関数": "実装あり",
        "create_tool_proposal_Agent公開": "実装なし",
        "search_web_Agent公開": "実装あり",
        "ResearchRecord_Agent接続": "実装なし",
        "pointer_bind_Agent接続": "実装なし",
        "pointer_bind_experimental": "fixtureのみ",
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_changed": False,
        "judgment": "AUDIT_COMPLETE",
        "judgment_ja": (
            "入口・LLM・Tool・Research・Memory の接続／非接続をコードから特定した。"
            "今回 agent.py は起動していない。Ollama が今生きているかは未確認。"
        ),
        "agent_imports_tda": (
            "development_assistance" in agent_src or "run_standard_workflow" in agent_src
        ),
        "agent_imports_research_record": "ResearchRecord" in agent_src,
        "agent_imports_development_session": "DevelopmentSessionState" in agent_src,
        "agent_has_input_confirm": "input(" in agent_src,
        "agent_user_request_env": "AI_AGENT_USER_REQUEST" in agent_src,
        "ollama_client": "from ollama import Client" in llm_py,
        "r3_calls_real_llm": "llm_enabled=True" in r3_src,
        "standard_workflow_default_off": 'facet_discovery: FacetDiscoveryFlag = "off"' in wf_src,
        "experimental_overlay_empty": "_EXPERIMENTAL_AGENT_TOOL_IDS = frozenset()" in bridge_src,
        "pointer_not_in_workflow_default": "Not wired into standard_workflow defaults" in pointer_src,
        "registry_visibility": vis,
        "workspace_tools_on_disk": ws_files,
        "agent_mentions_file_tools": agent_mentions_file_tools,
        "file_tools_in_agent_registry": file_tools_in_registry,
        "html_at_repo_root": html_count,
        "ui_framework_in_agent_src": ui_framework_hits,
        "problems": problems,
        "classification": classification,
        "cases": {
            "case1_hello_py": "Chat UI なし。env 1要求 → agent.py → Ollama → Tool Call。write_file なし。Test 自動なし。TDA Session なし。",
            "case2_research": "Agent は search_web / read_url_text。Goal/Gate/Discovery/Coverage/ResearchRecord は未接続。TDA は別 harness。",
            "case3_followup": "bind は experimental Adapter のみ。Agent は単発要求。Session ID は使わない。",
            "case4_create_tool": "create_tool_proposal は Registry にあるが visibility 未指定。Agent LLM からは見えない。自動 Registry 登録は未統合。",
        },
    }
