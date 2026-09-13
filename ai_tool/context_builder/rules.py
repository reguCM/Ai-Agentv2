from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.context_builder.identity import ToolIdentity
from ai_tool.context_builder.models import Priority, SelectedFile
from ai_tool.context_builder.sensitive import exclusion_reason, is_sensitive_path


def load_selection_rules(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "docs" / "ai_tool" / "context_builder" / "selection_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))


def collect_file_candidates(
    identity: ToolIdentity,
    rules: dict[str, Any],
) -> list[SelectedFile]:
    """Mechanically collect candidate files with slot, reason, priority."""
    candidates: list[SelectedFile] = []
    seen: set[tuple[str, str]] = set()

    def add(
        path: str,
        slot: str,
        reason: str,
        priority: Priority,
        *,
        content_status: str = "NOT_FETCHED",
    ) -> None:
        key = (path, slot)
        if key in seen:
            return
        seen.add(key)
        ex = exclusion_reason(path)
        status = "EXCLUDED_SENSITIVE" if ex else content_status
        candidates.append(
            SelectedFile(
                path=path.replace("\\", "/"),
                slot=slot,
                reason=reason,
                priority=priority,
                content_status=status,  # type: ignore[arg-type]
            )
        )

    global_docs = rules.get("global_documents") or {}
    for priority_key, entries in global_docs.items():
        priority: Priority = priority_key if priority_key in ("P0", "P1", "P2") else "P1"
        for entry in entries:
            add(entry["path"], entry["slot"], entry["reason"], priority)

    tool_rules = (rules.get("tool_specific") or {}).get(identity.canonical_id) or {}
    if identity.spec_path:
        add(identity.spec_path, "specification", "TOOL_SPECIFICATION", "P0")

    for priority_key in ("P0", "P1", "P2"):
        for entry in tool_rules.get(priority_key) or []:
            add(entry["path"], entry["slot"], entry["reason"], priority_key)  # type: ignore[arg-type]

    refs = tool_rules.get("reference_only") or {}
    impl = refs.get("implementation")
    if impl:
        ex = exclusion_reason(impl)
        candidates.append(
            SelectedFile(
                path=str(impl).replace("\\", "/"),
                slot="implementation",
                reason="REGISTRY_OR_SPEC_MODULE",
                priority="P0",
                content_status="EXCLUDED_SENSITIVE" if ex else "EXCLUDED_OUTSIDE_ALLOWLIST",
                error=None if not ex else ex,
            )
        )
    tests_ref = refs.get("tests")
    if tests_ref:
        ex = exclusion_reason(str(tests_ref))
        candidates.append(
            SelectedFile(
                path=str(tests_ref).replace("\\", "/"),
                slot="tests",
                reason="MAPPING_TEST_REFERENCE",
                priority="P0",
                content_status="EXCLUDED_SENSITIVE" if ex else "EXCLUDED_OUTSIDE_ALLOWLIST",
            )
        )

    candidates.sort(key=lambda f: (f.priority, f.slot, f.path))
    return candidates
