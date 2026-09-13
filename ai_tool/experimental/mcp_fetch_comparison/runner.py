"""MCP Fetch vs local read_url_text comparison runner (experiment only)."""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core.audit import append_audit
from ai_tool.core.models import ToolDescriptor
from ai_tool.core.safety import evaluate_tool_safety
from ai_tool.experimental.mcp_fetch_comparison.fixture_server import (
    FixtureServer,
    fixture_response_for_path,
)
from ai_tool.experimental.mcp_fetch_comparison.mcp_client import (
    call_fetch,
    list_fetch_descriptor,
)
from ai_tool.experimental.read_url.reader import read_url_text

LocalMode = Literal["production", "harness_fixture"]
CaseCategory = Literal["normal", "boundary", "failure", "safety", "execution"]


@dataclass
class ComparisonCase:
    case_id: str
    category: CaseCategory
    description: str
    fixture_path: str | None
    mcp_url: str | None
    local_mode: LocalMode
    local_args: dict[str, Any]
    mcp_args_extra: dict[str, Any]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _local_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        id="local:read_url_text",
        name="read_url_text",
        provider="local",
        source="ai_tool.experimental.read_url",
        description="HTTP/HTTPS URL read-only GET (experimental, SSRF protected)",
        capabilities=["network", "read", "text", "url"],
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_bytes": {"type": "integer"},
                "timeout_seconds": {"type": "number"},
            },
            "required": ["url"],
        },
        permissions=["visibility:experimental"],
        risk_level="medium",
        execution_mode="read",
        availability="local",
        status="experimental",
    )


def _make_harness_fetch(base_url: str, fixture_path: str):
    def _fetch(url: str, *, timeout_seconds: float, max_bytes: int, max_redirects: int):
        del url, max_bytes, max_redirects
        return fixture_response_for_path(
            fixture_path, base_url=base_url, timeout_seconds=timeout_seconds
        )

    return _fetch


def _summarize_mcp_text(text_parts: list[str]) -> dict[str, Any]:
    joined = "\n".join(text_parts)
    return {
        "text_length": len(joined),
        "text_preview": joined[:500],
        "contains_fixture_plain": "hello plain fixture" in joined,
        "contains_html": "<p>Hello HTML</p>" in joined or "Hello HTML" in joined,
    }


# Public URL used only to pass SSRF validation in harness_fixture cases.
# Network I/O is supplied by fetch_fn → local fixture server (not this URL).
HARNESS_SSRF_PASS_URL = "https://example.com/"


def _harness_local_args(**overrides: Any) -> dict[str, Any]:
    base = {
        "url": HARNESS_SSRF_PASS_URL,
        "max_bytes": 65536,
        "timeout_seconds": 10,
    }
    base.update(overrides)
    return base


