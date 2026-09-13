"""Evaluation fixtures A–H for Tool Development Assistance PoC."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- Fixture HTML sources ---

FIXTURE_POLARS = """
<html><head><title>Polars Documentation</title></head><body>
<main><h1>Polars</h1>
<p>Polars is a fast DataFrame library written in Rust. Requires Python 3.9+.
License: MIT. pip install polars. Supports CSV, Parquet, lazy evaluation.</p>
</main></body></html>
"""

FIXTURE_PYPDF = """
<html><head><title>PyPDF2</title></head><body>
<main><h1>PyPDF2</h1>
<p>PyPDF2 is a pure-python PDF library. Python 3.8+. License: BSD.
pip install pypdf2. Read and merge PDF files.</p>
</main></body></html>
"""

FIXTURE_PDFPLUMBER = """
<html><head><title>pdfplumber</title></head><body>
<main><h1>pdfplumber</h1>
<p>pdfplumber extracts text and tables from PDFs. Python 3.8+. License: MIT.
GitHub: jsvine/pdfplumber. Better table extraction than PyPDF2.</p>
</main></body></html>
"""

FIXTURE_PDF_API = """
<html><head><title>PDF API Service</title></head><body>
<main><h1>Cloud PDF API</h1>
<p>REST API for PDF parsing. Requires API key. Python SDK available.
No local GPU required. External service dependency.</p>
</main></body></html>
"""

FIXTURE_PANDAS_OLD = """
<html><head><title>Legacy Library Docs</title></head><body>
<main><h1>DataFrameLib</h1>
<p>DataFrameLib v1.2. Python 3.11 supported. Windows and Linux.</p>
</main></body></html>
"""

FIXTURE_PANDAS_NEW = """
<html><head><title>Current Library Docs</title></head><body>
<main><h1>DataFrameLib</h1>
<p>DataFrameLib v2.0. Python 3.12 supported. Dropped Python 3.10.</p>
</main></body></html>
"""

FIXTURE_LICENSE_A = """
<html><head><title>ToolX</title></head><body>
<main><p>ToolX library. License: MIT. Version 1.0.</p></main></body></html>
"""

FIXTURE_LICENSE_B = """
<html><head><title>ToolX Fork</title></head><body>
<main><p>ToolX community fork. License: GPL-3.0. Version 1.0.</p></main></body></html>
"""

FIXTURE_URSCRIPT = """
<html><head><title>URScript Manual</title></head><body>
<main><h1>URScript Programming</h1>
<p>URScript is the programming language for Universal Robots cobots.
Used in PolyScope. Commands: movej, movel, set_digital_out, Thread.
Not Python — do not confuse with Python robotics libraries.
Official documentation: universal-robots.com.</p>
</main></body></html>
"""

FIXTURE_UR_API = """
<html><head><title>Universal Robots SDK</title></head><body>
<main><h1>UR Client Library</h1>
<p>Python SDK for UR robots (urx, ur_rtde). Requires robot controller connection.
URScript runs on robot; PC sends programs via TCP. Safety limits apply.</p>
</main></body></html>
"""

FIXTURE_PYTORCH = """
<html><head><title>PyTorch Install</title></head><body>
<main><h1>PyTorch GPU</h1>
<p>PyTorch 2.2 requires Python 3.10+. CUDA 11.8 or 12.1.
GPU with sufficient VRAM recommended. Docker images available.
pip install torch --index-url pytorch.org.</p>
</main></body></html>
"""

FIXTURE_TORCH_CUDA = """
<html><head><title>CUDA Requirements</title></head><body>
<main><h1>CUDA for PyTorch</h1>
<p>NVIDIA CUDA 12.1. Windows 10/11 or Linux. Minimum 8GB VRAM for inference.
Requires compatible GPU driver.</p>
</main></body></html>
"""


@dataclass
class TDACaseSpec:
    case_id: str
    label: str
    user_requirement: str
    force_research: bool | None = None
    include_custom_build: bool = False
    url_html: dict[str, str] = field(default_factory=dict)
    search_hits: list[dict[str, Any]] = field(default_factory=list)
    mock_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    follow_ups: list[tuple[str, str]] = field(default_factory=list)
    expected_gate: str = "RESEARCH_REQUIRED"
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "label": self.label,
            "user_requirement": self.user_requirement,
            "expected_gate": self.expected_gate,
            "checks": self.checks,
        }


def tda_evaluation_cases() -> list[TDACaseSpec]:
    polars_url = "https://fixture.local/polars-docs"
    pypdf_url = "https://fixture.local/pypdf2"
    plum_url = "https://fixture.local/pdfplumber"
    api_url = "https://fixture.local/pdf-api"
    old_url = "https://fixture.local/lib-old"
    new_url = "https://fixture.local/lib-new"
    lic_a = "https://fixture.local/toolx-a"
    lic_b = "https://fixture.local/toolx-b"
    ur_doc = "https://fixture.local/urscript-manual"
    ur_sdk = "https://fixture.local/ur-sdk"
    pt_url = "https://fixture.local/pytorch"
    cuda_url = "https://fixture.local/cuda-req"

    return [
        TDACaseSpec(
            case_id="TDA-A",
            label="General Tool — JSON read",
            user_requirement="JSONファイルを読み込んで内容を返すToolを作りたい",
            force_research=False,
            expected_gate="RESEARCH_NOT_REQUIRED",
            checks={"llm_only_sufficient": True},
        ),
        TDACaseSpec(
            case_id="TDA-B",
            label="New/Niche OSS — Polars",
            user_requirement="Polarsという新しいデータフレームライブラリでCSVを処理するToolを作りたい",
            force_research=True,
            url_html={polars_url: FIXTURE_POLARS},
            search_hits=[{"title": "Polars docs", "url": polars_url}],
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "Polars Python documentation"}},
                {"name": "read_url_text", "arguments": {"url": polars_url}},
            ],
            checks={"min_candidates": 1, "expects_type": "Library", "web_beats_llm_only": True},
        ),
        TDACaseSpec(
            case_id="TDA-C",
            label="Multiple Existing Tools — PDF",
            user_requirement="PDFを解析するToolを作りたい。既存ライブラリやAPIを調べて",
            force_research=True,
            url_html={
                pypdf_url: FIXTURE_PYPDF,
                plum_url: FIXTURE_PDFPLUMBER,
                api_url: FIXTURE_PDF_API,
            },
            mock_tool_calls=[
                {"name": "read_url_text", "arguments": {"url": pypdf_url}},
                {"name": "read_url_text", "arguments": {"url": plum_url}},
                {"name": "read_url_text", "arguments": {"url": api_url}},
            ],
            checks={"min_candidates": 2, "multi_type": True},
        ),
        TDACaseSpec(
            case_id="TDA-D",
            label="Existing vs Custom Build",
            user_requirement="社内CSVを変換するToolを作りたい。既存Toolと自作を比較して",
            force_research=True,
            include_custom_build=True,
            url_html={pypdf_url: FIXTURE_PYPDF},
            mock_tool_calls=[{"name": "read_url_text", "arguments": {"url": pypdf_url}}],
            follow_ups=[("自作したい", "BUILD_CUSTOM")],
            checks={"has_custom_build": True},
        ),
        TDACaseSpec(
            case_id="TDA-E",
            label="Version Difference",
            user_requirement="DataFrameLibでデータ処理Toolを作りたい。Pythonバージョン要件を確認",
            force_research=True,
            url_html={old_url: FIXTURE_PANDAS_OLD, new_url: FIXTURE_PANDAS_NEW},
            mock_tool_calls=[
                {"name": "read_url_text", "arguments": {"url": old_url}},
                {"name": "read_url_text", "arguments": {"url": new_url}},
            ],
            checks={"version_conflict": True, "relation": "DEFINITION_DIFF"},
        ),
        TDACaseSpec(
            case_id="TDA-F",
            label="Conflicting Sources",
            user_requirement="ToolXライブラリを使うToolを作りたい",
            force_research=True,
            url_html={lic_a: FIXTURE_LICENSE_A, lic_b: FIXTURE_LICENSE_B},
            mock_tool_calls=[
                {"name": "read_url_text", "arguments": {"url": lic_a}},
                {"name": "read_url_text", "arguments": {"url": lic_b}},
            ],
            checks={"conflicts_preserved": True},
        ),
        TDACaseSpec(
            case_id="TDA-G",
            label="Specialized Language — URScript",
            user_requirement="Universal Robotsのロボット用コードを書くToolを作りたい",
            force_research=True,
            url_html={ur_doc: FIXTURE_URSCRIPT, ur_sdk: FIXTURE_UR_API},
            mock_tool_calls=[
                {"name": "read_url_text", "arguments": {"url": ur_doc}},
                {"name": "read_url_text", "arguments": {"url": ur_sdk}},
            ],
            follow_ups=[("Aを使いたい", "SELECT_CANDIDATE")],
            checks={"mentions_urscript": True, "no_python_fabrication": True},
        ),
        TDACaseSpec(
            case_id="TDA-H",
            label="Complex Environment — PyTorch GPU",
            user_requirement="PyTorchでGPU推論を行うToolを作りたい。必要環境を調べて",
            force_research=True,
            url_html={pt_url: FIXTURE_PYTORCH, cuda_url: FIXTURE_TORCH_CUDA},
            mock_tool_calls=[
                {"name": "read_url_text", "arguments": {"url": pt_url}},
                {"name": "read_url_text", "arguments": {"url": cuda_url}},
            ],
            checks={"environment_keys": ["python", "cuda", "gpu"]},
        ),
    ]
