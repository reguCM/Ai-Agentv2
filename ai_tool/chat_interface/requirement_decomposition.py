"""P2-16.6: bounded requirement extraction before Task execution."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import json
import re
from typing import Any, Callable, Iterable, Mapping


class RequirementStatus(str, Enum):
    READY = "READY"
    MISSING_INPUT = "MISSING_INPUT"
    AMBIGUOUS = "AMBIGUOUS"
    NEEDS_HUMAN_DECISION = "NEEDS_HUMAN_DECISION"
    TOOL_GAP = "TOOL_GAP"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class RequirementCondition:
    condition_id: str
    description: str
    required: bool = True
    source_hint: str | None = None
    source_hint_certainty: str = "UNVERIFIED"
    dependencies: list[str] = field(default_factory=list)
    ambiguity: str | None = None
    action_hint: str | None = None
    action_like: bool = False
    original_description: str | None = None


@dataclass
class RequirementDecomposition:
    conditions: list[RequirementCondition]
    status: str
    validator_errors: list[str] = field(default_factory=list)
    clarification: str | None = None
    source: str = "local_llm"
    rejected_conditions: list[RequirementCondition] = field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "conditions": [asdict(item) for item in self.conditions],
            "status": self.status,
            "validator_errors": list(self.validator_errors),
            "clarification": self.clarification,
            "source": self.source,
            "rejected_conditions": [asdict(item) for item in self.rejected_conditions],
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


_EXPLICIT = re.compile(r"(?m)^\s*\d+[.)．]\s*(.+?)\s*$")
_VAGUE = re.compile(r"(適切に|十分に|いい感じ|必要に応じて|properly|appropriately|enough)", re.I)
_HUMAN_DECISION = re.compile(r"(好み|どちらが良い|採用を決定|価値判断|prefer|choose the best)", re.I)
_SYSTEM = """REQUIREMENT_DECOMPOSITION_V1
Extract only completion conditions that the user request itself states.
Return one JSON object only: {"conditions":[{"condition_id":"C1","description":"...","required":true,"source_hint":"docs/example.md","action_hint":"read_fileで確認","dependencies":[],"ambiguity":null}]}.
Use ambiguity values missing_input, ambiguous, human_decision, or unsupported only when applicable.
Do not solve the task, call tools, or create a plan.
Do not add conditions from general knowledge, typical checklists, or guesswork.
Do not invent extra conditions to reach a count. Zero conditions is allowed when the request does not enumerate any.
依頼に列挙された確認項目は省略、統合、別概念への言い換えをせず、それぞれ独立したConditionにすること。
success、partial、failureのように個別に指定された項目は、それぞれ別Conditionとして保持すること。
依頼に書かれていない項目を一般常識や推測で追加しないこと。
「Toolで確認する」「ファイルを読む」などの実行手段はsource_hintであり、依頼された成果そのものでない限りConditionにしないこと。
実質的な確認項目がある場合、「報告する」だけを独立Conditionにしないこと。
descriptionは「何が成立・確認済みなら完了か」という状態または成果を書くこと。実行方法はaction_hint、情報源はsource_hintへ分離すること。
例: 「read_fileでpartial条件を確認する」ではなく、descriptionを「partial条件が確認できている」、action_hintを「read_fileで確認」とすること。
"""

_METHOD_PREFIX = re.compile(
    r"^(?P<method>[A-Za-z_][A-Za-z0-9_.-]*|Tool|ツール)(?:で|を使(?:用し|っ)て)"
    r"(?P<object>.+?)を(?P<verb>確認|検索|読む|取得|検証|実行)(?:する|した)?[。.]?$",
    re.I,
)
_ACTION_WITH_OBJECT = re.compile(
    r"^(?P<object>.+?)を(?P<verb>確認|検索|読む|取得|検証)(?:する|した)?[。.]?$"
)
_ACTION_ONLY = re.compile(
    r"^(?:Tool|ツール|[A-Za-z_][A-Za-z0-9_.-]*)?(?:を使(?:用し|っ)て)?(?:確認|検索|実行|呼び出し)(?:する|した)?[。.]?$"
    r"|^(?:ファイルを読む|コマンドを実行する|テストを実行する|APIを呼ぶ)[。.]?$",
    re.I,
)
_NAMED_CONSTRAINT = re.compile(
    r"(?<![A-Za-z0-9_])(?:IANA|ISO(?:[- ]?\d+)?|RFC[- ]?\d+)(?![A-Za-z0-9_])|"
    r"(?:Y{2,}[-/][MD]{1,2}[-/][MD]{1,2}(?:\s+[Hh]{1,2}:[Mm]{1,2}(?::[Ss]{1,2})?)?)",
    re.I,
)


def _normalize_action_condition(
    row: RequirementCondition,
) -> tuple[RequirementCondition | None, RequirementCondition | None]:
    """Separate a verifiable outcome from its method; reject method-only rows."""
    text = row.description.strip()
    if _ACTION_ONLY.fullmatch(text):
        rejected = replace(
            row, action_like=True, original_description=row.original_description or text
        )
        return None, rejected
    match = _METHOD_PREFIX.fullmatch(text)
    if match:
        target = match.group("object").strip()
        if not target:
            return None, replace(
                row, action_like=True, original_description=row.original_description or text
            )
        method = match.group("method")
        verb = match.group("verb")
        return replace(
            row,
            description=f"{target}が確認できている",
            action_hint=row.action_hint or f"{method}で{verb}",
            source_hint=row.source_hint or _source_hint(target),
            action_like=True,
            original_description=row.original_description or text,
        ), None
    match = _ACTION_WITH_OBJECT.fullmatch(text)
    if match:
        target = match.group("object").strip()
        verb = match.group("verb")
        return replace(
            row,
            description=f"{target}が確認できている",
            action_hint=row.action_hint or verb,
            source_hint=row.source_hint or _source_hint(target),
            action_like=True,
            original_description=row.original_description or text,
        ), None
    return row, None


def _semantic_key(description: str) -> str:
    key = re.sub(r"\W+", "", description.casefold())
    for suffix in (
        "確認すること", "取得すること", "確認してください", "取得してください",
        "確認する", "取得する", "すること", "してください", "する", "確認", "取得",
        "verify", "identify",
    ):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
            break
    return key


def _source_hint(description: str) -> str | None:
    low = description.casefold()
    if any(token in low for token in ("file", "document", "正本", "文書")):
        return "read_file"
    if any(token in low for token in ("web", "website", "最新", "インターネット")):
        return "search_web"
    return None


def _required_tool(source_hint: str | None) -> str | None:
    hint = str(source_hint or "").strip()
    low = hint.casefold()
    if not hint or low in {"user_input", "llm_output"}:
        return None
    if low.startswith(("http://", "https://")):
        return "search_web"
    if "/" in hint or "\\" in hint or re.search(r"\.[a-z0-9]{1,8}$", low):
        return "read_file"
    return hint


def explicit_conditions(request: str) -> list[RequirementCondition]:
    descriptions = list(dict.fromkeys(row.strip() for row in _EXPLICIT.findall(request) if row.strip()))
    return [
        RequirementCondition(f"C{index}", text, source_hint=_source_hint(text))
        for index, text in enumerate(descriptions, 1)
    ]


def _message_content(response: Any) -> str:
    return str(getattr(getattr(response, "message", None), "content", None) or "")


def _parse_conditions(content: str) -> list[RequirementCondition]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    payload = json.loads(text)
    rows = payload.get("conditions") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError("conditions must be an array")
    conditions: list[RequirementCondition] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise ValueError("condition must be an object")
        conditions.append(
            RequirementCondition(
                condition_id=str(row.get("condition_id") or f"C{index}"),
                description=str(row.get("description") or "").strip(),
                required=bool(row.get("required", True)),
                source_hint=str(row.get("source_hint") or "").strip() or None,
                source_hint_certainty="UNVERIFIED",
                dependencies=[str(item) for item in (row.get("dependencies") or [])],
                ambiguity=str(row.get("ambiguity") or "").strip() or None,
                action_hint=str(row.get("action_hint") or "").strip() or None,
            )
        )
    return conditions


def _drop_unrequested_named_constraints(
    request: str, conditions: Iterable[RequirementCondition]
) -> tuple[list[RequirementCondition], list[RequirementCondition]]:
    """Reject only explicit standards/formats invented outside the request."""
    request_low = request.casefold()
    kept: list[RequirementCondition] = []
    rejected: list[RequirementCondition] = []
    for row in conditions:
        markers = [match.group(0) for match in _NAMED_CONSTRAINT.finditer(row.description)]
        if markers and any(marker.casefold() not in request_low for marker in markers):
            rejected.append(replace(row, ambiguity="unrequested_constraint"))
        else:
            kept.append(row)
    return kept, rejected


def validate_conditions(
    conditions: Iterable[RequirementCondition],
    *,
    available_tools: Iterable[str] = (),
    source: str = "local_llm",
) -> RequirementDecomposition:
    original_rows = list(conditions)
    rows: list[RequirementCondition] = []
    rejected: list[RequirementCondition] = []
    for row in original_rows:
        normalized, rejected_row = (
            (row, None)
            if source == "explicit"
            else _normalize_action_condition(row)
        )
        if normalized is not None:
            rows.append(normalized)
        if rejected_row is not None:
            rejected.append(rejected_row)
    errors: list[str] = []
    if not rows:
        code = "action_only_conditions" if rejected else "condition_zero"
        return RequirementDecomposition(
            [], RequirementStatus.UNSUPPORTED.value, [code],
            "実行方法ではなく、何が確認・成立すれば完了かを指定してください。",
            source, rejected,
        )
    normalized: dict[str, str] = {}
    status = RequirementStatus.READY
    priority = {
        RequirementStatus.READY: 0,
        RequirementStatus.AMBIGUOUS: 1,
        RequirementStatus.MISSING_INPUT: 2,
        RequirementStatus.TOOL_GAP: 3,
        RequirementStatus.NEEDS_HUMAN_DECISION: 4,
        RequirementStatus.UNSUPPORTED: 5,
    }
    def raise_status(candidate: RequirementStatus) -> None:
        nonlocal status
        if priority[candidate] > priority[status]:
            status = candidate

    tools = set(available_tools)
    for row in rows:
        key = _semantic_key(row.description)
        if not row.description:
            errors.append(f"{row.condition_id}:description_missing")
            raise_status(RequirementStatus.UNSUPPORTED)
        duplicate = normalized.get(key)
        if row.description and duplicate:
            errors.append(f"{row.condition_id}:duplicate:{duplicate}")
            raise_status(RequirementStatus.AMBIGUOUS)
        elif row.description:
            normalized[key] = row.condition_id
        if _VAGUE.search(row.description):
            errors.append(f"{row.condition_id}:not_verifiable")
            raise_status(RequirementStatus.AMBIGUOUS)
        if _HUMAN_DECISION.search(row.description):
            errors.append(f"{row.condition_id}:human_decision")
            raise_status(RequirementStatus.NEEDS_HUMAN_DECISION)
        ambiguity = (row.ambiguity or "").casefold()
        if ambiguity == "missing_input":
            raise_status(RequirementStatus.MISSING_INPUT)
        elif ambiguity == "human_decision":
            raise_status(RequirementStatus.NEEDS_HUMAN_DECISION)
        elif ambiguity == "ambiguous":
            raise_status(RequirementStatus.AMBIGUOUS)
        elif ambiguity == "unsupported":
            raise_status(RequirementStatus.UNSUPPORTED)
        required_tool = _required_tool(row.source_hint)
        source_verified = row.source_hint_certainty in {"CONFIRMED", "OBSERVED"}
        if required_tool and required_tool not in tools and source_verified:
            errors.append(f"{row.condition_id}:tool_gap:{required_tool}")
            raise_status(RequirementStatus.TOOL_GAP)
    known_ids = {row.condition_id for row in rows}
    if not any(row.required for row in rows):
        errors.append("required_condition_zero")
        raise_status(RequirementStatus.UNSUPPORTED)
    for row in rows:
        unknown_dependencies = [item for item in row.dependencies if item not in known_ids]
        if unknown_dependencies:
            errors.append(
                f"{row.condition_id}:unknown_dependencies:{','.join(unknown_dependencies)}"
            )
            raise_status(RequirementStatus.UNSUPPORTED)
    clarification = None
    if status is not RequirementStatus.READY:
        target = next((row.description for row in rows if row.ambiguity or _VAGUE.search(row.description)), rows[0].description)
        clarification = f"「{target}」を検証可能にするため、必要な入力または判断基準を指定してください。"
    return RequirementDecomposition(
        rows, status.value, errors, clarification, source, rejected
    )


def decompose_requirements(
    request: str,
    *,
    chat_fn: Callable[..., Any],
    model: str,
    available_tools: Iterable[str],
) -> RequirementDecomposition:
    explicit = explicit_conditions(request)
    if explicit:
        return validate_conditions(explicit, available_tools=available_tools, source="explicit")
    # Numbered lists are the only T1-adopted conditions. An unenumerated request
    # stays READY with zero conditions so Chat can use the internal observation gate.
    return RequirementDecomposition([], RequirementStatus.READY.value, source="not_enumerated")


__all__ = [
    "RequirementCondition",
    "RequirementDecomposition",
    "RequirementStatus",
    "decompose_requirements",
    "explicit_conditions",
    "validate_conditions",
]
