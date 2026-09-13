"""Run Tool Development Context Builder Phase 2 — External Help Package experiment."""
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
    return f"{ts}_tool_development_context_phase2"


def main() -> int:
    from ai_tool.context_builder.package_generator import build_external_help_package
    from ai_tool.core.audit import append_audit

    run_id = _run_id()
    run_dir = RUNS / run_id / "tool_development_context"
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_log = run_dir / "audit.jsonl"

    tool_ids = [
        "local:workspace_read_text_scoped",
        "local:get_gpu_status",
        "local:cpu_status",
    ]
    inputs = [{"tool_id": t} for t in tool_ids]
    (run_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    packages = []
    wrong_inclusion = 0
    for item in inputs:
        out = run_dir / "packages" / item["tool_id"].replace(":", "_")
        pkg_result = build_external_help_package(
            item["tool_id"],
            out,
            repo_root=REPO_ROOT,
            audit=True,
            audit_log=audit_log,
        )
        packages.append(pkg_result.to_dict())

        manifest_path = out / "external_help_package" / "CONTEXT_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for p in manifest.get("content_paths") or []:
            if p.startswith("tools/"):
                wrong_inclusion += 1

        append_audit(
            {
                "event": "external_help_package_built",
                "tool_id": item["tool_id"],
                "readiness": pkg_result.readiness,
                "package_dir": pkg_result.package_dir,
            },
            log_path=audit_log,
        )

    (run_dir / "manifest.json").write_text(
        json.dumps({p["tool_id"]: p for p in packages}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(REPO_ROOT / "tests" / "ai_tool" / "context_builder"),
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

    evaluation = {
        "packages_built": len(packages),
        "all_ready": all(p["readiness"] == "READY" for p in packages),
        "wrong_file_inclusion": wrong_inclusion,
        "unsafe_accept": wrong_inclusion,
        "pytest_rc": proc.returncode,
    }
    (run_dir / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    (run_dir / "FAILURE_ANALYSIS.md").write_text(
        f"""# Phase 2 Failure Analysis

| Metric | Value |
|--------|-------|
| wrong_file_inclusion | {wrong_inclusion} |
| packages READY | {sum(1 for p in packages if p['readiness'] == 'READY')} |
| pytest | {proc.returncode} |

## Example package paths

{chr(10).join('- ' + p['package_dir'] for p in packages)}
""",
        encoding="utf-8",
    )

    (run_dir / "REPORT.md").write_text(
        f"""# Tool Development Context Builder — Phase 2 Report

**Run ID:** `{run_id}`

## External Help Package

- Generator: `ai_tool/context_builder/package_generator.py`
- Spec: `docs/ai_tool/context_builder/EXTERNAL_HELP_PACKAGE_SPEC.md`
- Tools: {', '.join(tool_ids)}

## Evaluation

```json
{json.dumps(evaluation, indent=2)}
```

## STOP

No Agent / LLM / Registry integration.
""",
        encoding="utf-8",
    )

    print(json.dumps({"run_id": run_id, "evaluation": evaluation}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
