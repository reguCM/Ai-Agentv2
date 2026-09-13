"""Git Governance Phase G5 — distribution and drift regression."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ai_tool.policy.git_governance_contract import (
    load_and_validate_git_governance_contract,
    load_git_governance_contract,
    validate_git_governance_adapters,
)
from ai_tool.policy.git_governance_enforcement import (
    build_enforcement_matrix,
    hook_deployment_status,
    validate_git_governance_enforcement,
)
from ai_tool.policy.git_governance_invariants import (
    EXPECTED_CONTRACT_VERSION,
    KNOWN_ENFORCEMENT_GAPS,
    SEMANTIC_INVARIANTS,
    SEMANTIC_POLICY_ANCHORS,
)
from ai_tool.policy.loader import load_development_policy
from ai_tool.policy.paths import git_governance_json_path, policy_json_path

REPO_ROOT = git_governance_json_path().resolve().parents[2]

DRIFT_KINDS = frozenset(
    {
        "CONTRACT_SCHEMA_DRIFT",
        "SEMANTIC_POLICY_DRIFT",
        "ADAPTER_REFERENCE_DRIFT",
        "MANIFEST_DISTRIBUTION_DRIFT",
        "GUARD_CONFIG_DRIFT",
        "HOOK_DEPLOYMENT_DRIFT",
        "ENFORCEMENT_CLASS_DRIFT",
        "CONTRACT_VERSION_DRIFT",
        "HOST_ADAPTER_NOT_VERIFIED",
        "KNOWN_GAP_REGISTRY_DRIFT",
    }
)

VERDICTS = frozenset(
    {"CONSISTENT", "CONSISTENT_WITH_KNOWN_GAPS", "DRIFT_FOUND", "NOT_VERIFIED"}
)

SHARED_HOOK_PRE_COMMIT = Path(r"D:\AI-Agent\.git\hooks\pre-commit")
SHARED_HOOK_PRE_PUSH = Path(r"D:\AI-Agent\.git\hooks\pre-push")


class GitGovernanceDriftError(RuntimeError):
    """Drift or distribution validation failed."""


def validate_semantic_invariants(contract: dict[str, Any] | None = None) -> dict[str, Any]:
    data = contract or load_git_governance_contract()
    mapping = {
        str(a.get("action_id")): str(a.get("approval_class"))
        for a in data.get("actions") or []
        if isinstance(a, dict) and a.get("action_id")
    }
    violations: list[dict[str, str]] = []
    for action_id, expected in SEMANTIC_INVARIANTS.items():
        actual = mapping.get(action_id)
        if actual != expected:
            violations.append(
                {
                    "action_id": action_id,
                    "expected": expected,
                    "actual": actual or "MISSING",
                    "drift_kind": "ENFORCEMENT_CLASS_DRIFT",
                }
            )
    return {
        "ok": not violations,
        "violations": violations,
    }


def validate_contract_version(contract: dict[str, Any] | None = None) -> dict[str, Any]:
    data = contract or load_git_governance_contract()
    version = str(data.get("contract_version") or "")
    ok = version == EXPECTED_CONTRACT_VERSION
    return {
        "ok": ok,
        "expected": EXPECTED_CONTRACT_VERSION,
        "actual": version,
        "drift_kind": "CONTRACT_VERSION_DRIFT" if not ok else None,
    }


def validate_semantic_policy_reference() -> dict[str, Any]:
    git_path = REPO_ROOT / "docs" / "GIT_OPERATION_POLICY.md"
    if not git_path.is_file():
        return {
            "ok": False,
            "drift_kind": "SEMANTIC_POLICY_DRIFT",
            "detail": "GIT_OPERATION_POLICY.md missing",
        }
    text = git_path.read_text(encoding="utf-8")
    missing = [a for a in SEMANTIC_POLICY_ANCHORS if a not in text]
    return {
        "ok": not missing,
        "anchors_checked": list(SEMANTIC_POLICY_ANCHORS),
        "missing_anchors": missing,
        "drift_kind": "SEMANTIC_POLICY_DRIFT" if missing else None,
    }


def validate_manifest_distribution() -> dict[str, Any]:
    manifest = load_development_policy()
    dist = manifest.get("distribution") or {}
    issues: list[dict[str, str]] = []

    canonical = [str(p) for p in dist.get("canonical_files") or []]
    if "docs/GIT_OPERATION_POLICY.md" not in canonical:
        issues.append(
            {
                "field": "canonical_files",
                "detail": "docs/GIT_OPERATION_POLICY.md missing",
                "drift_kind": "MANIFEST_DISTRIBUTION_DRIFT",
            }
        )
    ref = dist.get("git_governance_ref") or {}
    contract_path = str(ref.get("contract_path") or "")
    expected = "ai_tool/policy/git_governance.json"
    if contract_path != expected:
        issues.append(
            {
                "field": "git_governance_ref.contract_path",
                "detail": f"expected {expected}, got {contract_path}",
                "drift_kind": "MANIFEST_DISTRIBUTION_DRIFT",
            }
        )
    contract_file = REPO_ROOT / contract_path if contract_path else None
    if contract_file and not contract_file.is_file():
        issues.append(
            {
                "field": "git_governance_ref",
                "detail": "contract file missing",
                "drift_kind": "MANIFEST_DISTRIBUTION_DRIFT",
            }
        )
    refs_in_manifest = [contract_path] if contract_path else []
    if canonical.count(expected) > 0 and contract_path:
        pass
    dup_conflict = len(set(refs_in_manifest)) != len(refs_in_manifest)
    if dup_conflict:
        issues.append(
            {
                "field": "git_governance_ref",
                "detail": "duplicate conflicting ref",
                "drift_kind": "MANIFEST_DISTRIBUTION_DRIFT",
            }
        )

    for consumer, cfg in (dist.get("consumers") or {}).items():
        if not isinstance(cfg, dict):
            continue
        refs = cfg.get("required_references") or []
        if consumer in ("codex", "cursor") and expected not in refs:
            issues.append(
                {
                    "field": f"consumers.{consumer}.required_references",
                    "detail": f"missing {expected}",
                    "drift_kind": "MANIFEST_DISTRIBUTION_DRIFT",
                }
            )

    return {"ok": not issues, "issues": issues}


def validate_known_gap_registry(contract: dict[str, Any] | None = None) -> dict[str, Any]:
    data = contract or load_git_governance_contract()
    matrix = {r["action_id"]: r for r in build_enforcement_matrix(data)}
    issues: list[dict[str, str]] = []
    for action_id, gap in KNOWN_ENFORCEMENT_GAPS.items():
        if gap.get("status") != "KNOWN":
            issues.append(
                {
                    "action_id": action_id,
                    "detail": "status must be KNOWN until evidence-based closure",
                    "drift_kind": "KNOWN_GAP_REGISTRY_DRIFT",
                }
            )
        row = matrix.get(action_id)
        if not row:
            issues.append(
                {
                    "action_id": action_id,
                    "detail": "action missing from contract matrix",
                    "drift_kind": "KNOWN_GAP_REGISTRY_DRIFT",
                }
            )
            continue
        if row.get("actual_result") == "ENFORCED":
            issues.append(
                {
                    "action_id": action_id,
                    "detail": "gap marked KNOWN but matrix reports ENFORCED without G5 evidence",
                    "drift_kind": "ENFORCEMENT_CLASS_DRIFT",
                }
            )
    removed = set(KNOWN_ENFORCEMENT_GAPS) - set(matrix)
    if removed:
        issues.append(
            {
                "detail": f"registry references missing actions: {sorted(removed)}",
                "drift_kind": "KNOWN_GAP_REGISTRY_DRIFT",
            }
        )
    return {"ok": not issues, "known_gaps": KNOWN_ENFORCEMENT_GAPS, "issues": issues}


def inspect_live_hook_deployment() -> dict[str, Any]:
    """READ-ONLY shared .git/hooks inspection (not modified by tests)."""
    results: dict[str, Any] = {"mode": "live_read_only", "hooks": {}}
    for name, path in (
        ("pre-commit", SHARED_HOOK_PRE_COMMIT),
        ("pre-push", SHARED_HOOK_PRE_PUSH),
    ):
        entry: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            entry["thin_adapter"] = "guard.py" in text and "ai-agent." in text
            entry["references_in_repo_guard"] = "tools/git_guard/guard.py" in text
            entry["config_pattern_ok"] = bool(
                re.search(r"ai-agent\.pre-(commit|push)\.json", text)
            )
        else:
            entry["thin_adapter"] = False
            entry["status"] = "NOT_OBSERVED"
        results["hooks"][name] = entry
    observed = [h for h in results["hooks"].values() if h.get("exists")]
    if not observed:
        results["ok"] = True
        results["observed"] = False
        results["note"] = "shared .git/hooks not present in this environment (not a distribution fail)"
        return results
    results["observed"] = True
    results["ok"] = all(
        h.get("thin_adapter") and h.get("config_pattern_ok") for h in observed
    )
    if not results["ok"]:
        results["drift_kind"] = "HOOK_DEPLOYMENT_DRIFT"
    return results


def validate_host_adapter_checklist() -> dict[str, Any]:
    path = REPO_ROOT / "docs" / "adapters" / "GIT_GOVERNANCE_CURSOR_HOST.md"
    if not path.is_file():
        return {
            "ok": False,
            "verification_status": "HOST_ADAPTER_NOT_VERIFIED",
            "drift_kind": "ADAPTER_REFERENCE_DRIFT",
        }
    text = path.read_text(encoding="utf-8")
    required = (
        "ai_tool/policy/git_governance.json",
        "verification_status",
        EXPECTED_CONTRACT_VERSION,
    )
    missing = [r for r in required if r not in text]
    return {
        "ok": not missing,
        "verification_status": "HOST_ADAPTER_NOT_VERIFIED",
        "note": "Host User Rules are not observable from repository CI",
        "missing_in_checklist": missing,
        "drift_kind": "ADAPTER_REFERENCE_DRIFT" if missing else None,
    }


def validate_git_governance_distribution(
    *,
    contract: dict[str, Any] | None = None,
    include_live_hooks: bool = True,
) -> dict[str, Any]:
    """Manifest, adapters, semantic refs, guard config, invariants."""
    data = contract or load_and_validate_git_governance_contract()
    guard_result = validate_git_governance_enforcement(contract=data)
    guard_section = {
        **guard_result,
        "ok": bool(guard_result.get("config_alignment_ok")),
    }
    sections = {
        "contract_version": validate_contract_version(data),
        "semantic_invariants": validate_semantic_invariants(data),
        "semantic_policy": validate_semantic_policy_reference(),
        "manifest": validate_manifest_distribution(),
        "adapters": _validate_adapters_section(data),
        "guard_config": guard_section,
        "known_gaps": validate_known_gap_registry(data),
        "host_adapter": validate_host_adapter_checklist(),
    }
    if include_live_hooks:
        sections["hook_deployment"] = inspect_live_hook_deployment()
    else:
        sections["hook_deployment"] = {
            "ok": True,
            "mode": "skipped",
            "note": "live hook audit disabled",
        }

    drifts: list[dict[str, Any]] = []
    for name, result in sections.items():
        if not result.get("ok"):
            drifts.append({"section": name, "result": result})

    return {
        "contract_version": data.get("contract_version"),
        "sections": sections,
        "drifts": drifts,
        "distribution_ok": len(drifts) == 0,
    }


def _validate_adapters_section(contract: dict[str, Any]) -> dict[str, Any]:
    try:
        paths = validate_git_governance_adapters(contract)
        return {"ok": True, "consumers": paths}
    except Exception as exc:
        return {
            "ok": False,
            "drift_kind": "ADAPTER_REFERENCE_DRIFT",
            "error": str(exc),
        }


def audit_git_governance_drift(
    *,
    contract: dict[str, Any] | None = None,
    include_live_hooks: bool = True,
) -> dict[str, Any]:
    distribution = validate_git_governance_distribution(
        contract=contract, include_live_hooks=include_live_hooks
    )
    drifts = distribution.get("drifts") or []
    if drifts:
        verdict = "DRIFT_FOUND"
    elif KNOWN_ENFORCEMENT_GAPS:
        verdict = "CONSISTENT_WITH_KNOWN_GAPS"
    else:
        verdict = "CONSISTENT"

    host = distribution["sections"].get("host_adapter") or {}
    if host.get("verification_status") == "HOST_ADAPTER_NOT_VERIFIED":
        if verdict == "CONSISTENT":
            verdict = "CONSISTENT_WITH_KNOWN_GAPS"

    return {
        "verdict": verdict,
        "contract_version": distribution.get("contract_version"),
        "distribution": distribution,
        "known_enforcement_gaps": KNOWN_ENFORCEMENT_GAPS,
        "semantic_invariants": SEMANTIC_INVARIANTS,
    }


def assert_no_drift(audit: dict[str, Any]) -> None:
    if audit.get("verdict") == "DRIFT_FOUND":
        raise GitGovernanceDriftError(json.dumps(audit.get("drifts"), ensure_ascii=False))
