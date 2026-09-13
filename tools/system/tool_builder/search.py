BUILDER_TOOLS = {
    "create_tool_proposal",
    "create_tool_implementation",
    "validate_tool_implementation",
    "register_tool",
    "test_tool",
    "validate_tool_result",
    "repair_tool",
    "apply_repair",
    "research_tool",
    "research_executor",
    "research_result_validator",
    "research_result",
    "web_research",
    "research_verifier",
}


def search_tools(registry, request, category=None, subcategory=None):
    """
    Registryからユーザー要求に関連するToolを検索する。
    Toolのメタデータのみを返し、ソースコードは取得しない。
    """

    request_lower = request.lower()

    results = []

    for tool in registry.get("tools", []):
        if tool.get("name") in BUILDER_TOOLS:
            continue

        score = 0

        tool_category = tool.get("category", "")
        tool_subcategory = tool.get("subcategory", "")

        if category and tool_category == category:
            score += 5

        if subcategory and tool_subcategory == subcategory:
            score += 5

        description = tool.get("description", "")
        if description.lower() in request_lower:
            score += 2

        for keyword in tool.get("keywords", []):
            if keyword.lower() in request_lower:
                score += 2

        if score > 0:
            results.append(
                {
                    "score": score,
                    "name": tool.get("name"),
                    "category": tool.get("category"),
                    "subcategory": tool.get("subcategory"),
                    "description": tool.get("description"),
                    "keywords": tool.get("keywords", []),
                    "module": tool.get("module"),
                    "function": tool.get("function"),
                }
            )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results

def find_reference_tools(registry, category, limit=2):
    results = []

    for tool in registry.get("tools", []):
        if tool.get("name") in BUILDER_TOOLS:
            continue

        if tool.get("category") == category:
            results.append(tool)

        if len(results) >= limit:
            break

    return results
def load_tool_source(tool):
    """
    Registryに登録されたToolのソースコードを取得する。
    必要なToolだけをLLMへ渡すために使用する。
    """

    import importlib
    import inspect

    module = importlib.import_module(tool["module"])

    return {
        "name": tool["name"],
        "category": tool.get("category"),
        "subcategory": tool.get("subcategory"),
        "module": tool["module"],
        "function": tool["function"],
        "source": inspect.getsource(module),
    }