"""Definition-first routing for project-specific identifiers."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_PATH = REPO_ROOT / "registry" / "workspace_concepts.json"
RESOLUTION_STATUSES = {"NOT_NEEDED", "RESOLVING", "RESOLVED", "NOT_FOUND"}
_IDENTIFIER = re.compile(
    r"(?<![A-Za-z0-9_/])(?:[a-z][a-z0-9]*\.)?[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![A-Za-z0-9_/])"
)
_DEFINITION_INTENT = re.compile(
    r"(?:とは|意味|定義|何を表|何を数|what\s+is|meaning|definition)", re.I
)


@dataclass
class ConceptResolution:
    detected: bool = False
    concept: str | None = None
    resolution_status: str = "NOT_NEEDED"
    index_hit: bool = False
    category: str | None = None
    look_first: list[str] = field(default_factory=list)
    files_checked: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    resolved_definition: str | None = None
    returned_to_original_task: bool = False
    fallback_tool: str | None = None
    deferred_conditions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_workspace_index(path: Path = DEFAULT_INDEX_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for group in ("capabilities", "categories", "concepts"):
        for item in (payload.get(group) or {}).values():
            paths = [str(value) for value in item.get("look_first") or []]
            missing = [value for value in paths if not (REPO_ROOT / value).is_file()]
            if missing:
                raise ValueError(f"workspace concept index contains missing paths: {missing}")
    return payload


def detect_unknown_concept(
    request: str,
    *,
    index: Mapping[str, Any] | None = None,
    known_identifiers: set[str] | None = None,
) -> ConceptResolution:
    catalog = dict(index or load_workspace_index())
    concepts = catalog.get("concepts") or {}
    known = {item.casefold() for item in (known_identifiers or set())}
    request_text = (request or "").casefold()
    identifiers = [
        item
        for item in dict.fromkeys(_IDENTIFIER.findall(request_text))
        if item not in known and item.rsplit(".", 1)[-1] not in known
        # A user-chosen file name (for example ``hello_test.txt``) is a
        # mutation target, not a project-specific Runtime concept.  The
        # identifier regexp intentionally stops before the extension, so
        # exclude that lexical form explicitly before definition-first routing.
        and not re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(item)}\.[A-Za-z0-9]{{1,16}}(?![A-Za-z0-9_])",
            request_text,
        )
    ]
    # Plain concept names such as ``evidence`` are considered only in an
    # explicit definition question. This avoids treating ordinary prose as an
    # unknown-concept request while still making indexed concepts discoverable.
    if _DEFINITION_INTENT.search(request_text):
        for concept in concepts:
            if concept.casefold() in known:
                continue
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(concept.casefold())}(?![A-Za-z0-9_])", request_text):
                identifiers.append(concept.casefold())
    identifiers = list(dict.fromkeys(identifiers))
    if not identifiers:
        return ConceptResolution()
    selected = next(
        (item for item in identifiers if item in concepts or item.rsplit(".", 1)[-1] in concepts),
        identifiers[0],
    )
    key = selected if selected in concepts else selected.rsplit(".", 1)[-1]
    entry = concepts.get(key)
    if entry:
        return ConceptResolution(
            detected=True,
            concept=selected,
            resolution_status="RESOLVING",
            index_hit=True,
            category=str(entry.get("category") or "") or None,
            look_first=list(entry.get("look_first") or []),
            search_terms=list(entry.get("search_terms") or [key]),
            fallback_tool="read_file",
        )
    prefix = selected.split(".", 1)[0] if "." in selected else None
    category = prefix if prefix in (catalog.get("categories") or {}) else None
    category_entry = (catalog.get("categories") or {}).get(category) or {}
    return ConceptResolution(
        detected=True,
        concept=selected,
        resolution_status="RESOLVING",
        index_hit=False,
        category=category,
        look_first=list(category_entry.get("look_first") or []),
        search_terms=[selected, selected.rsplit(".", 1)[-1]],
        fallback_tool="read_file" if category_entry.get("look_first") else "search_files",
    )


def definition_conditions(resolution: ConceptResolution) -> list[str]:
    if not resolution.detected or not resolution.concept:
        return []
    if resolution.look_first:
        return [
            f"{resolution.concept}について{path}の定義・更新箇所が確認できている"
            for path in resolution.look_first
        ]
    return [f"{resolution.concept}のWorkspace内の定義・更新箇所が確認できている"]


def filter_definition_first_conditions(
    conditions: list[str], resolution: ConceptResolution
) -> list[str]:
    """Defer causal guesses about an unresolved concept, preserving outcomes."""
    if not resolution.detected or not resolution.concept:
        return list(conditions)
    leaf = resolution.concept.rsplit(".", 1)[-1].casefold()
    speculative = re.compile(r"(bug|原因|未登録|呼ばれていない|壊れて|誤動作)", re.I)
    accepted: list[str] = []
    for condition in conditions:
        if leaf in condition.casefold() and speculative.search(condition):
            resolution.deferred_conditions.append(condition)
        else:
            accepted.append(condition)
    return accepted


def apply_concept_guidance_to_requirements(
    requirement: Any,
    resolution: ConceptResolution,
) -> Any:
    """Replace LLM-guessed source names with verified index paths.

    Only Tool Gap errors produced by those unverified hints are suppressed;
    all unrelated validation states remain authoritative.
    """
    if not resolution.detected or not resolution.concept:
        return requirement
    leaf = resolution.concept.rsplit(".", 1)[-1].casefold()
    relevant = [
        row
        for row in getattr(requirement, "conditions", [])
        if leaf in str(getattr(row, "description", "")).casefold()
    ]
    for index, row in enumerate(relevant):
        if resolution.look_first:
            row.source_hint = resolution.look_first[min(index, len(resolution.look_first) - 1)]
            row.source_hint_certainty = "CONFIRMED"
            row.action_hint = f"read_fileで{row.source_hint}を確認"
        else:
            row.source_hint = "search_files"
            row.source_hint_certainty = "OBSERVED"
            row.action_hint = f"search_filesで{resolution.search_terms[0]}を完全一致検索"
    errors = list(getattr(requirement, "validator_errors", []) or [])
    non_gap_errors = [item for item in errors if ":tool_gap:" not in item]
    if getattr(requirement, "status", None) == "TOOL_GAP" and not non_gap_errors:
        requirement.status = "READY"
        requirement.validator_errors = ["definition_first:tool_gap_suppressed"]
        requirement.clarification = None
    return requirement


def next_definition_action(resolution: ConceptResolution) -> tuple[str, dict[str, str]] | None:
    if resolution.resolution_status == "NOT_FOUND":
        return None
    for path in resolution.look_first:
        if path not in resolution.files_checked:
            return "read_file", {"path": path}
    if resolution.resolution_status != "RESOLVED" and resolution.search_terms:
        return "search_files", {"query": resolution.search_terms[0], "path": "."}
    return None


def definition_hint(resolution: ConceptResolution) -> str:
    action = next_definition_action(resolution)
    if action is None:
        if resolution.resolution_status == "RESOLVED":
            return (
                "Definition First resolution is complete. Use these observed Workspace facts "
                "in the original Task and do not contradict them:\n"
                + json.dumps(
                    {
                        "concept": resolution.concept,
                        "resolution_status": resolution.resolution_status,
                        "files_checked": resolution.files_checked,
                        "evidence_ids": resolution.evidence_ids,
                        "resolved_definition": resolution.resolved_definition,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        if resolution.resolution_status == "NOT_FOUND":
            return (
                f"Definition First could not find {resolution.concept}. "
                "Keep its meaning unresolved and do not infer a Tool Gap from that fact alone."
            )
        return ""
    tool, arguments = action
    return (
        "Definition First: the project-specific concept below is not yet authoritative. "
        "Do not infer its meaning, create a cause hypothesis, or report a Tool Gap. "
        "Use the indicated read-only Tool before continuing the original Task.\n"
        + json.dumps(
            {
                "concept": resolution.concept,
                "resolution_status": resolution.resolution_status,
                "index_hit": resolution.index_hit,
                "category": resolution.category,
                "look_first": resolution.look_first,
                "search_terms": resolution.search_terms,
                "next_tool": tool,
                "next_arguments": arguments,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def observe_definition_result(
    resolution: ConceptResolution,
    *,
    tool_name: str,
    arguments: Mapping[str, Any],
    content: str,
) -> str | None:
    target = str(arguments.get("path") or "")
    if tool_name == "read_file" and target in resolution.look_first:
        if target not in resolution.files_checked:
            resolution.files_checked.append(target)
    elif tool_name == "search_files" and any(
        term.casefold() in str(arguments.get("query") or "").casefold()
        for term in resolution.search_terms
    ):
        marker = f"search:{arguments.get('query')}"
        if marker not in resolution.files_checked:
            resolution.files_checked.append(marker)
    matching_lines = [
        line.strip()
        for line in str(content or "").splitlines()
        if any(term.casefold() in line.casefold() for term in resolution.search_terms)
    ]
    excerpt = "\n".join(matching_lines[:12])[:3000] or None
    if excerpt:
        existing = str(resolution.resolved_definition or "")
        resolution.resolved_definition = "\n".join(
            dict.fromkeys([item for item in (existing, excerpt) if item])
        )[:6000]
    checked_all = bool(resolution.look_first) and all(
        path in resolution.files_checked for path in resolution.look_first
    )
    if checked_all and excerpt:
        resolution.resolution_status = "RESOLVED"
    elif not resolution.look_first and tool_name == "search_files":
        # A search hit is an address, not definition evidence. The caller may
        # promote verified hit paths to ``look_first``; without one the concept
        # remains unresolved rather than being inferred from a search snippet.
        resolution.resolution_status = "NOT_FOUND"
    else:
        resolution.resolution_status = "RESOLVING"
    return excerpt


__all__ = [
    "ConceptResolution",
    "definition_conditions",
    "definition_hint",
    "filter_definition_first_conditions",
    "apply_concept_guidance_to_requirements",
    "detect_unknown_concept",
    "load_workspace_index",
    "next_definition_action",
    "observe_definition_result",
]
