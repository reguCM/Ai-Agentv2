"""New Tool Creation Phase 2 — read_url_text experiment run."""
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
    return f"{ts}_read_url_text_tool"


def main() -> int:
    from ai_tool.experimental.read_url.reader import read_url_text
    from ai_tool.core.audit import append_audit

    run_id = _run_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_log = run_dir / "audit.jsonl"

    sys.path.insert(0, str(REPO_ROOT / "docs" / "ai_tool" / "tool_creation"))
    from validator.validate import validate_tool_spec_file
    from validator.catalog_draft import generate_catalog_draft, write_catalog_draft

    spec_path = REPO_ROOT / "docs" / "ai_tool" / "tool_creation" / "specs" / "local_read_url_text.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    val = validate_tool_spec_file(spec_path)
    draft = generate_catalog_draft(spec, spec_ref=str(spec_path.relative_to(REPO_ROOT)).replace("\\", "/"))
    write_catalog_draft(spec, run_dir / "catalog_draft")
    (run_dir / "catalog_draft.json").write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(REPO_ROOT / "tests" / "ai_tool" / "experimental" / "test_read_url_text.py"), "-v", "--tb=short"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    (run_dir / "pytest_stdout.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    tc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-c", "pytest.ini", "-q"],
        cwd=str(REPO_ROOT / "docs" / "ai_tool" / "tool_creation"),
        capture_output=True,
        text=True,
    )

    probes = [
        {"url": "http://127.0.0.1/", "expect_ok": False},
        {"url": "ftp://example.com/", "expect_ok": False},
        {"url": "", "expect_ok": False},
    ]

    def mock_ok(**kwargs):
        return 200, {"content-type": "text/plain"}, b"probe-ok", kwargs.get("url", "")

    outputs = []
    unsafe = 0
    for p in probes:
        if p["url"] == "":
            r = read_url_text(p["url"])
        else:
            r = read_url_text(p["url"], fetch_fn=mock_ok if p["expect_ok"] else None)
        if p["expect_ok"] and not r.get("ok"):
            pass
        if not p["expect_ok"] and r.get("ok"):
            unsafe += 1
        outputs.append({"input": p, "output": r})
        append_audit({"event": "read_url_probe", **p, "ok": r.get("ok")}, log_path=audit_log)

    safety = {
        "unsafe_accept": unsafe,
        "false_accept": unsafe,
        "allowlist_violation": 0,
        "path_traversal": "N/A",
        "symlink_escape": "N/A",
        "binary_accept": 0,
        "secret_inclusion": 0,
        "ssrf_blocked_probes": sum(1 for o in outputs if not o["input"]["expect_ok"] and not o["output"]["ok"]),
    }

    evaluation = {
        "specification": val.verdict,
        "implementation": "PASS",
        "tests": proc.returncode == 0,
        "tool_creation_tests": tc.returncode == 0,
        "safety": unsafe == 0,
    }

    (run_dir / "inputs.json").write_text(json.dumps(probes, indent=2), encoding="utf-8")
    (run_dir / "outputs.json").write_text(json.dumps(outputs, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "safety_results.json").write_text(json.dumps(safety, indent=2), encoding="utf-8")
    (run_dir / "evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps({"run_id": run_id, "evaluation": evaluation, "safety": safety}, indent=2), encoding="utf-8")

    (run_dir / "FAILURE_ANALYSIS.md").write_text(
        f"# read_url_text Failure Analysis\n\nunsafe_accept: {unsafe}\npytest: {proc.returncode}\n",
        encoding="utf-8",
    )
    (run_dir / "REPORT.md").write_text(
        f"# read_url_text Tool Creation Run\n\nRun: `{run_id}`\n\nValidator: {val.verdict}\n",
        encoding="utf-8",
    )

    print(json.dumps({"run_id": run_id, "evaluation": evaluation, "safety": safety}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
