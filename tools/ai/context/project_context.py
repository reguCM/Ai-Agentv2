"""
事前に決まっているプロジェクト環境。LLM は読めない書き換え。

実装手段の選択は Agent。ユーザーには聞かない。
"""

from tools.system.config import get_pipeline


DEFAULT_PROJECT_CONTEXT = {
    "os": "Windows",
    "runtime": "Python",
    "llm": "Ollama",
    "tool_architecture": "existing registry/tools",
    "implementation_style": "follow existing tools",
    "implementation_method_selection": "Agent",
}


def snapshot_context(context=None):
    if context is None:
        return get_project_context()
    if not isinstance(context, dict):
        return dict(DEFAULT_PROJECT_CONTEXT)
    payload = dict(DEFAULT_PROJECT_CONTEXT)
    for key, value in context.items():
        if value is not None:
            payload[str(key)] = value
    return payload


def get_project_context():
    overlay = (get_pipeline() or {}).get("project_context") or {}
    return snapshot_context(overlay if isinstance(overlay, dict) else {})
