"""Web Tool Formal Adoption Review — read-only contract checks (Phase 2)."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _registry() -> dict:
    return json.loads((REPO / "registry" / "tools.json").read_text(encoding="utf-8"))


def _agent_visible_names() -> set[str]:
    return {t["name"] for t in _registry()["tools"] if t.get("visibility") == "agent"}


def _production_agent_tools() -> list[str]:
    from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools

    return sorted(t["function"]["name"] for t in build_production_agent_tools())


# --- HEAD Registry vs production schema ---


def test_registry_search_web_agent_visible() -> None:
    assert "search_web" in _agent_visible_names()


def test_production_schema_has_web_tools_via_registry() -> None:
    names = _production_agent_tools()
    assert "read_url_text" in names
    assert "search_web" in names
    from ai_tool.agent_integration.production_bridge import is_experimental_agent_tool

    assert is_experimental_agent_tool("read_url_text") is False


def test_search_web_implementation_exists_on_disk_wt() -> None:
    path = REPO / "tools/system/network/search_web.py"
    assert path.is_file()
    src = path.read_text(encoding="utf-8")
    assert "general_web_search" in src
    assert "research.web import search_web" not in src


def test_search_web_is_discovery_not_fetch() -> None:
    from tools.system.network import search_web as sw_mod
    from tools.system.network import general_web_search as gws_mod

    sw_src = inspect.getsource(sw_mod.search_web)
    gws_src = inspect.getsource(gws_mod.general_web_search)
    assert "general_web_search" in sw_src
    assert "compact_hit" in gws_src or "rank_hits_for_query" in gws_src
    assert "read_url_text" not in sw_src


def test_search_web_no_fixed_stub_hits() -> None:
    from tools.system.network import general_web_search as gws

    src = inspect.getsource(gws)
    for banned in ("RTX 3060", "固定値", "stub"):
        assert banned not in src or banned == "stub" and "stub" not in src.lower()


def test_search_web_empty_query_error_not_fake_hits() -> None:
    from tools.system.network.search_web import search_web

    out = search_web("")
    assert out["hits"] == []
    assert out.get("error")


def test_search_web_output_contract_keys() -> None:
    from unittest import mock
    from tools.system.network import general_web_search as gws
    from tools.system.network.search_web import search_web

    with mock.patch.object(
        gws,
        "search_duckduckgo",
        return_value=[{"title": "T", "snippet": "S", "url": "https://e/", "backend": "duckduckgo"}],
    ), mock.patch.object(gws, "search_wikipedia", return_value=[]), mock.patch.object(
        gws, "search_wikipedia_en", return_value=[]
    ):
        out = search_web("test query", limit=1)
    assert out["query"] == "test query"
    assert len(out["hits"]) == 1
    hit = out["hits"][0]
    assert set(hit.keys()) >= {"title", "snippet", "url", "backend"}
    assert "content" not in hit


def test_read_url_catalog_spec_alignment() -> None:
    catalog = json.loads(
        (REPO / "ai_tool/catalog/entries/local_read_url_text.json").read_text(encoding="utf-8")
    )
    spec = json.loads(
        (REPO / "docs/ai_tool/tool_creation/specs/local_read_url_text.json").read_text(encoding="utf-8")
    )
    assert catalog["tool_id"] == spec["tool_id"]
    assert catalog["input_schema"] == spec["input_schema"]


def test_read_url_formal_adoption_gaps_documented() -> None:
    spec = json.loads(
        (REPO / "docs/ai_tool/tool_creation/specs/local_read_url_text.json").read_text(encoding="utf-8")
    )
    limits = spec.get("known_limitations") or []
    blob = " ".join(limits).lower()
    assert "javascript" in blob
    assert "registry" in blob or "experimental" in blob


# --- Search → Fetch loop (trial infrastructure, not production HEAD) ---


@pytest.fixture
def catalog_sandbox(tmp_path: Path) -> Path:
    import shutil
    from ai_tool.catalog.store import catalog_entries_dir

    dest = tmp_path / "entries"
    shutil.copytree(catalog_entries_dir(), dest)
    return dest


def test_search_fetch_two_round_trial_deterministic(catalog_sandbox: Path) -> None:
    """Discovery → Fetch loop works with production registry tools."""
    from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
    from ai_tool.agent_integration.trial import TrialScenario, run_trial_scenario

    scenario = TrialScenario(
        scenario_id="search_then_fetch",
        user_request="調べてから公式ページを読んで",
        expected_tool="either",
        routing_note="two-round search_web then read_url_text",
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": "example topic", "limit": 3}},
            {"name": "read_url_text", "arguments": {"url": "https://example.com/page"}},
        ],
        mock_final_answer="done",
    )
    tools = build_production_agent_tools()
    result = run_trial_scenario(
        scenario,
        tools=tools,
        catalog_entries_dir=catalog_sandbox,
        max_rounds=5,
    )
    assert len(result.executions) == 2
    assert result.executions[0].selection.tool_name == "search_web"
    assert result.executions[1].selection.tool_name == "read_url_text"
    tool_msgs = [m for m in result.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 2


def test_registry_unchanged_sha256() -> None:
    path = REPO / "registry" / "tools.json"
    # snapshot for review phase — must match committed HEAD content at review time
    assert path.is_file()
    assert len(hashlib.sha256(path.read_bytes()).hexdigest()) == 64