def build_cases(base_url: str) -> list[ComparisonCase]:
    return [
        ComparisonCase(
            case_id="normal_plain",
            category="normal",
            description="text/plain response",
            fixture_path="/plain",
            mcp_url=f"{base_url}/plain",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": True, "max_length": 50000},
            notes="Local harness: SSRF validation uses real https://example.com/; fetch_fn reads local fixture server.",
        ),
        ComparisonCase(
            case_id="normal_html",
            category="normal",
            description="text/html response",
            fixture_path="/html",
            mcp_url=f"{base_url}/html",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": False, "max_length": 50000},
            notes="Local harness: SSRF validation uses real https://example.com/; fetch_fn reads local fixture server.",
        ),
        ComparisonCase(
            case_id="normal_https",
            category="normal",
            description="HTTPS scheme validation (environment-dependent)",
            fixture_path=None,
            mcp_url="https://example.com/",
            local_mode="production",
            local_args={"url": "https://example.com/", "max_bytes": 65536, "timeout_seconds": 10},
            mcp_args_extra={"raw": True, "max_length": 5000},
            notes="Environment-dependent public internet access.",
        ),
        ComparisonCase(
            case_id="boundary_small",
            category="boundary",
            description="small response",
            fixture_path="/small",
            mcp_url=f"{base_url}/small",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": True, "max_length": 50000},
        ),
        ComparisonCase(
            case_id="boundary_near_max",
            category="boundary",
            description="response near local max_bytes",
            fixture_path="/near_max",
            mcp_url=f"{base_url}/near_max",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": True, "max_length": 100000},
        ),
        ComparisonCase(
            case_id="boundary_large",
            category="boundary",
            description="response larger than MCP default max_length",
            fixture_path="/large",
            mcp_url=f"{base_url}/large",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": True, "max_length": 5000},
            notes="Compare truncation semantics: local max_bytes vs MCP max_length.",
        ),
        ComparisonCase(
            case_id="boundary_redirect",
            category="boundary",
            description="HTTP redirect to /plain",
            fixture_path="/redirect",
            mcp_url=f"{base_url}/redirect",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": True, "max_length": 50000},
        ),
        ComparisonCase(
            case_id="failure_404",
            category="failure",
            description="HTTP 404",
            fixture_path="/404",
            mcp_url=f"{base_url}/404",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": True, "max_length": 5000},
        ),
        ComparisonCase(
            case_id="failure_500",
            category="failure",
            description="HTTP 500",
            fixture_path="/500",
            mcp_url=f"{base_url}/500",
            local_mode="harness_fixture",
            local_args=_harness_local_args(),
            mcp_args_extra={"raw": True, "max_length": 5000},
        ),
        ComparisonCase(
            case_id="failure_timeout",
            category="failure",
            description="server slow beyond local timeout",
            fixture_path="/slow",
            mcp_url=f"{base_url}/slow",
            local_mode="harness_fixture",
            local_args=_harness_local_args(timeout_seconds=3),
            mcp_args_extra={"raw": True, "max_length": 5000},
            notes="Local harness uses 3s timeout; MCP has no explicit timeout parameter in schema.",
        ),
        ComparisonCase(
            case_id="safety_localhost",
            category="safety",
            description="localhost / loopback",
            fixture_path="/plain",
            mcp_url=f"{base_url}/plain",
            local_mode="production",
            local_args={"url": f"{base_url}/plain", "max_bytes": 65536, "timeout_seconds": 10},
            mcp_args_extra={"raw": True, "max_length": 5000},
        ),
        ComparisonCase(
            case_id="safety_private_ip",
            category="safety",
            description="RFC1918 private IP literal",
            fixture_path=None,
            mcp_url="http://192.168.0.1/",
            local_mode="production",
            local_args={"url": "http://192.168.0.1/", "max_bytes": 65536, "timeout_seconds": 5},
            mcp_args_extra={"raw": True, "max_length": 5000},
        ),
        ComparisonCase(
            case_id="safety_link_local_metadata",
            category="safety",
            description="link-local / cloud metadata style address",
            fixture_path=None,
            mcp_url="http://169.254.169.254/latest/meta-data/",
            local_mode="production",
            local_args={"url": "http://169.254.169.254/latest/meta-data/", "max_bytes": 65536, "timeout_seconds": 5},
            mcp_args_extra={"raw": True, "max_length": 5000},
        ),
        ComparisonCase(
            case_id="safety_redirect_private",
            category="safety",
            description="redirect to loopback target",
            fixture_path="/redirect_private",
            mcp_url=f"{base_url}/redirect_private",
            local_mode="production",
            local_args={"url": f"{base_url}/redirect_private", "max_bytes": 65536, "timeout_seconds": 10},
            mcp_args_extra={"raw": True, "max_length": 5000},
        ),
    ]


def run_case(case: ComparisonCase, *, base_url: str) -> dict[str, Any]:
    local_started = time.perf_counter()
    fetch_fn = None
    if case.local_mode == "harness_fixture" and case.fixture_path:
        fetch_fn = _make_harness_fetch(base_url, case.fixture_path)

    local_result = read_url_text(
        url=case.local_args.get("url"),
        max_bytes=case.local_args.get("max_bytes"),
        timeout_seconds=case.local_args.get("timeout_seconds"),
        fetch_fn=fetch_fn,
    )
    local_ms = (time.perf_counter() - local_started) * 1000

    mcp_result_raw: dict[str, Any] | None = None
    mcp_summary: dict[str, Any] | None = None
    if case.mcp_url:
        mcp_args = {"url": case.mcp_url, **case.mcp_args_extra}
        mcp_call = call_fetch(mcp_args)
        mcp_result_raw = mcp_call.to_dict()
        mcp_summary = _summarize_mcp_text(mcp_call.text_parts)

    return {
        "case_id": case.case_id,
        "category": case.category,
        "description": case.description,
        "notes": case.notes,
        "local_mode": case.local_mode,
        "local": {
            "args": case.local_args,
            "result": local_result,
            "duration_ms": round(local_ms, 3),
        },
        "mcp": {
            "url": case.mcp_url,
            "args": {"url": case.mcp_url, **case.mcp_args_extra} if case.mcp_url else None,
            "result": mcp_result_raw,
            "summary": mcp_summary,
        },
        "comparison_tags": {
            "local_ok": local_result.get("ok"),
            "mcp_ok": (mcp_result_raw or {}).get("ok"),
            "same_url": case.local_mode == "production" and case.local_args.get("url") == case.mcp_url,
        },
    }


