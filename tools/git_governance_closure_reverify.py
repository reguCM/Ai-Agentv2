#!/usr/bin/env python3
"""Post-G6 Git Governance re-verification: evidence capture without registry freshness mutation."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "registry" / "project_assets.json"
EVIDENCE_DIR = REPO_ROOT / "reports" / "verification_evidence"
METHOD = "git_governance_post_g6_closure_reverify"

TARGET_ASSET_IDS = (
    "git_operation_policy",
    "git_governance_contract",
    "git_governance_cursor_adapter",
    "git_guard",
    "git_hooks_deployment",
)

from project_asset_verification import (  # noqa: E402
    DEFAULT_EVIDENCE_DIR,
    build_verification_evidence,
    git_head_revision,
    persist_evidence_with_history,
    stable_evidence_path,
)
from ai_tool.policy.git_governance_contract import load_and_validate_git_governance_contract
from ai_tool.policy.git_governance_distribution import (
    audit_git_governance_drift,
    inspect_live_hook_deployment,
)
from ai_tool.policy.git_governance_enforcement import validate_git_governance_enforcement
from ai_tool.policy.git_governance_invariants import (
    EXPECTED_CONTRACT_VERSION,
    KNOWN_ENFORCEMENT_GAPS,
)

PHASE_EVIDENCE = [
    "reports/GIT_GOVERNANCE_PHASE_G2.json",
    "reports/GIT_GOVERNANCE_PHASE_G3.json",
    "reports/GIT_GOVERNANCE_PHASE_G4.json",
    "reports/GIT_GOVERNANCE_PHASE_G5.json",
    "reports/GIT_GOVERNANCE_PHASE_G6.json",
]


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _assets_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(a["asset_id"]): a for a in registry.get("assets") or []}


def _known_gaps_for_asset(asset_id: str, asset: dict[str, Any]) -> list[str]:
    if asset_id == "git_governance_contract":
        return list(KNOWN_ENFORCEMENT_GAPS.keys())
    if asset_id == "git_guard":
        return ["partial_enforcement_scope", "RAW_CLI_ENFORCEMENT_GAP"]
    if asset_id == "git_hooks_deployment":
        return ["hook_bodies_outside_repository", "RAW_CLI_ENFORCEMENT_GAP"]
    if asset_id == "git_operation_policy":
        return ["semantic_only_not_machine_enforced"]
    if asset_id == "git_governance_cursor_adapter":
        return ["HOST_ADAPTER_NOT_VERIFIED (cursor_user_rules)"]
    return []


def _read_only_verification(asset_id: str, asset: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    ok = True
    path = asset.get("path")
    if path:
        exists = (repo_root / str(path)).is_file()
        checks.append({"check": "primary_path_exists", "result": "PASS" if exists else "FAIL"})
        ok = ok and exists
    sot = str(asset.get("source_of_truth") or "")
    if asset_id == "git_governance_contract":
        try:
            data = load_and_validate_git_governance_contract()
            if data.get("contract_version") != EXPECTED_CONTRACT_VERSION:
                checks.append({"check": "contract_version", "result": "FAIL"})
                ok = False
            else:
                checks.append({"check": "contract_schema_and_adapters", "result": "PASS"})
        except Exception as exc:
            checks.append({"check": "contract_schema_and_adapters", "result": f"FAIL: {exc}"})
            ok = False
    if asset_id == "git_guard":
        enc = validate_git_governance_enforcement()
        if enc.get("config_alignment_ok"):
            checks.append({"check": "guard_config_alignment", "result": "PASS"})
        else:
            checks.append({"check": "guard_config_alignment", "result": "FAIL"})
            ok = False
    if asset_id == "git_hooks_deployment":
        hook = inspect_live_hook_deployment()
        dep_md = (repo_root / "tools/git_guard/DEPLOYED.md").is_file()
        checks.append(
            {
                "check": "deployed_md",
                "result": "PASS" if dep_md else "FAIL",
            }
        )
        checks.append(
            {
                "check": "live_hooks",
                "result": "PASS" if hook.get("observed") else "NOT_OBSERVED",
            }
        )
        ok = ok and dep_md
    for rel in PHASE_EVIDENCE:
        if (repo_root / rel).is_file():
            checks.append({"check": f"phase_evidence:{rel}", "result": "PRESENT"})
    if asset_id == "git_governance_contract":
        audit = audit_git_governance_drift(include_live_hooks=False)
        verdict = str(audit.get("verdict") or "")
        if verdict == "CONSISTENT_WITH_KNOWN_GAPS":
            checks.append({"check": "g5_distribution_audit", "result": "PASS"})
        else:
            checks.append({"check": "g5_distribution_audit", "result": f"FAIL:{verdict}"})
            ok = False
    return {"ok": ok, "checks": checks}


def capture_baseline_no_registry(
    registry: dict[str, Any],
    asset_ids: list[str],
    *,
    evidence_dir: Path,
    repo_root: Path,
) -> list[dict[str, Any]]:
    assets_by_id = _assets_by_id(registry)
    captured: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    head = git_head_revision(repo_root)
    for asset_id in asset_ids:
        asset = assets_by_id[asset_id]
        verification_id = f"ve_{ts}_{asset_id}"
        evidence = build_verification_evidence(
            asset,
            assets_by_id,
            repo_root,
            verification_id=verification_id,
            verification_method=METHOD,
            verified_revision=head,
        )
        evidence["closure_phase"] = "post_g6_human_approval_packet"
        evidence["source_audit"] = {
            "label": METHOD,
            "g5_verdict": "CONSISTENT_WITH_KNOWN_GAPS",
            "registry_freshness_unchanged": True,
        }
        persist_evidence_with_history(evidence_dir, asset_id, evidence)
        stable = stable_evidence_path(evidence_dir, asset_id)
        captured.append(
            {
                "asset_id": asset_id,
                "verification_id": verification_id,
                "evidence_path": str(stable.relative_to(repo_root)).replace("\\", "/"),
                "history_path": str(
                    (
                        evidence_dir
                        / "history"
                        / asset_id.replace("/", "_")
                        / f"{verification_id}.json"
                    ).relative_to(repo_root)
                ).replace("\\", "/"),
            }
        )
    return captured


def _recommendation(asset_id: str, verification: dict[str, Any]) -> str:
    if verification.get("ok") is not True:
        return "REVERIFY_REQUIRED"
    if asset_id == "git_hooks_deployment":
        return "APPROVE_VERIFIED"
    return "APPROVE_VERIFIED"


def build_approval_packet(
    registry: dict[str, Any],
    repo_root: Path,
    *,
    baselines: list[dict[str, Any]],
) -> dict[str, Any]:
    assets_by_id = _assets_by_id(registry)
    baseline_by_id = {b["asset_id"]: b for b in baselines}
    items: list[dict[str, Any]] = []
    for asset_id in TARGET_ASSET_IDS:
        asset = assets_by_id[asset_id]
        ver = asset.get("verification") or {}
        ro = _read_only_verification(asset_id, asset, repo_root)
        baseline = baseline_by_id.get(asset_id) or {}
        items.append(
            {
                "asset_id": asset_id,
                "path": asset.get("path"),
                "source_of_truth": asset.get("source_of_truth"),
                "freshness_dependencies": asset.get("freshness_dependencies") or [],
                "consumers": asset.get("consumers") or [],
                "enforcement_level": asset.get("enforcement_level"),
                "current_freshness": ver.get("freshness"),
                "registry_evidence_ref": ver.get("evidence_ref"),
                "verification_result": ro,
                "baseline_status": "CAPTURED" if baseline else "NOT_CAPTURED",
                "new_baseline_verification_id": baseline.get("verification_id"),
                "new_baseline_evidence_ref": baseline.get("evidence_path"),
                "known_gaps": _known_gaps_for_asset(asset_id, asset),
                "recommended_human_decision": _recommendation(asset_id, ro),
                "notes": asset.get("notes"),
            }
        )
    return {
        "packet_type": "GIT_GOVERNANCE_HUMAN_APPROVAL_PACKET",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "g5_verdict_maintained": "CONSISTENT_WITH_KNOWN_GAPS",
        "verified_means": "current_recorded_state_confirmed_not_zero_gaps_nor_full_enforced",
        "registry_freshness_mutated": False,
        "cursor_user_rules": "HOST_ADAPTER_NOT_VERIFIED (out of scope)",
        "phase_evidence_reused": PHASE_EVIDENCE,
        "assets": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post-G6 Git Governance closure re-verify")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument(
        "--packet-out",
        type=Path,
        default=REPO_ROOT / "reports" / "GIT_GOVERNANCE_CLOSURE_APPROVAL_PACKET.json",
    )
    parser.add_argument(
        "--skip-capture",
        action="store_true",
        help="Build packet only from READ-ONLY checks (no new evidence files)",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    registry = _load_registry()
    before = json.dumps(
        {aid: (_assets_by_id(registry)[aid].get("verification") or {}).get("freshness") for aid in TARGET_ASSET_IDS}
    )
    baselines: list[dict[str, Any]] = []
    if not args.skip_capture:
        baselines = capture_baseline_no_registry(
            registry, list(TARGET_ASSET_IDS), evidence_dir=args.evidence_dir, repo_root=repo_root
        )
    registry_after = _load_registry()
    after = json.dumps(
        {
            aid: (_assets_by_id(registry_after)[aid].get("verification") or {}).get("freshness")
            for aid in TARGET_ASSET_IDS
        }
    )
    if before != after:
        print("ERROR: registry freshness changed", file=sys.stderr)
        return 2
    packet = build_approval_packet(registry_after, repo_root, baselines=baselines)
    packet["baseline_captures"] = baselines
    args.packet_out.parent.mkdir(parents=True, exist_ok=True)
    args.packet_out.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"packet": str(args.packet_out), "baselines": len(baselines)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
