from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.context_builder.builder import build_tool_development_context
from ai_tool.context_builder.models import (
    P0_SLOTS,
    P1_SLOTS,
    P2_SLOTS,
    ContextBuildResult,
)
from ai_tool.context_builder.package_models import (
    SLOT_TO_FILENAME,
    ExternalHelpPackageResult,
    PackageReadiness,
)
from ai_tool.context_builder.sensitive import is_sensitive_path
from ai_tool.experimental.scoped_read.paths import find_repo_root

PRIORITY_BY_SLOT: dict[str, str] = {}
for s in P0_SLOTS:
    PRIORITY_BY_SLOT[s] = "P0"
for s in P1_SLOTS:
    PRIORITY_BY_SLOT[s] = "P1"
for s in P2_SLOTS:
    PRIORITY_BY_SLOT[s] = "P2"
PRIORITY_BY_SLOT["identity"] = "P0"


def _readiness(context: ContextBuildResult) -> PackageReadiness:
    if context.status == "ERROR":
        return "NOT_READY"
    if context.missing_slots:
        return "PARTIAL"
    return "READY"


def _trust_for_status(status: str) -> str:
    if status == "FOUND":
        return "fetched_or_structured"
    if status == "REFERENCE_ONLY":
        return "metadata_only"
    if status == "UNKNOWN":
        return "not_available"
    return "not_available"


def _slot_sources(context: ContextBuildResult, slot: str) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "path": f.path,
                "reason": f.reason,
                "priority": f.priority,
                "content_status": f.content_status,
            }
            for f in context.selected_files
            if f.slot == slot
        ],
        key=lambda x: x["path"],
    )


def _body_for_slot(context: ContextBuildResult, slot: str, slot_meta: dict[str, Any]) -> str:
    status = slot_meta.get("status", "UNKNOWN")
    if status == "UNKNOWN":
        return f"_No body available. Reason: {slot_meta.get('reason', 'NOT_FOUND')}_"
    if status == "REFERENCE_ONLY":
        lines = [
            "_Body not included (REFERENCE_ONLY — outside experimental allowlist)._",
            "",
            "## Reference metadata",
            "",
            "```json",
            json.dumps(slot_meta.get("data") or {}, indent=2, ensure_ascii=False),
            "```",
        ]
        ref_files = slot_meta.get("files") or []
        if ref_files:
            lines.extend(["", "## Reference paths (not fetched)", ""])
            for p in ref_files:
                lines.append(f"- `{p}`")
        return "\n".join(lines)

    parts: list[str] = []
    sources = _slot_sources(context, slot)
    for src in sources:
        path = src["path"]
        if is_sensitive_path(path):
            continue
        if src["content_status"] != "FETCHED":
            continue
        if path.startswith("tools/"):
            continue
        body = context.content.get(path)
        if body is None:
            continue
        parts.append(f"### Source: `{path}`\n\n{body}")
    if slot_meta.get("data") and slot != "identity":
        data = slot_meta["data"]
        if "contract" in data:
            parts.append(
                "### Structured contract (from specification)\n\n```json\n"
                + json.dumps(data["contract"], indent=2, ensure_ascii=False)
                + "\n```"
            )
        if "known_limitations" in data:
            parts.append(
                "### Known limitations (from specification)\n\n"
                + "\n".join(f"- {x}" for x in data["known_limitations"])
            )
    if not parts:
        return "_No fetched body for this slot (metadata may be in CONTEXT_MANIFEST.json)._"
    return "\n\n---\n\n".join(parts)


def _render_slot_markdown(
    context: ContextBuildResult,
    slot: str,
    slot_meta: dict[str, Any],
) -> str:
    title = slot.replace("_", " ").title()
    status = slot_meta.get("status", "UNKNOWN")
    lines = [
        f"# {title}",
        "",
        f"**Slot:** `{slot}`",
        f"**Priority:** {PRIORITY_BY_SLOT.get(slot, 'P2')}",
        f"**Status:** {status}",
        f"**Trust:** {_trust_for_status(status)}",
        "",
        "## Sources",
        "",
        "| path | reason | content_status |",
        "|------|--------|----------------|",
    ]
    sources = _slot_sources(context, slot)
    if sources:
        for src in sources:
            lines.append(
                f"| `{src['path']}` | {src['reason']} | {src['content_status']} |"
            )
    else:
        lines.append("| _none_ | | |")
    lines.extend(["", "## Body", ""])
    lines.append(_body_for_slot(context, slot, slot_meta))
    return "\n".join(lines) + "\n"


