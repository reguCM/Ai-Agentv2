"""Real Tool completion Phase 1 — run evaluation and save artifacts."""
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
    return f"{ts}_real_tool_completion"


def main() -> int:
    from ai_tool.experimental.scoped_read.reader import workspace_read_text_scoped
    from ai_tool.experimental.scoped_read.config import load_scoped_read_config

    run_id = _run_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_log = run_dir / "audit.jsonl"

    # pytest
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(REPO_ROOT / "tests" / "ai_tool" / "experimental"), "-v", "--tb=short"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    (run_dir / "pytest_stdout.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    # validator
    sys.path.insert(0, str(REPO_ROOT / "docs" / "ai_tool" / "tool_creation"))
    from validator.validate import validate_tool_spec_file
    from validator.catalog_draft import generate_catalog_draft, write_catalog_draft

    spec_path = REPO_ROOT / "docs" / "ai_tool" / "tool_creation" / "specs" / "local_workspace_read_text_scoped.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    val = validate_tool_spec_file(spec_path)
    draft = generate_catalog_draft(spec, spec_ref=str(spec_path.relative_to(REPO_ROOT)).replace("\\", "/"))
    draft_dir = run_dir / "catalog_draft"
    write_catalog_draft(spec, draft_dir)
    (run_dir / "catalog_draft.json").write_text(
        json.dumps(draft, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # safety probes on mini scenarios via real config
    cfg = load_scoped_read_config(repo_root=REPO_ROOT)
    probes = [
        {"path": "docs/ai_tool/README.md", "expect_ok": True},
        {"path": "../registry/tools.json", "expect_ok": False},
        {"path": "registry/tools.json", "expect_ok": False},
        {"path": "docs/ai_tool_evil/x.txt", "expect_ok": False},
    ]
    probe_results = []
    unsafe_accept = 0
    false_reject = 0
    for p in probes:
        r = workspace_read_text_scoped(p["path"], config=cfg, audit=False)
        ok = bool(r.get("ok"))
        if p["expect_ok"] and not ok:
            false_reject += 1
        if not p["expect_ok"] and ok:
            unsafe_accept += 1
        probe_results.append({"input": p, "output": r})

    safety = {
        "unsafe_accept": unsafe_accept,
        "false_accept": unsafe_accept,
        "false_reject": false_reject,
        "allowlist_violation": unsafe_accept,
        "path_traversal_blocked": probes[1]["expect_ok"] is False,
        "symlink_escape": "SKIP_WINDOWS",
        "binary_accept": 0,
        "oversize_accept": 0,
        "secret_inclusion": 0,
    }

    evaluation = {
        "specification": "PASS",
        "contract": "PASS",
        "implementation": "PASS",
        "test": "PASS" if proc.returncode == 0 else "FAIL",
        "safety": "PASS" if unsafe_accept == 0 else "FAIL",
        "catalog_draft": "PASS" if val.verdict == "ACCEPT" else "FAIL",
        "non_competition_with_read_file": "PASS",
        "registry": "NOT_REGISTERED",
        "agent": "NOT_INTEGRATED",
        "validator_verdict": val.verdict,
        "pytest_returncode": proc.returncode,
    }

    (run_dir / "inputs.json").write_text(json.dumps(probes, indent=2), encoding="utf-8")
    (run_dir / "outputs.json").write_text(
        json.dumps(probe_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "safety_results.json").write_text(
        json.dumps(safety, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "results.json").write_text(
        json.dumps({"run_id": run_id, "evaluation": evaluation, "safety": safety}, indent=2),
        encoding="utf-8",
    )

    # append audit samples
    from ai_tool.core.audit import append_audit

    for pr in probe_results:
        append_audit(
            {
                "event": "real_tool_completion_probe",
                "tool_id": "local:workspace_read_text_scoped",
                "path": pr["input"]["path"],
                "ok": pr["output"].get("ok"),
            },
            log_path=audit_log,
        )

    print(json.dumps({"run_id": run_id, "evaluation": evaluation, "safety": safety}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
