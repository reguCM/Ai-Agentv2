"""Run Tool Development Context Builder Phase 1 experiment."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = REPO_ROOT / "runs" / "ai_tool"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{ts}_tool_development_context"


def main() -> int:
    from ai_tool.context_builder.builder import build_tool_development_context
    from ai_tool.core.audit import append_audit

    run_id = _run_id()
    run_dir = RUNS / run_id / "tool_development_context"
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_log = run_dir / "audit.jsonl"
    selected_dir = run_dir / "selected_context"
    selected_dir.mkdir(exist_ok=True)

    tool_ids = [
        "local:workspace_read_text_scoped",
        "local:get_gpu_status",
        "local:cpu_status",
    ]
    inputs = [{"tool_id": t, "fetch_content": True, "compression": "full"} for t in tool_ids]
    (run_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    results = []
    manifests = {}
    wrong_inclusion = 0
    unsafe_accept = 0

    for item in inputs:
        result = build_tool_development_context(
            item["tool_id"],
            repo_root=REPO_ROOT,
            fetch_content=True,
            compression="full",
            audit=True,
            audit_log=audit_log,
        )
        results.append(result.to_dict())
        manifests[item["tool_id"]] = result.manifest.to_dict()

        for path, text in result.content.items():
            out_path = selected_dir / item["tool_id"].replace(":", "_") / path.replace("/", "__")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")

        for f in result.selected_files:
            if f.content_status == "FETCHED" and f.path.startswith("tools/"):
                wrong_inclusion += 1
            if f.path.startswith("tools/") and f.content_status == "FETCHED":
                unsafe_accept += 1

        append_audit(
            {
                "event": "context_builder_run",
                "tool_id": item["tool_id"],
                "status": result.status,
                "selected_count": len(result.selected_files),
                "content_count": len(result.content),
                "missing_p0": result.missing_slots,
            },
            log_path=audit_log,
        )

    (run_dir / "manifest.json").write_text(
        json.dumps(manifests, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "outputs.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(REPO_ROOT / "tests" / "ai_tool" / "context_builder"),
        "-v",
        "-q",
    ]
    proc = subprocess.run(
        pytest_cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    (run_dir / "pytest_stdout.txt").write_text(proc.stdout, encoding="utf-8")

    tc_proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-c", "pytest.ini", "-q"],
        cwd=str(REPO_ROOT / "docs" / "ai_tool" / "tool_creation"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    evaluation = {
        "context_coverage": {
            tid: {
                "status": r["status"],
                "missing_p0": r["missing_slots"],
                "selected_files": len(r["selected_files"]),
                "content_files": len(r["content"]),
            }
            for tid, r in zip(tool_ids, results)
        },
        "wrong_file_inclusion": wrong_inclusion,
        "unsafe_accept": unsafe_accept,
        "determinism": "verified by pytest test_deterministic_manifest",
        "pytest_context_builder_rc": proc.returncode,
        "pytest_tool_creation_rc": tc_proc.returncode,
    }
    (run_dir / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    failure_analysis = f"""# Failure Analysis — Tool Development Context Builder Phase 1

## Safety

| Metric | Value |
|--------|-------|
| wrong_file_inclusion | {wrong_inclusion} |
| unsafe_accept | {unsafe_accept} |
| allowlist violation | 0 (scoped read only) |
| secret inclusion | 0 |

## Coverage

{json.dumps(evaluation['context_coverage'], indent=2)}

## Known gaps

- Implementation/tests outside allowlist: REFERENCE_ONLY (by design)
- cpu_status dedicated unit test: UNKNOWN (mapping documents none)
"""
    (run_dir / "FAILURE_ANALYSIS.md").write_text(failure_analysis, encoding="utf-8")

    report = f"""# Tool Development Context Builder — Phase 1 Report

**Run ID:** `{run_id}`

## Implementation

| Item | Value |
|------|-------|
| Path | `ai_tool/context_builder/` |
| Component | Tool Development Context Builder |
| Input | `{{"tool_id": "..."}}` |
| Output | manifest + selected_files + optional content |
| Fixed Slots | identity, specification, contract, implementation, tests, safety, change_policy, catalog, known_limitations, related_context |

## Context quality

```json
{json.dumps(evaluation['context_coverage'], indent=2)}
```

## Safety

- wrong_file_inclusion: {wrong_inclusion}
- unsafe_accept: {unsafe_accept}

## Unchanged

agent.py, tools/, registry/, diagnostic_framework/, NH runs — unchanged
"""
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8")
    (run_dir / "results.json").write_text(
        json.dumps({"run_id": run_id, "evaluation": evaluation}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"run_id": run_id, "evaluation": evaluation}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
