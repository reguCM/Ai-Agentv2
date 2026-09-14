"""Minimal P2-16 bridge from a chat request to AgentTaskRuntime v1."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path, PureWindowsPath
import re
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

from ai_tool.chat_interface.concept_resolution import (
    ConceptResolution,
    definition_conditions,
    definition_hint,
    filter_definition_first_conditions,
    next_definition_action,
    observe_definition_result,
    load_workspace_index,
)
from ai_tool.chat_interface.capability_resolution import (
    CapabilityResolution,
    MultipleCapabilitiesError,
    capability_hint,
    confirm_tool_gap,
    confirmed_read_path_grounds,
    detect_required_tool_gaps,
    required_capabilities,
    resolve_capabilities,
)
from ai_tool.chat_interface.goal_completion_gate import (
    build_goal_completion_human,
    build_goal_completion_resume,
    format_goal_completion_human,
    needs_goal_completion_human,
)

from tools.ai.task_runtime import (
    ActionRecord,
    AgentTaskRuntime,
    ClaimRecord,
    EvidenceRecord,
    FailureRecord,
    GoalNode,
    GoalStatus,
    InformationCertainty,
    MutationRecord,
    ReplanRecord,
    TaskRecord,
    TaskStatus,
)
from tools.ai.sandbox_workspace import SandboxSession, sandbox_status_ja
from ai_tool.chat_interface.workspace_read_bridge import (
    READ_FILE_MAX_CONTINUATION_PAGES,
    prepare_tool_result_for_llm,
    read_file_llm_delivery,
    read_file_observation_complete,
    runtime_continuation_read_arguments,
    runtime_initial_read_arguments,
)
from tools.system.tool_contract import canonical_tool_name
from tools.file.workspace._paths import SEARCH_MAX_CONTINUATION_PAGES, path_error
from ai_tool.help.api import GENERIC_TOOL_SELECTION_RULE, describe, prefer_tool_for_capability


REPO_ROOT = Path(__file__).resolve().parents[2]


AGENT_CORE_PROMPT = (
    """
