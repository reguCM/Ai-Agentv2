"""Predefined trial scenarios — search_web vs read_url_text routing (Phase 4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ExpectedTool = Literal["search_web", "read_url_text", "either"]


@dataclass
class TrialScenario:
    scenario_id: str
    user_request: str
    expected_tool: ExpectedTool
    routing_note: str
    mock_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    mock_final_answer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "user_request": self.user_request,
            "expected_tool": self.expected_tool,
            "routing_note": self.routing_note,
            "mock_tool_calls": self.mock_tool_calls,
            "mock_final_answer": self.mock_final_answer,
        }


URL_FETCH_SCENARIO = TrialScenario(
    scenario_id="url_fetch_known_page",
    user_request=(
        "次の URL のページ本文を取得して、先頭 200 文字を要約してください。"
        " https://example.com/docs/release-notes"
    ),
    expected_tool="read_url_text",
    routing_note=(
        "既知の HTTPS URL の本文取得 → read_url_text。"
        "search_web はクエリ検索用であり、特定 URL の GET 取得には使わない。"
    ),
    mock_tool_calls=[
        {
            "name": "read_url_text",
            "arguments": {"url": "https://example.com/docs/release-notes", "max_bytes": 8192},
        }
    ],
    mock_final_answer="example.com の release-notes ページ先頭を要約しました（trial mock）。",
)

WEB_SEARCH_SCENARIO = TrialScenario(
    scenario_id="web_search_open_question",
    user_request=(
        "Python 3.13 の新機能について、最新情報を Web 検索して 3 件の要点をまとめてください。"
    ),
    expected_tool="search_web",
    routing_note=(
        "URL 未指定の探索質問 → search_web。"
        "read_url_text は URL が与えられたときの本文 GET 専用。"
    ),
    mock_tool_calls=[
        {"name": "search_web", "arguments": {"query": "Python 3.13 new features", "limit": 3}}
    ],
    mock_final_answer="Python 3.13 の要点 3 件（trial mock、search_web 結果に基づく）。",
)

ROUTING_COMPARISON = {
    "search_web": {
        "purpose": "query-based web search returning multiple hits (title/snippet/url)",
        "inputs": ["query", "limit?"],
        "when_to_use": "URL 不明・探索が必要・複数ソース比較",
        "not_for": "既知 URL の本文直接取得",
    },
    "read_url_text": {
        "purpose": "read-only HTTP GET for a specific URL body (experimental trial)",
        "inputs": ["url", "max_bytes?", "timeout_seconds?"],
        "when_to_use": "URL が明示されている本文取得・SSRF 保護付き fetch",
        "not_for": "キーワード検索・複数候補の探索",
    },
}

DEFAULT_TRIAL_SCENARIOS = [URL_FETCH_SCENARIO, WEB_SEARCH_SCENARIO]
