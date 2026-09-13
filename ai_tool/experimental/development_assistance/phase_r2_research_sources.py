"""R2 実Research の取得ソース。TDA パイプラインに渡す HTML。Core ではない。

live インターネットは使わない。取得経路は既存の run_tda_case（search + read_url）。
"""
from __future__ import annotations

from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec

URL_A = "https://fixture.local/r2/liba-docs"
URL_B = "https://fixture.local/r2/libb-docs"
URL_C = "https://fixture.local/r2/ursim-docker"
URL_D = "https://fixture.local/r2/node-project"
URL_E = "https://fixture.local/r2/license-notes"

HTML_A = """
<html><head><title>LibA parse_a_payload Documentation</title></head><body>
<main><h1>LibA</h1>
<p>Requires Python 3.12. Supported OS: Windows. GPU stack: CUDA 12.3.
License: MIT. Unique API: parse_a_payload. Install with pip install liba.</p>
</main></body></html>
"""

HTML_B = """
<html><head><title>LibB Documentation</title></head><body>
<main><h1>LibB</h1>
<p>Requires Python 3.13. Supported OS: Linux. GPU stack: CUDA 12.4.
License: BSD. Install with pip install libb.</p>
</main></body></html>
"""

HTML_C = """
<html><head><title>URSim Docker ROS notes</title></head><body>
<main><h1>URSim</h1>
<p>URSim 5.15.2 runs in Docker on Ubuntu. ROS middleware is optional.
This note is not about LibA. Dashboard API is separate.</p>
</main></body></html>
"""

HTML_D = """
<html><head><title>Project D Node.js notes</title></head><body>
<main><h1>Project D</h1>
<p>Separate project. Node.js runtime on Windows.
This is not LibA and not LibB.</p>
</main></body></html>
"""

HTML_E = """
<html><head><title>License notes</title></head><body>
<main><h1>License notes</h1>
<p>Standalone license memo. License: Apache 2.0. No GPU stack. No robot simulator.</p>
</main></body></html>
"""

HTML_A_OFFICIAL = """
<html><head><title>LibA official Python support</title></head><body>
<main><h1>LibA official</h1>
<p>Official documentation: Python 3.12 is supported. Windows. CUDA 12.3. License: MIT.</p>
</main></body></html>
"""

HTML_A_THIRD = """
<html><head><title>LibA community Python notes</title></head><body>
<main><h1>LibA community</h1>
<p>Third-party blog: Python 3.13 is supported. Unofficial. Do not treat as official.</p>
</main></body></html>
"""


def spec_a() -> TDACaseSpec:
    return TDACaseSpec(
        case_id="R2-A",
        label="技術A LibA",
        user_requirement="技術A（LibA）について調べて。",
        force_research=True,
        url_html={URL_A: HTML_A},
        search_hits=[{"title": "LibA Documentation", "url": URL_A}],
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": "LibA Python documentation"}},
            {"name": "read_url_text", "arguments": {"url": URL_A}},
        ],
        checks={"min_candidates": 1},
    )


def spec_b() -> TDACaseSpec:
    return TDACaseSpec(
        case_id="R2-B",
        label="技術B LibB",
        user_requirement="技術B（LibB）について調べて。",
        force_research=True,
        url_html={URL_B: HTML_B},
        search_hits=[{"title": "LibB Documentation", "url": URL_B}],
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": "LibB Python documentation"}},
            {"name": "read_url_text", "arguments": {"url": URL_B}},
        ],
        checks={"min_candidates": 1},
    )


def spec_c() -> TDACaseSpec:
    return TDACaseSpec(
        case_id="R2-C",
        label="URSim Docker",
        user_requirement="URSimとDockerとROSについて調べて。",
        force_research=True,
        url_html={URL_C: HTML_C},
        search_hits=[{"title": "URSim Docker ROS notes", "url": URL_C}],
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": "URSim Docker ROS"}},
            {"name": "read_url_text", "arguments": {"url": URL_C}},
        ],
        checks={"min_candidates": 1},
    )


def spec_d() -> TDACaseSpec:
    return TDACaseSpec(
        case_id="R2-D",
        label="別プロジェクト Node.js",
        user_requirement="別プロジェクトDのNode.js構成を調べて。",
        force_research=True,
        url_html={URL_D: HTML_D},
        search_hits=[{"title": "Project D Node.js notes", "url": URL_D}],
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": "Project D Node.js"}},
            {"name": "read_url_text", "arguments": {"url": URL_D}},
        ],
        checks={"min_candidates": 1},
    )


def spec_e() -> TDACaseSpec:
    return TDACaseSpec(
        case_id="R2-E",
        label="License メモ",
        user_requirement="ライセンス関連のメモを調べて。",
        force_research=True,
        url_html={URL_E: HTML_E},
        search_hits=[{"title": "License notes", "url": URL_E}],
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": "license notes Apache"}},
            {"name": "read_url_text", "arguments": {"url": URL_E}},
        ],
        checks={"min_candidates": 1},
    )


def spec_a_conflict_sources() -> TDACaseSpec:
    """公式 3.12 と第三者 3.13 を同じ Research に混ぜる。"""
    off = "https://fixture.local/r2/liba-official"
    third = "https://fixture.local/r2/liba-community"
    return TDACaseSpec(
        case_id="R2-A-CONFLICT",
        label="技術A 公式と第三者",
        user_requirement="技術AのPython対応を調べて。",
        force_research=True,
        url_html={off: HTML_A_OFFICIAL, third: HTML_A_THIRD},
        search_hits=[
            {"title": "LibA official Python support", "url": off},
            {"title": "LibA community Python notes", "url": third},
        ],
        mock_tool_calls=[
            {"name": "read_url_text", "arguments": {"url": off}},
            {"name": "read_url_text", "arguments": {"url": third}},
        ],
        checks={"min_candidates": 1},
    )


def core_specs() -> list[TDACaseSpec]:
    return [spec_a(), spec_b(), spec_c(), spec_d(), spec_e()]
