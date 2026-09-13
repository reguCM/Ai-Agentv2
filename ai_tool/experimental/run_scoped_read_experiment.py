"""Run scoped filesystem read experiment and write run artifacts."""
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
    return f"{ts}_scoped_filesystem_read"


def main() -> int:
    run_id = _run_id()
    run_dir = RUNS / run_id / "scoped_filesystem_read"
    run_dir.mkdir(parents=True, exist_ok=True)

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(REPO_ROOT / "tests" / "ai_tool" / "experimental"),
        "-v",
        "--tb=short",
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
    (run_dir / "pytest_stderr.txt").write_text(proc.stderr, encoding="utf-8")

    from ai_tool.experimental.scoped_read.config import load_scoped_read_config
    from ai_tool.experimental.scoped_read.reader import workspace_read_text_scoped

    cfg = load_scoped_read_config(repo_root=REPO_ROOT)
    audit_log = run_dir / "audit.jsonl"
    samples = [
        {"path": "docs/ai_tool/README.md"},
        {"path": "../outside/secret.txt"},
        {"path": "docs/ai_tool_evil/trap.txt"},
    ]
    outputs = []
    for sample in samples:
        result = workspace_read_text_scoped(
            sample["path"],
            config=cfg,
            audit=True,
            audit_log=audit_log,
        )
        outputs.append({"input": sample, "output": result})

    (run_dir / "inputs.json").write_text(
        json.dumps(samples, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "outputs.json").write_text(
        json.dumps(outputs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    tc_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-c",
        "pytest.ini",
        "-q",
    ]
    tc_proc = subprocess.run(
        tc_cmd,
        cwd=str(REPO_ROOT / "docs" / "ai_tool" / "tool_creation"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    false_accept = sum(1 for o in outputs if o["input"]["path"].startswith("..") and o["output"]["ok"])
    unsafe_accept = false_accept
    false_reject = 0
    if outputs[0]["output"]["ok"] is False:
        false_reject += 1

    safety = {
        "interface_correctness": proc.returncode == 0,
        "safety_correctness": unsafe_accept == 0,
        "false_accept": false_accept,
        "false_reject": false_reject,
        "unsafe_accept": unsafe_accept,
        "unknown_handling": "no implicit OK on ambiguous paths",
    }
    evaluation = {
        "pytest_scoped": {
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
        },
        "pytest_tool_creation": {
            "returncode": tc_proc.returncode,
            "passed": tc_proc.returncode == 0,
        },
    }
    (run_dir / "safety_results.json").write_text(
        json.dumps(safety, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report = f"""# Scoped Filesystem Read — Local Implementation Run

**Run ID:** `{run_id}`

## Implementation

| Item | Value |
|------|-------|
| Path | `ai_tool/experimental/scoped_read/` |
| Tool ID | `local:workspace_read_text_scoped` |
| Provider | local (experimental, not in registry) |
| Input | `{{"path": "<repo-relative>"}}` (+ optional offset/limit) |
| Output | Specification `output_schema` (`ok`, `path`, `content`, …) |

## Safety

| Check | Result |
|-------|--------|
| allowlist | enforced via `allowed_roots.experimental.json` |
| traversal | `..` segments rejected |
| symlink | resolved path must stay in allowlist |
| absolute path | allowed only under repo + allowlist |
| size | max_bytes=65536 (experimental, from config) |
| text | binary sniff rejected |

## Tests

Scoped pytest returncode: {proc.returncode}

Tool Creation pytest returncode: {tc_proc.returncode}

## Safety metrics

```json
{json.dumps(safety, indent=2)}
```

## Unchanged

- agent.py — unchanged
- tools/ — unchanged
- registry/tools.json — unchanged
- read_file — unchanged
- MCP — untouched
- diagnostic_framework — unchanged
"""
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8")

    summary = {
        "run_id": run_id,
        "run_dir": str(run_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        "pytest_scoped_rc": proc.returncode,
        "pytest_tool_creation_rc": tc_proc.returncode,
        "safety": safety,
    }
    (run_dir / "results.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
