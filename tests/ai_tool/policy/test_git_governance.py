"""Git Governance Machine Contract (Phase G2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai_tool.policy.git_governance_contract import (
    GitGovernanceContractError,
    action_approval_map,
    load_and_validate_git_governance_contract,
    load_git_governance_contract,
    validate_git_governance_contract,
)
from ai_tool.policy.loader import load_development_policy
from ai_tool.policy.git_governance_invariants import (
    EXPECTED_CONTRACT_VERSION,
    SEMANTIC_INVARIANTS,
)
from ai_tool.policy.paths import git_governance_json_path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_contract_loads_and_validates_against_schema():
    data = load_and_validate_git_governance_contract()
    assert data["policy_id"] == "ai-agent-git-governance"
    assert data["contract_version"] == EXPECTED_CONTRACT_VERSION
    assert data["human_decision_g4_1"]["reset_hard"] == "AGENT_ALWAYS_BLOCK"
    assert data["role"] == "git_governance_machine_contract"
    assert data["human_decision_g2"]["commit_option"] == "C"
    assert data["authorization"]["agent_default_auto_commit"] is False
    assert data["authorization"]["auto_commit_token"] == "AUTO_COMMIT_ALLOWED"
    assert data["authorization"]["runtime_binding"] == "NOT_CONNECTED"


def test_semantic_source_primary_exists():
    data = load_git_governance_contract()
    primary = [s for s in data["semantic_sources"] if s["role"] == "primary"]
    assert len(primary) == 1
    assert primary[0]["path"] == "docs/GIT_OPERATION_POLICY.md"
    assert (REPO_ROOT / primary[0]["path"]).is_file()


def test_semantic_invariants_human_decision_g2():
    data = load_and_validate_git_governance_contract()
    mapping = action_approval_map(data)
    for action_id, expected in SEMANTIC_INVARIANTS.items():
        assert mapping.get(action_id) == expected, action_id


def test_manifest_git_governance_ref():
    manifest = load_development_policy()
    ref = manifest["distribution"]["git_governance_ref"]
    assert ref["contract_path"] == "ai_tool/policy/git_governance.json"
    assert (REPO_ROOT / ref["contract_path"]).is_file()
    assert (REPO_ROOT / ref["schema_path"]).is_file()


def test_agent_always_block_has_no_auto_allow_conditions():
    data = load_git_governance_contract()
    for action in data["actions"]:
        if action["approval_class"] != "AGENT_ALWAYS_BLOCK":
            continue
        for cond in action.get("required_conditions") or []:
            assert cond["condition_id"] not in {
                "authorization_present",
                "auto_commit_allowed",
            }


def test_force_push_human_direct_operation_outside_contract():
    data = load_git_governance_contract()
    by_id = {a["action_id"]: a for a in data["actions"]}
    assert by_id["force_push"]["human_direct_operation"] == "OUTSIDE_AGENT_CONTRACT"
    assert by_id["force_push_with_lease"]["human_direct_operation"] == "OUTSIDE_AGENT_CONTRACT"


def test_duplicate_action_id_rejected():
    data = load_git_governance_contract()
    broken = dict(data)
    broken["actions"] = list(data["actions"]) + [dict(data["actions"][0])]
    with pytest.raises(GitGovernanceContractError, match="duplicate action_id"):
        validate_git_governance_contract(broken)


def test_contract_file_is_canonical_path():
    assert git_governance_json_path().name == "git_governance.json"
