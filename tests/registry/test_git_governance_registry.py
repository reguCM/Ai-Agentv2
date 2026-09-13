"""G6 — Git Governance entries in project_assets registry."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "registry" / "project_assets.json"
SCHEMA = REPO_ROOT / "registry" / "schema" / "project_assets.schema.json"


def _assets_by_id() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {str(a["asset_id"]): a for a in data["assets"]}


def test_registry_validates_against_schema():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(registry))
    assert not errors, errors[0].message if errors else ""


def test_git_operation_policy_not_enforced_as_policy():
    asset = _assets_by_id()["git_operation_policy"]
    assert asset["enforcement_level"] == "DOCUMENTATION"
    assert asset["status"] == "DOCUMENT_ONLY"
    assert "git_governance_contract" in asset["related_assets"]


def test_git_governance_contract_asset():
    asset = _assets_by_id()["git_governance_contract"]
    assert asset["path"] == "ai_tool/policy/git_governance.json"
    assert asset["enforcement_level"] == "VALIDATED"
    deps = asset.get("freshness_dependencies") or []
    assert any(d.get("asset_id") == "git_operation_policy" for d in deps)


def test_git_guard_validator_role():
    asset = _assets_by_id()["git_guard"]
    assert asset["enforcement_level"] == "ENFORCED"
    assert "git_governance_contract" in asset["related_policies"]
    assert "known" not in (asset.get("notes") or "").lower() or "partial" in (asset.get("notes") or "").lower()


def test_freshness_dependencies_not_used_as_related_only():
    guard = _assets_by_id()["git_guard"]
    assert guard.get("freshness_dependencies")


def test_git_governance_closure_human_verified():
    """Post-closure Human Approval (APPROVE_VERIFIED); not full ENFORCED / zero gaps."""
    expected_method = "git_governance_post_g6_closure_reverify"
    for asset_id in (
        "git_governance_contract",
        "git_operation_policy",
        "git_governance_cursor_adapter",
        "git_guard",
        "git_hooks_deployment",
    ):
        ver = _assets_by_id()[asset_id].get("verification") or {}
        assert ver.get("freshness") == "VERIFIED", asset_id
        assert ver.get("verification_method") == expected_method, asset_id
        assert ver.get("verification_id", "").startswith("ve_20260911T222954"), asset_id
        assert "stale_reason" not in ver, asset_id
