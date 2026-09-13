ALLOWED_CATEGORIES = [
    "system",
    "file",
    "image",
    "audio",
    "network",
    "ai",
    "node_red",
]

ALLOWED_RISK = [
    "low",
    "medium",
    "high",
]

ALLOWED_PRIORITY = [
    "required",
    "optional",
]


def validate_tool_spec(
    spec,
    project_environment,
    request=None,
    existing_tools=None,
    allowed_categories=None,
):
    """
    Tool Specificationがプロジェクトの環境・ルールに
    適合しているかを検証する。
    """

    errors = []
    warnings = []
    allowed_categories = allowed_categories or ALLOWED_CATEGORIES
    existing_tools = existing_tools or []

    # 必須項目
    required_fields = [
        "name",
        "category",
        "subcategory",
        "description",
        "keywords",
        "risk",
        "module",
        "function",
        "input",
        "output",
        "dependencies",
        "runtime",
        "priority",
        "based_on",
        "implementation_notes",
    ]

    for field in required_fields:
        if field not in spec:
            errors.append(
                f"必須項目がありません: {field}"
            )

    # runtime確認
    runtime = spec.get("runtime", {})

    expected_language = project_environment.get("language")
    expected_version = project_environment.get("python_version")
    expected_platform = project_environment.get("platform")

    if runtime.get("language") != expected_language:
        errors.append(
            f"runtime.languageが環境と一致しません: "
            f"{runtime.get('language')} != {expected_language}"
        )

    runtime_version = runtime.get("version", "")

    if expected_version and expected_version not in runtime_version:
        warnings.append(
            f"Pythonバージョンを確認してください: "
            f"現在 {expected_version}, Tool側 {runtime_version}"
        )

    platforms = runtime.get("platform", [])
    if not isinstance(platforms, list):
        platforms = []

    normalized_platforms = [
        str(item).lower() for item in platforms
    ]
    expected_platform_normalized = str(expected_platform or "").lower()

    if expected_platform_normalized and expected_platform_normalized not in normalized_platforms:
        errors.append(
            f"現在の環境 {expected_platform} が"
            f"Toolのplatformに含まれていません"
        )

    extra_platforms = [
        item for item in platforms
        if str(item).lower() != expected_platform_normalized
    ]
    if extra_platforms:
        warnings.append(
            f"検証していないplatformが含まれています: {extra_platforms}"
        )

    if spec.get("risk") not in ALLOWED_RISK:
        errors.append(
            f"riskは low / medium / high のいずれかにしてください: "
            f"{spec.get('risk')}"
        )

    if spec.get("priority") not in ALLOWED_PRIORITY:
        errors.append(
            f"priorityの値が不正です: {spec.get('priority')}"
        )

    category = spec.get("category")
    if category not in allowed_categories:
        errors.append(
            f"categoryは次のいずれかにしてください: {allowed_categories}"
        )

    module = spec.get("module") or ""
    module_parts = module.split(".")
    if len(module_parts) < 4 or module_parts[0] != "tools":
        errors.append(
            "moduleは tools.<category>.<subcategory>.<filename> 形式にしてください"
        )
    elif category and module_parts[1] != category:
        errors.append(
            f"moduleのcategoryが一致しません: {module} != {category}"
        )

    existing_names = {
        tool.get("name")
        for tool in existing_tools
        if isinstance(tool, dict)
    }
    if spec.get("name") in existing_names:
        errors.append(
            f"既存Toolと同じ名前です: {spec.get('name')}"
        )

    request_text = (request or "").lower()
    name = str(spec.get("name") or "").lower()
    subcategory = str(spec.get("subcategory") or "").lower()
    for tool in existing_tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("name") == "create_tool_proposal":
            continue
        marker = str(tool.get("subcategory") or "").lower()
        if not marker:
            continue
        if marker in name or marker == subcategory:
            if marker not in request_text:
                errors.append(
                    f"要求にない対象 '{marker}' のToolを提案しています。"
                    f"要求: {request}"
                )
                break

    # 結果
    if errors:
        status = "fail"
    elif warnings:
        status = "warning"
    else:
        status = "pass"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
    }