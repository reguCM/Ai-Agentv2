from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_tool.policy.loader import (
    PolicyLoadError,
    policy_identity,
    policy_identity_is_current,
    policy_identity_snapshot,
    validate_policy_distribution,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _fixture_repo(tmp_path: Path) -> Path:
    canonical = [
        "ai_tool/policy/development_policy.json",
        "docs/POLICY.md",
    ]
    consumers = {
        "codex": {
            "adapter": "AGENTS.md",
            "mode": "reference",
            "required_references": canonical,
        },
        "cursor": {
            "adapter": ".cursor/rules/policy.mdc",
            "mode": "reference",
            "required_references": canonical,
        },
        "local_agent": {
            "adapter": "ai_tool/policy/loader.py",
            "mode": "loader",
            "required_references": ["development_policy.json"],
        },
    }
    payload = {
        "policy_id": "test-policy",
        "version": "1",
        "item_statuses": ["CONNECTED"],
        "completion": {},
        "human_decision_required_when": [],
        "definition_boundary": {},
        "distribution": {
            "schema_version": "1",
            "policy_version": "test.1",
            "canonical_files": canonical,
            "consumers": consumers,
        },
    }
    policy = tmp_path / canonical[0]
    policy.parent.mkdir(parents=True)
    policy.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/POLICY.md").write_text("canonical", encoding="utf-8")
    marker = "policy-distribution-version: test.1\n"
    (tmp_path / "AGENTS.md").write_text(
        marker + "\n".join(canonical), encoding="utf-8"
    )
    (tmp_path / ".cursor/rules").mkdir(parents=True)
    (tmp_path / ".cursor/rules/policy.mdc").write_text(
        marker + "\n".join(canonical), encoding="utf-8"
    )
    (tmp_path / "ai_tool/policy/loader.py").write_text(
        "# development_policy.json\ndef policy_identity(): pass\n", encoding="utf-8"
    )
    return policy


def test_repository_policy_distribution_is_connected():
    result = validate_policy_distribution()

    assert result["sync_valid"] is True
    assert result["loaded"] is True
    assert result["version"] == "2026-09-13.1"
    assert result["canonical_hash"].startswith("sha256:")
    assert set(result["consumers"]) == {"codex", "cursor", "local_agent"}
    assert all((REPO_ROOT / path).is_file() for path in result["canonical_files"])


def test_reference_adapters_do_not_copy_a_canonical_document_verbatim():
    identity = policy_identity()
    canonical = (REPO_ROOT / "docs/DEVELOPMENT_TEST_POLICY.md").read_text(encoding="utf-8")
    for adapter_path in ("AGENTS.md", ".cursor/rules/agent-development-policy.mdc"):
        adapter = (REPO_ROOT / adapter_path).read_text(encoding="utf-8")
        assert canonical not in adapter
        assert identity["version"] in adapter


def test_canonical_change_changes_hash(tmp_path):
    policy = _fixture_repo(tmp_path)
    before = policy_identity(path=policy, repo_root=tmp_path)
    (tmp_path / "docs/POLICY.md").write_text("changed", encoding="utf-8")
    after = policy_identity(path=policy, repo_root=tmp_path)

    assert before["canonical_hash"] != after["canonical_hash"]
    assert not policy_identity_is_current(before, current=after)


def test_missing_canonical_file_is_detected(tmp_path):
    policy = _fixture_repo(tmp_path)
    (tmp_path / "docs/POLICY.md").unlink()

    with pytest.raises(PolicyLoadError, match="canonical policy file missing"):
        validate_policy_distribution(path=policy, repo_root=tmp_path)


@pytest.mark.parametrize("consumer", ["codex", "cursor"])
def test_missing_or_stale_reference_adapter_is_detected(tmp_path, consumer):
    policy = _fixture_repo(tmp_path)
    data = json.loads(policy.read_text(encoding="utf-8"))
    adapter = tmp_path / data["distribution"]["consumers"][consumer]["adapter"]
    adapter.write_text("policy-distribution-version: stale", encoding="utf-8")

    with pytest.raises(PolicyLoadError, match="reference missing|version stale"):
        validate_policy_distribution(path=policy, repo_root=tmp_path)


def test_stale_local_loader_is_detected_and_snapshot_fails_closed(tmp_path):
    policy = _fixture_repo(tmp_path)
    loader = tmp_path / "ai_tool/policy/loader.py"
    loader.write_text("# development_policy.json\n", encoding="utf-8")

    snapshot = policy_identity_snapshot(path=policy, repo_root=tmp_path)

    assert snapshot["loaded"] is False
    assert snapshot["sync_valid"] is False
    assert "identity unavailable" in snapshot["error"]
