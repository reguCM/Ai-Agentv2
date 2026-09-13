"""
PROJECT_CONTEXT をプロンプトへ出す契約。実体は tools.ai.context。

確定済みの環境。実装手段は Agent が決める。
"""

CONTEXT_CONTRACT = [
    {
        "id": "context_readonly",
        "ja": "PROJECT_CONTEXT は事前に確定した環境である。勝手に変えない。",
        "en": "PROJECT_CONTEXT is confirmed environment. Do not change it.",
    },
    {
        "id": "agent_methods",
        "ja": "implementation_method_selection が Agent なら、実現方法はユーザーに聞かない。Research のあとエージェントが決める。",
        "en": "If implementation_method_selection is Agent, do not ask the user how to implement. The agent decides after Research.",
    },
]
