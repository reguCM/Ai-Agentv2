from tools.system.tool_builder.validate.warning_actions import unique_texts


def classify_research_item(text):
    text = str(text)

    if text.startswith("output "):
        return "output"
    if text.startswith("unimplemented "):
        return "unimplemented"
    if "platform" in text:
        return "platform"
    if "dependency" in text.lower() or "dependencies" in text:
        return "dependency"
    if "ライブラリ" in text or "コマンド" in text:
        return "capability"
    return "unconfirmed"


def research_tool(
    research_request=None,
    proposal=None,
    tool_name=None,
):
    """
    調査対象を整理し、調べる項目だけを返す。
    実際の調査（import / pip / コマンド確認）は行わない。
    """

    research_request = research_request or {}
    proposal = proposal or {}
    required = unique_texts(research_request.get("required_information") or [])

    if not required:
        return {
            "result": "NG",
            "status": "fail",
            "error": "調査対象がありません",
            "research_items": [],
            "item_count": 0,
        }

    research_items = []
    for index, question in enumerate(required, start=1):
        research_items.append(
            {
                "id": index,
                "kind": classify_research_item(question),
                "question": question,
            }
        )

    return {
        "result": "OK",
        "status": "blocked",
        "subject": {
            "tool_name": tool_name or proposal.get("name"),
            "subcategory": proposal.get("subcategory"),
        },
        "reason": research_request.get("reason") or "",
        "research_items": research_items,
        "item_count": len(research_items),
        "notes": [
            "実際の調査は research_executor が行う。",
            "research_items が次の調査対象である。",
        ],
    }
