"""
Tool Contract 参照・検証ヘルパ。

正本: registry/tools.json
規約: docs/TOOL_CALLING_RULES.md

Registry を直接散在読み込みさせず、検証と Agent 向け一覧取得の最小 API を提供する。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from tools.system.config import ROOT

REGISTRY_PATH = ROOT / "registry" / "tools.json"

TOOL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

FORBIDDEN_DESCRIPTION_PATTERNS = (
    re.compile(r"^情報を取得します\.?$"),
    re.compile(r"^処理を実行します\.?$"),
    re.compile(r"^データを確認します\.?$"),
)

AGENT_VISIBILITY = "agent"

_registry_cache: dict[str, Any] | None = None


class ToolContractError(Exception):
    """Tool Contract / Registry エラー。"""


class ToolNotFoundError(ToolContractError):
    """Registry に存在しない tool name。"""


def canonical_tool_name(entry: Mapping[str, Any]) -> str:
    """Return one canonical name from a Registry row or provider Tool schema."""
    function = entry.get("function")
    if isinstance(function, Mapping):
        return str(function.get("name") or "").strip()
    return str(entry.get("name") or "").strip()


def load_tool_registry(*, reload: bool = False) -> dict[str, Any]:
    global _registry_cache
    if _registry_cache is None or reload:
        if not REGISTRY_PATH.is_file():
            raise ToolContractError(f"Tool Registry が見つかりません: {REGISTRY_PATH}")
        _registry_cache = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return _registry_cache


def list_registry_tools(*, reload: bool = False) -> list[dict[str, Any]]:
    registry = load_tool_registry(reload=reload)
    return [dict(item) for item in registry.get("tools") or []]


def get_registry_tool(name: str, *, reload: bool = False) -> dict[str, Any]:
    for item in list_registry_tools(reload=reload):
        if str(item.get("name")) == str(name):
            return dict(item)
    raise ToolNotFoundError(f"Registry に Tool がありません: {name}")


def is_agent_visible(entry: dict[str, Any]) -> bool:
    return str(entry.get("visibility") or "") == AGENT_VISIBILITY


def list_agent_visible_tools(*, reload: bool = False) -> list[dict[str, Any]]:
    return [t for t in list_registry_tools(reload=reload) if is_agent_visible(t)]


def registry_entry_to_ollama_parameters(entry: dict[str, Any]) -> dict[str, Any]:
    """agent.create_ollama_tools と同じ input → parameters 変換。"""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, parameter in (entry.get("input") or {}).items():
        param = dict(parameter)
        is_required = bool(param.pop("required", False))
        properties[param_name] = param
        if is_required:
            required.append(param_name)

    for param_name in entry.get("required") or []:
        if param_name not in required:
            required.append(param_name)

    parameters: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return parameters


def registry_entry_to_ollama_tool(entry: dict[str, Any]) -> dict[str, Any]:
    """agent.create_ollama_tools が生成する 1 件分の Ollama tool 定義。"""
    return {
        "type": "function",
        "function": {
            "name": str(entry["name"]),
            "description": str(entry.get("description") or ""),
            "parameters": registry_entry_to_ollama_parameters(entry),
        },
    }


def build_agent_ollama_tools(*, reload: bool = False) -> list[dict[str, Any]]:
    return [
        registry_entry_to_ollama_tool(entry)
        for entry in list_agent_visible_tools(reload=reload)
    ]


def validate_tool_id(name: str) -> list[str]:
    issues: list[str] = []
    if not TOOL_ID_PATTERN.match(str(name)):
        issues.append(f"tool_id '{name}' は snake_case 規約に合致しません")
    return issues


def validate_description(description: str) -> list[str]:
    issues: list[str] = []
    text = (description or "").strip()
    if len(text) < 20:
        issues.append("description が短すぎます（20 文字未満）")
    for pattern in FORBIDDEN_DESCRIPTION_PATTERNS:
        if pattern.match(text):
            issues.append(f"description が禁止パターンに一致: {pattern.pattern}")
    return issues


def validate_input_schema(tool_input: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for param_name, parameter in (tool_input or {}).items():
        if not isinstance(parameter, dict):
            issues.append(f"input.{param_name} はオブジェクトである必要があります")
            continue
        if not parameter.get("type"):
            issues.append(f"input.{param_name} に type がありません")
        if not str(parameter.get("description") or "").strip():
            issues.append(f"input.{param_name} に description がありません")
    return issues


def validate_registry_entry(entry: dict[str, Any], *, strict_new: bool = False) -> list[str]:
    """
    Registry エントリの規約チェック。

    strict_new=True のときのみ description 禁止パターン等を厳格適用（既存 Tool 監査用は False）。
    """
    issues: list[str] = []
    name = str(entry.get("name") or "")
    if not name:
        issues.append("name がありません")
    else:
        issues.extend(validate_tool_id(name))

    if not str(entry.get("description") or "").strip():
        issues.append(f"{name}: description がありません")
    elif strict_new:
        issues.extend(validate_description(str(entry.get("description"))))

    if not str(entry.get("module") or "").strip():
        issues.append(f"{name}: module がありません")
    if not str(entry.get("function") or "").strip():
        issues.append(f"{name}: function がありません")

    issues.extend(validate_input_schema(entry.get("input") or {}))
    return issues


def validate_agent_visible_registry(*, reload: bool = False) -> dict[str, Any]:
    """Agent 公開 Tool の一括検証。issues は name → [messages]。"""
    issues_by_name: dict[str, list[str]] = {}
    for entry in list_agent_visible_tools(reload=reload):
        name = str(entry.get("name"))
        issues = validate_registry_entry(entry, strict_new=False)
        if issues:
            issues_by_name[name] = issues
    return {
        "agent_visible_count": len(list_agent_visible_tools(reload=reload)),
        "issue_count": sum(len(v) for v in issues_by_name.values()),
        "issues_by_name": issues_by_name,
    }


def tool_calling_capability_summary(*, reload: bool = False) -> dict[str, Any]:
    """観測用: Registry → Ollama schema 変換の要約。"""
    agent_tools = build_agent_ollama_tools(reload=reload)
    return {
        "registry_path": str(REGISTRY_PATH),
        "total_tools": len(list_registry_tools(reload=reload)),
        "agent_visible_tools": len(agent_tools),
        "agent_tool_names": sorted(t["function"]["name"] for t in agent_tools),
    }
