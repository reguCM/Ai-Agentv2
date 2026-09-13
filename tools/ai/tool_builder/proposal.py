PROJECT_CONVENTIONS = {
    "categories": [
        "system",
        "file",
        "image",
        "audio",
        "network",
        "ai",
        "node_red",
    ],
    "path": "tools/<category>/<subcategory>/<name>.py",
    # 構造・配置の例。センサー値のコピー元ではない。
    "module_example": "tools.system.cpu.cpu_status",
    "name_example": "cpu_status",
    "observation_example": "tools.system.gpu.nvidia_smi（nvidia-smi 実測。固定値禁止）",
    "observation_source_values": ["real", "mock", "fixture", "unknown"],
    "risk_values": ["low", "medium", "high"],
    "priority_values": ["required", "optional"],
}



def create_tool_proposal(
    request,
    project_spec=None,
    registry=None,
    related_tools=None,
    reference_tools=None,
    reference_sources=None,
    environment=None,
):
    """
    新しいToolの設計案を作るための、検証済み入力をまとめる。
    実際のファイル作成やRegistry変更は行わない。
    """

    return {
    "target_request": request,
    "verified_environment": environment,
    "project_conventions": project_spec or PROJECT_CONVENTIONS,
    "registry": registry,
    "related_tools": related_tools or [],
    "reference_tools": reference_tools or [],
    "reference_sources": reference_sources or [],
    "rules": [
        "target_request の対象を変えないこと。",
        "この結果に含まれる情報だけを事実として使うこと。",
        "verified_environment の情報は実行環境の事実であり、要求対象とは限らない。",
        "要求対象と異なる既存Toolを再提案しないこと。",
        "runtime は verified_environment の language / python_version / platform をそのまま使うこと。",
        "risk は low / medium / high のみ。文章を書かないこと。",
        "category は project_conventions.categories から選ぶこと。",
        "module は tools.<category>.<subcategory>.<filename> にすること。",
        "既存Toolの構造をまねるが、対象は要求に合わせること。",
        "observation_source=real の Tool だけを実環境センサーの参考にすること。",
        "固定値・架空値・ベンチ Fixture の数値を正しいセンサー実装としてコピーしないこと。",
        "GPU 観測は tools.system.gpu.nvidia_smi 経由の実測を参考にし、特定モデル名や温度・使用率のハードコード例を作らないこと。",
        "取得可否が未確認の項目は implementation_notes に『未確認』と書くこと。",
        "ファイル作成や Registry 変更はまだ行わないこと。",
        "reference_tools は実装構造・命名・配置などの参考に使用し、具体的な取得値や対象固有の情報をそのままコピーしないこと。",
    ],
    }
