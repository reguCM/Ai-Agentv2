from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_tool.context_builder.fetch import fetch_selected_contents
from ai_tool.context_builder.identity import resolve_identity
from ai_tool.context_builder.models import (
    ALL_SLOTS,
    P0_SLOTS,
    ContextBuildResult,
    ContextManifest,
    SelectedFile,
    SlotEntry,
)
from ai_tool.context_builder.rules import collect_file_candidates, load_selection_rules
from ai_tool.context_builder.sensitive import is_sensitive_path
from ai_tool.experimental.scoped_read.paths import find_repo_root


def _slot_from_candidates(
    slot_name: str,
    candidates: list[SelectedFile],
    identity_data: dict[str, Any],
    spec: dict[str, Any] | None,
    tool_rules: dict[str, Any],
) -> SlotEntry:
    slot_files = [c.path for c in candidates if c.slot == slot_name]
    if slot_name == "identity":
        return SlotEntry(status="FOUND", data=identity_data, files=[])

    if slot_name == "specification":
        if identity_data.get("spec_path"):
            return SlotEntry(
                status="FOUND",
                data={"spec_path": identity_data["spec_path"]},
                files=[identity_data["spec_path"]],
            )
        return SlotEntry(status="UNKNOWN", reason="NOT_FOUND")

    if slot_name == "contract":
        if spec and spec.get("contract"):
            return SlotEntry(
                status="FOUND",
                data={"contract": spec["contract"], "source": "specification"},
                files=slot_files,
            )
        if slot_files:
            return SlotEntry(status="FOUND", data={"source": "global_documents"}, files=slot_files)
        return SlotEntry(status="UNKNOWN", reason="NOT_FOUND")

    if slot_name == "implementation":
        module = identity_data.get("module")
        if module:
            return SlotEntry(
                status="REFERENCE_ONLY",
                reason="OUTSIDE_ALLOWLIST",
                data={"module": module, "function": identity_data.get("function")},
                files=[c.path for c in candidates if c.slot == "implementation"],
            )
        return SlotEntry(status="UNKNOWN", reason="NOT_FOUND")

    if slot_name == "tests":
        refs = (tool_rules.get("reference_only") or {}).get("tests")
        if refs:
            return SlotEntry(
                status="REFERENCE_ONLY",
                reason="OUTSIDE_ALLOWLIST",
                data={"test_path": refs},
                files=[str(refs).replace("\\", "/")],
            )
        if slot_files:
            return SlotEntry(status="FOUND", data={"source": "global_test_contract"}, files=slot_files)
        return SlotEntry(status="UNKNOWN", reason="NOT_FOUND")

    if slot_name == "known_limitations":
        if spec and spec.get("known_limitations"):
            return SlotEntry(
                status="FOUND",
                data={"known_limitations": spec["known_limitations"]},
                files=[],
            )
        return SlotEntry(status="UNKNOWN", reason="NOT_FOUND")

    if slot_files:
        return SlotEntry(status="FOUND", files=slot_files)
    return SlotEntry(status="UNKNOWN", reason="NOT_FOUND")


def build_tool_development_context(
    tool_id: str,
    *,
    repo_root: Path | None = None,
    fetch_content: bool = True,
    compression: str = "full",
    audit: bool = False,
    audit_log: Path | None = None,
) -> ContextBuildResult:
    """
    Build Tool Development Context manifest and optionally fetch allowlisted content.

    Mechanical rules only — no LLM selection or summarization.
    """
    root = (repo_root or find_repo_root()).resolve()
    rules = load_selection_rules(root)
    identity = resolve_identity(tool_id, repo_root=root, rules=rules)
    if identity is None:
        empty_manifest = ContextManifest(tool_id=tool_id, slots={})
        return ContextBuildResult(
            status="ERROR",
            tool_id=tool_id,
            manifest=empty_manifest,
            selected_files=[],
            missing_slots=list(P0_SLOTS),
            excluded_files=[],
            warnings=[f"unknown tool_id: {tool_id}"],
        )

    identity_data = identity.to_dict()
    tool_rules = (rules.get("tool_specific") or {}).get(identity.canonical_id) or {}
    candidates = collect_file_candidates(identity, rules)

    excluded: list[dict[str, Any]] = []
    for c in candidates:
        if c.content_status.startswith("EXCLUDED"):
            excluded.append(
                {
                    "path": c.path,
                    "slot": c.slot,
                    "reason": c.content_status,
                    "priority": c.priority,
                }
            )

    slots: dict[str, dict[str, Any]] = {}
    for slot_name in ALL_SLOTS:
        entry = _slot_from_candidates(
            slot_name,
            candidates,
            identity_data,
            identity.spec,
            tool_rules,
        )
        slots[slot_name] = entry.to_dict()

    missing_p0 = [
        s for s in P0_SLOTS
        if slots[s].get("status") in ("UNKNOWN",)
    ]
    status = "OK" if not missing_p0 else "PARTIAL"

    manifest = ContextManifest(tool_id=identity.canonical_id, slots=slots)

    fetchable = [
        c.path
        for c in candidates
        if c.content_status == "NOT_FETCHED" and not is_sensitive_path(c.path)
    ]
    content: dict[str, str] = {}
    warnings: list[str] = []
    if fetch_content and compression != "none":
        content, errors = fetch_selected_contents(
            fetchable,
            repo_root=root,
            compression=compression,
            audit=audit,
            audit_log=audit_log,
        )
        for c in candidates:
            if c.path in content:
                c.content_status = "FETCHED"
            elif c.content_status == "NOT_FETCHED" and c.path in errors:
                c.content_status = "FETCH_FAILED"
                c.error = errors[c.path]
                warnings.append(f"fetch failed: {c.path}: {errors[c.path]}")
            elif c.content_status == "NOT_FETCHED" and c.path in fetchable:
                c.content_status = "EXCLUDED_OUTSIDE_ALLOWLIST"

    return ContextBuildResult(
        status=status,
        tool_id=identity.canonical_id,
        manifest=manifest,
        selected_files=candidates,
        missing_slots=missing_p0,
        excluded_files=sorted(excluded, key=lambda x: x["path"]),
        warnings=warnings,
        content=content,
    )
