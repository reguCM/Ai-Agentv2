#!/usr/bin/env python3
"""Run Phase I-R-B — Preflight and checkpoints (WSL install requires approval flag)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.ur_program_validator.phase_i_r_b_harness import run_phase_i_r_b
from ai_tool.experimental.ur_program_validator.storage_policy import resolve_storage_root

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_ur_program_validator_phase_i_r_b"
RUN_DIR = resolve_storage_root(_REPO) / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wsl-approved",
        action="store_true",
        help="Set after user approved wsl --install (does not run install itself)",
    )
    args = parser.parse_args()

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_i_r_b(wsl_install_approved=args.wsl_approved, project_root=_REPO)
    result["run_id"] = RUN_ID

    (RUN_DIR / "preflight.json").write_text(
        json.dumps(result.get("preflight", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps({"decision": result.get("decision"), "checkpoints": result.get("checkpoints")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/experimental/test_ur_program_validator_phase_i_r_b.py", "-q", "--tb=no"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    result["pytest_exit"] = proc.returncode

    print(f"Phase I-R-B Decision: {result.get('decision')}")
    print(f"Preflight OK for WSL install: {result.get('preflight', {}).get('preflight_ok_for_wsl_install')}")
    print(f"WSL installed: {result.get('preflight', {}).get('wsl', {}).get('installed')}")
    print(f"Docker Engine up: {bool(result.get('preflight', {}).get('docker', {}).get('client_server', {}).get('server'))}")
    print(f"Run dir: {RUN_DIR}")
    if result.get("decision") == "PENDING_USER_APPROVAL":
        print("ACTION: User approval required before wsl --install")

    ok = result.get("decision") in (
        "PENDING_USER_APPROVAL",
        "CHECKPOINT_0_COMPLETE",
        "LIVE_URSIM_CONFIRMED",
        "LIVE_DEVELOPMENT_LOOP_CONFIRMED",
        "ENVIRONMENT_BLOCKED",
    )
    return 0 if ok and proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
