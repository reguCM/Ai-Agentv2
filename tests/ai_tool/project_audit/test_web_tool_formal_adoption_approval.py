"""Web Tool Formal Adoption Approval — record consistency checks (no production changes)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
AUDIT = REPO / "docs/ai_tool/project_audit"


@pytest.fixture
def approval_text() -> str:
    return (AUDIT / "WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md").read_text(encoding="utf-8")


@pytest.fixture
def lifecycle_text() -> str:
    return (AUDIT / "TOOL_LIFECYCLE_POLICY_CANDIDATE.md").read_text(encoding="utf-8")


def test_approval_document_exists() -> None:
    assert (AUDIT / "WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md").is_file()


def test_all_hr_decisions_approved_or_deferred(approval_text: str) -> None:
    for hr in ("HR-1", "HR-2", "HR-3", "HR-4", "HR-5", "HR-6"):
        assert "APPROVED" in approval_text.split(hr, 1)[1][:400]
    assert "HR-7" in approval_text
    assert "DEFERRED" in approval_text.split("HR-7", 1)[1][:300]


def test_hr3_hr4_no_interface_change(approval_text: str) -> None:
    assert "NO INTERFACE CHANGE" in approval_text
    assert approval_text.count("NO INTERFACE CHANGE") >= 2


def test_rename_not_required_stated(approval_text: str) -> None:
    assert "NOT REQUIRED" in approval_text
    assert "search_web_include_mean" in approval_text or "Rename" in approval_text


def test_implementation_phase_authorized_not_started(approval_text: str) -> None:
    assert "Implementation Phase" in approval_text
    assert "Production changes this phase" in approval_text
    assert "Git commit this phase" in approval_text
    # Approval phase explicitly records no production/commit in this phase
    assert re.search(r"Production changes[^\n]*NONE", approval_text)
    assert re.search(r"Git commit[^\n]*NONE", approval_text)


def test_search_fetch_workflow_approved(approval_text: str) -> None:
    assert "search_web" in approval_text
    assert "read_url_text" in approval_text
    assert "Search → Fetch" in approval_text or "Search → Fetch workflow" in approval_text


def test_lifecycle_implemented_not_adopted_label(lifecycle_text: str) -> None:
    assert "IMPLEMENTED_NOT_ADOPTED" in lifecycle_text
    assert "PROMPT_REGISTRY_DRIFT" in lifecycle_text


def test_approval_matches_review_recommendations() -> None:
    review = (AUDIT / "WEB_TOOL_FORMAL_ADOPTION_REVIEW.md").read_text(encoding="utf-8")
    approval = (AUDIT / "WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md").read_text(encoding="utf-8")
    assert "ADOPT" in review
    assert "APPROVED" in approval
    assert "RENAME NOT REQUIRED" in review
    assert "NOT REQUIRED" in approval


def test_registry_contains_web_tools() -> None:
    reg = json.loads((REPO / "registry/tools.json").read_text(encoding="utf-8"))
    agent = {t["name"] for t in reg["tools"] if t.get("visibility") == "agent"}
    assert "search_web" in agent
    assert "read_url_text" in agent


def test_approval_records_head_commit() -> None:
    text = (AUDIT / "WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md").read_text(encoding="utf-8")
    assert "875cc47" in text
