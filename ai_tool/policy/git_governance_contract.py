"""Git Governance Machine Contract loader and structural validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ai_tool.policy.paths import git_governance_json_path, git_governance_schema_path

_APPROVAL_CLASSES = frozenset(
    {
        "ALLOW",
        "TASK_AUTHORIZATION_REQUIRED",
        "HUMAN_APPROVAL_REQUIRED",
        "AGENT_ALWAYS_BLOCK",
        "GUIDANCE_ONLY",
        "UNDECIDED",
    }
)

_AUTO_ALLOW_CONDITION_IDS = frozenset(
    {
        "authorization_present",
        "auto_commit_allowed",
        "implicit_allow",
        "allow_without_approval",
    }
)


class GitGovernanceContractError(RuntimeError):
    """Contract missing, invalid JSON, or fails schema / semantic invariants."""


def load_git_governance_contract(*, path: Path | None = None) -> dict[str, Any]:
    target = path or git_governance_json_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GitGovernanceContractError(f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise GitGovernanceContractError("contract root must be an object")
    return data


def validate_git_governance_contract(
    data: dict[str, Any], *, schema_path: Path | None = None
) -> None:
    schema_file = schema_path or git_governance_schema_path()
    try:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GitGovernanceContractError(f"schema load failed: {exc}") from exc
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        raise GitGovernanceContractError(f"schema: {first.message} at {list(first.path)}")

    _validate_semantic_sources_exist(data)
    _validate_action_ids_unique(data)
    _validate_approval_classes_declared(data)
    _validate_agent_always_block_invariants(data)


def _validate_semantic_sources_exist(data: dict[str, Any]) -> None:
    repo_root = git_governance_json_path().resolve().parents[2]
    sources = data.get("semantic_sources")
    if not isinstance(sources, list):
        return
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "")
        if rel and not (repo_root / rel).is_file():
            raise GitGovernanceContractError(f"semantic source missing: {rel}")


def _validate_action_ids_unique(data: dict[str, Any]) -> None:
    actions = data.get("actions")
    if not isinstance(actions, list):
        return
    seen: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action_id") or "")
        if not action_id:
            continue
        if action_id in seen:
            raise GitGovernanceContractError(f"duplicate action_id: {action_id}")
        seen.add(action_id)


def _validate_approval_classes_declared(data: dict[str, Any]) -> None:
    declared = data.get("approval_class_enum")
    if not isinstance(declared, list):
        return
    declared_set = {str(x) for x in declared}
    if declared_set != _APPROVAL_CLASSES:
        raise GitGovernanceContractError("approval_class_enum does not match canonical set")


def _validate_agent_always_block_invariants(data: dict[str, Any]) -> None:
    actions = data.get("actions")
    if not isinstance(actions, list):
        return
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("approval_class") != "AGENT_ALWAYS_BLOCK":
            continue
        conditions = action.get("required_conditions") or []
        if not isinstance(conditions, list):
            continue
        for cond in conditions:
            if not isinstance(cond, dict):
                continue
            cid = str(cond.get("condition_id") or "")
            if cid in _AUTO_ALLOW_CONDITION_IDS:
                raise GitGovernanceContractError(
                    f"AGENT_ALWAYS_BLOCK action {action.get('action_id')} "
                    f"has disallowed condition {cid}"
                )


def action_approval_map(data: dict[str, Any]) -> dict[str, str]:
    actions = data.get("actions")
    if not isinstance(actions, list):
        return {}
    out: dict[str, str] = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action_id") or "")
        approval = str(action.get("approval_class") or "")
        if action_id:
            out[action_id] = approval
    return out


def validate_git_governance_adapters(
    data: dict[str, Any], *, repo_root: Path | None = None
) -> dict[str, str]:
    """Ensure declared Git governance adapters exist and reference the contract."""
    root = repo_root or git_governance_json_path().resolve().parents[2]
    adapters = data.get("adapters")
    if not isinstance(adapters, dict):
        raise GitGovernanceContractError("adapters section missing")
    consumers = adapters.get("consumers")
    if not isinstance(consumers, dict) or not consumers:
        raise GitGovernanceContractError("adapters.consumers missing")
    checked: dict[str, str] = {}
    contract_body = json.dumps(data, ensure_ascii=False)
    for consumer, config in consumers.items():
        if not isinstance(config, dict):
            raise GitGovernanceContractError(f"adapter config not object: {consumer}")
        adapter_rel = str(config.get("adapter") or "")
        if not adapter_rel:
            raise GitGovernanceContractError(f"adapter path missing: {consumer}")
        adapter_path = (root / adapter_rel).resolve()
        try:
            adapter_path.relative_to(root.resolve())
        except ValueError as exc:
            raise GitGovernanceContractError(f"adapter escapes repo: {adapter_rel}") from exc
        if not adapter_path.is_file():
            raise GitGovernanceContractError(f"adapter missing: {adapter_rel}")
        text = adapter_path.read_text(encoding="utf-8")
        if adapter_rel.endswith((".mdc", ".md")) and contract_body in text:
            raise GitGovernanceContractError(
                f"adapter must not embed full contract JSON: {adapter_rel}"
            )
        for reference in config.get("required_references") or []:
            ref = str(reference)
            if ref not in text:
                raise GitGovernanceContractError(
                    f"adapter reference missing: {consumer}: {ref}"
                )
        checked[str(consumer)] = adapter_rel
    return checked


def load_and_validate_git_governance_contract(*, path: Path | None = None) -> dict[str, Any]:
    data = load_git_governance_contract(path=path)
    validate_git_governance_contract(data)
    validate_git_governance_adapters(data)
    return data
