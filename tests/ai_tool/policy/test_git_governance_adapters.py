"""Git Governance Phase G3 — adapter alignment tests."""
from __future__ import annotations

from pathlib import Path

from ai_tool.policy.git_governance_contract import (
    load_and_validate_git_governance_contract,
    validate_git_governance_adapters,
)
from ai_tool.policy.loader import validate_policy_distribution

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_g3_adapters_connected():
    data = load_and_validate_git_governance_contract()
    consumers = data["adapters"]["consumers"]
    assert "cursor_git" in consumers
    assert consumers["cursor_git"]["adapter"] == ".cursor/rules/git-governance-adapter.mdc"
    assert data["adapters"]["phase"] == "G3"


def test_development_policy_adapters_reference_git_governance():
    result = validate_policy_distribution()
    assert result["sync_valid"] is True
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ai_tool/policy/git_governance.json" in agents
    mdc = (REPO_ROOT / ".cursor/rules/agent-development-policy.mdc").read_text(encoding="utf-8")
    assert "ai_tool/policy/git_governance.json" in mdc


def test_git_operation_policy_references_machine_contract():
    git_doc = (REPO_ROOT / "docs/GIT_OPERATION_POLICY.md").read_text(encoding="utf-8")
    assert "ai_tool/policy/git_governance.json" in git_doc
    assert "AUTO_COMMIT_ALLOWED" in git_doc
    assert "Option C" in git_doc
    assert "amend" in git_doc.lower()


def test_adapters_do_not_embed_contract_json():
    data = load_and_validate_git_governance_contract()
    validate_git_governance_adapters(data, repo_root=REPO_ROOT)
