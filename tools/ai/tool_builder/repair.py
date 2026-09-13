import json
import os

from tools.ai.prompts.base import (
    REQUIRED_MATERIAL_KEYS,
    TEST_RESULT_MATERIAL_FIELDS,
    WARNING_MATERIAL_FIELDS,
)
from tools.system.tool_builder.validate.result import attach_parsed_tables_to_research


def find_registry_entry(tools, tool_name):
    for tool in tools:
        if tool.get("name") == tool_name:
            return tool
    return None


def module_to_path(module):
    if not module:
        return None
    return module.replace(".", "/") + ".py"


def read_source(path):
    normalized = path.replace("\\", "/")
    if not os.path.exists(normalized):
        return None
    with open(normalized, "r", encoding="utf-8") as f:
        return f.read()


def _slim_warning(item):
    return {
        field: (item or {}).get(field)
        for field in WARNING_MATERIAL_FIELDS
        if (item or {}).get(field) not in (None, [], {}, "")
    }


def _slim_warnings(items):
    return [_slim_warning(item) for item in items or []]


def _slim_test_result(test_result):
    if not test_result:
        return {}
    return {
        field: test_result[field]
        for field in TEST_RESULT_MATERIAL_FIELDS
        if field in test_result
    }


def _slim_research(research_result):
    if not research_result:
        return None
    usable = research_result.get("usable_findings") or []
    unresolved = research_result.get("unresolved") or []
    if not usable and not unresolved:
        return None
    return attach_parsed_tables_to_research(
        {
            "usable_findings": usable,
            "unresolved": unresolved,
        }
    )


def _needs_research(gathered):
    for item in (gathered.get("repairable_warnings") or []) + (
        gathered.get("blocked_warnings") or []
    ):
        if item.get("needs_research_findings"):
            return True
    return bool(gathered.get("research_result"))


def select_repair_materials(gathered):
    """
    今回の修復に必要な MATERIALS だけを残す。
    契約（rules）はここへ入れない。PROFILE が選ぶキーでもない。
    """

    gathered = gathered or {}
    selected = {}

    for key in REQUIRED_MATERIAL_KEYS:
        if key == "repairable_warnings":
            selected[key] = _slim_warnings(gathered.get(key))
        elif key == "test_result":
            selected[key] = _slim_test_result(gathered.get(key))
        elif key in gathered:
            selected[key] = gathered[key]

    blocked = _slim_warnings(gathered.get("blocked_warnings"))
    if blocked:
        selected["blocked_warnings"] = blocked

    if _needs_research(gathered):
        research = _slim_research(gathered.get("research_result"))
        if research is not None:
            selected["research_result"] = research

    return selected


def repair_tool(
    tool_name,
    proposal,
    implementation,
    test_result,
    result_validation,
    registry_path="registry/tools.json",
    research_result=None,
):
    """
    修正に必要な MATERIALS をまとめる。ファイル変更は行わない。
    契約は tools.ai.prompts.base。モデル別の包装は tools.ai.llm.adapter。
    """

    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    tools = registry_data.get("tools", [])
    registry_entry = find_registry_entry(tools, tool_name)

    source_path = None
    if registry_entry and registry_entry.get("module"):
        source_path = module_to_path(registry_entry["module"])
    elif implementation and implementation.get("path"):
        source_path = implementation.get("path")

    disposition = (result_validation or {}).get("disposition") or {}
    gathered = {
        "tool_name": tool_name,
        "current_source": read_source(source_path) if source_path else None,
        "target_path": source_path,
        "target_function": (registry_entry or {}).get("function"),
        "target_output": (proposal or {}).get("output") or [],
        "repairable_warnings": disposition.get("repairable") or [],
        "blocked_warnings": disposition.get("blocked") or [],
        "test_result": test_result,
        "research_result": research_result or {},
    }
    return select_repair_materials(gathered)
