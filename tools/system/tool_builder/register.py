import json
import os


def build_registry_entry(proposal, implementation):
    proposal = proposal or {}
    implementation = implementation or {}

    return {
        "name": proposal.get("name"),
        "category": proposal.get("category"),
        "subcategory": proposal.get("subcategory"),
        "description": proposal.get("description"),
        "keywords": proposal.get("keywords") or [],
        "risk": proposal.get("risk") or "low",
        "module": proposal.get("module"),
        "function": implementation.get("function") or proposal.get("function"),
        "input": proposal.get("input") or {},
        "output": proposal.get("output") or [],
    }


def register_tool(
    proposal,
    implementation,
    registry_path="registry/tools.json",
    validation_result=None,
):
    """
    検証済みの設計案と実装案をRegistryに登録し、コードファイルを作成する。
    コードは実行しない。
    """

    proposal = proposal or {}
    implementation = implementation or {}
    errors = []
    warnings = []

    if not validation_result:
        errors.append("validation_result がありません")
    elif validation_result.get("result") != "OK":
        errors.append("実装案の検証が OK ではありません")

    tool_name = proposal.get("name")
    file_path = implementation.get("path")
    code = implementation.get("code")

    if not tool_name:
        errors.append("proposal.name がありません")
    if not file_path:
        errors.append("implementation.path がありません")
    if not code or not str(code).strip():
        errors.append("implementation.code がありません")

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
    existing_names = {
        tool.get("name")
        for tool in tools
        if isinstance(tool, dict)
    }

    if tool_name in existing_names:
        errors.append(f"Registry に同名Toolが既に存在します: {tool_name}")

    normalized_path = file_path.replace("\\", "/")
    if os.path.exists(normalized_path):
        errors.append(f"ファイルが既に存在します: {normalized_path}")

    if errors:
        return {
            "status": "fail",
            "result": "NG",
            "errors": errors,
            "warnings": warnings,
        }

    if proposal.get("name") != implementation.get("function"):
        warnings.append(
            f"Tool名と関数名が異なります: "
            f"{proposal.get('name')} != {implementation.get('function')}"
        )

    registry_entry = build_registry_entry(proposal, implementation)

    os.makedirs(os.path.dirname(normalized_path), exist_ok=True)
    with open(normalized_path, "w", encoding="utf-8") as f:
        f.write(str(code).rstrip() + "\n")

    tools.append(registry_entry)
    registry_data["tools"] = tools

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, ensure_ascii=False, indent=4)
        f.write("\n")

    return {
        "status": "warning" if warnings else "pass",
        "result": "OK",
        "registered_name": tool_name,
        "registered_function": registry_entry.get("function"),
        "path": normalized_path,
        "registry_path": registry_path,
        "registry_entry": registry_entry,
        "errors": [],
        "warnings": warnings,
    }
