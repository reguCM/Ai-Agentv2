"""G5 — Git Governance distribution and negative drift fixtures."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ai_tool.policy.git_governance_contract import validate_git_governance_contract
from ai_tool.policy.git_governance_distribution import (
    GitGovernanceDriftError,
    audit_git_governance_drift,
    assert_no_drift,
    validate_git_governance_distribution,
    validate_semantic_invariants,
)
from ai_tool.policy.git_governance_enforcement import validate_git_governance_enforcement
from ai_tool.policy.git_governance_invariants import EXPECTED_CONTRACT_VERSION
from ai_tool.policy.paths import git_governance_json_path

REPO_ROOT = Path(__file__).resolve().parents[3]
PRE_PUSH_CFG = REPO_ROOT / "tools" / "git_guard" / "configs" / "ai-agent.pre-push.json"


def test_g5_audit_consistent_with_known_gaps():
    audit = audit_git_governance_drift()
    assert audit["verdict"] in ("CONSISTENT_WITH_KNOWN_GAPS", "CONSISTENT")
    assert audit["contract_version"] == EXPECTED_CONTRACT_VERSION
    assert_no_drift(audit)


def test_distribution_sections_ok():
    dist = validate_git_governance_distribution()
    assert dist["distribution_ok"] is True
    assert dist["sections"]["semantic_invariants"]["ok"] is True
    assert dist["sections"]["manifest"]["ok"] is True
    assert dist["sections"]["host_adapter"]["verification_status"] == "HOST_ADAPTER_NOT_VERIFIED"


def test_negative_contract_enforcement_class_drift():
    data = json.loads(git_governance_json_path().read_text(encoding="utf-8"))
    broken = copy.deepcopy(data)
    for action in broken["actions"]:
        if action.get("action_id") == "force_push":
            action["approval_class"] = "HUMAN_APPROVAL_REQUIRED"
            break
    result = validate_semantic_invariants(broken)
    assert result["ok"] is False


def test_negative_guard_config_drift(tmp_path: Path):
    data = json.loads(git_governance_json_path().read_text(encoding="utf-8"))
    cfg = json.loads(PRE_PUSH_CFG.read_text(encoding="utf-8-sig"))
    broken_cfg = copy.deepcopy(cfg)
    broken_cfg["forbid_actions"] = [a for a in broken_cfg["forbid_actions"] if a != "force_push_with_lease"]
    broken_path = tmp_path / "pre-push.json"
    broken_path.write_text(json.dumps(broken_cfg), encoding="utf-8")
    result = validate_git_governance_enforcement(contract=data, pre_push_path=broken_path)
    assert result["config_alignment_ok"] is False


def test_negative_manifest_drift(tmp_path: Path):
    manifest_path = REPO_ROOT / "ai_tool/policy/development_policy.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    broken = copy.deepcopy(manifest)
    broken["distribution"]["git_governance_ref"]["contract_path"] = "ai_tool/policy/missing.json"
    broken_manifest = tmp_path / "development_policy.json"
    broken_manifest.write_text(json.dumps(broken), encoding="utf-8")
    from ai_tool.policy.git_governance_distribution import validate_manifest_distribution
    from ai_tool.policy.loader import load_development_policy

    original_load = load_development_policy

    def _load_broken():
        return json.loads(broken_manifest.read_text(encoding="utf-8"))

    import ai_tool.policy.git_governance_distribution as dist_mod

    dist_mod.load_development_policy = _load_broken  # type: ignore[method-assign]
    try:
        result = validate_manifest_distribution()
        assert result["ok"] is False
    finally:
        dist_mod.load_development_policy = original_load  # type: ignore[method-assign]


def test_negative_contract_version_drift():
    data = json.loads(git_governance_json_path().read_text(encoding="utf-8"))
    broken = copy.deepcopy(data)
    broken["contract_version"] = "0.0.0-wrong"
    validate_git_governance_contract(broken)
    version_check = audit_git_governance_drift(contract=broken)
    assert version_check["verdict"] == "DRIFT_FOUND"


def test_assert_no_drift_raises_on_drift():
    data = json.loads(git_governance_json_path().read_text(encoding="utf-8"))
    broken = copy.deepcopy(data)
    broken["contract_version"] = "invalid"
    audit = audit_git_governance_drift(contract=broken)
    with pytest.raises(GitGovernanceDriftError):
        assert_no_drift(audit)


def test_false_positive_prose_change_does_not_break_invariants(tmp_path: Path):
    git_path = REPO_ROOT / "docs/GIT_OPERATION_POLICY.md"
    text = git_path.read_text(encoding="utf-8")
    tweaked = text.replace("基本思想", "基本思想", 1)  # no-op
    assert tweaked == text
    inv = validate_semantic_invariants()
    assert inv["ok"] is True