def _collect_unknown_entries(context: ContextBuildResult) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for slot_name, slot_meta in sorted(context.manifest.slots.items()):
        status = slot_meta.get("status")
        if status in ("UNKNOWN", "REFERENCE_ONLY", "EXCLUDED"):
            entries.append(
                {
                    "slot": slot_name,
                    "status": status,
                    "reason": slot_meta.get("reason"),
                    "priority": PRIORITY_BY_SLOT.get(slot_name, "P2"),
                }
            )
    for ex in context.excluded_files:
        entries.append(
            {
                "slot": ex.get("slot"),
                "path": ex.get("path"),
                "status": "EXCLUDED",
                "reason": ex.get("reason"),
                "priority": ex.get("priority"),
            }
        )
    return entries


def _render_unknown_and_missing(context: ContextBuildResult) -> str:
    entries = _collect_unknown_entries(context)
    lines = [
        "# Unknown and Missing",
        "",
        "Aggregated slots and files that are not fully available as fetched body.",
        "",
        "| slot | status | reason | priority | path |",
        "|------|--------|--------|----------|------|",
    ]
    if not entries:
        lines.append("| _none_ | | | | |")
    else:
        for e in entries:
            lines.append(
                f"| {e.get('slot', '')} | {e.get('status', '')} | {e.get('reason', '')} | "
                f"{e.get('priority', '')} | {e.get('path', '')} |"
            )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- UNKNOWN is not filled by inference",
            "- REFERENCE_ONLY paths are listed but body is not fetched (allowlist)",
            "- EXCLUDED paths are not included as body content",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_summary(context: ContextBuildResult, readiness: PackageReadiness) -> str:
    slots = context.manifest.slots
    identity = slots.get("identity", {}).get("data") or {}
    spec_slot = slots.get("specification", {})
    impl_slot = slots.get("implementation", {})
    test_slot = slots.get("tests", {})
    safety_slot = slots.get("safety", {})

    unknown_entries = _collect_unknown_entries(context)
    known_facts = [
        f"Tool ID: `{context.tool_id}`",
        f"Name: `{identity.get('name', 'UNKNOWN')}`",
        f"Provider: `{identity.get('provider', 'UNKNOWN')}`",
        f"Specification path: `{identity.get('spec_path') or 'NOT_FOUND'}`",
    ]
    if impl_slot.get("status") == "REFERENCE_ONLY":
        known_facts.append(
            f"Implementation reference: `{identity.get('module')}` (body not in package)"
        )
    elif impl_slot.get("status") == "FOUND":
        known_facts.append("Implementation: metadata present")

    unknown_lines = []
    if context.missing_slots:
        unknown_lines.append(f"Missing P0 slots: {', '.join(context.missing_slots)}")
    for e in unknown_entries:
        if e.get("status") == "UNKNOWN":
            unknown_lines.append(f"- {e.get('slot')}: {e.get('reason')}")
    if not unknown_lines:
        unknown_lines.append("- _No UNKNOWN P0 slots recorded_")

    return f"""# Tool Development External Help Package

## Purpose

This package organizes **known facts** about a Tool for human / Cursor / Large LLM review.
It is **not** an implementation directive. Do not treat missing sections as approval to guess.

## Tool identity

- **Tool ID:** `{context.tool_id}`
- **Purpose:** see SPECIFICATION.md (if present)
- **Provider:** `{identity.get('provider', 'UNKNOWN')}`
- **Package readiness:** `{readiness}` (Phase 1 context status: `{context.status}`)

## What we know

{chr(10).join('- ' + f for f in known_facts)}

| Area | Slot status |
|------|-------------|
| Specification | {spec_slot.get('status', 'UNKNOWN')} |
| Contract | {slots.get('contract', {}).get('status', 'UNKNOWN')} |
| Implementation | {impl_slot.get('status', 'UNKNOWN')} |
| Tests | {test_slot.get('status', 'UNKNOWN')} |
| Safety | {safety_slot.get('status', 'UNKNOWN')} |

## Context coverage

- Selected files: {len(context.selected_files)}
- Fetched bodies: {len(context.content)}
- Missing P0: {context.missing_slots or 'none'}
- Excluded: {len(context.excluded_files)}

## What we do not know (or did not fetch)

{chr(10).join(unknown_lines)}

## Warnings

{chr(10).join('- ' + w for w in context.warnings) if context.warnings else '- none'}

## Constraints (read request.json)

- Do not modify production code without human approval
- Do not fabricate specification or test results
- UNKNOWN is acceptable
- REFERENCE_ONLY paths require separate allowlisted access to read source code

## Suggested next steps (human decision)

1. Review SPECIFICATION.md and CONTRACT.md
2. Confirm missing items in UNKNOWN_AND_MISSING.md
3. If implementation body is needed, open reference paths outside this package manually
4. Decide whether to extend Tool, fix tests, or update specification — **human judgment**
"""


