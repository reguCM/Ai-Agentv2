def module_to_path(module):
    if not module:
        return None
    return module.replace(".", "/") + ".py"


def create_tool_implementation(
    proposal,
    reference_tools=None,
    reference_sources=None,
    environment=None,
    research_result=None,
    request=None,
):
    """
    Tool設計案から実装コードを生成するための入力をまとめる。
    実際のファイル作成は行わない。
    """

    proposal = proposal or {}
    research_result = research_result or {}

    return {
        "target_request": request or proposal.get("description"),
        "proposal": proposal,
        "target_path": module_to_path(proposal.get("module")),
        "target_function": proposal.get("function"),
        "reference_tools": reference_tools or [],
        "reference_sources": reference_sources or [],
        "environment": environment,
        "research_result": research_result,
        "insufficient_findings": research_result.get("insufficient_findings") or [],
        "rules": [
            "proposal の対象・name・module・function を変更しないこと。",
            "既存Toolを変更しないこと。",
            "参考Toolの固定値を実装結果としてコピーしないこと。",
            "検証済み環境以外を想像しないこと。",
            "research_result.usable_findings（confidence=high）だけを実装の事実として使うこと。",
            "research_result.reference_findings（confidence=medium）は参考情報であり、実装根拠にしないこと。",
            "コマンドやライブラリの存在確認だけでは、取得方法を実装しないこと。",
            "usable_findings の evidence.command / sample があるときだけ、その取得方法を実装すること。",
            "insufficient_findings は要求を満たさない調査結果なので、その取得方法を実装しないこと。",
            "research_result.unresolved は未実装にすること。",
            "research_result が空、または usable_findings が空なら、取得方法は未確認として扱うこと。",
            "proposal.output にない項目を実装しないこと。",
            "取得方法が未確認の項目は未実装として明示すること。",
            "未確認の値を、取得成功に見える文や固定値で埋めてはいけない。",
            "未実装の return 値は '未実装' にすること。",
            "ファイル作成は行わないこと。",
        ],
    }