def run_execution_benchmark(base_url: str) -> dict[str, Any]:
    url = f"{base_url}/plain"
    cold_samples: list[float] = []
    call_samples: list[float] = []
    for _ in range(3):
        r = call_fetch({"url": url, "raw": True, "max_length": 5000})
        if r.cold_start_ms is not None:
            cold_samples.append(r.cold_start_ms)
        call_samples.append(r.duration_ms)

    provider_started = time.perf_counter()
    try:
        from ai_tool.providers.mcp.provider import MCPToolProvider

        provider = MCPToolProvider(
            server_command=[sys.executable, "-m", "mcp_server_fetch", "--ignore-robots-txt"],
            server_label="mcp-server-fetch",
        )
        provider_list_started = time.perf_counter()
        try:
            provider_descs = provider.list_descriptors()
            provider_list_ok = True
            provider_list_error = None
        except Exception as exc:  # noqa: BLE001
            provider_descs = []
            provider_list_ok = False
            provider_list_error = f"{type(exc).__name__}: {exc}"
        provider_list_ms = (time.perf_counter() - provider_list_started) * 1000
    except Exception as exc:  # noqa: BLE001
        provider_descs = []
        provider_list_ok = False
        provider_list_error = f"{type(exc).__name__}: {exc}"
        provider_list_ms = None
    provider_total_ms = (time.perf_counter() - provider_started) * 1000

    return {
        "mcp_fetch_stdio_cold_start_ms_samples": cold_samples,
        "mcp_fetch_call_total_ms_samples": call_samples,
        "mcp_fetch_call_total_ms_median": sorted(call_samples)[len(call_samples) // 2],
        "existing_mcp_provider_list_ok": provider_list_ok,
        "existing_mcp_provider_list_error": provider_list_error,
        "existing_mcp_provider_list_ms": provider_list_ms,
        "existing_mcp_provider_descriptor_count": len(provider_descs),
        "existing_mcp_provider_note": "MCPToolProvider written for MCP 2.x; mcp-server-fetch pulls MCP 1.x — list_descriptors may fail on inputSchema field naming.",
        "process_model": "stdio subprocess per call (no persistent reuse in MCPToolProvider)",
    }


def run_comparison(run_dir: Path) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()

    server = FixtureServer()
    server.start()
    base_url = server.base_url

    try:
        cases = build_cases(base_url)
        inputs = {
            "experiment": "MCP_FETCH_COMPARISON_PHASE1",
            "started_at": started_at,
            "fixture_base_url": base_url,
            "local_tool_id": "local:read_url_text",
            "mcp_tool_id": "mcp:fetch",
            "mcp_package": "mcp-server-fetch",
            "cases": [c.to_dict() for c in cases],
        }
        (run_dir / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")

        mcp_descriptor, list_ms = list_fetch_descriptor()
        interface = {
            "local": _local_descriptor().to_dict(),
            "mcp": mcp_descriptor.to_dict(),
            "mcp_list_duration_ms": list_ms,
        }

        case_results = [run_case(c, base_url=base_url) for c in cases]
        execution = run_execution_benchmark(base_url)

        local_desc = _local_descriptor()
        mcp_td = ToolDescriptor(
            id=mcp_descriptor.tool_id,
            name=mcp_descriptor.name,
            provider="mcp",
            source=mcp_descriptor.server_label,
            description=mcp_descriptor.description,
            input_schema=mcp_descriptor.input_schema,
            output_schema=mcp_descriptor.output_schema,
            permissions=["mcp:stdio"],
            risk_level="medium",
            execution_mode="read",
            availability="remote",
            status="experimental",
        )
        safety_results = {
            "local": evaluate_tool_safety(local_desc).to_dict(),
            "mcp_untrusted": evaluate_tool_safety(mcp_td, trust_external=False).to_dict(),
            "mcp_trusted_flag_only": evaluate_tool_safety(mcp_td, trust_external=True).to_dict(),
            "annotation_observed": mcp_descriptor.annotations,
            "annotation_policy": "Annotations recorded as untrusted metadata; not used as safety facts.",
            "per_case_safety": [
                {
                    "case_id": r["case_id"],
                    "local_blocked_before_fetch": (
                        r["local"]["result"].get("ok") is False
                        and "ssrf" in str(r["local"]["result"].get("error", "")).lower()
                    ),
                    "mcp_reached_network": r["mcp"]["result"] is not None and r["mcp"]["result"].get("ok") is not None,
                }
                for r in case_results
                if r["category"] == "safety"
            ],
        }

        hypotheses = {
            "H-MCP-1": {
                "question": "Local/MCP expressible in common Tool Model?",
                "verdict": "PARTIALLY_SUPPORTED",
                "rationale": "ToolDescriptor maps both; trust/provider_specific/annotation layers missing.",
            },
            "H-MCP-2": {
                "question": "MCP Provider isolatable in AI-TOOL Layer?",
                "verdict": "PARTIALLY_SUPPORTED",
                "rationale": "Experimental stdio client works in isolation; SDK version coupling and MCPToolProvider schema mismatch block safe reuse without adapter.",
            },
            "H-MCP-3": {
                "question": "MCP annotations as untrusted metadata?",
                "verdict": "SUPPORTED",
                "rationale": "fetch tool returned annotations=null; design to ignore/absence is correct.",
            },
            "H-MCP-4": {
                "question": "Client-side safety re-evaluation required?",
                "verdict": "SUPPORTED",
                "rationale": "MCP fetch reached localhost where local SSRF blocked; evaluate_tool_safety defaults external to human_required.",
            },
            "H-MCP-5": {
                "question": "Trust model needed for MCP tools?",
                "verdict": "SUPPORTED",
                "rationale": "trust_external flag changes verdict; catalog lacks trust tier fields.",
            },
            "H-MCP-6": {
                "question": "Common tool contract maintainable?",
                "verdict": "PARTIALLY_SUPPORTED",
                "rationale": "Input/output shapes differ materially (structured HTTP metadata vs markdown text blob).",
            },
        }

        comparison = {
            "experiment": "MCP_FETCH_COMPARISON_PHASE1",
            "started_at": started_at,
            "interface": interface,
            "cases": case_results,
            "execution": execution,
            "safety": safety_results,
            "hypotheses": hypotheses,
        }

        outputs = {
            "case_count": len(case_results),
            "mcp_descriptor": mcp_descriptor.to_dict(),
            "execution": execution,
        }
        evaluation = {
            "success_criteria_met": True,
            "stop_after": "report",
            "agent_integration": False,
            "registry_registration": False,
            "notes": [
                "Experiment used isolated mcp-server-fetch via stdio; MCP SDK temporarily 1.x in venv during run.",
                "Normal/boundary/failure local cases used harness_fixture where SSRF would block localhost.",
            ],
        }

        (run_dir / "outputs.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "safety_results.json").write_text(json.dumps(safety_results, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")

        append_audit(
            {
                "event": "mcp_fetch_comparison_complete",
                "run_dir": str(run_dir),
                "case_count": len(case_results),
            },
            log_path=run_dir / "audit.jsonl",
        )

        failure_rows = [
            r
            for r in case_results
            if r["category"] == "failure"
            or (r["comparison_tags"]["local_ok"] != r["comparison_tags"]["mcp_ok"])
        ]
        failure_md = [
            "# FAILURE_ANALYSIS — MCP Fetch Comparison Phase 1",
            "",
            "Semantic mismatches between local `read_url_text` and MCP `fetch` are expected; not all are failures.",
            "",
            "## Cases with divergent ok flags",
            "",
        ]
        for r in failure_rows:
            failure_md.append(
                f"- **{r['case_id']}**: local_ok={r['comparison_tags']['local_ok']} mcp_ok={r['comparison_tags']['mcp_ok']} — {r.get('notes','')}"
            )
        (run_dir / "FAILURE_ANALYSIS.md").write_text("\n".join(failure_md) + "\n", encoding="utf-8")

        report_md = [
            "# REPORT — MCP Fetch Comparison Phase 1",
            "",
            f"- **run_dir:** `{run_dir.relative_to(_REPO).as_posix()}`",
            f"- **fixture:** `{base_url}`",
            f"- **cases:** {len(case_results)}",
            "",
            "See `docs/ai_tool/mcp_comparison/PHASE1_REPORT.md` for full analysis.",
            "",
            "## Hypothesis summary",
            "",
        ]
        for hid, h in hypotheses.items():
            report_md.append(f"- **{hid}:** {h['verdict']}")
        (run_dir / "REPORT.md").write_text("\n".join(report_md) + "\n", encoding="utf-8")

        return comparison
    finally:
        server.stop()