def _build_request_json(context: ContextBuildResult, readiness: PackageReadiness) -> dict[str, Any]:
    return {
        "tool_id": context.tool_id,
        "kind": "tool_development_external_help",
        "package_readiness": readiness,
        "context_builder_status": context.status,
        "missing_p0": context.missing_slots,
        "constraints": [
            "This package is not an implementation directive",
            "Do not modify production code without human approval",
            "Do not fabricate missing specification or test fields",
            "Do not infer UNKNOWN slots as confirmed facts",
            "REFERENCE_ONLY paths were not fetched (allowlist)",
            "UNKNOWN is acceptable",
        ],
        "auto_implement_allowed": False,
        "auto_fix_allowed": False,
        "llm_auto_submit": False,
    }


def _build_context_manifest_json(
    context: ContextBuildResult,
    readiness: PackageReadiness,
) -> dict[str, Any]:
    return {
        "tool_id": context.tool_id,
        "package_readiness": readiness,
        "context_builder_status": context.status,
        "manifest": context.manifest.to_dict(),
        "selected_files": [f.to_dict() for f in context.selected_files],
        "missing_p0": context.missing_slots,
        "excluded_files": context.excluded_files,
        "warnings": context.warnings,
        "content_paths": sorted(context.content.keys()),
        "policy": {
            "manifest_body_separation": True,
            "unknown_inference": False,
            "glossary_bulk_inject": False,
        },
    }


def build_external_help_package(
    tool_id: str,
    output_dir: Path,
    *,
    repo_root: Path | None = None,
    fetch_content: bool = True,
    audit: bool = False,
    audit_log: Path | None = None,
) -> ExternalHelpPackageResult:
    """
    Build External Help Package from Context Builder output.

    Writes structured files under output_dir/external_help_package/.
    """
    root = (repo_root or find_repo_root()).resolve()
    context = build_tool_development_context(
        tool_id,
        repo_root=root,
        fetch_content=fetch_content,
        compression="full",
        audit=audit,
        audit_log=audit_log,
    )
    readiness = _readiness(context)
    pkg_root = output_dir / "external_help_package"
    pkg_root.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    request = _build_request_json(context, readiness)
    (pkg_root / "request.json").write_text(
        json.dumps(request, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written.append("request.json")

    (pkg_root / "SUMMARY.md").write_text(
        _render_summary(context, readiness),
        encoding="utf-8",
    )
    written.append("SUMMARY.md")

    manifest_json = _build_context_manifest_json(context, readiness)
    (pkg_root / "CONTEXT_MANIFEST.json").write_text(
        json.dumps(manifest_json, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written.append("CONTEXT_MANIFEST.json")

    for slot, filename in sorted(SLOT_TO_FILENAME.items()):
        slot_meta = context.manifest.slots.get(slot) or {
            "status": "UNKNOWN",
            "reason": "NOT_FOUND",
        }
        (pkg_root / filename).write_text(
            _render_slot_markdown(context, slot, slot_meta),
            encoding="utf-8",
        )
        written.append(filename)

    (pkg_root / "UNKNOWN_AND_MISSING.md").write_text(
        _render_unknown_and_missing(context),
        encoding="utf-8",
    )
    written.append("UNKNOWN_AND_MISSING.md")

    try:
        package_dir_str = str(pkg_root.relative_to(root)).replace("\\", "/")
    except ValueError:
        package_dir_str = str(pkg_root)

    unknown_entries = _collect_unknown_entries(context)
    return ExternalHelpPackageResult(
        tool_id=context.tool_id,
        package_dir=package_dir_str,
        readiness=readiness,
        context_status=context.status,
        missing_p0=list(context.missing_slots),
        files_written=sorted(written),
        unknown_count=sum(1 for e in unknown_entries if e.get("status") == "UNKNOWN"),
        reference_only_count=sum(
            1 for e in unknown_entries if e.get("status") == "REFERENCE_ONLY"
        ),
        excluded_count=len(context.excluded_files),
        warnings=list(context.warnings),
    )
