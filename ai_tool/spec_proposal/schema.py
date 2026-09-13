"""SpecificationProposal の機械フィールド。Tool JSON と同一視しない。"""
from __future__ import annotations

from typing import Any

CLAIM_STATUSES = (
    "CONFIRMED",
    "PROPOSED",
    "ASSUMED",
    "UNKNOWN",
    "HUMAN_CONFIRMATION_REQUIRED",
)

LIST_FIELDS = (
    "objectives",
    "inputs",
    "outputs",
    "behavior",
    "constraints",
    "completion_conditions",
    "risks",
    "alternatives",
)

CLAIM_LIST_FIELDS = {
    "confirmed": "CONFIRMED",
    "proposed": "PROPOSED",
    "assumptions": "ASSUMED",
    "unknowns": "UNKNOWN",
    "human_confirmation_required": "HUMAN_CONFIRMATION_REQUIRED",
}

ORIGIN_LLM_PROPOSAL = "llm_proposal"
ORIGIN_HUMAN_REVISION = "human_revision"
ORIGIN_PROBLEM_RECORD = "problem_record"

ORIGINS = (
    ORIGIN_LLM_PROPOSAL,
    ORIGIN_HUMAN_REVISION,
    ORIGIN_PROBLEM_RECORD,
)

PHASES_NOT_IMPLEMENTED = (
    "semantic_difference_classification",
    "implementation_link",
    "tendency_analysis",
    "auto_improvement",
    "learning_method",
)

RAW_CHAR_LIMIT = 8000


def observation_flags() -> dict[str, Any]:
    """学習方法は未確立。提案保存を正しさや完成としない。"""
    return {
        "role": "provisional_observation",
        "learning_method": "NOT_DETERMINED",
        "llm_judgment": "NOT_IMPLEMENTED",
        "auto_improvement": "NOT_IMPLEMENTED",
        "parse_success_is_not_specification_valid": True,
        "pytest_pass_is_not_specification_complete": True,
        "saved_proposal_is_not_final_specification": True,
    }


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = _as_text(item)
            if text:
                out.append(text)
        return out
    text = _as_text(value)
    return [text] if text else []


def _claim_status(raw: Any, default: str) -> str:
    text = str(raw or "").strip().upper().replace(" ", "_")
    if text in CLAIM_STATUSES:
        return text
    return default


def _claim_item(value: Any, default_status: str) -> dict[str, str] | None:
    if isinstance(value, dict):
        text = _as_text(value.get("text") or value.get("item") or value.get("content"))
        if not text:
            return None
        return {"text": text, "status": _claim_status(value.get("status"), default_status)}
    text = _as_text(value)
    if not text:
        return None
    return {"text": text, "status": default_status}


def normalize_claim_lists(data: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """status ごとに分離する。混在した入力は status で再配置する。"""
    buckets = {name: [] for name in CLAIM_LIST_FIELDS}
    status_to_field = {status: name for name, status in CLAIM_LIST_FIELDS.items()}
    for field, default_status in CLAIM_LIST_FIELDS.items():
        raw = data.get(field)
        if raw is None:
            continue
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            claim = _claim_item(item, default_status)
            if not claim:
                continue
            dest = status_to_field.get(claim["status"], field)
            buckets[dest].append(claim)
    return buckets


def empty_proposal_body() -> dict[str, Any]:
    return {
        "proposed_specification": "",
        "objectives": [],
        "inputs": [],
        "outputs": [],
        "behavior": [],
        "constraints": [],
        "completion_conditions": [],
        "assumptions": [],
        "unknowns": [],
        "human_confirmation_required": [],
        "confirmed": [],
        "proposed": [],
        "risks": [],
        "alternatives": [],
        "rationale": "",
        "llm_reported_confidence": "",
    }


def apply_body_fields(target: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    target["proposed_specification"] = _as_text(data.get("proposed_specification"))
    for field in LIST_FIELDS:
        target[field] = _as_str_list(data.get(field))
    claims = normalize_claim_lists(data)
    target.update(claims)
    target["rationale"] = _as_text(data.get("rationale"))
    target["llm_reported_confidence"] = _as_text(data.get("confidence"))
    return target
