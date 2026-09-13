import json
import os

from tools.system.tool_builder.register import build_registry_entry


REJECT_EMPTY_REPAIR_CODE = "code がない repair 案は適用しない"


def has_repair_code(implementation):
    code = (implementation or {}).get("code")
    return bool(code and str(code).strip())


def find_registry_entry(tools, tool_name):
    for tool in tools:
        if tool.get("name") == tool_name:
            return tool
    return None


def apply_repair(
    tool_name,
    proposal,
    implementation,
    validation_result,
    registry_path="registry/tools.json",
):
    """
    検証済みの修正案を既存Toolに適用する。
    新規登録は行わない。コードは実行しない。
    """

    proposal = proposal or {}
    implementation = implementation or {}
    errors = []
    warnings = []

    if not validation_result:
        errors.append("validation_result がありません")
    elif validation_result.get("result") != "OK":
        errors.append("修正案の検証が OK ではありません")

    file_path = implementation.get("path")
    code = implementation.get("code")

    if not tool_name:
        errors.append("tool_name がありません")
    if not file_path:
        errors.append("implementation.path がありません")
    if not has_repair_code(implementation):
        errors.append(REJECT_EMPTY_REPAIR_CODE)

    if errors:
        return {
            "status": "fail",
            "result": "NG",
            "errors": errors,
            "warnings": warnings,
        }

    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    tools = registry_data.get("tools", [])
    entry_index = None
    registry_entry = None

    for index, tool in enumerate(tools):
        if tool.get("name") == tool_name:
            entry_index = index
            registry_entry = tool
            break

    normalized_path = file_path.replace("\\", "/")

    if registry_entry is None:
        errors.append(f"Registry に Tool が見つかりません: {tool_name}")
    elif not os.path.exists(normalized_path):
        errors.append(f"修正対象ファイルがありません: {normalized_path}")

    if errors:
        return {
            "status": "fail",
            "result": "NG",
            "errors": errors,
            "warnings": warnings,
        }

    updated_entry = build_registry_entry(proposal, implementation)
    updated_entry["name"] = tool_name

    if registry_entry.get("module") != updated_entry.get("module"):
        warnings.append(
            "module は変更せず Registry の既存値を維持します"
        )
        updated_entry["module"] = registry_entry.get("module")

    with open(normalized_path, "w", encoding="utf-8") as f:
        f.write(str(code).rstrip() + "\n")

    tools[entry_index] = updated_entry
    registry_data["tools"] = tools

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, ensure_ascii=False, indent=4)
        f.write("\n")

    return {
        "status": "warning" if warnings else "pass",
        "result": "OK",
        "tool_name": tool_name,
        "path": normalized_path,
        "registry_path": registry_path,
        "registry_entry": updated_entry,
        "errors": [],
        "warnings": warnings,
    }