あなたは利用可能なToolとRuntime状態を使い、Goal達成へ進むLocal AI-Agentです。
環境・workspace・Repository・Tool状態に依存する事実は、確認可能なら推測せずToolで観測してください。
確認していないファイル、Tool、Registry、API、実装の存在を断定しないでください。
Tool Callの成功ではなく、Current TaskのCompletion Conditionで進捗を判断してください。
Tool Resultを見て次のActionを判断し、Current Goal / Current Taskから逸脱しないでください。
安全なread-only観測は、Goal達成に必要な範囲で進めて構いません。
"""
    + "\n\n"
    + GENERIC_TOOL_SELECTION_RULE
).strip()


_AGENT_TASK = re.compile(
    r"(調査|実装|修正|設計|確認|監査|計画|テスト|repository|workspace|tool|"
    r"investigate|implement|fix|design|audit|plan|test)",
    re.IGNORECASE,
)
_CREATION_INTENT = re.compile(
    r"(作って|作る|作成|作成して|build|create\b|implement\b)",
    re.IGNORECASE,
)

_GENERAL_KNOWLEDGE_REQUEST = re.compile(
    r"(?:一般知識|とは(?:何|どんな|どういう)|意味(?:は|を)|解説して|説明して)",
    re.IGNORECASE,
)


def has_creation_intent(text: str) -> bool:
    """True when the request is a make/build/create implementation, not mere observation."""
    return bool(_CREATION_INTENT.search(text or ""))


def is_agent_task(
    text: str,
    *,
    known_tool_names: Iterable[str] = (),
    agent_visible_tools: Iterable[Mapping[str, Any]] = (),
) -> bool:
    raw = text or ""
    if _AGENT_TASK.search(raw):
        return True
    if _CREATION_INTENT.search(raw):
        return True
    # An explicit reference to an actually agent-visible Tool is an execution
    # request boundary. Unknown snake_case identifiers do not qualify.
    if any(
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(str(name))}(?![A-Za-z0-9_])", raw)
        for name in known_tool_names
        if str(name).strip()
    ):
        return True
    # Registry keywords identify observable capabilities.  The small negative
    # boundary below identifies definition/explanation intent only; it is not
    # a second capability catalogue.
    if _GENERAL_KNOWLEDGE_REQUEST.search(raw):
        return False
    raw_low = raw.casefold()
    return any(
        tool.get("visibility") == "agent"
        and tool.get("observation_source") == "real"
        and any(
            str(keyword).strip().casefold() in raw_low
            for keyword in tool.get("keywords") or []
            if str(keyword).strip()
        )
        for tool in agent_visible_tools
    )


def _explicit_completion_conditions(request: str) -> list[str]:
    rows = re.findall(r"(?m)^\s*\d+[.)．]\s*(.+?)\s*$", request)
    return list(dict.fromkeys(row.strip() for row in rows if row.strip()))


def _result_text(result: Mapping[str, Any]) -> str:
    lines = result.get("lines")
    if isinstance(lines, list):
        return "\n".join(
            str(row.get("text") or "") if isinstance(row, Mapping) else str(row)
            for row in lines
        )
    for key in ("content", "text", "result", "output"):
        if result.get(key) is not None:
            return str(result[key])
    # Observation Tools often return facts as top-level scalar fields rather
    # than a text body. Keep the contract envelope out of Evidence content,
    # while preserving the measured values in a compact, generic form.
    observed = {
        str(key): value
        for key, value in result.items()
        if key not in {"ok", "status", "error", "warnings"}
        and value is not None
        and isinstance(value, (str, int, float, bool))
    }
    if observed:
        return json.dumps(observed, ensure_ascii=False, sort_keys=True)[:3000]
    return ""


def _condition_support(condition: str, content: str) -> str | None:
    low_condition = condition.casefold()
    low_content = content.casefold()
    anchors = [
        token
        for token in ("envelope", "status", "success", "partial", "failure")
        if token in low_condition
    ]
    if not anchors:
        return None
    anchor = anchors[0]
    required = {
        "envelope": ("ok", "status", "error", "warnings"),
        "status": ("success", "partial", "failure"),
        "success": ("### success",),
        "partial": ("### partial",),
        "failure": ("### failure",),
    }[anchor]
    if not all(token in low_content for token in required):
        return None
    content_anchor = anchor if anchor in low_content else required[0]
    lines = content.splitlines()
    indexes = [
        index for index, line in enumerate(lines) if content_anchor in line.casefold()
    ]
    if not indexes:
        return None
    start = max(0, indexes[0] - 2)
    end = min(len(lines), indexes[0] + 14)
    return "\n".join(lines[start:end])[:1500]


def _structured_condition_support(
    condition: str, tool_name: str, result: Mapping[str, Any], content: str
) -> str | None:
    """Match observed scalar fields to a condition without semantic guessing."""
    if not content:
        return None
    condition_low = condition.casefold()
    observed = {
        str(key).casefold(): value
        for key, value in result.items()
        if value is not None and isinstance(value, (str, int, float, bool))
    }
    aliases = {
        "datetime": ("datetime", "日時", "時刻", "current time", "現在時刻"),
        "timezone": ("timezone", "time zone", "タイムゾーン"),
        "formatted": ("formatted", "形式", "フォーマット"),
    }
    matched_field = any(
        key in observed and any(alias in condition_low for alias in field_aliases)
        for key, field_aliases in aliases.items()
    )
    measured_tool_result = bool(
        tool_name.casefold() in condition_low
        and observed.get("observation_source") == "real"
    )
    return content[:1500] if matched_field or measured_tool_result else None


def _read_file_condition_support(
    condition: str, path: str, content: str
) -> str | None:
    """Return only mechanically observed support from a successful file read."""
    if not content:
        return None
    condition_low = condition.casefold()
    content_low = content.casefold()
    path_low = path.casefold()
    basename = PureWindowsPath(path).name.casefold()
    mentions_target = bool(path_low and (path_low in condition_low or basename in condition_low))
    observation_words = (
        "read", "exist", "present", "available", "確認", "存在", "読", "取得",
    )
    if mentions_target and any(word in condition_low for word in observation_words):
        return content[:1500]

    # Preserve distinctive ASCII facts (for example ``P2-18 Safe Mutation
    # Tools``) without treating a generic request to summarize as satisfied.
    tokens = [
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,}", condition)
        if token.casefold() not in {"file", "read", "summary", "summarize", "content"}
        and token.casefold() not in {part.casefold() for part in PureWindowsPath(path).parts}
    ]
    # One generic token such as ``status`` is not enough to establish the
    # semantics requested by a Completion Condition.
    if len(tokens) >= 2 and all(token in content_low for token in tokens):
        return content[:1500]
    return None


def _search_matches(result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    matches = result.get("matches")
    return [item for item in matches if isinstance(item, Mapping)] if isinstance(matches, list) else []


def _search_path_arg(arguments: Mapping[str, Any]) -> str:
    raw = str(arguments.get("path") or ".").strip()
    return raw or "."


def _action_path_key(arguments: Mapping[str, Any] | None) -> str:
    raw = _normalize_rel_path(_search_path_arg(arguments or {}))
    while raw.startswith("./"):
        raw = raw[2:]
    return raw or "."


# Display truncation for hint() only. Not ranking and not a read-target allowlist.
SEARCH_CANDIDATE_HINT_PATH_LIMIT = 40
# Display truncation for Human Grill evidence only. Not ranking.
CONVERSATION_GRILL_SAMPLE_PATH_LIMIT = 8
CONVERSATION_GRILL_SEGMENT_LIMIT = 8
# Max NOT_EXECUTABLE conversions that still return the reason to the Agent
# for a different Need. Not a Human handoff. Provisional cap (C).
FOLLOWUP_CONVERSION_RETRY_LIMIT = 3
OBSERVED_MATCH_TEXT_LIMIT = 8
OBSERVED_MATCH_TEXT_CHARS = 240
_CLARIFICATION_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}")
_CLARIFICATION_CJK_TOKEN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]{2,}")
_CLARIFICATION_CJK_SPLIT = re.compile(r"[のはがをにへとでやも、。！？]+")


def _clarification_tokens(text: str) -> list[str]:
    stripped = str(text or "")
    tokens: list[str] = []

    def add(token: str) -> None:
        value = str(token or "").strip()
        if len(value) < 2 or value in tokens:
            return
        tokens.append(value.casefold() if re.fullmatch(r"[A-Za-z0-9_-]+", value) else value)

    for match in _CLARIFICATION_ASCII_TOKEN.finditer(stripped):
        add(match.group(0))
    for match in _CLARIFICATION_CJK_TOKEN.finditer(stripped):
        run = match.group(0)
        parts = [part for part in _CLARIFICATION_CJK_SPLIT.split(run) if part]
        cleaned: list[str] = []
        for part in parts:
            for suffix in ("でした", "ました", "です", "ます"):
                if part.endswith(suffix) and len(part) > len(suffix):
                    part = part[: -len(suffix)]
                    break
            if len(part) >= 2:
                cleaned.append(part)
        if cleaned:
            for part in cleaned:
                add(part)
        else:
            add(run)
    return tokens


def _fold_observed_match_texts(
    paths: Iterable[str],
    observed_match_texts: Mapping[str, Iterable[str]] | None,
) -> dict[str, list[str]]:
    allowed = {
        _normalize_rel_path(path)
        for path in paths
        if _normalize_rel_path(path)
    }
    folded: dict[str, list[str]] = {}
    for raw_path, rows in dict(observed_match_texts or {}).items():
        path = _normalize_rel_path(str(raw_path))
        if path not in allowed:
            continue
        texts: list[str] = []
        for item in rows or []:
            text = str(item or "").strip()[:OBSERVED_MATCH_TEXT_CHARS]
            if text and text not in texts:
                texts.append(text)
            if len(texts) >= OBSERVED_MATCH_TEXT_LIMIT:
                break
        if texts:
            folded[path] = texts
    return folded


def _path_identity_blobs(path: str) -> list[str]:
    normalized = _normalize_rel_path(path).casefold()
    blobs: list[str] = []
    if normalized:
        blobs.append(normalized)
    for segment in normalized.split("/"):
        if not segment:
            continue
        blobs.append(segment)
        stem, _sep, _ext = segment.rpartition(".")
        if stem:
            blobs.append(stem)
            blobs.extend(
                part
                for part in re.split(r"[_\-.]+", stem)
                if part
            )
    return list(dict.fromkeys(blobs))


def _token_matches_candidate(
    token: str,
    path: str,
    match_texts: Iterable[str],
) -> bool:
    needle = str(token or "").strip()
    if not needle:
        return False
    ascii_token = bool(re.fullmatch(r"[a-z0-9_-]+", needle))
    blobs = _path_identity_blobs(path)
    if needle in blobs:
        return True
    if ascii_token and len(needle) >= 3:
        if any(needle in blob for blob in blobs):
            return True
    elif (not ascii_token) and len(needle) >= 2:
        if any(needle in blob for blob in blobs):
            return True
    haystacks = [
        str(item or "").strip()
        for item in match_texts
        if str(item or "").strip()
    ]
    if ascii_token:
        return any(needle in item.casefold() for item in haystacks)
    return any(needle in item for item in haystacks)


def match_clarification_to_candidate_paths(
    text: str,
    candidate_paths: Iterable[str],
    *,
    observed_match_texts: Mapping[str, Iterable[str]] | None = None,
    ignore_tokens: Iterable[str] = (),
) -> list[str]:
    """Intersect a path-less clarification with preserved candidates.

    Tokens that match every candidate are not identity. Order is not ranking.
    """
    paths = [
        _normalize_rel_path(path)
        for path in dict.fromkeys(
            _normalize_rel_path(item) for item in candidate_paths
        )
        if _normalize_rel_path(path)
    ]
    if len(paths) < 2:
        return []
    ignored = {
        str(token or "").strip().casefold()
        for token in ignore_tokens
        if str(token or "").strip()
    }
    texts = {
        _normalize_rel_path(path): [
            str(item or "").strip()
            for item in (rows or [])
            if str(item or "").strip()
        ]
        for path, rows in dict(observed_match_texts or {}).items()
    }
    for path, rows in list(texts.items()):
        texts[path] = [
            item
            for item in rows
            if item.casefold() not in ignored
        ]
    union: list[str] = []
    for token in _clarification_tokens(text):
        if token.casefold() in ignored:
            continue
        matched = [
            path
            for path in paths
            if _token_matches_candidate(token, path, texts.get(path) or [])
        ]
        if not matched or len(matched) == len(paths):
            continue
        for path in matched:
            if path not in union:
                union.append(path)
    return union


def _first_path_segment(rel: str) -> str:
    normalized = str(rel).replace("\\", "/").strip()
    if not normalized:
        return ""
    return normalized.split("/")[0]


def fold_search_candidate_set(
    *,
    query: str,
    search_path: str,
    match_paths: Iterable[str],
    scan_complete: bool,
    page_count: int = 0,
    observed_match_texts: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """Fold substring hit paths into an observation. Does not select a read target."""
    rows = [str(path).replace("\\", "/").strip() for path in match_paths if str(path).strip()]
    counts = Counter(rows)
    unique = list(dict.fromkeys(rows))
    segments = Counter(_first_path_segment(path) for path in rows)
    unique_n = len(counts)
    if not scan_complete:
        cardinality = "INCOMPLETE_SCAN"
    elif unique_n == 0:
        cardinality = "NO_SUBSTRING_HITS"
    elif unique_n == 1:
        cardinality = "SINGLE_SUBSTRING_PATH"
    else:
        cardinality = "MULTIPLE_SUBSTRING_PATHS"
    return {
        "query": query,
        "path": search_path,
        "scan_complete": scan_complete,
        "page_count": int(page_count),
        "match_row_count": len(rows),
        "unique_path_count": unique_n,
        "matches_per_path": dict(counts),
        "matches_per_first_path_segment": dict(segments),
        "returned_paths_in_order": unique,
        "substring_cardinality": cardinality,
        "read_target_selected": None,
        "read_target_status": None,
        "read_target_reason": None,
        "confirmed_path_grounds": [],
        "matched_confirmed_paths": [],
        "unresolved_for_read": True,
        "observation_role": None,
        "observed_match_texts": _fold_observed_match_texts(
            unique, observed_match_texts
        ),
        "note": (
            "Substring hits are not Goal-target confirmation. "
            "unique_path_count is substring cardinality, not worth."
        ),
    }


def _normalize_rel_path(path: str) -> str:
    return str(path).replace("\\", "/").strip()


def _match_confirmed_paths_in_candidates(
    confirmed_paths: Iterable[str],
    candidate_paths: Iterable[str],
) -> list[str]:
    """Intersect Q25 grounds with observed hit paths. Order is not a selection key."""
    unique_candidates = [
        _normalize_rel_path(path)
        for path in dict.fromkeys(_normalize_rel_path(item) for item in candidate_paths)
        if _normalize_rel_path(path)
    ]
    by_name: dict[str, list[str]] = {}
    for path in unique_candidates:
        by_name.setdefault(path.rsplit("/", 1)[-1].casefold(), []).append(path)
    matched: list[str] = []

    def add(path: str) -> None:
        if path and path not in matched:
            matched.append(path)

    for raw in confirmed_paths:
        token = _normalize_rel_path(raw)
        if not token:
            continue
        if "/" in token:
            if token in unique_candidates:
                add(token)
            continue
        hits = by_name.get(token.casefold()) or []
        for path in hits:
            add(path)
    return matched


def resolve_search_read_target(
    candidate_set: Mapping[str, Any],
    confirmed_paths: Iterable[str],
) -> dict[str, Any]:
    """Decide read target from candidate set ∩ confirmed path grounds only.

    Substring uniqueness and returned_paths_in_order[0] are not grounds.
    """
    grounds = [
        _normalize_rel_path(path)
        for path in confirmed_paths
        if _normalize_rel_path(path)
    ]
    grounds = list(dict.fromkeys(grounds))
    resolved = dict(candidate_set)
    resolved["confirmed_path_grounds"] = grounds
    resolved["read_target_selected"] = None
    if not resolved.get("scan_complete"):
        resolved["read_target_status"] = "UNRESOLVED"
        resolved["read_target_reason"] = "SCAN_INCOMPLETE"
        resolved["matched_confirmed_paths"] = []
        resolved["unresolved_for_read"] = True
        return resolved
    unique_n = int(resolved.get("unique_path_count") or 0)
    if unique_n == 0:
        resolved["read_target_status"] = "UNRESOLVED"
        resolved["read_target_reason"] = "NO_SUBSTRING_HITS"
        resolved["matched_confirmed_paths"] = []
        resolved["unresolved_for_read"] = True
        return resolved
    if not grounds:
        resolved["read_target_status"] = "UNRESOLVED"
        resolved["read_target_reason"] = "NO_CONFIRMED_PATH_GROUND"
        resolved["matched_confirmed_paths"] = []
        resolved["unresolved_for_read"] = True
        return resolved
    matched = _match_confirmed_paths_in_candidates(
        grounds, resolved.get("returned_paths_in_order") or []
    )
    resolved["matched_confirmed_paths"] = matched
    if not matched:
        resolved["read_target_status"] = "UNRESOLVED"
        resolved["read_target_reason"] = "CONFIRMED_PATH_NOT_IN_CANDIDATES"
        resolved["unresolved_for_read"] = True
        return resolved
    if len(matched) > 1:
        resolved["read_target_status"] = "UNRESOLVED"
        resolved["read_target_reason"] = "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES"
        resolved["unresolved_for_read"] = True
        return resolved
    resolved["read_target_status"] = "SELECTED"
    resolved["read_target_reason"] = "CONFIRMED_UNIQUE_PATH_IN_CANDIDATES"
    resolved["read_target_selected"] = matched[0]
    resolved["unresolved_for_read"] = False
    return resolved


def empty_user_variable() -> dict[str, Any]:
    return {
        "interchangeability_status": "UNCONFIRMED",
        "candidates": [],
        "provisional_selected": None,
        "selection_rule": None,
        "replaceable_by": ["user_preference", "project_convention"],
        "source": None,
    }


def empty_goal_read_target() -> dict[str, Any]:
    return {
        "status": None,
        "reason": None,
        "selected": None,
        "confirmed_path_grounds": [],
        "matched_confirmed_paths": [],
        "source_queries": [],
        "request_path_grounds": [],
        "grill_answer_path_grounds": [],
        "observation_path_grounds": [],
        "excluded_proposed_paths": [],
        "ground_source": None,
        "uniqueness_cause": None,
        "uniqueness_class": None,
        "user_variable": empty_user_variable(),
        "close_status": None,
    }


def confirm_interchangeable_paths(
    identity_paths: Iterable[str],
    equivalent_sets: Iterable[Iterable[str]] | None,
) -> list[str]:
    """Confirm Goal-interchangeable paths. Substring hit cardinality is not a source.

    All identity paths must sit in one equivalent set, and there must be at least two.
    Partial overlap is not confirmation.
    """
    paths = [
        _normalize_rel_path(path)
        for path in dict.fromkeys(
            _normalize_rel_path(item) for item in identity_paths
        )
        if _normalize_rel_path(path)
    ]
    if len(paths) < 2:
        return []
    identity = frozenset(paths)
    for raw in equivalent_sets or []:
        equivalent = frozenset(
            _normalize_rel_path(item)
            for item in raw
            if _normalize_rel_path(item)
        )
        if identity <= equivalent:
            return sorted(paths)
    return []


def _goal_identity_paths(
    target: Mapping[str, Any],
    candidate_sets: Iterable[Mapping[str, Any]],
) -> list[str]:
    reason = str(target.get("reason") or "")
    if reason == "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES":
        return [
            _normalize_rel_path(path)
            for path in target.get("matched_confirmed_paths") or []
            if _normalize_rel_path(path)
        ]
    paths: list[str] = []
    for item in candidate_sets:
        if item.get("observation_role") == "goal_request" and item.get("scan_complete"):
            paths.extend(str(path) for path in (item.get("returned_paths_in_order") or []))
    return list(
        dict.fromkeys(
            _normalize_rel_path(path)
            for path in paths
            if _normalize_rel_path(path)
        )
    )


def classify_uniqueness_and_user_variable(
    target: dict[str, Any],
    candidate_sets: Iterable[Mapping[str, Any]],
    equivalent_sets: Iterable[Iterable[str]] | None,
) -> dict[str, Any]:
    """Classify why uniqueness failed. User-variable only if Goal-interchangeable."""
    reason = str(target.get("reason") or "")
    target["user_variable"] = empty_user_variable()
    if target.get("status") == "SELECTED":
        target["uniqueness_class"] = "UNIQUE_CONFIRMED"
        return target
    if reason == "SCAN_INCOMPLETE":
        target["uniqueness_class"] = "INCOMPLETE_OBSERVATION"
        return target
    if reason == "NO_SUBSTRING_HITS":
        target["uniqueness_class"] = "EMPTY_OBSERVATION"
        return target
    if reason in {"CONFIRMED_PATH_NOT_IN_CANDIDATES", "AGENT_STEERED_UNIQUE_PATH"}:
        target["uniqueness_class"] = "IDENTITY_UNRESOLVED"
        return target
    interchangeable = confirm_interchangeable_paths(
        _goal_identity_paths(target, candidate_sets),
        equivalent_sets,
    )
    if interchangeable:
        chosen = interchangeable[0]
        target["uniqueness_class"] = "USER_VARIABLE"
        target["status"] = "PROVISIONAL_SELECTED"
        target["selected"] = chosen
        target["user_variable"] = {
            "interchangeability_status": "CONFIRMED",
            "candidates": interchangeable,
            "provisional_selected": chosen,
            "selection_rule": "lexicographic_path",
            "replaceable_by": ["user_preference", "project_convention"],
            "source": "equivalent_path_set",
        }
        return target
    target["uniqueness_class"] = "IDENTITY_UNRESOLVED"
    return target


def _goal_request_unique_path_count(candidate_sets: Iterable[Mapping[str, Any]]) -> int:
    counts = [
        int(item.get("unique_path_count") or 0)
        for item in candidate_sets
        if item.get("observation_role") == "goal_request"
    ]
    if counts:
        return max(counts)
    return max((int(item.get("unique_path_count") or 0) for item in candidate_sets), default=0)


def goal_needs_human_grill(
    target: Mapping[str, Any],
    candidate_sets: Iterable[Mapping[str, Any]],
) -> bool:
    """True when multiple candidates remain and confirmed System facts cannot pick the next target.

    Incomplete scans still have a System next action (continue the same search).
    One named request path is already human identity and does not open Grill.
    Hit count by itself is not the trigger.
    """
    if target.get("status") in {"SELECTED", "PROVISIONAL_SELECTED"}:
        return False
    if target.get("uniqueness_class") != "IDENTITY_UNRESOLVED":
        return False
    request_grounds = [
        path for path in (target.get("request_path_grounds") or []) if path
    ]
    if request_grounds and str(target.get("reason") or "") != (
        "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES"
    ):
        return False
    rows = list(candidate_sets)
    goal_sets = [
        item for item in rows if item.get("observation_role") == "goal_request"
    ]
    check = goal_sets or rows
    if not check:
        return False
    if any(not item.get("scan_complete") for item in check):
        return False
    return _goal_request_unique_path_count(rows) >= 2


def build_conversation_grill(
    target: Mapping[str, Any],
    candidate_sets: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(item) for item in candidate_sets]
    goal_sets = [item for item in rows if item.get("observation_role") == "goal_request"]
    primary = (goal_sets or rows)[0] if (goal_sets or rows) else {}
    unique_n = _goal_request_unique_path_count(rows)
    paths = [str(path) for path in (primary.get("returned_paths_in_order") or [])]
    segments = dict(primary.get("matches_per_first_path_segment") or {})
    top_segments = dict(
        sorted(segments.items(), key=lambda item: (-int(item[1] or 0), str(item[0])))[
            :CONVERSATION_GRILL_SEGMENT_LIMIT
        ]
    )
    return {
        "phase": "conversation_grill",
        "status": "AWAITING_HUMAN",
        "reason": "CONFIRMED_INFO_INSUFFICIENT_FOR_NEXT_TARGET",
        "uniqueness_class": target.get("uniqueness_class"),
        "goal_reason": target.get("reason"),
        "uniqueness_cause": target.get("uniqueness_cause"),
        "question": (
            "検索候補が複数残っています。"
            "既存Systemの確認済み情報だけでは、次に調査すべき対象を合理的に決められません。"
            "何を指しているか、path・ファイル名、または役割を指定してください。"
        ),
        "recommended": (
            "確認済み情報で決まらない対象選択は人間が行う。システムは候補から1件選ばない。"
        ),
        "evidence": {
            "query": primary.get("query"),
            "path": primary.get("path"),
            "unique_path_count": unique_n,
            "match_row_count": primary.get("match_row_count"),
            "scan_complete": primary.get("scan_complete"),
            "substring_cardinality": primary.get("substring_cardinality"),
            "matches_per_first_path_segment": top_segments,
            "sample_paths": paths[:CONVERSATION_GRILL_SAMPLE_PATH_LIMIT],
            "sample_paths_truncated": len(paths) > CONVERSATION_GRILL_SAMPLE_PATH_LIMIT,
            "note": "sample_pathsは観測順の例であり、優先順位ではない。全件の選択UIではない。",
        },
        "selected": None,
        "candidates_preserved": True,
        "evidence_preserved": True,
    }


def format_conversation_grill(record: Mapping[str, Any]) -> str:
    """Short chat-facing prompt. Machine fields stay on the grill record, not in UI."""
    evidence = dict(record.get("evidence") or {})
    samples = [str(path) for path in (evidence.get("sample_paths") or [])]
    lines = [
        str(record.get("question") or ""),
        "",
        "返信で指定してください。こちらでは候補から1件選びません。",
    ]
    if samples:
        lines.extend(["", "観測の例（優先順位ではありません）:"])
        lines.extend(f"- {path}" for path in samples)
        if evidence.get("sample_paths_truncated"):
            lines.append("（例は一部です）")
    return "\n".join(lines).strip()


def search_candidate_hint(candidate_set: Mapping[str, Any]) -> str:
    payload = {
        "query": candidate_set.get("query"),
        "path": candidate_set.get("path"),
        "scan_complete": candidate_set.get("scan_complete"),
        "page_count": candidate_set.get("page_count"),
        "match_row_count": candidate_set.get("match_row_count"),
        "unique_path_count": candidate_set.get("unique_path_count"),
        "matches_per_first_path_segment": candidate_set.get(
            "matches_per_first_path_segment"
        ),
        "substring_cardinality": candidate_set.get("substring_cardinality"),
        "read_target_selected": candidate_set.get("read_target_selected"),
        "read_target_status": candidate_set.get("read_target_status"),
        "read_target_reason": candidate_set.get("read_target_reason"),
        "confirmed_path_grounds": candidate_set.get("confirmed_path_grounds"),
        "matched_confirmed_paths": candidate_set.get("matched_confirmed_paths"),
        "unresolved_for_read": candidate_set.get("unresolved_for_read"),
        "observation_role": candidate_set.get("observation_role"),
        "note": candidate_set.get("note"),
    }
    paths = [str(item) for item in (candidate_set.get("returned_paths_in_order") or [])]
    truncated = len(paths) > SEARCH_CANDIDATE_HINT_PATH_LIMIT
    payload["returned_paths_in_order"] = paths[:SEARCH_CANDIDATE_HINT_PATH_LIMIT]
    payload["hint_paths_truncated"] = truncated
    if candidate_set.get("read_target_status") == "SELECTED":
        instruction = (
            "読む対象は要求内の確認済みpath根拠と候補集合の交差で1件に確定しました。"
            "返却順や部分文字列の件数では選んでいません。"
        )
    elif candidate_set.get("unresolved_for_read"):
        instruction = (
            "この集合は部分文字列ヒットの観測です。Goalの読む対象の確定ではありません。"
            "1件を選んでreadしないでください。"
            "次の調査判断を意味レベルで出してください。"
            "その判断が既存のread-only Capability Actionになる場合のみSystemが再調査します。"
            "Action化できないときは直ちにHuman確認へ落とさず、既存のCapability/引数/Gap観測で理由を切り分けます。"
            "Agentが提案した調査対象はGoal対象ではありません。"
            "ヒットが1件でも、それだけではGoal対象の確定ではありません。"
        )
    else:
        instruction = (
            "この集合は部分文字列ヒットの観測です。Goalの読む対象の確定ではありません。"
        )
    return (
        f"Search Candidate Set:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        f"{instruction}"
    )


@dataclass
class ToolExpectation:
    generated: bool = False
    required_capability: str | None = None
    expected_tool: str | None = None
    expected_arguments: dict[str, Any] | None = None
    reason: str | None = None
    level: str = "none"
    actual_tool_called: str | None = None
    expectation_matched: bool = False


_WORKSPACE_PATH = re.compile(
    r"(?<![\w/])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)"
)
_WORKSPACE_FILE_NAME = re.compile(
    r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_-]+\.[A-Za-z0-9]{1,16})(?![A-Za-z0-9_.-])"
)
_FILE_OBSERVATION = re.compile(
    r"(読む|読ん|確認|内容を調べ|実際に調べ|read|inspect|check)", re.I
)


def _canonical_help_tool_name(card: Mapping[str, Any] | None, fallback: str = "") -> str | None:
    tid = ""
    if isinstance(card, Mapping):
        tid = str(card.get("name") or card.get("tool_id") or "").strip()
    if not tid:
        tid = fallback.strip()
    if ":" in tid:
        tid = tid.split(":", 1)[-1]
    return tid or None


def _help_confirmed_tool_for_capability(capability: str) -> str | None:
    """Resolve a tool via Help, then Capability Index + Help describe.

    ``prefer_tool_for_capability`` search currently misses ``workspace_file_read``
    (query ``read file`` does not match ``read_file`` / capability lists). Index
    ``tools`` plus Help describe is the canonical confirmation path. This is not
    a ``fallback="read_file"`` guess.
    """
    cap = (capability or "").strip()
    if not cap:
        return None
    resolved = prefer_tool_for_capability(cap)
    if resolved:
        return resolved
    spec = (load_workspace_index().get("capabilities") or {}).get(cap) or {}
    for raw in spec.get("tools") or []:
        name = str(raw).strip()
        if not name:
            continue
        for tool_id in (name, f"local:{name}"):
            result = describe(tool_id)
            if not result.get("ok"):
                continue
            card = result.get("tool")
            if not isinstance(card, Mapping) or not card.get("agent_available", True):
                continue
            return _canonical_help_tool_name(card, name)
    return None


_MUTATION_INTENT = re.compile(
    r"(作成|生成|実装|write|create|build|implement|edit|追加)",
    re.I,
)


def _task_operation_text(task: Any | None, request: str) -> str:
    if task is None:
        return str(request or "")
    return " ".join(
        str(value or "")
        for value in (
            getattr(task, "title", None),
            getattr(task, "instruction", None),
            request,
        )
    ).strip()


def _build_mutation_tool_expectation(
    text: str,
    tools: Iterable[Mapping[str, Any]],
) -> ToolExpectation | None:
    if not _MUTATION_INTENT.search(text or ""):
        return None
    match = _WORKSPACE_PATH.search(text or "") or _WORKSPACE_FILE_NAME.search(text or "")
    if not match:
        return None
    path = match.group(1).strip("`'\"").replace("\\", "/")
    available = {canonical_tool_name(tool) for tool in tools}
    create_tool = _help_confirmed_tool_for_capability("workspace_file_create")
    if create_tool and create_tool in available:
        return ToolExpectation(
            generated=True,
            required_capability="workspace_file_create",
            expected_tool=create_tool,
            expected_arguments={"path": path},
            reason="Current Task requires a Sandbox file mutation via create_file",
            level="required",
        )
    edit_tool = _help_confirmed_tool_for_capability("workspace_file_edit")
    if edit_tool and edit_tool in available and re.search(r"\bedit\b|編集", text, re.I):
        return ToolExpectation(
            generated=True,
            required_capability="workspace_file_edit",
            expected_tool=edit_tool,
            expected_arguments={"path": path},
            reason="Current Task requires a Sandbox file mutation via edit_file",
            level="required",
        )
    return None


def build_tool_expectation(
    request: str,
    tools: Iterable[Mapping[str, Any]],
    *,
    task: Any | None = None,
) -> ToolExpectation:
    """Infer read or mutation requirements from the current Task; never execute Tools."""
    text = _task_operation_text(task, request)
    mutation = _build_mutation_tool_expectation(text, tools)
    if mutation is not None:
        return mutation
    match = _WORKSPACE_PATH.search(text or "")
    if not match or not _FILE_OBSERVATION.search(text or ""):
        return ToolExpectation()
    path = match.group(1).strip("`'\"")
    if ".." in path.split("/") or re.match(r"^[A-Za-z]:", path):
        return ToolExpectation()
    resolved = _help_confirmed_tool_for_capability("workspace_file_read")
    if not resolved:
        return ToolExpectation()
    if resolved not in {canonical_tool_name(tool) for tool in tools}:
        return ToolExpectation()
    return ToolExpectation(
        generated=True,
        required_capability="workspace_file_read",
        expected_tool=resolved,
        expected_arguments=runtime_initial_read_arguments(path),
        reason="ユーザーがWorkspace内の指定ファイルを実際に確認することを要求している",
        level="required",
    )


class ChatTaskOrchestrator:
    """One-turn orchestration; no Tool permission or execution responsibility."""

    def __init__(
        self,
        runtime_id: str,
        request: str,
        *,
        completion_conditions: Iterable[str] | None = None,
        concept_resolution: ConceptResolution | None = None,
        sandbox_session: SandboxSession | None = None,
    ):
        self.request = request.strip()
        self.runtime = AgentTaskRuntime(runtime_id, sandbox_session=sandbox_session)
        self.current_goal_id = "G1.1"
        self.current_task_id = "T1"
        self._action_index = 0
        self._evidence_index = 0
        self._failure_index = 0
        self.concept_resolution = concept_resolution or ConceptResolution()
        self._completion_conditions = filter_definition_first_conditions(
            list(completion_conditions or []), self.concept_resolution
        )
        self.tool_expectation = ToolExpectation()
        self.local_reviews: list[dict[str, Any]] = []
        self._review_task_targets: dict[str, list[tuple[str, str]]] = {}
        self.capability_resolutions: dict[str, list[CapabilityResolution]] = {}
        self._registry_tools: list[dict[str, Any]] = []
        self._pending_observation_action: dict[str, Any] | None = None
        self._run_test_plan_continuation: dict[str, Any] | None = None
        self._injected_capability_tool: str | None = None
        self.search_observations: list[dict[str, Any]] = []
        self._search_hit_paths: dict[tuple[str, str], list[str]] = {}
        self._search_hit_texts: dict[tuple[str, str], dict[str, list[str]]] = {}
        self.search_candidate_sets: dict[tuple[str, str], dict[str, Any]] = {}
        self.followup_investigations: list[dict[str, Any]] = []
        self.goal_read_target: dict[str, Any] = empty_goal_read_target()
        self._observation_path_grounds: list[str] = []
        self._directory_listings: dict[str, dict[str, Any]] = {}
        self._human_grill_answers: list[str] = []
        self.confirmed_clarifications: list[dict[str, Any]] = []
        self.boundary_grill_resolved_dimensions: list[str] = []
        self.boundary_grill_round: int = 0
        self.interchangeable_path_sets: list[frozenset[str]] = []
        self.mission_id = ""
        self.execution_id = ""
        self.persistent_evidence_ids: dict[str, str] = {}
        self.user_explicit_conditions: list[str] = []
        self.goal_completion_supplements: list[dict[str, str]] = []
        self.goal_completion_consumed = False
        self.structured_requirements: list[dict[str, Any]] = []
        self.requirement_resolution_phase: str = ""
        self.projected_explicit_constraints: list[str] = []
        self.canonical_requirement_projection: list[dict[str, str]] = []
        self.handoff_acceptance_projection: list[dict[str, str]] = []
        self.handoff_task_acceptance_mapping: list[dict[str, Any]] = []
        self.handoff_test_plan: dict[str, Any] = {}
        self.domain_goal_adoption_result: Any = None
        self.task_graph_projection_sidecar: list[dict[str, Any]] = []

    def handoff_acceptance_runtime_trace(self) -> list[dict[str, Any]]:
        """READ-ONLY: Handoff A* identity and T* → gh-T* maps_to_acceptance trace."""
        from ai_tool.goal_handoff_runtime_bridge import build_handoff_acceptance_runtime_trace

        return build_handoff_acceptance_runtime_trace(self)

    def apply_canonical_requirements_from_state(self, state: Mapping[str, Any]) -> None:
        """Restore mission-canonical structured requirements from a snapshot or mission row."""
        rows = state.get("structured_requirements")
        if isinstance(rows, list):
            self.structured_requirements = [
                dict(item) for item in rows if isinstance(item, Mapping)
            ]
        phase = state.get("requirement_resolution_phase")
        if phase:
            self.requirement_resolution_phase = str(phase)
        from ai_tool.chat_interface.requirement_resolution import (
            sync_canonical_requirement_projection,
        )

        sync_canonical_requirement_projection(self)

    def canonical_requirement_evidence_trace(self) -> list[dict[str, Any]]:
        """READ-ONLY: requirement_id → completion_condition → task → evidence_ids."""
        from ai_tool.chat_interface.requirement_resolution import (
            build_canonical_requirement_evidence_trace,
        )

        return build_canonical_requirement_evidence_trace(self)

    def canonical_requirement_runtime_coverage(self) -> list[dict[str, Any]]:
        """READ-ONLY: projected requirement runtime condition_status and evidence per task."""
        from ai_tool.chat_interface.requirement_resolution import (
            build_canonical_requirement_runtime_coverage,
        )

        return build_canonical_requirement_runtime_coverage(self)

    def initialize(
        self,
        handoff_packet: Mapping[str, Any] | None = None,
        *,
        domain_goal_graph: Mapping[str, Any] | None = None,
        domain_task_graph: Mapping[str, Any] | None = None,
    ) -> None:
        if handoff_packet is not None:
            from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff

            seed_orchestrator_from_handoff(self, handoff_packet)
            return
        if domain_goal_graph is not None:
            if domain_task_graph is not None:
                from ai_tool.domain_task_graph_adoption import adopt_domain_goal_and_task_graph

                adopt_domain_goal_and_task_graph(self, domain_goal_graph, domain_task_graph)
            else:
                from ai_tool.domain_goal_graph_adoption import adopt_domain_goal_graph

                adopt_domain_goal_graph(self, domain_goal_graph)
            return
        if domain_task_graph is not None:
            from ai_tool.domain_task_graph_adoption import DomainTaskGraphValidationError

            raise DomainTaskGraphValidationError(
                "domain_task_graph requires domain_goal_graph"
            )
        observation_conditions = list(self._completion_conditions)
        if not observation_conditions:
            observation_conditions = _explicit_completion_conditions(self.request)
        if not observation_conditions:
            observation_conditions = ["relevant evidence observed"]
        self.runtime.add_goal(
            GoalNode("G1", self.request, completion_conditions=["all tasks complete"])
        )
        self.runtime.add_goal(
            GoalNode(
                self.current_goal_id,
                "Observe facts required by the request",
                parent_goal_id="G1",
            )
        )
        if self.concept_resolution.detected:
            self.runtime.add_task(
                TaskRecord(
                    "TC1",
                    self.current_goal_id,
                    f"{self.concept_resolution.concept}の定義を確認する",
                    "Concept Indexの案内順にWorkspace内の定義・更新箇所を確認する",
                    definition_conditions(self.concept_resolution),
                )
            )
            self.current_task_id = "TC1"
        self.runtime.add_task(
            TaskRecord(
                "T1",
                self.current_goal_id,
                "Observe the facts required by the request",
                self.request,
                observation_conditions,
                depends_on=["TC1"] if self.concept_resolution.detected else [],
            )
        )
        self.runtime.add_goal(
            GoalNode("G1.2", "Produce the requested result", parent_goal_id="G1")
        )
        self.runtime.add_task(
            TaskRecord(
                "T2",
                "G1.2",
                "Synthesize the answer from known evidence",
                self.request,
                ["answer produced"],
                depends_on=["T1"],
            )
        )

    @property
    def task(self) -> TaskRecord:
        return self.runtime.tasks[self.current_task_id]

    def hint(self) -> str:
        hint = self.runtime.small_task_hint(self.current_task_id)
        concept_hint = definition_hint(self.concept_resolution)
        if concept_hint:
            hint = f"{hint}\n\n{concept_hint}"
        for capability in self.capability_resolutions.get(self.current_task_id) or []:
            bridge_hint = capability_hint(capability)
            if bridge_hint:
                hint = f"{hint}\n\n{bridge_hint}"
        for candidate_set in self.search_candidate_sets.values():
            extra = search_candidate_hint(candidate_set)
            if extra:
                hint = f"{hint}\n\n{extra}"
        if self.search_candidate_sets:
            hint = (
                f"{hint}\n\nGoal Read Target:\n"
                f"{json.dumps(self.goal_read_target, ensure_ascii=False, indent=2)}\n"
                "Agentが提案した調査対象と、最終的に確認されたGoal対象は別です。"
                "Goal対象がSELECTEDで、そのファイルを読んだEvidenceがあるときだけ根拠付き要約へ進みます。"
                "検索候補が複数残り、既存の確認済み情報だけでは次の調査対象を合理的に決められないときは、"
                "1件を選ばず会話のGrillフェーズで人間に意図を聞きます。"
                "Goal上交換可能と確認できた候補だけがユーザー可変要素です。"
                "ユーザー可変は暫定選択して進められ、後からユーザー好みやProject Conventionで差し替え可能です。"
                "部分文字列の複数ヒットだけでは交換可能とは確認しません。"
            )
        if self._human_grill_answers:
            hint = (
                f"{hint}\n\nConversation Grill:\n"
                "ユーザー回答は同一Goalへの confirmed clarification です。"
                "新しいGoalではありません。Need→Capabilityの調査再試行でもありません。"
                "完了済みの検索・調査は繰り返さず、更新した Goal を再評価します。"
            )
        if self.followup_investigations:
            hint = (
                f"{hint}\n\nFollow-up Investigation:\n"
                f"{json.dumps(self.followup_investigations[-1], ensure_ascii=False, indent=2)}"
            )
        if not self.tool_expectation.generated:
            return hint
        payload = asdict(self.tool_expectation)
        return (
            f"{hint}\n\nTool Expectation:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            "このTaskでは実ファイル観測が必要です。Tool Resultを得る前に、"
            "ファイルの存在や内容を推測で断定しないでください。"
        )

    def configure_tool_expectation(
        self,
        tools: Iterable[Mapping[str, Any]],
        *,
        registry_tools: Iterable[Mapping[str, Any]] | None = None,
    ) -> ToolExpectation:
        tool_rows = list(tools)
        self._registry_tools = [dict(item) for item in (registry_tools or [])]
        current_task = self.runtime.tasks.get(self.current_task_id)
        self.tool_expectation = build_tool_expectation(
            self.request,
            tool_rows,
            task=current_task,
        )
        action = next_definition_action(self.concept_resolution)
        if action is not None:
            tool, arguments = action
            names = {canonical_tool_name(item) for item in tool_rows}
            if tool in names:
                self.tool_expectation = ToolExpectation(
                    generated=True,
                    required_capability="workspace_definition_lookup",
                    expected_tool=tool,
                    expected_arguments=arguments,
                    reason="Workspace固有概念は推測せず、Indexの案内先で定義を確認する",
                    level="required",
                )
        self._resolve_current_capability(tool_rows)
        return self.tool_expectation

    def _task_resolutions(self, task_id: str | None = None) -> list[CapabilityResolution]:
        return list(self.capability_resolutions.get(task_id or self.current_task_id) or [])

    def _search_pages_for(self, query: str, path: str) -> list[dict[str, Any]]:
        needle = str(query or "")
        base = path or "."
        return [
            item
            for item in self.search_observations
            if str(item.get("query") or "") == needle
            and (str(item.get("path") or ".") or ".") == base
        ]

    def _request_path_grounds(self) -> list[str]:
        """Q25 grounds from the Goal request. Follow-up Need text is not included."""
        extra: list[str] = []
        expected = (self.tool_expectation.expected_arguments or {}).get("path")
        if expected:
            extra.append(str(expected))
        for rows in self.capability_resolutions.values():
            for item in rows:
                path = (item.resolved_arguments or {}).get("path")
                if path:
                    extra.append(str(path))
                action = item.next_action or {}
                if action.get("tool") == "read_file":
                    arg_path = (action.get("arguments") or {}).get("path")
                    if arg_path:
                        extra.append(str(arg_path))
        return confirmed_read_path_grounds(
            self.request,
            capability_index=load_workspace_index(),
            registry_tools=self._registry_tools or None,
            extra_paths=extra,
        )

    def _proposed_investigation_paths(self) -> list[str]:
        """Agent-proposed investigation targets. Not Goal confirmation grounds."""
        paths: list[str] = []

        def add(path: str) -> None:
            normalized = _normalize_rel_path(path)
            if not normalized or normalized == ".":
                return
            if normalized not in paths:
                paths.append(normalized)

        for item in self.followup_investigations:
            for raw in item.get("proposed_path_grounds") or []:
                add(str(raw))
            target = item.get("proposed_investigation_target") or {}
            arguments = dict(target.get("arguments") or {})
            add(str(arguments.get("path") or ""))
        return paths

    def _ingest_observation_text_grounds(self, texts: Iterable[str]) -> None:
        """Collect Q25 path/filename forms from Tool Result text, not hit-path metadata."""
        for text in texts:
            for path in confirmed_read_path_grounds(
                str(text or ""),
                capability_index=load_workspace_index(),
                registry_tools=self._registry_tools or None,
                include_look_first=False,
            ):
                if path not in self._observation_path_grounds:
                    self._observation_path_grounds.append(path)

    def _agent_steered_path_grounds(self) -> list[str]:
        """Path forms the Agent proposed or put in the follow-up query. Not Evidence."""
        paths: list[str] = []

        def add(path: str) -> None:
            normalized = _normalize_rel_path(path)
            if not normalized or normalized == ".":
                return
            if normalized not in paths:
                paths.append(normalized)

        for item in self._proposed_investigation_paths():
            add(item)
        index = load_workspace_index()
        registry = self._registry_tools or None
        for item in self.followup_investigations:
            need = str(item.get("need") or "")
            for raw in confirmed_read_path_grounds(
                need,
                capability_index=index,
                registry_tools=registry,
                include_look_first=False,
            ):
                add(raw)
            action = item.get("action") or item.get("proposed_investigation_target") or {}
            arguments = dict(action.get("arguments") or {})
            query = str(arguments.get("query") or "")
            for raw in confirmed_read_path_grounds(
                query,
                capability_index=index,
                registry_tools=registry,
                include_look_first=False,
            ):
                add(raw)
        return paths

    def _grill_answer_path_grounds(self) -> list[str]:
        """Q25 path/filename forms, else distinctive matches against preserved candidates."""
        if not self._human_grill_answers:
            return []
        latest = str(self._human_grill_answers[-1] or "")
        grounds: list[str] = []
        for path in confirmed_read_path_grounds(
            latest,
            capability_index=load_workspace_index(),
            registry_tools=self._registry_tools or None,
            include_look_first=False,
        ):
            if path not in grounds:
                grounds.append(path)
        if grounds:
            return grounds
        return self._clarification_matched_candidate_paths(latest)

    def _clarification_matched_candidate_paths(self, text: str) -> list[str]:
        rows = list(self.search_candidate_sets.values())
        goal_sets = [
            item for item in rows if item.get("observation_role") == "goal_request"
        ]
        check = goal_sets or rows
        paths: list[str] = []
        texts: dict[str, list[str]] = {}
        ignore: list[str] = []
        for item in check:
            ignore.append(str(item.get("query") or ""))
            for path in item.get("returned_paths_in_order") or []:
                normalized = _normalize_rel_path(str(path))
                if normalized and normalized not in paths:
                    paths.append(normalized)
            for path, snippets in dict(item.get("observed_match_texts") or {}).items():
                key = _normalize_rel_path(str(path))
                if not key:
                    continue
                bucket = texts.setdefault(key, [])
                for snippet in snippets or []:
                    value = str(snippet or "").strip()
                    if value and value not in bucket:
                        bucket.append(value)
        ignore.extend(_clarification_tokens(self.request))
        return match_clarification_to_candidate_paths(
            text,
            paths,
            observed_match_texts=texts,
            ignore_tokens=ignore,
        )

    def _goal_confirmed_read_paths(self) -> list[str]:
        """Effective Goal grounds: request Q25 plus Grill answer plus observation text, minus Agent steering."""
        request_grounds = self._request_path_grounds()
        grill_grounds = self._grill_answer_path_grounds()
        excluded = set(self._agent_steered_path_grounds())
        merged = list(request_grounds)
        for path in grill_grounds:
            if path not in merged:
                merged.append(path)
        observation = [
            path
            for path in self._observation_path_grounds
            if path not in excluded and path not in merged
        ]
        return merged + observation

    def _search_is_followup(self, query: str, search_path: str) -> bool:
        for item in self.followup_investigations:
            action = item.get("action") or {}
            if str(action.get("tool") or "") != "search_files":
                continue
            arguments = dict(action.get("arguments") or {})
            if str(arguments.get("query") or "") != query:
                continue
            if _search_path_arg(arguments) == search_path:
                return True
        return False

    def _refresh_goal_read_target(self) -> None:
        """Re-apply Goal grounds to every search observation. Does not adopt Agent Need paths."""
        request_grounds = self._request_path_grounds()
        grill_grounds = self._grill_answer_path_grounds()
        excluded = self._agent_steered_path_grounds()
        observation_grounds = [
            path
            for path in self._observation_path_grounds
            if path not in set(excluded)
            and path not in request_grounds
            and path not in grill_grounds
        ]
        grounds = self._goal_confirmed_read_paths()
        selected: list[str] = []
        source_queries: list[str] = []
        goal_reason = None
        if not self.search_candidate_sets:
            self.goal_read_target = empty_goal_read_target()
            self.goal_read_target["confirmed_path_grounds"] = grounds
            self.goal_read_target["request_path_grounds"] = request_grounds
            self.goal_read_target["grill_answer_path_grounds"] = grill_grounds
            self.goal_read_target["observation_path_grounds"] = observation_grounds
            self.goal_read_target["excluded_proposed_paths"] = excluded
            return
        for key, current in list(self.search_candidate_sets.items()):
            query, search_path = key
            resolved = resolve_search_read_target(current, grounds)
            resolved["observation_role"] = (
                "followup_investigation"
                if self._search_is_followup(query, search_path)
                else "goal_request"
            )
            self.search_candidate_sets[key] = resolved
            if resolved.get("observation_role") == "goal_request" and goal_reason is None:
                goal_reason = resolved.get("read_target_reason")
            if resolved.get("read_target_status") == "SELECTED":
                path = str(resolved.get("read_target_selected") or "")
                if path:
                    selected.append(path)
                    source_queries.append(str(resolved.get("query") or ""))
        unique_selected = list(dict.fromkeys(selected))
        target = empty_goal_read_target()
        target["confirmed_path_grounds"] = grounds
        target["request_path_grounds"] = request_grounds
        target["grill_answer_path_grounds"] = grill_grounds
        target["observation_path_grounds"] = observation_grounds
        target["excluded_proposed_paths"] = excluded
        if len(unique_selected) == 1:
            chosen = unique_selected[0]
            steered = bool(_match_confirmed_paths_in_candidates(excluded, [chosen]))
            requested = bool(_match_confirmed_paths_in_candidates(request_grounds, [chosen]))
            grilled = bool(_match_confirmed_paths_in_candidates(grill_grounds, [chosen]))
            if steered and not requested and not grilled:
                target["status"] = "UNRESOLVED"
                target["reason"] = "AGENT_STEERED_UNIQUE_PATH"
                target["uniqueness_cause"] = "agent_proposal"
                target["matched_confirmed_paths"] = unique_selected
                target["source_queries"] = source_queries
            else:
                target["status"] = "SELECTED"
                target["reason"] = "CONFIRMED_UNIQUE_PATH_IN_CANDIDATES"
                target["selected"] = chosen
                target["matched_confirmed_paths"] = unique_selected
                target["source_queries"] = source_queries
                if grilled:
                    target["ground_source"] = "human_grill"
                    target["uniqueness_cause"] = "goal_request"
                elif requested:
                    target["ground_source"] = "goal_request"
                    target["uniqueness_cause"] = "goal_request"
                else:
                    target["ground_source"] = "followup_observation"
                    target["uniqueness_cause"] = "evidence_text"
        elif len(unique_selected) > 1:
            target["status"] = "UNRESOLVED"
            target["reason"] = "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES"
            target["matched_confirmed_paths"] = unique_selected
            target["source_queries"] = source_queries
            target["uniqueness_cause"] = "multiple_evidence_paths"
        else:
            target["status"] = "UNRESOLVED"
            target["reason"] = goal_reason or "NO_CONFIRMED_PATH_GROUND"
            goal_sets = [
                item
                for item in self.search_candidate_sets.values()
                if item.get("observation_role") == "goal_request"
            ]
            if goal_sets:
                target["matched_confirmed_paths"] = list(
                    goal_sets[0].get("matched_confirmed_paths") or []
                )
            if (goal_reason or "") == "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES" or len(
                target["matched_confirmed_paths"]
            ) > 1:
                target["uniqueness_cause"] = "multiple_evidence_paths"
            else:
                followup_single_hit = any(
                    item.get("observation_role") == "followup_investigation"
                    and item.get("substring_cardinality") == "SINGLE_SUBSTRING_PATH"
                    for item in self.search_candidate_sets.values()
                )
                if followup_single_hit and not observation_grounds:
                    target["uniqueness_cause"] = "followup_hit_cardinality"
        self.goal_read_target = classify_uniqueness_and_user_variable(
            target,
            list(self.search_candidate_sets.values()),
            self.interchangeable_path_sets,
        )

    def _goal_target_read_observed(self, path: str) -> bool:
        needle = _normalize_rel_path(path)
        if not needle:
            return False
        return any(
            item.tool_name == "read_file"
            and _normalize_rel_path(str(item.target or "")) == needle
            and (item.relevant_content or item.summary)
            for item in self.runtime.evidence.values()
        )

    def _can_bridge_goal_read(self, candidate: str) -> bool:
        if not candidate or Path(candidate).is_absolute():
            return False
        if self._goal_target_read_observed(candidate):
            return False
        candidate_path = Path(candidate)
        try:
            resolved_candidate = (REPO_ROOT / candidate_path).resolve()
            resolved_candidate.relative_to(REPO_ROOT)
        except (OSError, ValueError):
            return False
        if not resolved_candidate.is_file():
            return False
        return bool(_help_confirmed_tool_for_capability("workspace_file_read"))

    def _maybe_bridge_selected_goal_read(
        self,
        *,
        current_tool: str | None = None,
        current_arguments: Mapping[str, Any] | None = None,
    ) -> None:
        if self._pending_observation_action is not None:
            return
        selected = str(self.goal_read_target.get("selected") or "")
        if not selected or not self._can_bridge_goal_read(selected):
            return
        current_path = _normalize_rel_path(str((current_arguments or {}).get("path") or ""))
        if current_tool == "read_file" and current_path == _normalize_rel_path(selected):
            return
        reader = _help_confirmed_tool_for_capability("workspace_file_read")
        if reader:
            self._pending_observation_action = {
                "tool": reader,
                "arguments": runtime_initial_read_arguments(selected),
            }

    def _goal_summary_ready(self) -> bool:
        if not self.search_candidate_sets:
            return True
        if self.goal_read_target.get("status") in {"SELECTED", "PROVISIONAL_SELECTED"}:
            selected = str(self.goal_read_target.get("selected") or "")
            return self._goal_target_read_observed(selected)
        return False

    def _named_paths_confirmed_absent(
        self, arguments: Mapping[str, Any]
    ) -> list[str]:
        """Request-named files omitted from a complete listing of their parent.

        Observation only. Does not add or replace Goal completion conditions.
        """
        listing_dir = _action_path_key(arguments)
        listing = self._directory_listings.get(listing_dir)
        if not listing or listing.get("truncated"):
            return []
        grounds = confirmed_read_path_grounds(
            self.request,
            include_look_first=False,
        )
        names = {str(item).casefold() for item in listing.get("names") or []}
        rels = {
            _action_path_key({"path": item}).casefold()
            for item in listing.get("paths") or []
        }
        absent: list[str] = []
        for ground in grounds:
            key = _action_path_key({"path": ground})
            parent, _, name = key.rpartition("/")
            parent_key = _action_path_key({"path": parent or "."})
            if parent_key != listing_dir or not name:
                continue
            if name.casefold() in names or key.casefold() in rels:
                continue
            if key not in absent:
                absent.append(key)
        return absent

    def omitted_request_named_paths(self) -> list[str]:
        """Request-named paths omitted from any complete parent listing."""
        omitted: list[str] = []
        for listing_dir in self._directory_listings:
            for path in self._named_paths_confirmed_absent({"path": listing_dir}):
                if path not in omitted:
                    omitted.append(path)
        return omitted

    def _generic_observation_completes_task(
        self, tool_name: str, arguments: Mapping[str, Any]
    ) -> bool:
        """Action success is not Task success for locating scans.

        search_files / list_files record Observation; they do not satisfy
        the fallback 'relevant evidence observed' condition. A search Goal
        completes that fallback only after the confirmed target is read.

        Exception: a complete list_files of the parent that omits a
        request-named file is observation of that named path. It may support
        the existing fallback condition. It is not a new Goal condition.
        """
        if tool_name == "search_files":
            return False
        if tool_name == "list_files":
            return bool(self._named_paths_confirmed_absent(arguments))
        if not self.search_candidate_sets:
            return True
        if self.goal_read_target.get("status") not in {"SELECTED", "PROVISIONAL_SELECTED"}:
            return False
        selected = str(self.goal_read_target.get("selected") or "")
        if self._goal_target_read_observed(selected):
            return True
        current = _normalize_rel_path(str(arguments.get("path") or ""))
        return tool_name == "read_file" and current == _normalize_rel_path(selected)

    def needs_human_grill(self) -> bool:
        return goal_needs_human_grill(
            self.goal_read_target,
            self.search_candidate_sets.values(),
        )

    def needs_goal_completion_human(self) -> bool:
        return needs_goal_completion_human(self)

    def goal_completion_human_record(self) -> dict[str, Any]:
        return build_goal_completion_human(self)

    def goal_completion_resume_state(self) -> dict[str, Any]:
        state = build_goal_completion_resume(self)
        state["completion_runtime"] = self.completion_runtime_slice()
        return state

    @staticmethod
    def completion_runtime_requires_graph_restore(snapshot: Mapping[str, Any] | None) -> bool:
        """True when completion_runtime carries a non-default Task graph (e.g. goal handoff)."""
        rows = [
            item
            for item in (snapshot or {}).get("tasks") or []
            if isinstance(item, Mapping)
        ]
        if not rows:
            return False
        return any(
            str(item.get("source") or "") == "goal_handoff"
            or str(item.get("task_id") or "").startswith("gh-")
            for item in rows
        )

    def _goal_node_from_snapshot(self, item: Mapping[str, Any]) -> GoalNode:
        allowed = {field.name for field in fields(GoalNode)}
        payload = {key: item[key] for key in allowed if key in item}
        return GoalNode(**payload)

    def _task_record_from_snapshot(self, item: Mapping[str, Any]) -> TaskRecord:
        allowed = {field.name for field in fields(TaskRecord)}
        payload = {key: item[key] for key in allowed if key in item}
        return TaskRecord(**payload)

    def _replace_runtime_graph_from_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        """Replace goals/tasks from completion_runtime without default Observe/Synthesize seed."""
        self.runtime.goals.clear()
        self.runtime.tasks.clear()
        goal_rows = [
            item for item in (snapshot.get("goals") or []) if isinstance(item, Mapping)
        ]
        task_rows = [
            item for item in (snapshot.get("tasks") or []) if isinstance(item, Mapping)
        ]
        for item in sorted(goal_rows, key=lambda row: str(row.get("goal_id") or "")):
            goal = self._goal_node_from_snapshot(item)
            self.runtime.goals[goal.goal_id] = goal
        for item in task_rows:
            task = self._task_record_from_snapshot(item)
            self.runtime.tasks[task.task_id] = task
            goal = self.runtime.goals.get(task.goal_id)
            if goal is not None and task.task_id not in goal.task_ids:
                goal.task_ids.append(task.task_id)
        current_goal = str(snapshot.get("current_goal_id") or "")
        if current_goal in self.runtime.goals:
            self.current_goal_id = current_goal
        current_task = str(snapshot.get("current_task_id") or "")
        if current_task in self.runtime.tasks:
            self.current_task_id = current_task

    def completion_runtime_slice(self) -> dict[str, Any]:
        """Task / Goal / Evidence completion already established this execution."""
        from ai_tool.task_change_propagation_guard import (
            GUARD_KEY,
            get_propagation_guard,
        )

        payload = {
            "current_goal_id": self.current_goal_id,
            "current_task_id": self.current_task_id,
            "goals": [asdict(item) for item in self.runtime.goals.values()],
            "tasks": [asdict(item) for item in self.runtime.tasks.values()],
            "evidence": [
                self._evidence_row_for_grill(item)
                for item in self.runtime.evidence.values()
            ],
            "directory_listings": {
                key: dict(value) for key, value in self._directory_listings.items()
            },
            "search_observations": [dict(item) for item in self.search_observations],
        }
        guard = get_propagation_guard(self)
        if guard is not None:
            payload[GUARD_KEY] = dict(guard)
        if self.task_graph_projection_sidecar:
            from ai_tool.domain_task_graph_adoption import TASK_GRAPH_PROJECTION_SIDECAR_KEY

            payload[TASK_GRAPH_PROJECTION_SIDECAR_KEY] = [
                dict(item) for item in self.task_graph_projection_sidecar
            ]
        return payload

    def apply_completion_runtime(
        self,
        snapshot: Mapping[str, Any] | None,
        *,
        replace_graph: bool = False,
    ) -> None:
        """Restore Task / Goal / Evidence completion from a prior execution."""
        row = dict(snapshot or {})
        if replace_graph:
            self._replace_runtime_graph_from_snapshot(row)
        from ai_tool.domain_task_graph_adoption import TASK_GRAPH_PROJECTION_SIDECAR_KEY

        sidecar_rows = row.get(TASK_GRAPH_PROJECTION_SIDECAR_KEY)
        if isinstance(sidecar_rows, list):
            self.task_graph_projection_sidecar = [
                dict(item) for item in sidecar_rows if isinstance(item, Mapping)
            ]
        elif replace_graph:
            self.task_graph_projection_sidecar = []
        self._restore_preserved_evidence(row.get("evidence") or [])
        listings = row.get("directory_listings") or {}
        if isinstance(listings, Mapping):
            for key, value in listings.items():
                if isinstance(value, Mapping):
                    self._directory_listings[str(key)] = dict(value)
        self.search_observations = [
            dict(item)
            for item in (row.get("search_observations") or [])
            if isinstance(item, Mapping)
        ]
        from ai_tool.human_decision_premise import coerce_decision_premises

        for item in row.get("tasks") or []:
            if not isinstance(item, Mapping):
                continue
            task_id = str(item.get("task_id") or "")
            task = self.runtime.tasks.get(task_id)
            if task is None:
                continue
            if item.get("status"):
                task.status = str(item.get("status"))
            task.satisfied_conditions = list(item.get("satisfied_conditions") or [])
            task.condition_status = {
                str(key): str(value)
                for key, value in dict(item.get("condition_status") or {}).items()
            }
            task.condition_evidence = {
                str(key): [str(ref) for ref in (refs or [])]
                for key, refs in dict(item.get("condition_evidence") or {}).items()
            }
            task.evidence_ids = [str(ref) for ref in (item.get("evidence_ids") or [])]
            if item.get("result_summary") is not None:
                summary = str(item.get("result_summary") or "").strip()
                task.result_summary = summary or None
            if "decision_premises" in item:
                task.decision_premises = coerce_decision_premises(item.get("decision_premises"))
            if "superseded_by_task_id" in item:
                token = str(item.get("superseded_by_task_id") or "").strip() or None
                task.superseded_by_task_id = token
            if "supersedes_task_id" in item:
                token = str(item.get("supersedes_task_id") or "").strip() or None
                task.supersedes_task_id = token
            if "source_task_id" in item:
                token = str(item.get("source_task_id") or "").strip() or None
                task.source_task_id = token
            revalidation = item.get("revalidation")
            if isinstance(revalidation, Mapping):
                task.revalidation = dict(revalidation)
            elif revalidation is None and "revalidation" in item:
                task.revalidation = None
        for item in row.get("goals") or []:
            if not isinstance(item, Mapping):
                continue
            goal = self.runtime.goals.get(str(item.get("goal_id") or ""))
            if goal is None:
                continue
            if item.get("status"):
                goal.status = str(item.get("status"))
            goal.evidence_ids = [str(ref) for ref in (item.get("evidence_ids") or [])]
        current_task = str(row.get("current_task_id") or "")
        if current_task in self.runtime.tasks:
            self.current_task_id = current_task
        current_goal = str(row.get("current_goal_id") or "")
        if current_goal in self.runtime.goals:
            self.current_goal_id = current_goal
        from ai_tool.task_change_propagation_guard import (
            propagation_guard_from_completion_runtime,
            set_propagation_guard,
        )

        set_propagation_guard(
            self,
            propagation_guard_from_completion_runtime(row),
        )
        from ai_tool.human_decision_premise import refresh_task_revalidation

        refresh_task_revalidation(self)

    def conversation_grill_record(self) -> dict[str, Any]:
        return build_conversation_grill(
            self.goal_read_target,
            self.search_candidate_sets.values(),
        )

    def conversation_grill_state(self) -> dict[str, Any]:
        """Persist Goal / candidates / observations / evidence for the conversation Grill loop."""
        return {
            "original_request": self.request,
            "completion_conditions": list(self._completion_conditions),
            "search_candidate_sets": [
                dict(item) for item in self.search_candidate_sets.values()
            ],
            "search_observations": [dict(item) for item in self.search_observations],
            "observation_path_grounds": list(self._observation_path_grounds),
            "human_grill_answers": list(self._human_grill_answers),
            "confirmed_clarifications": [dict(item) for item in self.confirmed_clarifications],
            "followup_investigations": [dict(item) for item in self.followup_investigations],
            "mission_id": self.mission_id or None,
            "evidence": [
                self._evidence_row_for_grill(item) for item in self.runtime.evidence.values()
            ],
            "search_hit_paths": [
                {
                    "query": query,
                    "path": search_path,
                    "hits": list(hits),
                }
                for (query, search_path), hits in self._search_hit_paths.items()
            ],
        }

    def grill_resume_state(self) -> dict[str, Any]:
        """Compat alias. Conversation Grill state is not Agent investigation resume."""
        return self.conversation_grill_state()

    @classmethod
    def restore_from_grill_resume(
        cls,
        runtime_id: str,
        state: Mapping[str, Any],
    ) -> "ChatTaskOrchestrator":
        """Restore the same Goal so a Grill reply can be added as clarification."""
        orchestrator = cls(
            runtime_id,
            str(state.get("original_request") or ""),
            completion_conditions=list(state.get("completion_conditions") or []),
        )
        orchestrator.initialize()
        orchestrator._human_grill_answers = [
            str(item) for item in (state.get("human_grill_answers") or []) if str(item).strip()
        ]
        orchestrator.confirmed_clarifications = [
            dict(item) for item in (state.get("confirmed_clarifications") or [])
        ]
        orchestrator._observation_path_grounds = [
            str(item) for item in (state.get("observation_path_grounds") or []) if item
        ]
        orchestrator.search_observations = [
            dict(item) for item in (state.get("search_observations") or [])
        ]
        orchestrator.followup_investigations = [
            dict(item) for item in (state.get("followup_investigations") or [])
        ]
        orchestrator.search_candidate_sets = {}
        for item in state.get("search_candidate_sets") or []:
            row = dict(item)
            query = str(row.get("query") or "")
            search_path = str(row.get("path") or ".") or "."
            orchestrator.search_candidate_sets[(query, search_path)] = row
        orchestrator._search_hit_paths = {}
        for row in state.get("search_hit_paths") or []:
            query = str(row.get("query") or "")
            search_path = str(row.get("path") or ".") or "."
            orchestrator._search_hit_paths[(query, search_path)] = [
                str(path) for path in (row.get("hits") or []) if path
            ]
        orchestrator._restore_search_hit_paths_from_candidates()
        orchestrator.mission_id = str(state.get("mission_id") or "")
        orchestrator._restore_preserved_evidence(state.get("evidence") or [])
        orchestrator._refresh_goal_read_target()
        return orchestrator

    def _evidence_row_for_grill(self, item: Any) -> dict[str, Any]:
        row = asdict(item)
        persistent_id = self.persistent_evidence_ids.get(item.evidence_id)
        if persistent_id:
            row["persistent_evidence_id"] = persistent_id
        return row

    def _restore_preserved_evidence(self, rows: Iterable[Mapping[str, Any]]) -> None:
        for item in rows:
            row = dict(item)
            evidence_id = str(row.get("evidence_id") or "").strip()
            if not evidence_id or evidence_id in self.runtime.evidence:
                continue
            task_ids = [
                str(task_id)
                for task_id in (row.get("task_ids") or [])
                if str(task_id) in self.runtime.tasks
            ]
            if not task_ids:
                task_ids = [self.current_task_id]
            record = EvidenceRecord(
                evidence_id=evidence_id,
                source_type=str(row.get("source_type") or "tool"),
                source=str(row.get("source") or ""),
                summary=str(row.get("summary") or ""),
                created_by_action=str(row.get("created_by_action") or ""),
                tool_name=row.get("tool_name"),
                target=row.get("target"),
                relevant_content=row.get("relevant_content"),
                supported_completion_conditions=list(
                    row.get("supported_completion_conditions") or []
                ),
                certainty=str(row.get("certainty") or InformationCertainty.OBSERVED.value),
                verified=bool(row.get("verified", True)),
            )
            self.runtime.add_evidence(record, task_ids)
            persistent_id = str(row.get("persistent_evidence_id") or "").strip()
            if persistent_id:
                self.persistent_evidence_ids[evidence_id] = persistent_id

    def apply_human_grill_answer(self, text: str) -> dict[str, Any]:
        """Add a confirmed clarification and re-evaluate Goal. Does not rerun completed searches."""
        answer = str(text or "").strip()
        if answer:
            self._human_grill_answers.append(answer)
        extracted = self._grill_answer_path_grounds()
        if answer:
            from ai_tool.human_decision_premise import (
                build_initial_grill_decision_record,
                initial_grill_question_id_for_orchestrator,
                initial_grill_semantic_decision_key,
            )

            self.confirmed_clarifications.append(
                build_initial_grill_decision_record(
                    answer,
                    decision_key=initial_grill_semantic_decision_key(self),
                    question_id=initial_grill_question_id_for_orchestrator(self),
                    extracted_path_grounds=extracted,
                )
            )
        self._refresh_goal_read_target()
        self._maybe_select_grill_named_workspace_file()
        if not self.needs_human_grill():
            self._maybe_bridge_selected_goal_read()
        return {
            "status": "CLARIFICATION_APPLIED",
            "extracted_path_grounds": extracted,
            "goal_status": self.goal_read_target.get("status"),
            "selected": self.goal_read_target.get("selected"),
            "needs_human_grill": self.needs_human_grill(),
            "original_request": self.request,
            "ground_source": self.goal_read_target.get("ground_source"),
            "completed_search_repeated": False,
        }

    def pending_definition_action(self) -> dict[str, Any] | None:
        """TC1 Index action for Runtime inject. Not a capability next_action."""
        if self.current_task_id != "TC1":
            return None
        if not self.concept_resolution.detected:
            return None
        action = next_definition_action(self.concept_resolution)
        if action is None:
            return None
        tool, arguments = action
        if tool not in {"read_file", "search_files"}:
            return None
        names = {canonical_tool_name(item) for item in self._registry_tools}
        if names and tool not in names:
            return None
        return {"tool": tool, "arguments": dict(arguments)}

    def pending_selected_read_action(self) -> dict[str, Any] | None:
        """After Grill re-eval, only the unread selected file. Never a completed search."""
        if self.needs_human_grill():
            return None
        if self.goal_read_target.get("status") not in {"SELECTED", "PROVISIONAL_SELECTED"}:
            return None
        selected = str(self.goal_read_target.get("selected") or "")
        if not selected or self._goal_target_read_observed(selected):
            return None
        self._maybe_bridge_selected_goal_read()
        pending = self._pending_observation_action
        if not pending:
            return None
        if str(pending.get("tool") or "") == "search_files":
            return None
        if str((pending.get("arguments") or {}).get("path") or "") != selected:
            return None
        return self.pending_capability_action()

    def _restore_search_hit_paths_from_candidates(self) -> None:
        for key, item in self.search_candidate_sets.items():
            if self._search_hit_paths.get(key):
                continue
            counts = item.get("matches_per_path") or {}
            hits: list[str] = []
            for candidate, count in counts.items():
                path = str(candidate or "").strip()
                if not path:
                    continue
                hits.extend([path] * max(1, int(count or 1)))
            if not hits:
                hits = [
                    str(path)
                    for path in (item.get("returned_paths_in_order") or [])
                    if str(path).strip()
                ]
            self._search_hit_paths[key] = hits
        for key, item in self.search_candidate_sets.items():
            if self._search_hit_texts.get(key):
                continue
            texts = {
                _normalize_rel_path(str(path)): [
                    str(snippet)
                    for snippet in (rows or [])
                    if str(snippet).strip()
                ]
                for path, rows in dict(item.get("observed_match_texts") or {}).items()
            }
            if texts:
                self._search_hit_texts[key] = texts

    def _maybe_select_grill_named_workspace_file(self) -> None:
        """If Grill named a unique existing path that was not a search hit, accept that identity."""
        if self.goal_read_target.get("status") in {"SELECTED", "PROVISIONAL_SELECTED"}:
            return
        grill = self._grill_answer_path_grounds()
        if len(grill) != 1:
            return
        token = _normalize_rel_path(grill[0])
        if not token or "/" not in token:
            return
        candidate_paths: list[str] = []
        for item in self.search_candidate_sets.values():
            if item.get("observation_role") == "goal_request":
                candidate_paths.extend(
                    str(path) for path in (item.get("returned_paths_in_order") or [])
                )
        if _match_confirmed_paths_in_candidates([token], candidate_paths):
            return
        if not self._can_bridge_goal_read(token):
            return
        target = dict(self.goal_read_target)
        target["status"] = "SELECTED"
        target["reason"] = "HUMAN_GRILL_CONFIRMED_PATH"
        target["selected"] = token
        target["ground_source"] = "human_grill"
        target["uniqueness_cause"] = "goal_request"
        target["uniqueness_class"] = "UNIQUE_CONFIRMED"
        target["matched_confirmed_paths"] = [token]
        self.goal_read_target = target

    def _can_close_unresolved_goal(self) -> bool:
        """True when identity is unresolved after a complete scan, not missing Evidence."""
        if self.goal_read_target.get("status") in {"SELECTED", "PROVISIONAL_SELECTED"}:
            return False
        if goal_needs_human_grill(
            self.goal_read_target,
            self.search_candidate_sets.values(),
        ):
            return False
        if self.goal_read_target.get("uniqueness_class") != "IDENTITY_UNRESOLVED":
            return False
        complete_sets = [
            item
            for item in self.search_candidate_sets.values()
            if item.get("scan_complete")
        ]
        if not complete_sets:
            return False
        goal_incomplete = [
            item
            for item in self.search_candidate_sets.values()
            if item.get("observation_role") == "goal_request"
            and not item.get("scan_complete")
        ]
        if goal_incomplete:
            return False
        reason = str(self.goal_read_target.get("reason") or "")
        if reason == "SCAN_INCOMPLETE":
            return False
        unique_n = max(int(item.get("unique_path_count") or 0) for item in complete_sets)
        cause = str(self.goal_read_target.get("uniqueness_cause") or "")
        if cause in {
            "multiple_evidence_paths",
            "followup_hit_cardinality",
            "agent_proposal",
        }:
            return True
        if reason in {
            "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES",
            "NO_CONFIRMED_PATH_GROUND",
            "AGENT_STEERED_UNIQUE_PATH",
            "CONFIRMED_PATH_NOT_IN_CANDIDATES",
        } and unique_n >= 1:
            return True
        return False

    def unresolved_goal_close_record(self) -> dict[str, Any]:
        return {
            "status": "CLOSED_UNRESOLVED",
            "reason": self.goal_read_target.get("reason"),
            "uniqueness_cause": self.goal_read_target.get("uniqueness_cause"),
            "uniqueness_class": self.goal_read_target.get("uniqueness_class"),
            "selected": None,
            "user_variable": dict(self.goal_read_target.get("user_variable") or empty_user_variable()),
            "candidates_preserved": True,
            "evidence_preserved": True,
            "unique_path_counts": [
                {
                    "query": item.get("query"),
                    "unique_path_count": item.get("unique_path_count"),
                    "substring_cardinality": item.get("substring_cardinality"),
                }
                for item in self.search_candidate_sets.values()
            ],
        }

    def _unresolved_complete_search_sets(self) -> list[dict[str, Any]]:
        if self.goal_read_target.get("status") in {"SELECTED", "PROVISIONAL_SELECTED"}:
            return []
        return [
            item
            for item in self.search_candidate_sets.values()
            if item.get("scan_complete") and item.get("unresolved_for_read")
        ]

    def _followup_not_additional_reason(self, action: Mapping[str, Any]) -> str | None:
        """None means this action is additional System investigation."""
        tool = str(action.get("tool") or "")
        arguments = dict(action.get("arguments") or {})
        if tool == "search_files":
            query = str(arguments.get("query") or "").strip()
            path = _search_path_arg(arguments)
            if not query:
                return "SEARCH_QUERY_MISSING"
            existing = self.search_candidate_sets.get((query, path))
            if existing and existing.get("scan_complete"):
                return "SEARCH_ALREADY_COMPLETE"
            if existing and not existing.get("scan_complete"):
                return "SEARCH_ALREADY_IN_PROGRESS"
            return None
        if tool == "list_files":
            path = _search_path_arg(arguments)
            if path in {"", "."}:
                return "LIST_PATH_NOT_GROUNDED"
            return None
        if tool == "read_file":
            if not str(arguments.get("path") or "").strip():
                return "READ_PATH_MISSING"
            return None
        return "NOT_PREPARED_FOLLOWUP_ACTION"

    def _followup_conversion_observation(
        self,
        *,
        rows: list[CapabilityResolution],
        gaps: list[CapabilityResolution],
        blocked: list[str],
        executable: list[dict[str, Any]],
        skipped_not_readonly: int,
    ) -> dict[str, Any]:
        """Facts from existing Resolution / Gap APIs. Does not invent a new mapper."""
        return {
            "required_capabilities": [
                item.required_capability
                for item in rows
                if item.required_capability
            ],
            "resolution_statuses": [item.status for item in rows],
            "selected_tools": [item.selected_tool for item in rows if item.selected_tool],
            "candidate_tools": [
                tool
                for item in rows
                for tool in item.candidate_tools
            ],
            "unresolved_arguments": [
                name
                for item in rows
                for name in item.unresolved_arguments
            ],
            "gap_capabilities": [
                item.required_capability
                for item in gaps
                if item.required_capability
            ],
            "blocked_action_reasons": list(blocked),
            "executable_count": len(executable),
            "skipped_not_readonly_count": skipped_not_readonly,
            "stagnation_observed": self.runtime.is_stagnating(self.current_task_id),
            "recovery_classifies_followup_conversion": False,
        }

    def _classify_followup_action_block(
        self,
        *,
        need: str,
        observation: Mapping[str, Any],
    ) -> str:
        if not str(need or "").strip():
            return "EMPTY_NEED"
        if int(observation.get("executable_count") or 0) > 1:
            return "MULTIPLE_EXECUTABLE_FOLLOWUPS"
        blocked = list(observation.get("blocked_action_reasons") or [])
        if blocked and int(observation.get("executable_count") or 0) == 0:
            if len(blocked) == 1:
                return str(blocked[0])
            return "FOLLOWUP_NOT_ADDITIONAL"
        caps = list(observation.get("required_capabilities") or [])
        if not caps:
            return "NO_REQUIRED_CAPABILITY"
        if observation.get("gap_capabilities"):
            return "TOOL_GAP_UNCONFIRMED"
        statuses = list(observation.get("resolution_statuses") or [])
        if "CANDIDATES_AVAILABLE" in statuses:
            return "CANDIDATES_AVAILABLE"
        unresolved = list(observation.get("unresolved_arguments") or [])
        if unresolved:
            return "ARGUMENTS_UNRESOLVED"
        if observation.get("selected_tools") and not blocked:
            return "ACTION_PREP_ABSENT"
        if int(observation.get("skipped_not_readonly_count") or 0) > 0:
            return "NOT_READ_ONLY"
        return "NO_EXECUTABLE_FOLLOWUP"

    def accept_semantic_followup(self, need_text: str) -> dict[str, Any]:
        """Resolve a meaning-level next investigation via existing Capability Action.

        Does not pick a search hit. Conversion failure is classified from
        existing Resolution/Gap/argument facts. Search cardinality that needs
        human intent opens conversation Grill instead of more investigation.
        """
        if self.needs_human_grill():
            return {
                "status": "NOT_APPLICABLE",
                "action": None,
                "reason": "HUMAN_GRILL_REQUIRED",
                "human_confirmation_eligible": True,
            }
        if not self._unresolved_complete_search_sets():
            return {
                "status": "NOT_APPLICABLE",
                "action": None,
                "human_confirmation_eligible": False,
            }
        need = str(need_text or "").strip()
        record: dict[str, Any] = {
            "need": need[:2000],
            "status": "NOT_EXECUTABLE",
            "action": None,
            "reason": None,
            "conversion": None,
            "human_confirmation_eligible": False,
            "proposed_investigation_target": None,
            "proposed_path_grounds": [],
        }
        if not need:
            record["reason"] = "EMPTY_NEED"
            record["conversion"] = {
                "required_capabilities": [],
                "resolution_statuses": [],
                "blocked_action_reasons": [],
                "executable_count": 0,
                "recovery_classifies_followup_conversion": False,
            }
            self.followup_investigations.append(record)
            return record
        task = SimpleNamespace(
            task_id="TF",
            title=need,
            instruction=need,
            completion_conditions=[],
        )
        index = load_workspace_index()
        registry = self._registry_tools or None
        rows = resolve_capabilities(
            task,
            capability_index=index,
            registry_tools=registry,
        )
        gaps = detect_required_tool_gaps(
            task,
            capability_index=index,
            registry_tools=registry,
        )
        prepared: list[dict[str, Any]] = []
        skipped_not_readonly = 0
        for item in rows:
            if not item.next_action:
                continue
            if not self._is_read_only_entry(str(item.next_action.get("tool") or "")):
                skipped_not_readonly += 1
                continue
            prepared.append(dict(item.next_action))
        executable: list[dict[str, Any]] = []
        blocked: list[str] = []
        for action in prepared:
            why_not = self._followup_not_additional_reason(action)
            if why_not:
                blocked.append(why_not)
                continue
            executable.append(action)
        observation = self._followup_conversion_observation(
            rows=rows,
            gaps=gaps,
            blocked=blocked,
            executable=executable,
            skipped_not_readonly=skipped_not_readonly,
        )
        record["conversion"] = observation
        record["proposed_path_grounds"] = confirmed_read_path_grounds(
            need,
            capability_index=index,
            registry_tools=registry,
        )
        if len(executable) == 1:
            record["status"] = "EXECUTABLE"
            record["action"] = executable[0]
            record["proposed_investigation_target"] = {
                "tool": executable[0]["tool"],
                "arguments": dict(executable[0].get("arguments") or {}),
            }
            record["reason"] = None
            record["human_confirmation_eligible"] = False
        else:
            record["reason"] = self._classify_followup_action_block(
                need=need, observation=observation
            )
            record["human_confirmation_eligible"] = False
        self.followup_investigations.append(record)
        return record

    def should_retry_semantic_followup(self, record: Mapping[str, Any] | None) -> bool:
        """Return the conversion reason to the Agent instead of Human handoff."""
        if not isinstance(record, Mapping):
            return False
        if self.needs_human_grill():
            return False
        if record.get("status") != "NOT_EXECUTABLE":
            return False
        if not self._unresolved_complete_search_sets():
            return False
        need = str(record.get("need") or "")
        earlier_same = [
            item
            for item in self.followup_investigations[:-1]
            if item.get("status") == "NOT_EXECUTABLE"
            and str(item.get("need") or "") == need
        ]
        if earlier_same:
            return False
        failed = sum(
            1
            for item in self.followup_investigations
            if item.get("status") == "NOT_EXECUTABLE"
        )
        return failed <= FOLLOWUP_CONVERSION_RETRY_LIMIT

    def followup_retry_hint(self, record: Mapping[str, Any] | None = None) -> str:
        payload = dict(record or (self.followup_investigations[-1] if self.followup_investigations else {}))
        reason = str(payload.get("reason") or "NOT_EXECUTABLE")
        return (
            f"{self.hint()}\n\n"
            "直前の次調査はSystem Actionにできませんでした。"
            "直ちにHuman確認へは落としません。\n"
            f"切り分けた理由: {reason}\n"
            "この理由を踏まえ、別の意味レベルの次調査を1つだけ出してください。"
            "検索ヒットから1件を選んでreadしないでください。"
        )

    def _registry_entry(self, tool_name: str | None) -> Mapping[str, Any] | None:
        if not tool_name:
            return None
        for entry in self._registry_tools:
            if canonical_tool_name(entry) == tool_name:
                return entry
        return None

    def _is_read_only_entry(self, tool_name: str | None) -> bool:
        entry = self._registry_entry(tool_name)
        if entry is None:
            return False
        side = str(entry.get("side_effect") or "").strip().casefold()
        if side in {"sandbox-write", "write"}:
            return False
        security = entry.get("security")
        if isinstance(security, Mapping) and security.get("dedicated_sandbox_required"):
            return False
        return True

    def _resolve_current_capability(
        self, llm_tools: Iterable[Mapping[str, Any]] | None = None
    ) -> list[CapabilityResolution]:
        index = load_workspace_index()
        registry = self._registry_tools if self._registry_tools else None
        results = resolve_capabilities(
            self.task,
            capability_index=index,
            registry_tools=registry,
            expectation=self.tool_expectation,
        )
        previous = {
            item.required_capability: item
            for item in self._task_resolutions()
            if item.required_capability
        }
        merged: list[CapabilityResolution] = []
        current_ids: set[str] = set()
        for item in results:
            cap = item.required_capability
            if cap and cap in previous:
                item.evidence_ids = list(previous[cap].evidence_ids)
            if cap:
                current_ids.add(cap)
            merged.append(item)
        self.capability_resolutions[self.current_task_id] = merged
        for gap_id, gap in list(self.runtime.tool_gaps.items()):
            if gap.task_id == self.current_task_id and gap.required_capability not in current_ids:
                del self.runtime.tool_gaps[gap_id]
        names = {canonical_tool_name(item) for item in (llm_tools or [])}
        actions = [
            item.next_action
            for item in merged
            if item.next_action and item.next_action.get("tool") in names
        ]
        if len(actions) == 1:
            action = actions[0]
            owner = next(item for item in merged if item.next_action == action)
            self.tool_expectation = ToolExpectation(
                generated=True,
                required_capability=owner.required_capability,
                expected_tool=str(action["tool"]),
                expected_arguments=dict(action.get("arguments") or {}),
                reason="Current Taskを既存のagent-visible Capabilityへ接続する",
                level="required",
            )
        elif len(actions) == 0:
            mutation = [
                item
                for item in merged
                if item.selected_tool and self._registry_entry(item.selected_tool)
                and (self._registry_entry(item.selected_tool) or {}).get("security", {}).get("dedicated_sandbox_required")
            ]
            if len(mutation) == 1:
                task_text = _task_operation_text(self.task, self.request)
                match = _WORKSPACE_PATH.search(task_text) or _WORKSPACE_FILE_NAME.search(task_text)
                if match:
                    selected = mutation[0].selected_tool
                    self.tool_expectation = ToolExpectation(
                        generated=True,
                        required_capability=str(mutation[0].required_capability or "workspace_file_mutation"),
                        expected_tool=selected,
                        expected_arguments={"path": match.group(1).strip("`'\"")},
                        reason=(
                            "The request identifies a concrete Sandbox file mutation. "
                            "Use the Runtime-owned Dedicated Sandbox; never choose its root or session id."
                        ),
                        level="required",
                    )
        for result in merged:
            if (
                result.status == "NO_MATCH"
                and result.capability_index_checked
                and result.registry_checked
            ):
                self._evidence_index += 1
                evidence_id = f"E{self._evidence_index}"
                self.runtime.add_evidence(
                    EvidenceRecord(
                        evidence_id,
                        "capability_registry_check",
                        "registry/tools.json",
                        f"{result.required_capability}: agent-visible equivalent not found",
                        "capability_resolution",
                        target="registry/tools.json",
                        relevant_content=json.dumps(
                            {
                                "candidate_tools": result.candidate_tools,
                                "existing_candidates": result.existing_candidates,
                                "rejection_reasons": result.rejection_reasons,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                    [self.current_task_id],
                )
                confirm_tool_gap(result, evidence_id)
                self.runtime.record_confirmed_tool_gap(
                    self.current_task_id,
                    str(result.required_capability),
                    registry_checked=result.registry_checked,
                    capability_index_checked=result.capability_index_checked,
                    existing_candidates=result.existing_candidates,
                    rejected_candidates=result.rejection_reasons,
                    suggested_minimal_tool=result.suggested_minimal_tool,
                    evidence_ids=result.evidence_ids,
                )
        return merged

    def _registry_requires_dedicated_sandbox(self, tool_name: str | None) -> bool:
        if not tool_name:
            return False
        entry = self._registry_entry(tool_name)
        security = entry.get("security") if isinstance(entry, Mapping) else None
        return isinstance(security, Mapping) and bool(security.get("dedicated_sandbox_required"))

    def _request_implies_sandbox_mutation(self) -> bool:
        text = _task_operation_text(self.task, self.request).casefold()
        if "sandbox" not in text and "tetris/" not in text:
            return False
        create_hints = ("作", "create", "作成", "書き込", "write", "build", "implement")
        return any(hint in text for hint in create_hints)

    def requires_dedicated_sandbox(self) -> bool:
        for item in self._task_resolutions():
            if self._registry_requires_dedicated_sandbox(item.selected_tool):
                return True
        expected = self.tool_expectation.expected_tool if self.tool_expectation else None
        if self._registry_requires_dedicated_sandbox(expected):
            return True
        if self._request_implies_sandbox_mutation():
            for entry in self._registry_tools:
                if self._registry_requires_dedicated_sandbox(canonical_tool_name(entry)):
                    return True
        return False

    def required_mutation_tool(self) -> str | None:
        """Return the unique Runtime-selected mutation Tool, never an LLM guess."""
        names: list[str] = []
        for item in self._task_resolutions():
            if item.status != "RESOLVED" or not item.selected_tool:
                continue
            entry = self._registry_entry(item.selected_tool)
            security = entry.get("security") if isinstance(entry, Mapping) else None
            if isinstance(security, Mapping) and security.get("dedicated_sandbox_required"):
                names.append(item.selected_tool)
        if len(names) == 1:
            return names[0]
        return None

    def relevant_tools(self, tools: Iterable[Mapping[str, Any]]) -> list[str]:
        text = f"{self.task.title} {self.task.instruction}".casefold()
        available = {
            name for item in tools if (name := canonical_tool_name(item))
        }
        if not self._registry_tools:
            # Compatibility for isolated callers that only provide provider schemas.
            return sorted(available)
        selected: set[str] = set()
        for entry in self._registry_tools:
            name = canonical_tool_name(entry)
            if not name or name not in available or entry.get("visibility") != "agent":
                continue
            terms = [
                name,
                entry.get("category"),
                entry.get("subcategory"),
                *(entry.get("keywords") or []),
            ]
            if any(
                str(term).strip().casefold() in text
                for term in terms
                if term is not None and str(term).strip()
            ):
                selected.add(name)
        expected = self.tool_expectation.expected_tool
        if expected in available:
            selected.add(str(expected))
        for resolution in self._task_resolutions():
            if resolution.selected_tool in available:
                selected.add(str(resolution.selected_tool))
            action = resolution.next_action
            if action and action.get("tool") in available:
                selected.add(str(action["tool"]))
        if self._injected_capability_tool in available:
            selected.add(str(self._injected_capability_tool))
        return sorted(selected)

    def pending_observation_continuation(self) -> dict[str, Any] | None:
        """T1 Observation が決めた次の1手。H4 next_action ではない。"""
        if self.current_task_id != "T1":
            return None
        if self.task.status == TaskStatus.COMPLETE.value:
            return None
        if self.needs_human_grill():
            return None
        pending = self._pending_observation_action
        if not pending:
            return None
        tool = str(pending.get("tool") or "")
        if not tool:
            self._pending_observation_action = None
            return None
        self._pending_observation_action = None
        return {"tool": tool, "arguments": dict(pending.get("arguments") or {})}

    def pending_mutation_capability_action(self) -> dict[str, Any] | None:
        """Return one Runtime-owned mutation bridge when arguments are complete enough."""
        if not self.tool_expectation.generated:
            return None
        tool = str(self.tool_expectation.expected_tool or "")
        if not tool or not self._registry_requires_dedicated_sandbox(tool):
            return None
        if self.runtime.sandbox_session is None:
            return None
        arguments = dict(self.tool_expectation.expected_arguments or {})
        path = str(arguments.get("path") or "").strip()
        if not path:
            return None
        if tool == "create_file" and not str(arguments.get("content") or "").strip():
            return None
        if tool == "edit_file" and not (
            str(arguments.get("old_text") or "").strip()
            and str(arguments.get("new_text") or "").strip()
        ):
            return None
        if any(
            item.tool_name == tool
            and item.task_id == self.current_task_id
            and item.result_status == "success"
            and _action_path_key(item.arguments) == path
            for item in self.runtime.actions
        ):
            return None
        self._injected_capability_tool = tool
        return {"tool": tool, "arguments": arguments}

    def goal_is_incomplete(self) -> bool:
        goal = self.runtime.goals.get("G1") or self.runtime.goals.get(self.current_goal_id)
        return goal is None or goal.status != GoalStatus.COMPLETE.value

    def has_open_runnable_task(self) -> bool:
        from ai_tool.task_execution_guard import task_execution_blocked

        by_id = self.runtime.tasks
        for task in by_id.values():
            if task.status in {TaskStatus.COMPLETE.value, TaskStatus.CANCELLED.value}:
                continue
            if task_execution_blocked(task):
                continue
            deps = task.depends_on or []
            if all(
                dep_id in by_id and by_id[dep_id].status == TaskStatus.COMPLETE.value
                for dep_id in deps
            ):
                return True
        return False

    def premise_execution_block_for_task(self, task_id: str | None = None) -> dict[str, Any] | None:
        from ai_tool.task_execution_guard import task_execution_blocked

        token = str(task_id or self.current_task_id or "")
        task = self.runtime.tasks.get(token)
        if task is None:
            return None
        return task_execution_blocked(task)

    def assert_current_task_executable_for_premise(self) -> None:
        from ai_tool.task_execution_guard import TaskExecutionBlockedError

        graph_block = self.graph_propagation_execution_block()
        if graph_block is not None:
            raise TaskExecutionBlockedError(graph_block)
        block = self.premise_execution_block_for_task()
        if block is not None:
            raise TaskExecutionBlockedError(block)

    def graph_propagation_execution_block(self) -> dict[str, Any] | None:
        from ai_tool.task_change_propagation_guard import graph_propagation_blocks_execution

        return graph_propagation_blocks_execution(self)

    def propagation_goal_completion_block(self) -> dict[str, Any] | None:
        from ai_tool.task_change_propagation_guard import propagation_blocks_goal_completion

        return propagation_blocks_goal_completion(self)

    def premise_revalidation_goal_completion_block(self) -> dict[str, Any] | None:
        from ai_tool.premise_corrective_replan import premise_revalidation_blocks_goal_completion

        return premise_revalidation_blocks_goal_completion(self)

    def _requires_incomplete_goal_guard(self) -> bool:
        if not self.goal_is_incomplete():
            return False
        if self.propagation_goal_completion_block() is not None:
            return True
        if self.premise_revalidation_goal_completion_block() is not None:
            return True
        if not self.has_open_runnable_task():
            return False
        task = self.task
        if getattr(task, "source", None) == "goal_handoff":
            return True
        capability = str(self.tool_expectation.required_capability or "")
        return self.tool_expectation.generated and capability in {
            "workspace_file_create",
            "workspace_file_edit",
            "workspace_file_mutation",
        }

    def incomplete_goal_bridge_before_break(self) -> dict[str, Any] | None:
        """Prefer execute/continuation/replan over silent loop exit when work remains."""
        if not self._requires_incomplete_goal_guard():
            return None
        mutation = self.pending_mutation_capability_action()
        if mutation is not None:
            return {"outcome": "execute", "action": mutation}
        from ai_tool.production_verification_acceptance import (
            advance_runnable_handoff_task,
            pending_verification_action,
            pytest_failed_repair_hint,
        )

        advance_runnable_handoff_task(self)
        verification = pending_verification_action(self)
        if verification is not None:
            return {"outcome": "execute", "action": verification}
        if not self.requires_dedicated_sandbox():
            read_action = self._pending_read_capability_action()
            if read_action is not None:
                return {"outcome": "execute", "action": read_action}
        continuation = self.pending_observation_continuation()
        if continuation is not None:
            return {"outcome": "continuation", "action": continuation}
        repair = pytest_failed_repair_hint(self)
        if repair:
            return {"outcome": "replan", "replan_hint": repair}
        recovery = self.recovery_hint()
        if recovery:
            return {"outcome": "replan", "replan_hint": recovery}
        confirmed_gaps = [
            item
            for item in self.runtime.tool_gaps.values()
            if item.status == "confirmed" and item.requires_human_approval
        ]
        if confirmed_gaps:
            return {"outcome": "blocked", "reason": "confirmed_tool_gap"}
        return {"outcome": "incomplete", "reason": "goal_incomplete_open_tasks"}

    def incomplete_goal_terminal_outcome(self) -> str | None:
        """Terminal outcome when silent COMPLETED must be withheld."""
        bridge = self.incomplete_goal_bridge_before_break()
        if bridge is None:
            return None
        outcome = str(bridge.get("outcome") or "")
        if outcome in {"execute", "continuation", "replan"}:
            return outcome
        return str(bridge.get("outcome") or "incomplete")

    def pending_capability_action(self) -> dict[str, Any] | None:
        """Return one verified bridge action not yet taken."""
        mutation = self.pending_mutation_capability_action()
        if mutation is not None:
            return mutation
        from ai_tool.production_verification_acceptance import (
            advance_runnable_handoff_task,
            pending_verification_action,
        )

        advance_runnable_handoff_task(self)
        verification = pending_verification_action(self)
        if verification is not None:
            self._injected_capability_tool = "run_test_plan"
            return verification
        continued = self.pending_observation_continuation()
        if continued is not None:
            self._injected_capability_tool = str(continued["tool"])
            return continued
        if self.requires_dedicated_sandbox():
            return None
        return self._pending_read_capability_action()

    def _pending_read_capability_action(self) -> dict[str, Any] | None:
        """Return one verified read-only bridge action not yet taken."""
        actions = []
        for resolution in self._task_resolutions():
            action = resolution.next_action
            if not action or not resolution.selected_tool:
                continue
            if not self._is_read_only_entry(str(action.get("tool") or resolution.selected_tool)):
                continue
            actions.append(action)
        if len(actions) != 1:
            return None
        action = actions[0]
        arguments = dict(action.get("arguments") or {})
        if (
            self.tool_expectation.expected_tool == action.get("tool")
            and self.tool_expectation.expectation_matched
        ):
            return None
        if action.get("tool") == "search_files":
            query = str(arguments.get("query") or "")
            search_path = _search_path_arg(arguments)
            existing = self.search_candidate_sets.get((query, search_path))
            if existing and existing.get("scan_complete"):
                return None
            if self._search_pages_for(query, search_path):
                return None
        elif self._path_capability_action_already_taken(
            str(action.get("tool") or ""), arguments
        ) or self.path_absent_from_complete_listing(
            str(action.get("tool") or ""), arguments
        ):
            return None
        self._injected_capability_tool = str(action["tool"])
        return {"tool": str(action["tool"]), "arguments": arguments}

    def _read_file_pages_for(self, path: str) -> list[Any]:
        normalized = _action_path_key({"path": path})
        return [
            item
            for item in self.runtime.actions
            if item.tool_name == "read_file"
            and _action_path_key(item.arguments) == normalized
        ]

    def _path_capability_action_already_taken(
        self, tool: str, arguments: Mapping[str, Any]
    ) -> bool:
        """Bridge injects one unread path action. Do not repeat a taken path."""
        if tool not in {"read_file", "list_files"}:
            return False
        path = _action_path_key(arguments)
        if tool == "read_file":
            offset = int(arguments.get("offset") or 1)
            limit = arguments.get("limit")
            return any(
                item.tool_name == tool
                and _action_path_key(item.arguments) == path
                and int(item.arguments.get("offset") or 1) == offset
                and (
                    item.arguments.get("limit") == limit
                    if limit is not None
                    else True
                )
                for item in self.runtime.actions
            )
        return any(
            item.tool_name == tool
            and _action_path_key(item.arguments) == path
            for item in self.runtime.actions
        )

    def path_absent_from_complete_listing(
        self, tool: str, arguments: Mapping[str, Any]
    ) -> bool:
        """True when a complete list_files of the parent omitted this path."""
        if tool not in {"read_file", "list_files"}:
            return False
        path = _action_path_key(arguments)
        if path in {".", ""}:
            return False
        parent, _, name = path.rpartition("/")
        parent_key = _action_path_key({"path": parent or "."})
        listing = self._directory_listings.get(parent_key)
        if not listing or listing.get("truncated") or not name:
            return False
        names = {str(item).casefold() for item in listing.get("names") or []}
        rels = {
            _action_path_key({"path": item}).casefold()
            for item in listing.get("paths") or []
        }
        return name.casefold() not in names and path.casefold() not in rels

    def missing_path_observation(
        self, tool: str, arguments: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Same Tool Result Contract as a missing-path Tool call, without re-probing."""
        path = arguments.get("path")
        if tool == "list_files":
            return path_error("パスが存在しません", code="path_not_found", path=path)
        return path_error("ファイルが存在しません", code="path_not_found", path=path)

    def _record_directory_listing(
        self, arguments: Mapping[str, Any], source_result: Mapping[str, Any]
    ) -> None:
        base = _action_path_key(
            {"path": str(arguments.get("path") or source_result.get("base") or ".")}
        )
        names: list[str] = []
        paths: list[str] = []
        entries = source_result.get("entries")
        if isinstance(entries, list):
            for item in entries:
                if not isinstance(item, Mapping):
                    continue
                name = str(item.get("name") or "").strip()
                rel = str(item.get("path") or name).strip()
                if name:
                    names.append(name)
                if rel:
                    paths.append(rel)
        self._directory_listings[base] = {
            "names": names,
            "paths": paths,
            "truncated": bool(
                source_result.get("truncated") or source_result.get("has_more")
            ),
        }

    def required_capability(self) -> str | None:
        """Compat wrapper over required_capabilities(). Core internals must not call this."""
        found = required_capabilities(
            self.task,
            expectation=self.tool_expectation,
            capability_index=load_workspace_index(),
            registry_tools=self._registry_tools or None,
        )
        if not found:
            return None
        if len(found) == 1:
            return found[0]
        raise MultipleCapabilitiesError(
            "required_capabilities returned multiple ids; singular API cannot fold them: "
            + ", ".join(found)
        )

    def detect_required_tool_gaps(
        self, registry_tools: Iterable[Mapping[str, Any]]
    ) -> list:
        rows = detect_required_tool_gaps(
            self.task,
            capability_index=load_workspace_index(),
            registry_tools=list(registry_tools),
            expectation=self.tool_expectation,
        )
        gaps = []
        for item in rows:
            resolved = None
            if item.required_capability:
                resolved = _help_confirmed_tool_for_capability(item.required_capability)
            names = {canonical_tool_name(row) for row in registry_tools}
            if resolved and resolved in names:
                continue
            gap = self.runtime.detect_tool_gap(
                self.current_task_id,
                str(item.required_capability),
                registry_tools,
                candidate_tool=resolved,
            )
            if gap is not None:
                gaps.append(gap)
        return gaps

    def detect_required_tool_gap(
        self, registry_tools: Iterable[Mapping[str, Any]]
    ) -> object | None:
        gaps = self.detect_required_tool_gaps(registry_tools)
        if not gaps:
            return None
        if len(gaps) == 1:
            return gaps[0]
        raise MultipleCapabilitiesError(
            "detect_required_tool_gaps returned multiple gaps; singular API cannot fold them"
        )

    def allocate_action_id(self) -> str:
        self._action_index += 1
        return f"A{self._action_index}"

    def execute_test_plan_action(
        self,
        arguments: Mapping[str, Any],
        *,
        relevant_tools: Iterable[str],
        authorization_packet: Mapping[str, Any] | None = None,
        verification_only_task_id: str | None = None,
    ) -> dict[str, Any]:
        from test_safety.runtime_bridge import bridge_test_execution, build_llm_tool_summary
        from test_safety.tool_argument_validation import (
            extract_optional_authorization_packet,
            extract_test_plan_from_arguments,
        )
        from test_safety.plan_fingerprint import compute_plan_fingerprint
        from tools.system.tool_result_contract import normalize_tool_result

        plan = extract_test_plan_from_arguments(arguments)
        plan_fp = compute_plan_fingerprint(plan)
        auth = authorization_packet or extract_optional_authorization_packet(arguments)

        continuation = self._run_test_plan_continuation
        observe_mode = "full"
        if (
            continuation
            and str(continuation.get("plan_fingerprint") or "") == plan_fp
            and continuation.get("observed")
        ):
            action_id = str(continuation["action_id"])
            observe_mode = "continuation_update"
        else:
            action_id = self.allocate_action_id()
            self._run_test_plan_continuation = None

        outcome = bridge_test_execution(
            action_id=action_id,
            test_plan=plan,
            authorization_packet=auth,
        )
        summary_payload = build_llm_tool_summary(outcome)
        resolution_result = (outcome.get("resolution") or {}).get("resolution_result")

        if resolution_result == "AWAITING_HUMAN_APPROVAL":
            self._run_test_plan_continuation = {
                "action_id": action_id,
                "plan_fingerprint": plan_fp,
                "observed": False,
            }
        elif resolution_result in ("BLOCKED", "ERROR", "UNRESOLVED"):
            self._run_test_plan_continuation = None
        elif outcome.get("run_closed") and not outcome.get("test_failed"):
            self._run_test_plan_continuation = None

        if resolution_result == "AWAITING_HUMAN_APPROVAL":
            status = "blocked"
        elif not outcome.get("executor_called"):
            status = "failure"
        elif outcome.get("test_failed"):
            status = "failure"
        else:
            status = "success"

        raw = {
            "ok": status == "success",
            "test_safety": outcome,
            "test_safety_summary": summary_payload,
            "status": status,
        }
        normalized = normalize_tool_result(raw, tool_name="run_test_plan")
        summary = summary_payload.get("stdout_tail") or str(summary_payload.get("resolution_result") or "")

        if observe_mode == "full":
            self.observe_tool(
                "run_test_plan",
                dict(arguments),
                normalized,
                summary,
                relevant_tools=relevant_tools,
                raw_result=raw,
                predetermined_action_id=action_id,
                verification_only_task_id=verification_only_task_id,
            )
            if self._run_test_plan_continuation is not None:
                self._run_test_plan_continuation["observed"] = True
        else:
            self._finalize_run_test_plan_continuation(
                action_id,
                arguments=dict(arguments),
                normalized_result=normalized,
                raw_result=raw,
                summary=summary,
            )

        return raw

    def _finalize_run_test_plan_continuation(
        self,
        action_id: str,
        *,
        arguments: Mapping[str, Any],
        normalized_result: Mapping[str, Any],
        raw_result: Mapping[str, Any],
        summary: Any,
    ) -> None:
        from test_safety.runtime_bridge import safety_run_closure_predicate

        outcome = raw_result.get("test_safety") or {}
        status = str(normalized_result.get("status") or "failure")
        predicate_ok = safety_run_closure_predicate(outcome)
        evidence_gain = status in {"success", "partial"} and predicate_ok
        self.runtime.patch_action_result(
            action_id,
            result_status=status,
            evidence_gain=evidence_gain,
        )
        self._append_test_safety_evidence(
            action_id=action_id,
            arguments=arguments,
            raw_result=raw_result,
            summary=summary,
            predicate_ok=predicate_ok,
        )
        self._run_test_plan_continuation = None

    def _observe_run_test_plan(
        self,
        *,
        action_id: str,
        arguments: Mapping[str, Any],
        normalized_result: Mapping[str, Any],
        raw_result: Mapping[str, Any],
        summary: Any,
        audit: str,
        status: str,
        observed_task_id: str,
        verification_only: bool = False,
    ) -> str:
        from test_safety.runtime_bridge import safety_run_closure_predicate

        outcome = raw_result.get("test_safety") or {}
        predicate_ok = safety_run_closure_predicate(outcome)
        evidence_gain = (
            audit == "ACCEPT" and status in {"success", "partial"} and predicate_ok
        )
        action = ActionRecord(
                action_id,
                observed_task_id,
                "tool_call",
                "run_test_plan",
                dict(arguments),
                status,
                audit,
                evidence_gain,
            )
        if verification_only:
            self.runtime.record_verification_action(action)
        else:
            self.runtime.record_action(action)
        self._append_test_safety_evidence(
            action_id=action_id,
            arguments=arguments,
            raw_result=raw_result,
            summary=summary,
            predicate_ok=predicate_ok,
            task_id=observed_task_id,
        )
        if status == "failure":
            self._failure_index += 1
            resolution = (outcome.get("resolution") or {}).get("resolution_result")
            if not outcome.get("executor_called"):
                code = "test_safety_execution_authorization_failure"
            elif outcome.get("test_failed"):
                code = "pytest_failed"
            else:
                code = "test_safety_failure"
            if resolution == "AWAITING_HUMAN_APPROVAL":
                code = "test_safety_human_approval_required"
            self.runtime.record_failure(
                FailureRecord(
                    f"F{self._failure_index}",
                    observed_task_id,
                    action_id,
                    "run_test_plan",
                    dict(arguments),
                    code,
                )
            )
        return audit

    def _append_test_safety_evidence(
        self,
        *,
        action_id: str,
        arguments: Mapping[str, Any],
        raw_result: Mapping[str, Any],
        summary: Any,
        predicate_ok: bool,
        task_id: str | None = None,
    ) -> None:
        outcome = raw_result.get("test_safety") or {}
        summary_payload = raw_result.get("test_safety_summary") or {}
        compact = json.dumps(summary_payload, ensure_ascii=False)[:3000]
        self._evidence_index += 1
        evidence_id = f"E{self._evidence_index}"
        path = str(summary_payload.get("persisted_run_path") or "")
        self.runtime.add_evidence(
            EvidenceRecord(
                evidence_id,
                "test_safety_run",
                path or f"test_safety://{action_id}",
                compact,
                action_id,
                tool_name="run_test_plan",
                target=path or None,
                relevant_content=compact,
                supported_completion_conditions=(
                    ["test_run_closed"] if predicate_ok else []
                ),
            ),
            [task_id or self.current_task_id],
        )
        target_task_id = task_id or self.current_task_id
        target_task = self.runtime.tasks[target_task_id]
        if predicate_ok and "test_run_closed" in target_task.completion_conditions:
            self.runtime.support_completion_conditions(
                target_task_id,
                evidence_id,
                ["test_run_closed"],
            )
            self.runtime.evaluate_task(
                target_task_id,
                target_task.satisfied_conditions,
            )

    def observe_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        normalized_result: Mapping[str, Any],
        summary: Any,
        *,
        relevant_tools: Iterable[str],
        raw_result: Mapping[str, Any] | None = None,
        predetermined_action_id: str | None = None,
        verification_only_task_id: str | None = None,
    ) -> str:
        if verification_only_task_id is None:
            self.assert_current_task_executable_for_premise()
        observed_task_id = verification_only_task_id or self.current_task_id
        if observed_task_id not in self.runtime.tasks:
            raise ValueError(f"unknown verification task: {observed_task_id}")
        if predetermined_action_id:
            action_id = str(predetermined_action_id)
        else:
            self._action_index += 1
            action_id = f"A{self._action_index}"
        if self.tool_expectation.generated:
            expected_path = (self.tool_expectation.expected_arguments or {}).get("path")
            matched = bool(
                tool_name == self.tool_expectation.expected_tool
                and arguments.get("path") == expected_path
            )
            if self.tool_expectation.actual_tool_called is None or matched:
                self.tool_expectation.actual_tool_called = tool_name
            self.tool_expectation.expectation_matched = (
                self.tool_expectation.expectation_matched or matched
            )
        audit = self.runtime.audit_relevance(
            observed_task_id,
            tool_name=tool_name,
            relevant_tools=relevant_tools,
        )
        status = str(normalized_result.get("status") or "failure")
        if tool_name == "run_test_plan":
            return self._observe_run_test_plan(
                action_id=action_id,
                arguments=arguments,
                normalized_result=normalized_result,
                raw_result=raw_result or normalized_result,
                summary=summary,
                audit=audit,
                status=status,
                observed_task_id=observed_task_id,
                verification_only=verification_only_task_id is not None,
            )
        novel_action = not self.runtime.has_reusable_evidence(
            self.current_task_id, tool_name, arguments
        )
        source_result = raw_result or normalized_result
        if tool_name == "list_files" and status in {"success", "partial"}:
            self._record_directory_listing(arguments, source_result)
        content = _result_text(source_result)
        search_matches = _search_matches(source_result) if tool_name == "search_files" else []
        if search_matches:
            content = "\n".join(
                f"{item.get('path')}:{item.get('line')}: {item.get('text')}"
                for item in search_matches
            )
        next_cursor = ""
        if tool_name == "search_files" and isinstance(source_result, Mapping):
            next_cursor = str(source_result.get("next_cursor") or "").strip()
        query = str(arguments.get("query") or "")
        search_path = _search_path_arg(arguments)
        page_count = len(self._search_pages_for(query, search_path))
        scan_incomplete = bool(next_cursor)
        candidate_set = None
        if tool_name == "search_files":
            key = (query, search_path)
            hits = self._search_hit_paths.setdefault(key, [])
            hits.extend(
                str(item.get("path") or "").replace("\\", "/").strip()
                for item in search_matches
                if str(item.get("path") or "").strip()
            )
            texts = self._search_hit_texts.setdefault(key, {})
            for item in search_matches:
                path = str(item.get("path") or "").replace("\\", "/").strip()
                snippet = str(item.get("text") or "").strip()
                if not path or not snippet:
                    continue
                bucket = texts.setdefault(path, [])
                if snippet not in bucket:
                    bucket.append(snippet[:OBSERVED_MATCH_TEXT_CHARS])
                del bucket[OBSERVED_MATCH_TEXT_LIMIT:]
            candidate_set = fold_search_candidate_set(
                query=query,
                search_path=search_path,
                match_paths=hits,
                scan_complete=not scan_incomplete,
                page_count=page_count + 1,
                observed_match_texts=texts,
            )
            self.search_candidate_sets[key] = candidate_set
            if self._search_is_followup(query, search_path):
                self._ingest_observation_text_grounds(
                    str(item.get("text") or "") for item in search_matches
                )
            self._refresh_goal_read_target()
            candidate_set = self.search_candidate_sets[key]
        elif (
            tool_name == "read_file"
            and status in {"success", "partial"}
            and self.goal_read_target.get("status")
            not in {"SELECTED", "PROVISIONAL_SELECTED"}
        ):
            self._ingest_observation_text_grounds([content])
            self._refresh_goal_read_target()
        if (
            tool_name == "search_files"
            and scan_incomplete
            and page_count + 1 < SEARCH_MAX_CONTINUATION_PAGES
        ):
            self._pending_observation_action = {
                "tool": tool_name,
                "arguments": {
                    "query": query,
                    "path": search_path,
                    "after": next_cursor,
                },
            }
        elif not scan_incomplete and tool_name == "search_files":
            self._maybe_bridge_selected_goal_read(
                current_tool=tool_name,
                current_arguments=arguments,
            )
        elif (
            tool_name == "read_file"
            and status in {"success", "partial"}
            and isinstance(source_result, Mapping)
            and not source_result.get("has_more")
        ):
            self._maybe_bridge_selected_goal_read(
                current_tool=tool_name,
                current_arguments=arguments,
            )
        if tool_name == "search_files" and status in {"success", "partial"}:
            if scan_incomplete:
                observation_status = "INCOMPLETE_OBSERVATION"
            elif search_matches:
                observation_status = "OBSERVED_CANDIDATES"
            else:
                observation_status = "NOT_FOUND_YET"
            self.search_observations.append(
                {
                    "query": query,
                    "path": search_path,
                    "after": arguments.get("after"),
                    "status": observation_status,
                    "match_count": len(search_matches),
                    "files_scanned": (
                        source_result.get("files_scanned")
                        if isinstance(source_result, Mapping)
                        else None
                    ),
                    "has_more": (
                        bool(source_result.get("has_more"))
                        if isinstance(source_result, Mapping)
                        else False
                    ),
                    "next_cursor": next_cursor or None,
                    "confirmed_absent": (
                        not scan_incomplete and not search_matches
                    ),
                }
            )
        definition_content = content
        if self.current_task_id == "TC1" and isinstance(source_result, Mapping):
            lines = source_result.get("lines")
            if isinstance(lines, list):
                definition_content = "\n".join(
                    str(item.get("text") if isinstance(item, Mapping) else item)
                    for item in lines
                )
            if tool_name == "search_files":
                matches = source_result.get("matches")
                if isinstance(matches, list):
                    for item in matches:
                        if not isinstance(item, Mapping):
                            continue
                        candidate = str(item.get("path") or "")
                        candidate_path = Path(candidate)
                        try:
                            resolved_candidate = (REPO_ROOT / candidate_path).resolve()
                            resolved_candidate.relative_to(REPO_ROOT)
                        except (OSError, ValueError):
                            continue
                        if (
                            candidate
                            and not candidate_path.is_absolute()
                            and candidate not in self.concept_resolution.look_first
                            and resolved_candidate.is_file()
                        ):
                            # Search locates a candidate; read_file remains the
                            # authority for definition evidence.
                            self.concept_resolution.look_first.append(candidate)
                            break
        definition_excerpt = None
        if self.current_task_id == "TC1":
            definition_excerpt = observe_definition_result(
                self.concept_resolution,
                tool_name=tool_name,
                arguments=arguments,
                content=definition_content,
            )
            next_action = next_definition_action(self.concept_resolution)
            if next_action is not None:
                next_tool, next_arguments = next_action
                self.tool_expectation = ToolExpectation(
                    generated=True,
                    required_capability="workspace_definition_lookup",
                    expected_tool=next_tool,
                    expected_arguments=next_arguments,
                    reason="Workspace固有概念は推測せず、Indexの次の案内先を確認する",
                    level="required",
                )
        supported = {
            condition: excerpt
            for condition in self.task.completion_conditions
            if (excerpt := _condition_support(condition, content)) is not None
        }
        if status in {"success", "partial"} and isinstance(source_result, Mapping):
            supported.update(
                {
                    condition: excerpt
                    for condition in self.task.completion_conditions
                    if condition not in supported
                    and (
                        excerpt := _structured_condition_support(
                            condition, tool_name, source_result, content
                        )
                    ) is not None
                }
            )
        if tool_name == "read_file" and status in {"success", "partial"}:
            path = str(arguments.get("path") or "")
            supported.update(
                {
                    condition: excerpt
                    for condition in self.task.completion_conditions
                    if condition not in supported
                    and (excerpt := _read_file_condition_support(condition, path, content)) is not None
                }
            )
        if self.current_task_id == "TC1" and definition_excerpt:
            target = str(arguments.get("path") or "")
            path_specific = any(
                path in condition
                for path in self.concept_resolution.look_first
                for condition in self.task.completion_conditions
            )
            supported.update(
                {
                    condition: definition_excerpt
                    for condition in self.task.completion_conditions
                    if not target or target in condition or not path_specific
                }
            )
        if self.task.completion_conditions == ["relevant evidence observed"]:
            observed = content or str(summary)
            if tool_name == "list_files":
                absent = self._named_paths_confirmed_absent(arguments)
                if absent:
                    listing_dir = _action_path_key(arguments)
                    observed = (
                        f"Complete listing of {listing_dir} omitted "
                        f"request-named path(s): {', '.join(absent)}"
                    )
            if observed and self._generic_observation_completes_task(tool_name, arguments):
                supported = {"relevant evidence observed": observed[:1500]}
            else:
                supported.pop("relevant evidence observed", None)
        read_has_more = (
            tool_name == "read_file"
            and status in {"success", "partial"}
            and isinstance(source_result, Mapping)
            and bool(source_result.get("has_more"))
        )
        generic_observation_complete = bool(
            self.task.completion_conditions == ["relevant evidence observed"]
            and supported.get("relevant evidence observed")
        )
        delivery = (
            read_file_llm_delivery(source_result)
            if tool_name == "read_file" and isinstance(source_result, Mapping)
            else None
        )
        continuation_has_more = bool(
            (delivery or {}).get("has_more")
            if delivery is not None
            else read_has_more
        )
        if continuation_has_more and not read_file_observation_complete(
            supported=supported,
            completion_conditions=self.task.completion_conditions,
            generic_observation_completes=generic_observation_complete,
            source_result=source_result,
        ):
            path = str(arguments.get("path") or "")
            next_offset = (
                (delivery or {}).get("next_offset")
                if delivery is not None
                else source_result.get("next_offset")
            )
            if path and next_offset and len(self._read_file_pages_for(path)) < READ_FILE_MAX_CONTINUATION_PAGES:
                self._pending_observation_action = {
                    "tool": "read_file",
                    "arguments": runtime_continuation_read_arguments(
                        path,
                        next_offset=int(next_offset),
                    ),
                }
        matched_resolution = None
        capability_observation = False
        for item in self._task_resolutions():
            action = item.next_action
            if (
                action
                and tool_name == action.get("tool")
                and dict(arguments) == dict(action.get("arguments") or {})
                and status in {"success", "partial"}
                and content
            ):
                matched_resolution = item
                capability_observation = True
                break
        direct_observation = bool(
            status in {"success", "partial"}
            and (
                (tool_name == "read_file" and content)
                or (tool_name == "search_files" and search_matches)
                or content
            )
        )
        relevant_content = "\n\n".join(dict.fromkeys(supported.values()))[:3000]
        if (capability_observation or direct_observation) and not relevant_content:
            relevant_content = content[:3000]
        compact = relevant_content or str(summary)[:500]
        novel_evidence = all(
            item.summary != compact for item in self.runtime.evidence.values()
        )
        evidence_gain = (
            audit == "ACCEPT"
            and status in {"success", "partial"}
            and novel_action
            and novel_evidence
            and (bool(supported) or capability_observation or direct_observation)
        )
        self.runtime.record_action(
            ActionRecord(
                action_id,
                self.current_task_id,
                "tool_call",
                tool_name,
                dict(arguments),
                status,
                audit,
                evidence_gain,
            )
        )
        if evidence_gain:
            self._evidence_index += 1
            evidence_id = f"E{self._evidence_index}"
            self.runtime.add_evidence(
                EvidenceRecord(
                    evidence_id,
                    "tool_result",
                    f"tool://{tool_name}",
                    compact,
                    action_id,
                    tool_name=tool_name,
                    target=str(arguments.get("path") or arguments.get("url") or arguments.get("query") or "") or None,
                    relevant_content=relevant_content or None,
                    supported_completion_conditions=list(supported),
                ),
                [self.current_task_id],
            )
            if self.current_task_id == "TC1":
                self.concept_resolution.evidence_ids.append(evidence_id)
            if capability_observation and matched_resolution is not None:
                if evidence_id not in matched_resolution.evidence_ids:
                    matched_resolution.evidence_ids.append(evidence_id)
            self.runtime.support_completion_conditions(
                self.current_task_id, evidence_id, supported
            )
            for source_task_id, condition in self._review_task_targets.get(
                self.current_task_id, []
            ):
                if condition not in supported:
                    continue
                self.runtime.add_evidence(
                    self.runtime.evidence[evidence_id], [source_task_id]
                )
                self.runtime.support_completion_conditions(
                    source_task_id, evidence_id, [condition]
                )
                self.runtime.evaluate_task(
                    source_task_id,
                    self.runtime.tasks[source_task_id].satisfied_conditions,
                )
            completed = self.runtime.evaluate_task(
                self.current_task_id, self.task.satisfied_conditions
            )
            if observed_task_id == "TC1" and completed:
                self.concept_resolution.resolution_status = "RESOLVED"
                self.concept_resolution.returned_to_original_task = True
                if self.concept_resolution.resolved_definition:
                    self.runtime.add_claim(
                        ClaimRecord(
                            claim_id=f"CL{len(self.runtime.claims) + 1}",
                            claim=self.concept_resolution.resolved_definition,
                            certainty=InformationCertainty.CONFIRMED.value,
                            source="concept_resolution",
                            evidence_ids=list(self.concept_resolution.evidence_ids),
                            verified=True,
                        )
                    )
                for concept_evidence_id in self.concept_resolution.evidence_ids:
                    self.runtime.add_evidence(
                        self.runtime.evidence[concept_evidence_id], ["T1", "T2"]
                    )
                for condition in self.runtime.tasks["T1"].completion_conditions:
                    if (
                        self.concept_resolution.concept
                        and self.concept_resolution.concept.rsplit(".", 1)[-1].casefold()
                        in condition.casefold()
                    ):
                        self.runtime.support_completion_conditions(
                            "T1", self.concept_resolution.evidence_ids[-1], [condition]
                        )
                original_complete = self.runtime.evaluate_task(
                    "T1", self.runtime.tasks["T1"].satisfied_conditions
                )
                self.runtime.evaluate_goal(self.current_goal_id, [])
                if original_complete:
                    self.current_goal_id = "G1.2"
                    self.current_task_id = "T2"
                else:
                    self.current_task_id = "T1"
                next_action = next_definition_action(self.concept_resolution)
                if next_action is None:
                    self.tool_expectation = ToolExpectation()
            if observed_task_id == "T1" and completed:
                self.runtime.evaluate_goal("G1.1", [])
                self.current_goal_id = "G1.2"
                self.current_task_id = "T2"
            elif completed and observed_task_id in self._review_task_targets:
                target_ids = {
                    task_id
                    for task_id, _condition in self._review_task_targets[observed_task_id]
                }
                if all(
                    self.runtime.tasks[task_id].status == "complete"
                    for task_id in target_ids
                ):
                    for goal_id in {
                        self.runtime.tasks[task_id].goal_id for task_id in target_ids
                    }:
                        self.runtime.evaluate_goal(goal_id, [])
                    self.current_goal_id = self.runtime.tasks["T2"].goal_id
                    self.current_task_id = "T2"
        elif status == "failure":
            self._failure_index += 1
            error = normalized_result.get("error")
            code = error.get("code") if isinstance(error, Mapping) else "tool_failure"
            self.runtime.record_failure(
                FailureRecord(
                    f"F{self._failure_index}",
                    self.current_task_id,
                    action_id,
                    tool_name,
                    dict(arguments),
                    str(code or "tool_failure"),
                )
            )
        return audit

    def begin_action(self, tool_name: str) -> None:
        self.runtime.emit_event(
            "ACTION_STARTED", task_id=self.current_task_id, tool_name=tool_name
        )

    def record_sandbox_mutation(self, result: Mapping[str, Any]) -> str | None:
        """Record mutation fact as OBSERVED Evidence, never as condition coverage."""
        value = result.get("mutation")
        if not isinstance(value, Mapping) or value.get("changed") is not True:
            return None
        record = MutationRecord(**dict(value))
        self.runtime.record_mutation(record)
        self._evidence_index += 1
        evidence_id = f"E{self._evidence_index}"
        action_id = self.runtime.actions[-1].action_id if self.runtime.actions else ""
        self.runtime.add_evidence(
            EvidenceRecord(
                evidence_id=evidence_id,
                source_type="sandbox_mutation",
                source=f"sandbox://{record.sandbox_session_id}/{record.relative_path}",
                summary=f"{record.action}: {record.relative_path}",
                created_by_action=action_id,
                tool_name=record.tool,
                target=record.relative_path,
                relevant_content=None,
                supported_completion_conditions=[],
                certainty=InformationCertainty.OBSERVED.value,
                verified=True,
            ),
            [self.current_task_id],
        )
        if self.runtime.actions:
            self.runtime.actions[-1].evidence_gain = True
        return evidence_id

    def recovery_hint(self) -> str | None:
        if self.runtime.is_stagnating(self.current_task_id):
            return self.runtime.recovery_hint(self.current_task_id)
        return None

    def add_local_replan(self, title: str, instruction: str) -> TaskRecord:
        task_id = f"T{len(self.runtime.tasks) + 1}"
        task = TaskRecord(task_id, self.current_goal_id, title, instruction, ["done"])
        self.runtime.replan_add_task(
            ReplanRecord(f"R{len(self.runtime.replans) + 1}", self.current_goal_id, title),
            task,
        )
        return task

    def add_review_task(self, candidate: Mapping[str, Any]) -> TaskRecord:
        """Register one runtime-validated reviewer proposal as additive work."""
        task_id = f"T{len(self.runtime.tasks) + 1}"
        proposed_conditions = [
            str(item) for item in candidate.get("supports_conditions") or [] if str(item)
        ]
        description = str(candidate.get("description") or "Review follow-up")
        unresolved = {
            condition
            for item in self.runtime.tasks.values()
            for condition in item.completion_conditions
            if item.condition_status.get(condition) != "SATISFIED"
        }
        # Reviewer-provided conditions are references to existing unresolved
        # outcomes, not a license to copy unrelated parent requirements into a
        # replan Task.  A task-specific fallback remains independently testable.
        conditions = [item for item in proposed_conditions if item in unresolved]
        if not conditions:
            conditions = [description]
        targets = [
            (item.task_id, condition)
            for item in self.runtime.tasks.values()
            for condition in conditions
            if condition in item.completion_conditions
            and item.condition_status.get(condition) != "SATISFIED"
        ]
        task = TaskRecord(
            task_id,
            self.current_goal_id,
            description,
            description,
            conditions,
        )
        self.runtime.replan_add_task(
            ReplanRecord(
                f"R{len(self.runtime.replans) + 1}",
                self.current_goal_id,
                str(candidate.get("reason") or "Local review follow-up"),
            ),
            task,
        )
        self._review_task_targets[task_id] = targets
        self.current_task_id = task_id
        if self._registry_tools:
            self.tool_expectation = ToolExpectation()
            self._resolve_current_capability(self._registry_tools)
        return task

    def record_local_review(self, record: Mapping[str, Any]) -> None:
        self.local_reviews.append(dict(record))
        review_value = record.get("structured_review") or {}
        review = review_value if isinstance(review_value, Mapping) else {}
        for fact in review.get("facts") or []:
            fact_text = str(fact)
            supporting_evidence = [
                item.evidence_id
                for item in self.runtime.evidence.values()
                if fact_text.casefold()
                in f"{item.summary}\n{item.relevant_content or ''}".casefold()
                and item.verified
                and item.certainty
                in {
                    InformationCertainty.CONFIRMED.value,
                    InformationCertainty.OBSERVED.value,
                }
            ]
            self.runtime.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.runtime.claims) + 1}",
                    claim=fact_text,
                    certainty=(
                        InformationCertainty.CONFIRMED.value
                        if supporting_evidence
                        else InformationCertainty.UNVERIFIED.value
                    ),
                    source="local_review.fact",
                    evidence_ids=supporting_evidence,
                    verified=bool(supporting_evidence),
                )
            )
        for problem in review.get("problems") or []:
            self.runtime.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.runtime.claims) + 1}",
                    claim=str(problem),
                    certainty=InformationCertainty.HYPOTHESIS.value,
                    source="local_review.problem",
                )
            )
        self.runtime.emit_event(
            "LOCAL_REVIEW_VALIDATED",
            iteration=record.get("review_iteration"),
            review_status=record.get("final_review_status"),
            accepted_new_task_count=len(record.get("accepted_new_tasks") or []),
            rejected_new_task_count=len(record.get("rejected_new_tasks") or []),
        )

    def gate_answer(self, answer: str) -> tuple[str, dict[str, Any]]:
        """Keep an unsupported model answer out of the confirmed-fact channel."""
        observation = self.runtime.tasks.get("T1")
        required = list(observation.completion_conditions) if observation else []
        conditions_supported = bool(required) and all(
            observation.condition_status.get(condition) == "SATISFIED"
            and bool(observation.condition_evidence.get(condition))
            for condition in required
        )
        evidence_ids = list(observation.evidence_ids) if observation else []
        if self.needs_human_grill():
            grill = self.conversation_grill_record()
            self.goal_read_target["grill_status"] = grill["status"]
            gated = format_conversation_grill(grill)
            extra = str(answer or "").strip()
            if extra:
                gated = gated + "\n\n" + extra
            claim = self.runtime.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.runtime.claims) + 1}",
                    claim=str(grill.get("question") or gated),
                    certainty=InformationCertainty.OBSERVED.value,
                    source="conversation_grill",
                    evidence_ids=evidence_ids,
                    verified=True,
                )
            )
            return gated, {
                "certainty": claim.certainty,
                "verified": True,
                "evidence_ids": claim.evidence_ids,
                "reason": "awaiting_human_grill",
                "conversation_grill": grill,
            }
        from ai_tool.chat_interface.boundary_grill import needs_boundary_spec_clarification

        if needs_boundary_spec_clarification(self):
            from ai_tool.chat_interface.boundary_grill import (
                build_boundary_grill_contract,
                format_boundary_grill,
            )

            contract = build_boundary_grill_contract(self)
            gated = format_boundary_grill(contract)
            claim = self.runtime.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.runtime.claims) + 1}",
                    claim=str(contract.question),
                    certainty=InformationCertainty.OBSERVED.value,
                    source="boundary_grill",
                    evidence_ids=evidence_ids,
                    verified=False,
                )
            )
            return gated, {
                "certainty": claim.certainty,
                "verified": False,
                "evidence_ids": claim.evidence_ids,
                "reason": "spec_meaning_ambiguous",
                "boundary_grill_contract": contract.as_dict(),
            }
        if self.needs_goal_completion_human():
            packet = self.goal_completion_human_record()
            gated = format_goal_completion_human(packet)
            claim = self.runtime.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.runtime.claims) + 1}",
                    claim=str(packet.get("question") or gated),
                    certainty=InformationCertainty.OBSERVED.value,
                    source="goal_completion_human",
                    evidence_ids=evidence_ids,
                    verified=True,
                )
            )
            return gated, {
                "certainty": claim.certainty,
                "verified": True,
                "evidence_ids": claim.evidence_ids,
                "reason": "awaiting_goal_completion_human",
                "goal_completion_human": packet,
            }
        if self._can_close_unresolved_goal():
            close = self.unresolved_goal_close_record()
            self.goal_read_target["close_status"] = close["status"]
            preamble = (
                "【結果】Goal対象を一意に確定できませんでした。対象同一性は未確定です。1件は選んでいません。\n"
                f"close_status: {close['status']}\n"
                f"uniqueness_class: {close['uniqueness_class']}\n"
                f"reason: {close['reason']}\n"
                f"uniqueness_cause: {close['uniqueness_cause']}\n"
                "候補集合とEvidenceは保持しています。部分文字列ヒットはユーザー可変ではありません。"
            )
            gated = preamble
            extra = str(answer or "").strip()
            if extra:
                gated = (
                    preamble
                    + "\n\n【参考】以下は一意対象の要約ではありません。\n"
                    + extra
                )
            claim = self.runtime.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.runtime.claims) + 1}",
                    claim=preamble,
                    certainty=InformationCertainty.OBSERVED.value,
                    source="unresolved_goal_close",
                    evidence_ids=evidence_ids,
                    verified=True,
                )
            )
            return gated, {
                "certainty": claim.certainty,
                "verified": True,
                "evidence_ids": claim.evidence_ids,
                "reason": "closed_unresolved_goal_target",
                "goal_close": close,
            }
        goal_ready = self._goal_summary_ready()
        if (
            self.goal_read_target.get("status") == "PROVISIONAL_SELECTED"
            and goal_ready
        ):
            variable = dict(
                self.goal_read_target.get("user_variable") or empty_user_variable()
            )
            preamble = (
                "【結果】Goal対象は交換可能なユーザー可変要素です。暫定選択して進めました。\n"
                f"provisional_selected: {variable.get('provisional_selected')}\n"
                f"selection_rule: {variable.get('selection_rule')}\n"
                "後からユーザー好みやProject Conventionで差し替え可能です。"
            )
            extra = str(answer or "").strip()
            gated = preamble + ("\n\n" + extra if extra else "")
            claim = self.runtime.add_claim(
                ClaimRecord(
                    claim_id=f"CL{len(self.runtime.claims) + 1}",
                    claim=preamble,
                    certainty=InformationCertainty.OBSERVED.value,
                    source="provisional_user_variable",
                    evidence_ids=evidence_ids,
                    verified=True,
                )
            )
            return gated, {
                "certainty": claim.certainty,
                "verified": True,
                "evidence_ids": claim.evidence_ids,
                "reason": "provisional_user_variable_target",
                "user_variable": variable,
            }
        supported = conditions_supported and goal_ready
        certainty = (
            InformationCertainty.CONFIRMED.value
            if supported
            else InformationCertainty.UNVERIFIED.value
        )
        claim = self.runtime.add_claim(
            ClaimRecord(
                claim_id=f"CL{len(self.runtime.claims) + 1}",
                claim=str(answer or "")[:6000],
                certainty=certainty,
                source="final_llm_answer",
                evidence_ids=evidence_ids if supported else [],
                verified=supported,
            )
        )
        gated = str(answer or "")
        if gated.strip() and not claim.verified:
            gated = (
                "【未確認】以下は確認済みEvidenceが不足しているため、"
                "確定事項ではありません。\n\n" + gated
            )
        if supported:
            reason = None
        elif self.search_candidate_sets and self.goal_read_target.get("status") not in {
            "SELECTED",
            "PROVISIONAL_SELECTED",
        }:
            reason = "goal_read_target_unresolved"
        elif self.search_candidate_sets and not goal_ready:
            reason = "goal_read_target_not_observed"
        else:
            reason = "completion_evidence_incomplete"
        return gated, {
            "certainty": claim.certainty,
            "verified": claim.verified,
            "evidence_ids": claim.evidence_ids,
            "reason": reason,
        }

    def finish(self, answer: str, *, allow_completion: bool = True) -> dict[str, Any]:
        conditions = list(self.task.satisfied_conditions)
        if allow_completion and answer.strip():
            if "answer produced" in (self.task.completion_conditions or []):
                if "answer produced" not in conditions:
                    conditions.append("answer produced")
            elif self.task.status == "complete" and "answer produced" not in conditions:
                conditions.append("answer produced")
        completed_goal_id = self.task.goal_id
        self.runtime.evaluate_task(self.current_task_id, conditions)
        from ai_tool.production_verification_acceptance import advance_runnable_handoff_task

        if completed_goal_id in self.runtime.goals:
            # Empty satisfied list cannot complete G1 whose conditions are A*.
            self.runtime.evaluate_goal(completed_goal_id, [])
        advance_runnable_handoff_task(self)
        handoff_seeded = any(
            str(getattr(task, "source", "") or "") == "goal_handoff"
            for task in self.runtime.tasks.values()
        )
        if handoff_seeded:
            return self.runtime.final_synthesis_context("G1")
        g1 = self.runtime.goals.get("G1")
        if g1 is not None:
            for child_id in g1.child_goal_ids:
                if child_id in self.runtime.goals:
                    self.runtime.evaluate_goal(child_id, [])
        self.runtime.evaluate_goal(
            "G1",
            ["all tasks complete"]
            if all(task.status == "complete" for task in self.runtime.tasks.values())
            else [],
        )
        return self.runtime.final_synthesis_context("G1")

    def snapshot(self) -> dict[str, Any]:
        sandbox = self.runtime.sandbox_identity()
        return {
            "original_request": self.request,
            "mission_id": self.mission_id or None,
            "execution_id": self.execution_id or None,
            "current_goal_id": self.current_goal_id,
            "current_task_id": self.current_task_id,
            "goals": [asdict(item) for item in self.runtime.goals.values()],
            "tasks": [asdict(item) for item in self.runtime.tasks.values()],
            "actions": [asdict(item) for item in self.runtime.actions],
            "evidence": [asdict(item) for item in self.runtime.evidence.values()],
            "failures": [asdict(item) for item in self.runtime.failures],
            "mutations": [asdict(item) for item in self.runtime.mutations],
            "replans": [asdict(item) for item in self.runtime.replans],
            "tool_gaps": [asdict(item) for item in self.runtime.tool_gaps.values()],
            "events": [dict(item) for item in self.runtime.task_events],
            "tool_expectation": asdict(self.tool_expectation),
            "concept_resolution": self.concept_resolution.as_dict(),
            "capability_resolution": [
                item.as_dict()
                for rows in self.capability_resolutions.values()
                for item in rows
            ],
            "claims": [asdict(item) for item in self.runtime.claims],
            "effective_claims": [asdict(item) for item in self.runtime.effective_claims()],
            "local_reviews": [dict(item) for item in self.local_reviews],
            "search_observations": [dict(item) for item in self.search_observations],
            "search_candidate_sets": [
                dict(item) for item in self.search_candidate_sets.values()
            ],
            "goal_read_target": dict(self.goal_read_target),
            "goal_close": (
                self.unresolved_goal_close_record()
                if self.goal_read_target.get("close_status") == "CLOSED_UNRESOLVED"
                else None
            ),
            "conversation_grill": (
                self.conversation_grill_record()
                if self.needs_human_grill()
                else None
            ),
            "awaiting_human_grill": self.needs_human_grill(),
            "awaiting_goal_completion_human": self.needs_goal_completion_human(),
            "goal_completion_human": (
                self.goal_completion_human_record()
                if self.needs_goal_completion_human()
                else None
            ),
            "goal_completion_resume": (
                self.goal_completion_resume_state()
                if self.needs_goal_completion_human()
                else None
            ),
            "conversation_grill_state": (
                self.conversation_grill_state() if self.needs_human_grill() else None
            ),
            "confirmed_clarifications": [
                dict(item) for item in self.confirmed_clarifications
            ],
            "followup_investigations": [dict(item) for item in self.followup_investigations],
            "human_confirmation_eligible": any(
                item.get("human_confirmation_eligible")
                for item in self.followup_investigations
            )
            and bool(self._unresolved_complete_search_sets()),
            "review_task_targets": {
                task_id: [
                    {"task_id": target_id, "condition": condition}
                    for target_id, condition in targets
                ]
                for task_id, targets in self._review_task_targets.items()
            },
            "sandbox_session": sandbox,
            "sandbox_status_ja": (
                sandbox_status_ja(self.runtime.sandbox_session)
                if self.runtime.sandbox_session is not None
                else None
            ),
            **(
                {"structured_requirements": [dict(item) for item in self.structured_requirements]}
                if self.structured_requirements
                else {}
            ),
            **(
                {"requirement_resolution_phase": self.requirement_resolution_phase}
                if self.requirement_resolution_phase
                else {}
            ),
        }


__all__ = [
    "AGENT_CORE_PROMPT",
    "ChatTaskOrchestrator",
    "ToolExpectation",
    "build_tool_expectation",
    "fold_search_candidate_set",
    "is_agent_task",
    "has_creation_intent",
    "empty_goal_read_target",
    "empty_user_variable",
    "confirm_interchangeable_paths",
    "classify_uniqueness_and_user_variable",
    "goal_needs_human_grill",
    "build_conversation_grill",
    "format_conversation_grill",
    "needs_goal_completion_human",
    "match_clarification_to_candidate_paths",
    "resolve_search_read_target",
    "search_candidate_hint",
]
