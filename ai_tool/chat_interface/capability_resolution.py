"""H4 Core: request -> Index capabilities -> Registry/Help Tool resolution."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Iterable, Mapping

from ai_tool.chat_interface.workspace_read_bridge import runtime_initial_read_arguments
from tools.system.tool_contract import canonical_tool_name, registry_entry_to_ollama_parameters


CAPABILITY_STATUSES = {
    "NOT_NEEDED",
    "RESOLVING",
    "RESOLVED",
    "CANDIDATES_AVAILABLE",
    "NO_MATCH",
    "TOOL_GAP_CONFIRMED",
}

_WORKSPACE_PATH = re.compile(r"(?<![\w/])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)")
_WORKSPACE_FILE_NAME = re.compile(
    r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_-]+\.[A-Za-z0-9]{1,16})(?![A-Za-z0-9_.-])"
)
# Same filename shape as _WORKSPACE_FILE_NAME. list_files path must be a directory.
_LIST_FILES_FILE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,16}$")
_URI = re.compile(r"https?://[^\s<>\"']+", re.I)
_SEARCH_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_QUOTED = re.compile(r"[\"「]([^\"」]{1,80})[\"」]")
# Provisional heuristic (C): unique object of 「を検索」 in Goal/State prose.
# Latin/path token or quotes immediately before を検索. Not a Grid allowlist.
_SEARCH_OBJECT = re.compile(
    r"(?:[\"「]([^\"」]{1,80})[\"」]|([A-Za-z][A-Za-z0-9_.-]{0,79}))を検索"
)
_LABELED_SECTION = re.compile(
    r"(?ms)^(Goal|Current State):\s*\n(.*?)(?=\n(?:Goal|Current State|Next need|現在の未解決点):|\Z)"
)
_WRITE_SIDE_EFFECTS = {"sandbox-write", "write"}
_REGISTRY_READ = "registry_read"


class MultipleCapabilitiesError(ValueError):
    """Singular compat API received two or more capabilities."""


@dataclass
class CapabilityResolution:
    required_capability: str | None = None
    source_task_id: str | None = None
    status: str = "NOT_NEEDED"
    capability_index_checked: bool = False
    registry_checked: bool = False
    candidate_tools: list[str] = field(default_factory=list)
    selected_tool: str | None = None
    rejection_reasons: list[dict[str, str]] = field(default_factory=list)
    tool_gap_confirmed: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    existing_candidates: list[str] = field(default_factory=list)
    missing_capability: str | None = None
    suggested_minimal_tool: str | None = None
    requires_human_approval: bool = False
    next_action: dict[str, Any] | None = None
    resolved_arguments: dict[str, Any] = field(default_factory=dict)
    unresolved_arguments: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _task_text(task: Any) -> str:
    return " ".join(
        str(value or "")
        for value in (getattr(task, "title", None), getattr(task, "instruction", None))
    )


def _request_body_text(task: Any) -> str:
    """User Goal/State blob. Do not prepend orchestrator English titles."""
    instruction = str(getattr(task, "instruction", None) or "").strip()
    if instruction:
        return instruction
    return str(getattr(task, "title", None) or "").strip()


def _confirmed_goal_state_text(text: str) -> str:
    labeled = [
        (str(match.group(1)), str(match.group(2)).strip())
        for match in _LABELED_SECTION.finditer(text or "")
        if str(match.group(2)).strip()
    ]
    if labeled:
        return "\n".join(body for _name, body in labeled)
    return str(text or "").strip()


def _literal_search_object(text: str) -> str | None:
    """Return the unique を検索 object if it is a literal substring of text."""
    found: list[str] = []
    for match in _SEARCH_OBJECT.finditer(text or ""):
        value = str(match.group(1) or match.group(2) or "").strip()
        if value and value in text:
            found.append(value)
    unique = list(dict.fromkeys(found))
    if len(unique) != 1:
        return None
    return unique[0]


def _confirmed_search_query(task: Any) -> str | None:
    return _literal_search_object(_confirmed_goal_state_text(_request_body_text(task)))


def _is_latin_keyword(keyword: str) -> bool:
    return bool(keyword) and all(ord(char) < 128 for char in keyword)


def _keyword_spans(text: str, keyword: str) -> list[tuple[int, int]]:
    if not text or not keyword:
        return []
    if _is_latin_keyword(keyword):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(keyword)}(?![A-Za-z0-9_])", re.I)
        return [(match.start(), match.end()) for match in pattern.finditer(text)]
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = text.find(keyword, start)
        if index < 0:
            return spans
        spans.append((index, index + len(keyword)))
        start = index + 1


def _exclusion_spans(text: str, tokens: Iterable[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for token in tokens:
        token = str(token or "").strip()
        if not token:
            continue
        spans.extend(_keyword_spans(text, token))
    return spans


def _overlaps(span: tuple[int, int], others: Iterable[tuple[int, int]]) -> bool:
    left, right = span
    for other_left, other_right in others:
        if left < other_right and right > other_left:
            return True
    return False


def _file_marker_span(match: tuple[int, int], text: str) -> tuple[int, int]:
    start, end = match
    marker = "ファイル"
    relative = text.find(marker, start, end)
    if relative >= 0:
        return (relative, relative + len(marker))
    return match


def _classifier_config(index: Mapping[str, Any]) -> Mapping[str, Any]:
    config = index.get("classifier")
    return config if isinstance(config, Mapping) else {}


def _capability_specs(index: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = index.get("capabilities") or {}
    return {str(name): spec for name, spec in raw.items() if isinstance(spec, Mapping)}


def _tool_index_capabilities(index: Mapping[str, Any]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for capability, spec in _capability_specs(index).items():
        for raw in spec.get("tools") or []:
            name = str(raw).strip()
            if name:
                mapping.setdefault(name, set()).add(capability)
    return mapping


def _entry_capabilities(entry: Mapping[str, Any], index: Mapping[str, Any]) -> set[str]:
    name = canonical_tool_name(entry)
    values = {str(item) for item in entry.get("capabilities") or []}
    for capability, spec in _capability_specs(index).items():
        if name in (spec.get("tools") or []):
            values.add(str(capability))
    return values


def _available(entry: Mapping[str, Any]) -> tuple[bool, str | None]:
    if entry.get("visibility") != "agent":
        return False, "visibility_not_agent"
    if str(entry.get("status") or "active").casefold() in {"disabled", "inactive", "deprecated"}:
        return False, "status_not_active"
    if not canonical_tool_name(entry):
        return False, "name_missing"
    if not isinstance(entry.get("function"), Mapping) and (
        not entry.get("module") or not entry.get("function") or not isinstance(entry.get("input", {}), Mapping)
    ):
        return False, "schema_or_implementation_missing"
    return True, None


def _is_write_entry(entry: Mapping[str, Any]) -> bool:
    side = str(entry.get("side_effect") or "").strip().casefold()
    if side in _WRITE_SIDE_EFFECTS:
        return True
    security = entry.get("security")
    if isinstance(security, Mapping) and security.get("dedicated_sandbox_required"):
        return True
    return False


def _write_side_capabilities(
    index: Mapping[str, Any], registry_tools: Iterable[Mapping[str, Any]]
) -> set[str]:
    names: set[str] = set()
    by_name = {canonical_tool_name(entry): entry for entry in registry_tools}
    for capability, spec in _capability_specs(index).items():
        tools = [str(item) for item in spec.get("tools") or [] if str(item).strip()]
        if not tools:
            continue
        if any(_is_write_entry(by_name[name]) for name in tools if name in by_name):
            names.add(capability)
    demotes = _classifier_config(index).get("audit_demotes_capabilities") or []
    for item in demotes:
        names.add(str(item))
    return names


def _look_first_selectable(index: Mapping[str, Any], capability: str, registry_by_name: Mapping[str, Mapping[str, Any]]) -> bool:
    if capability == _REGISTRY_READ:
        return True
    spec = _capability_specs(index).get(capability) or {}
    tools = [str(item) for item in spec.get("tools") or [] if str(item).strip()]
    if not tools:
        return False
    return not any(
        _is_write_entry(registry_by_name[name])
        for name in tools
        if name in registry_by_name
    )


def _look_first_mentioned(text: str, paths: Iterable[str]) -> list[str]:
    mentioned: list[str] = []
    folded = text.casefold()
    for raw in paths:
        path = str(raw or "").strip().replace("\\", "/")
        if not path:
            continue
        if path.casefold() in folded:
            mentioned.append(path)
            continue
        filename = path.rsplit("/", 1)[-1]
        if "." in filename and filename.casefold() in folded:
            mentioned.append(path)
            continue
        first = path.split("/", 1)[0]
        if len(first) >= 3 and _keyword_spans(text, first):
            mentioned.append(path)
    return mentioned


def _text_without_uris(text: str) -> str:
    return _URI.sub(" ", text)


def _has_path_form(text: str) -> bool:
    stripped = _text_without_uris(text)
    return bool(_WORKSPACE_PATH.search(stripped) or _WORKSPACE_FILE_NAME.search(stripped))


def _path_from_request(text: str, spec: Mapping[str, Any]) -> str | None:
    stripped = _text_without_uris(text)
    match = _WORKSPACE_PATH.search(stripped) or _WORKSPACE_FILE_NAME.search(stripped)
    if match:
        return match.group(1).strip("`'\"")
    mentioned = _look_first_mentioned(stripped, spec.get("look_first") or [])
    if mentioned:
        return mentioned[0]
    return None


def list_files_directory_path(path: str | None) -> str:
    """list_files requires a directory. A request filename is not a listing root.

    README.md → . ; docs/README.md → docs. Hidden dirs like .agents stay as-is.
    """
    raw = str(path or "").replace("\\", "/").strip().strip("/")
    if not raw or raw == ".":
        return "."
    last = raw.rsplit("/", 1)[-1]
    if not _LIST_FILES_FILE_SEGMENT.fullmatch(last):
        return raw
    parent = raw[: -len(last)].rstrip("/")
    return parent or "."


def confirmed_read_path_grounds(
    text: str,
    *,
    capability_index: Mapping[str, Any] | None = None,
    registry_tools: Iterable[Mapping[str, Any]] | None = None,
    extra_paths: Iterable[str] = (),
    include_look_first: bool = True,
) -> list[str]:
    """Q25 path/filename forms in text. Not ranking and not look_first[0] default.

    Request text also includes read-only capability look_first paths actually
    mentioned (Q25). Observation/Evidence text should pass include_look_first=False
    so Index look_first is not treated as a Goal ground. Write/execution
    look_first is ignored (Q26). Concept look_first is a different layer (Q46).
    """
    from ai_tool.chat_interface.concept_resolution import load_workspace_index

    index = dict(capability_index or load_workspace_index())
    if registry_tools is None:
        from ai_tool.agent_integration.experimental_exposure import load_registry_tools

        registry_rows = list(load_registry_tools())
    else:
        registry_rows = list(registry_tools)
    registry_by_name = {
        canonical_tool_name(row): row
        for row in registry_rows
        if canonical_tool_name(row)
    }
    stripped = _text_without_uris(text or "")
    grounds: list[str] = []

    def add(path: str) -> None:
        normalized = str(path).replace("\\", "/").strip().strip("`'\"" )
        if not normalized or normalized == ".":
            return
        if normalized not in grounds:
            grounds.append(normalized)

    for match in _WORKSPACE_PATH.finditer(stripped):
        add(match.group(1))
    for match in _WORKSPACE_FILE_NAME.finditer(stripped):
        add(match.group(1))
    if include_look_first:
        for capability, spec in _capability_specs(index).items():
            if not _look_first_selectable(index, capability, registry_by_name):
                continue
            for path in _look_first_mentioned(stripped, spec.get("look_first") or []):
                add(path)
    for path in extra_paths:
        add(str(path))
    return grounds


def _help_describes_available(name: str) -> bool:
    from ai_tool.help.api import describe

    for tool_id in (name, f"local:{name}"):
        result = describe(tool_id)
        if not result.get("ok"):
            continue
        card = result.get("tool")
        if isinstance(card, Mapping) and card.get("agent_available", True):
            return True
    return False


def _tool_family(entry: Mapping[str, Any]) -> tuple[str, str]:
    return (str(entry.get("category") or ""), str(entry.get("subcategory") or ""))


def required_capabilities(
    task: Any,
    *,
    expectation: Any = None,
    capability_index: Mapping[str, Any] | None = None,
    registry_tools: Iterable[Mapping[str, Any]] | None = None,
) -> list[str]:
    """Return Index capability ids mechanically required by the request."""
    from ai_tool.chat_interface.concept_resolution import load_workspace_index

    index = dict(capability_index or load_workspace_index())
    expected = getattr(expectation, "required_capability", None)
    if expected and expected != "workspace_definition_lookup":
        return [str(expected)]
    if registry_tools is None:
        from ai_tool.agent_integration.experimental_exposure import load_registry_tools

        registry_rows = list(load_registry_tools())
    else:
        registry_rows = list(registry_tools)
    text = _task_text(task)
    selected = _classify_capabilities(text, index, registry_rows)
    return selected


def infer_required_capability(
    task: Any,
    *,
    expectation: Any = None,
    capability_index: Mapping[str, Any] | None = None,
    registry_tools: Iterable[Mapping[str, Any]] | None = None,
) -> str | None:
    """Compat wrapper: 0→None, 1→value, 2+→error. Core internals must not call this."""
    found = required_capabilities(
        task,
        expectation=expectation,
        capability_index=capability_index,
        registry_tools=registry_tools,
    )
    if not found:
        return None
    if len(found) == 1:
        return found[0]
    raise MultipleCapabilitiesError(
        "required_capabilities returned multiple ids; singular API cannot fold them: "
        + ", ".join(found)
    )


def _classify_capabilities(
    text: str,
    index: Mapping[str, Any],
    registry_rows: list[Mapping[str, Any]],
) -> list[str]:
    config = _classifier_config(index)
    exclusion_tokens = list(
        ((config.get("match_exclusions") or {}) if isinstance(config.get("match_exclusions"), Mapping) else {}).get(
            "japanese_file_object_tokens"
        )
        or []
    )
    excluded = _exclusion_spans(text, exclusion_tokens)
    write_caps = _write_side_capabilities(index, registry_rows)
    tool_to_caps = _tool_index_capabilities(index)
    registry_by_name = {canonical_tool_name(entry): entry for entry in registry_rows}
    hits: dict[str, list[dict[str, Any]]] = {}
    keyword_families: dict[str, set[tuple[str, str]]] = {}

    for entry in registry_rows:
        name = canonical_tool_name(entry)
        caps = _entry_capabilities(entry, index)
        if not caps:
            continue
        family = _tool_family(entry)
        for raw in entry.get("keywords") or []:
            keyword = str(raw or "").strip()
            if not keyword:
                continue
            spans = _keyword_spans(text, keyword)
            if not spans:
                continue
            keyword_families.setdefault(keyword.casefold(), set()).add(family)
            for span in spans:
                file_span = _file_marker_span(span, text)
                excluded_hit = _overlaps(file_span, excluded) and "ファイル" in keyword
                for capability in caps:
                    if capability == _REGISTRY_READ:
                        continue
                    hits.setdefault(capability, []).append(
                        {
                            "keyword": keyword,
                            "tool": name,
                            "family": family,
                            "excluded": excluded_hit,
                            "span": span,
                        }
                    )

    file_object = False
    for capability, rows in hits.items():
        if capability in write_caps:
            continue
        for row in rows:
            if row["keyword"] in {"ファイル", "file"} and not row["excluded"]:
                file_object = True
    if _has_path_form(text):
        file_object = True

    for capability in list(hits):
        if capability not in write_caps:
            continue
        rows = [row for row in hits[capability] if not row["excluded"]]
        has_intent = bool(rows)
        phrase_object = any("ファイル" in str(row["keyword"]) for row in rows)
        if not (has_intent and (file_object or phrase_object)):
            hits.pop(capability, None)
        else:
            hits[capability] = rows

    if _has_path_form(text) and "workspace_file_read" not in hits:
        hits["workspace_file_read"] = []

    if _URI.search(text):
        for entry in registry_rows:
            schema = entry.get("input")
            if not isinstance(schema, Mapping):
                continue
            if any(str(key).casefold() == "url" for key in schema):
                for capability in _entry_capabilities(entry, index):
                    if capability != _REGISTRY_READ:
                        hits.setdefault(capability, [])

    audit_intent = any(_keyword_spans(text, str(token)) for token in (config.get("audit_intent") or []))
    demote = set(str(item) for item in (config.get("audit_demotes_capabilities") or []))
    if audit_intent:
        for capability in list(hits):
            if capability in demote:
                hits.pop(capability, None)

    look_first_caps: list[str] = []
    for capability, spec in _capability_specs(index).items():
        if not _look_first_selectable(index, capability, registry_by_name):
            continue
        mentioned = _look_first_mentioned(text, spec.get("look_first") or [])
        if mentioned:
            look_first_caps.append(capability)

    if audit_intent and _REGISTRY_READ in look_first_caps:
        hits[_REGISTRY_READ] = hits.get(_REGISTRY_READ) or []
    elif not audit_intent:
        path_only = [name for name in look_first_caps if name != _REGISTRY_READ]
        for name in path_only:
            hits.setdefault(name, hits.get(name) or [])

    competing = {name: rows for name, rows in hits.items() if name in _capability_specs(index)}
    if not competing:
        return []

    keyword_owners: dict[str, set[str]] = {}
    for capability, rows in competing.items():
        for row in rows:
            key = str(row["keyword"]).casefold()
            if not key:
                continue
            keyword_owners.setdefault(key, set()).add(capability)

    def _cross_family(keyword: str) -> bool:
        families = keyword_families.get(keyword.casefold()) or set()
        categories = {item[0] for item in families}
        subcats = {item[1] for item in families}
        return len(categories) > 1 or len(subcats) > 1

    def _is_selecting(capability: str, keyword: str) -> bool:
        owners = keyword_owners.get(keyword.casefold()) or set()
        if len(owners) == 1:
            return True
        if not _cross_family(keyword):
            return False
        if file_object and capability == "workspace_file_search" and keyword.casefold() in {
            "検索", "search", "grep",
        }:
            return True
        return False

    def _has_intra_family_hit(capability: str, rows: list[dict[str, Any]]) -> bool:
        if capability == "workspace_file_read" and not rows:
            return True
        return any(
            not _cross_family(str(row["keyword"]))
            for row in rows
            if str(row.get("keyword") or "")
        )

    kept: set[str] = set()
    shared_only: set[str] = set()
    for capability, rows in competing.items():
        exclusive = [
            str(row["keyword"])
            for row in rows
            if str(row.get("keyword") or "") and _is_selecting(capability, str(row["keyword"]))
        ]
        if exclusive:
            kept.add(capability)
        elif _has_intra_family_hit(capability, rows):
            shared_only.add(capability)

    if _URI.search(text):
        for capability, spec in _capability_specs(index).items():
            for raw in spec.get("tools") or []:
                entry = registry_by_name.get(str(raw))
                if not isinstance(entry, Mapping):
                    continue
                schema = entry.get("input")
                if isinstance(schema, Mapping) and any(str(key).casefold() == "url" for key in schema):
                    kept.add(capability)

    remaining_shared = shared_only - kept
    if not kept:
        preferred = {
            name
            for name in remaining_shared
            if (_capability_specs(index).get(name) or {}).get("prefer_when_ambiguous")
            and _has_intra_family_hit(name, competing.get(name) or [])
        }
        kept.update(preferred)
        if not kept and "workspace_file_read" in remaining_shared:
            kept.add("workspace_file_read")
    if audit_intent and _REGISTRY_READ in look_first_caps:
        kept.add(_REGISTRY_READ)
    elif not kept and _REGISTRY_READ in remaining_shared and audit_intent:
        kept.add(_REGISTRY_READ)

    if file_object:
        kept.discard("web_search")

    # Cross-family shared keywords (e.g. 「検索」) previously dropped every
    # competing cap. Keep Index/Registry/Help-reachable candidates. If some of
    # those already have next_capability_action prep, skip selectable-but
    # unusable siblings instead of stalling on first-item choice.
    if not kept:
        reachable_tools = {
            capability: _available_tools_for_capability(
                capability, index, registry_rows
            )
            for capability in competing
        }
        reachable = [
            capability
            for capability, tools in reachable_tools.items()
            if tools
        ]
        preparable = [
            capability
            for capability in reachable
            if any(
                _tool_has_next_action_prep(name)
                for name in reachable_tools[capability]
            )
        ]
        kept.update(preparable or reachable)

    order = list(_capability_specs(index))
    return [name for name in order if name in kept]


def resolve_capabilities(
    task: Any,
    *,
    capability_index: Mapping[str, Any],
    registry_tools: Iterable[Mapping[str, Any]] | None,
    expectation: Any = None,
) -> list[CapabilityResolution]:
    caps = required_capabilities(
        task,
        expectation=expectation,
        capability_index=capability_index,
        registry_tools=registry_tools,
    )
    if not caps:
        return [CapabilityResolution(source_task_id=getattr(task, "task_id", None))]
    return [
        resolve_capability(
            task,
            capability=capability,
            capability_index=capability_index,
            registry_tools=registry_tools,
            expectation=expectation,
        )
        for capability in caps
    ]


def _available_tools_for_capability(
    capability: str,
    index: Mapping[str, Any],
    registry_rows: list[Mapping[str, Any]],
    *,
    result: CapabilityResolution | None = None,
) -> list[str]:
    """Index tools that Registry + Help currently expose as agent-available."""
    spec = _capability_specs(index).get(capability) or {}
    index_tool_names = {
        str(item).strip() for item in (spec.get("tools") or []) if str(item).strip()
    }
    candidates: list[str] = []
    for entry in registry_rows:
        if capability not in _entry_capabilities(entry, index):
            continue
        name = canonical_tool_name(entry)
        if result is not None:
            result.existing_candidates.append(name)
        available, reason = _available(entry)
        if not available:
            if result is not None and name:
                result.rejection_reasons.append({"tool": name, "reason": str(reason)})
            continue
        if name in index_tool_names and not _help_describes_available(name):
            if result is not None:
                result.rejection_reasons.append({"tool": name, "reason": "help_not_available"})
            continue
        candidates.append(name)
    return candidates


def _required_input_names(entry: Mapping[str, Any]) -> list[str]:
    parameters = registry_entry_to_ollama_parameters(dict(entry))
    return [str(name) for name in (parameters.get("required") or [])]


def _apply_selected_tool_parameters(
    result: CapabilityResolution,
    task: Any,
    spec: Mapping[str, Any],
    registry_rows: list[Mapping[str, Any]],
) -> None:
    """Record schema required params from confirmed Goal/State. Do not invent values."""
    tool = result.selected_tool
    if not tool:
        return
    entry = next(
        (row for row in registry_rows if canonical_tool_name(row) == tool),
        None,
    )
    if not isinstance(entry, Mapping):
        return
    text = _task_text(task)
    path = _path_from_request(text, spec)
    resolved: dict[str, Any] = {}
    schema = entry.get("input")
    has_path = isinstance(schema, Mapping) and "path" in schema
    # Reuse next_capability_action path defaults only; do not add new tool maps.
    if tool == "read_file":
        if path:
            resolved.update(runtime_initial_read_arguments(path))
    elif has_path and tool == "list_files":
        resolved["path"] = list_files_directory_path(path)
    elif has_path and tool == "search_files":
        resolved["path"] = path or "."
    if tool == "search_files":
        query = _confirmed_search_query(task)
        if query:
            resolved["query"] = query
    required = _required_input_names(entry)
    result.resolved_arguments = resolved
    result.unresolved_arguments = [name for name in required if name not in resolved]


def resolve_capability(
    task: Any,
    *,
    capability_index: Mapping[str, Any],
    registry_tools: Iterable[Mapping[str, Any]] | None,
    expectation: Any = None,
    capability: str | None = None,
) -> CapabilityResolution:
    if capability is None:
        found = required_capabilities(
            task,
            expectation=expectation,
            capability_index=capability_index,
            registry_tools=registry_tools,
        )
        if not found:
            return CapabilityResolution(source_task_id=getattr(task, "task_id", None))
        if len(found) > 1:
            raise MultipleCapabilitiesError(
                "resolve_capability cannot fold multiple capabilities: " + ", ".join(found)
            )
        capability = found[0]
    result = CapabilityResolution(
        required_capability=capability,
        source_task_id=getattr(task, "task_id", None),
        status="RESOLVING",
    )
    spec = (_capability_specs(capability_index).get(capability) or None)
    result.capability_index_checked = spec is not None
    if spec is None:
        result.status = "NO_MATCH"
        result.missing_capability = capability
        return result
    if registry_tools is None:
        result.status = "NO_MATCH"
        return result
    result.registry_checked = True
    registry_rows = list(registry_tools)
    result.candidate_tools = _available_tools_for_capability(
        capability, capability_index, registry_rows, result=result
    )
    if len(result.candidate_tools) == 1:
        result.selected_tool = result.candidate_tools[0]
        result.status = "RESOLVED"
    elif result.candidate_tools:
        result.status = "CANDIDATES_AVAILABLE"
    else:
        result.status = "NO_MATCH"
        result.missing_capability = capability
        result.suggested_minimal_tool = str(spec.get("suggested_minimal_tool") or "") or None
    _apply_selected_tool_parameters(result, task, spec, registry_rows)
    result.next_action = next_capability_action(result, task, spec)
    return result


def _tool_has_next_action_prep(tool: str) -> bool:
    """Whether next_capability_action already prepares this Registry tool.

    This is the existing Action-prep surface, not a search-intent map and not a
    claim that other tools are absent from Registry/Help.
    """
    return tool in {"read_file", "search_files", "list_files"}


def next_capability_action(
    resolution: CapabilityResolution, task: Any, spec: Mapping[str, Any]
) -> dict[str, Any] | None:
    if not resolution.selected_tool:
        return None
    text = _task_text(task)
    tool = resolution.selected_tool
    path = _path_from_request(text, spec)
    if tool == "read_file":
        if not path:
            return None
        return {
            "tool": tool,
            "arguments": runtime_initial_read_arguments(path),
        }
    if tool == "search_files":
        query = None
        resolved = resolution.resolved_arguments or {}
        if isinstance(resolved.get("query"), str) and resolved["query"].strip():
            query = str(resolved["query"]).strip()
        confirmed = _confirmed_goal_state_text(_request_body_text(task))
        if not query:
            query = _literal_search_object(confirmed)
        if not query:
            query = _search_query(confirmed)
        if not query:
            return None
        return {"tool": tool, "arguments": {"query": query, "path": path or "."}}
    if tool == "list_files":
        return {"tool": tool, "arguments": {"path": list_files_directory_path(path)}}
    return None


def _search_query(text: str) -> str | None:
    quoted = _QUOTED.search(text)
    if quoted:
        return quoted.group(1).strip()
    ident = next((word for word in _SEARCH_IDENT.findall(text) if "_" in word), None)
    if ident:
        return ident
    return None


def confirm_tool_gap(resolution: CapabilityResolution, evidence_id: str) -> CapabilityResolution:
    if not (
        resolution.required_capability
        and resolution.capability_index_checked
        and resolution.registry_checked
        and not resolution.candidate_tools
        and evidence_id
    ):
        return resolution
    resolution.evidence_ids.append(evidence_id)
    resolution.tool_gap_confirmed = True
    resolution.status = "TOOL_GAP_CONFIRMED"
    resolution.requires_human_approval = True
    return resolution


def capability_hint(resolution: CapabilityResolution) -> str:
    if resolution.status == "NOT_NEEDED":
        return ""
    payload = resolution.as_dict()
    if resolution.status == "TOOL_GAP_CONFIRMED":
        instruction = (
            "The required capability is confirmed absent from the agent-visible Registry. "
            "Do not invent or execute a Tool. Explain the evidence, propose only the minimal Tool, "
            "and stop for Human Approval."
        )
    elif resolution.next_action:
        instruction = (
            "Bridge the current Task to the indicated read-only action. Do not stop merely because "
            "a guessed Tool name was absent."
        )
    else:
        instruction = "Keep this capability unresolved; do not claim a Tool Gap."
    import json
    return f"Capability Resolution:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n{instruction}"


def detect_required_tool_gaps(
    task: Any,
    *,
    capability_index: Mapping[str, Any],
    registry_tools: Iterable[Mapping[str, Any]] | None,
    expectation: Any = None,
) -> list[CapabilityResolution]:
    from ai_tool.agent_integration.experimental_exposure import load_registry_tools

    caps = required_capabilities(
        task,
        expectation=expectation,
        capability_index=capability_index,
        registry_tools=load_registry_tools(),
    )
    gaps: list[CapabilityResolution] = []
    for capability in caps:
        item = resolve_capability(
            task,
            capability=capability,
            capability_index=capability_index,
            registry_tools=registry_tools,
            expectation=expectation,
        )
        if (
            item.required_capability
            and item.capability_index_checked
            and item.registry_checked
            and not item.candidate_tools
        ):
            gaps.append(item)
    return gaps


__all__ = [
    "CAPABILITY_STATUSES",
    "CapabilityResolution",
    "MultipleCapabilitiesError",
    "capability_hint",
    "confirm_tool_gap",
    "confirmed_read_path_grounds",
    "detect_required_tool_gaps",
    "infer_required_capability",
    "next_capability_action",
    "required_capabilities",
    "resolve_capabilities",
    "resolve_capability",
]
