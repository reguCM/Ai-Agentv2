"""Run real-web smoke tests for local:read_url_text and record results (experimental)."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core.audit import append_audit
from ai_tool.experimental.read_url.reader import read_url_text
from ai_tool.experimental.read_url.smoke_targets import REAL_WEB_SMOKE_TARGETS, RealWebSmokeTarget


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content") or ""
    return {
        "ok": result.get("ok"),
        "url": result.get("url"),
        "final_url": result.get("final_url"),
        "status_code": result.get("status_code"),
        "content_type": result.get("content_type"),
        "size_bytes": result.get("size_bytes"),
        "truncated": result.get("truncated"),
        "error": result.get("error"),
        "content_length": len(content),
        "content_preview": content[:120] if content else "",
    }


def _classify_outcome(result: dict[str, Any], *, content_kind: str) -> str:
    if not result.get("ok"):
        err = str(result.get("error") or "")
        if "timeout" in err or "connection failure" in err:
            return "network_indeterminate"
        return "failed"
    content = result.get("content") or ""
    if not content:
        return "failed"
    ctype = (result.get("content_type") or "").lower()
    if content_kind == "html" and "html" not in ctype and "<" not in content[:200]:
        return "unexpected_format"
    if content_kind == "plain" and "plain" not in ctype and "text/" not in ctype:
        return "unexpected_format"
    return "passed"


def run_smoke_case(
    target: RealWebSmokeTarget,
    *,
    max_bytes: int | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    result = read_url_text(
        target.url,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    summary = _summarize_result(result)
    outcome = _classify_outcome(result, content_kind=target.content_kind)
    return {
        "case_id": target.case_id,
        "target": target.to_dict(),
        "args": {
            "url": target.url,
            "max_bytes": max_bytes,
            "timeout_seconds": timeout_seconds,
        },
        "outcome": outcome,
        "duration_ms": round(duration_ms, 3),
        "result_summary": summary,
        "network_dependent": True,
    }


def run_smoke_suite(run_dir: Path) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()

    cases: list[dict[str, Any]] = []
    for target in REAL_WEB_SMOKE_TARGETS:
        cases.append(run_smoke_case(target))

    # max_bytes / timeout behavior on a real page (no golden body comparison)
    max_bytes_case = run_smoke_case(
        REAL_WEB_SMOKE_TARGETS[0],
        max_bytes=256,
        timeout_seconds=15,
    )
    max_bytes_case["case_id"] = "smoke_max_bytes_applied"
    max_bytes_case["note"] = "max_bytes=256 on https://example.com/"
    cases.append(max_bytes_case)

    passed = sum(1 for c in cases if c["outcome"] == "passed")
    indeterminate = sum(1 for c in cases if c["outcome"] == "network_indeterminate")
    failed = len(cases) - passed - indeterminate

    suite = {
        "experiment": "read_url_text_real_web_smoke",
        "tool_id": "local:read_url_text",
        "tool_status": "experimental",
        "started_at": started_at,
        "test_class": "real_web_smoke",
        "deterministic_tests_separate": True,
        "targets": [t.to_dict() for t in REAL_WEB_SMOKE_TARGETS],
        "cases": cases,
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": failed,
            "network_indeterminate": indeterminate,
            "deterministic_gate": "not_applicable",
        },
    }

    (run_dir / "inputs.json").write_text(
        json.dumps({"targets": suite["targets"], "started_at": started_at}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "outputs.json").write_text(
        json.dumps({"cases": cases, "summary": suite["summary"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "smoke_results.json").write_text(json.dumps(suite, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "evaluation.json").write_text(
        json.dumps(
            {
                "success_criteria_met": failed == 0,
                "real_web_smoke_passed": passed,
                "network_indeterminate": indeterminate,
                "agent_integration": False,
                "registry_registration": False,
                "tool_status": "experimental",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    append_audit(
        {"event": "read_url_smoke_complete", "run_dir": str(run_dir), "passed": passed, "failed": failed},
        log_path=run_dir / "audit.jsonl",
    )
    report = [
        "# Real Web Smoke Test — local:read_url_text",
        "",
        f"- **started_at:** {started_at}",
        f"- **passed:** {passed}",
        f"- **failed:** {failed}",
        f"- **network_indeterminate:** {indeterminate}",
        "",
        "Deterministic fixture/mock tests are separate; this run is network-dependent.",
        "",
        "## Cases",
        "",
    ]
    for c in cases:
        s = c["result_summary"]
        report.append(
            f"- **{c['case_id']}** `{c['target']['url']}` → {c['outcome']} "
            f"(status={s.get('status_code')}, size={s.get('size_bytes')}, ms={c['duration_ms']})"
        )
    (run_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return suite
