"""Human Review → Catalog adoption_status update flow (Phase 3).

Updates catalog metadata only. Does not execute tools, modify registry, or
change agent_available / LLM tool schema.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.catalog.store import load_catalog_entry, save_catalog_entry
from ai_tool.core.audit import append_audit

# Existing catalog schema enum (docs/ai_tool/catalog/catalog_entry.schema.json)
ADOPTION_STATUS_VALUES = frozenset({"not_reviewed", "candidate", "approved", "rejected"})

# Human review outcomes (review record layer)
ReviewStatus = Literal["approved", "rejected", "deferred", "candidate"]
REVIEW_STATUS_VALUES = frozenset({"approved", "rejected", "deferred", "candidate"})

# deferred is NOT a catalog adoption_status value — adoption stays not_reviewed
_DEFERRED_ADOPTION_UNCHANGED = True

_REVIEW_TO_ADOPTION: dict[str, str | None] = {
    "approved": "approved",
    "rejected": "rejected",
    "candidate": "candidate",
    "deferred": None,  # record only; adoption_status unchanged
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HumanReviewRecord:
    tool_id: str
    review_status: ReviewStatus
    reviewed_at: str
    reviewer: str
    reason: str
    notes: str
    before_adoption_status: str
    after_adoption_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HumanReviewResult:
    ok: bool
    tool_id: str
    record: HumanReviewRecord | None
    before_status: dict[str, str]
    after_status: dict[str, str]
    agent_available: bool
    discovery_category: str
    audit_id: str | None
    error: str | None = None
    execution_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool_id": self.tool_id,
            "record": self.record.to_dict() if self.record else None,
            "before_status": self.before_status,
            "after_status": self.after_status,
            "agent_available": self.agent_available,
            "discovery_category": self.discovery_category,
            "audit_id": self.audit_id,
            "error": self.error,
            "execution_count": self.execution_count,
        }


def _status_layers(entry: dict[str, Any]) -> dict[str, str]:
    return {
        "tool_status": str(entry.get("tool_status") or "unknown"),
        "experiment_status": str(entry.get("experiment_status") or "unknown"),
        "adoption_status": str(entry.get("adoption_status") or "unknown"),
    }


def _derive_discovery_preview(entry: dict[str, Any]) -> tuple[bool, str]:
    """Mirror discovery.py experimental logic — preview only, no execution."""
    layers = _status_layers(entry)
    if layers["tool_status"] == "disabled":
        return False, "unavailable"
    if layers["adoption_status"] in ("rejected", "deprecated"):
        return False, "unavailable"
    if layers["experiment_status"] == "experimental":
        return False, "experimental"
    return False, "not_ready"


def get_reviewable_tool(
    tool_id: str,
    *,
    entries_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Return catalog entry if it exists in catalog/entries (read-only)."""
    loaded = load_catalog_entry(tool_id, entries_dir=entries_dir)
    if loaded is None:
        return None
    _, entry = loaded
    return dict(entry)


def apply_human_review(
    tool_id: str,
    review_status: ReviewStatus,
    *,
    reviewer: str = "human",
    reason: str = "",
    notes: str = "",
    entries_dir: Path | None = None,
    reviews_log: Path | None = None,
    audit_log: Path | None = None,
    allow_rereview: bool = True,
) -> HumanReviewResult:
    """Apply human review judgment to catalog adoption_status only.

    Safety: catalog metadata write only. No tool execution, registry, MCP, or network.
    """
    if review_status not in REVIEW_STATUS_VALUES:
        return HumanReviewResult(
            ok=False,
            tool_id=tool_id,
            record=None,
            before_status={},
            after_status={},
            agent_available=False,
            discovery_category="unknown",
            audit_id=None,
            error=f"invalid review_status: {review_status!r}",
        )

    loaded = load_catalog_entry(tool_id, entries_dir=entries_dir)
    if loaded is None:
        return HumanReviewResult(
            ok=False,
            tool_id=tool_id,
            record=None,
            before_status={},
            after_status={},
            agent_available=False,
            discovery_category="unknown",
            audit_id=None,
            error="tool_not_found_in_catalog",
        )

    path, entry = loaded
    before = _status_layers(entry)
    before_adoption = before["adoption_status"]

    if not allow_rereview and before_adoption != "not_reviewed":
        return HumanReviewResult(
            ok=False,
            tool_id=tool_id,
            record=None,
            before_status=before,
            after_status=before,
            agent_available=False,
            discovery_category=_derive_discovery_preview(entry)[1],
            audit_id=None,
            error="rereview_not_allowed",
        )

    target_adoption = _REVIEW_TO_ADOPTION[review_status]
    after_adoption = before_adoption if target_adoption is None else target_adoption

    if after_adoption not in ADOPTION_STATUS_VALUES:
        return HumanReviewResult(
            ok=False,
            tool_id=tool_id,
            record=None,
            before_status=before,
            after_status=before,
            agent_available=False,
            discovery_category=_derive_discovery_preview(entry)[1],
            audit_id=None,
            error=f"invalid adoption_status mapping: {after_adoption!r}",
        )

    reviewed_at = _now_iso()
    record = HumanReviewRecord(
        tool_id=tool_id,
        review_status=review_status,
        reviewed_at=reviewed_at,
        reviewer=reviewer,
        reason=reason,
        notes=notes,
        before_adoption_status=before_adoption,
        after_adoption_status=after_adoption,
    )

    entry["adoption_status"] = after_adoption
    entry["human_review"] = {
        "review_status": review_status,
        "reviewed_at": reviewed_at,
        "reviewer": reviewer,
        "reason": reason,
        "notes": notes,
    }

    save_catalog_entry(path, entry)

    after = _status_layers(entry)
    agent_available, discovery_category = _derive_discovery_preview(entry)

    if reviews_log is not None:
        reviews_log.parent.mkdir(parents=True, exist_ok=True)
        import json

        with reviews_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    audit_id = append_audit(
        {
            "event": "human_review_catalog_update",
            "tool_id": tool_id,
            "review_action": review_status,
            "before_status": before,
            "after_status": after,
            "before_adoption_status": before_adoption,
            "after_adoption_status": after_adoption,
            "agent_available_unchanged": agent_available is False,
        },
        log_path=audit_log,
    )

    return HumanReviewResult(
        ok=True,
        tool_id=tool_id,
        record=record,
        before_status=before,
        after_status=after,
        agent_available=agent_available,
        discovery_category=discovery_category,
        audit_id=audit_id,
    )
