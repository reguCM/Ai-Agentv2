"""
status の単位質問への答えを、3つの認識に分けて記録する。

採点ラベルは LLM に渡さない。答えの文言から機械が付ける。
"""


def _hay(text):
    return str(text or "").lower()


def _has(haystack, tokens):
    return any(token.lower() in haystack for token in tokens)


MEMORY_TOKENS = (
    "メモリ使用率",
    "メモリの使用",
    "使用率",
    "memory usage",
    "memory use",
    "ram usage",
    "used memory",
    "percentcommitted",
)
TOOL_TOKENS = (
    "43.2",
    "戻り値",
    "返り値",
    "return_value",
    "return value",
    "returned",
    "今回の",
    "このツール",
    "このtool",
    "this tool",
    "the tool",
    "get_memory_status",
    "statusの値",
    "status の値",
    "value of status",
    "status value",
)
PERCENT_TOKENS = (
    "%",
    "percent",
    "percentage",
    "パーセント",
    "百分率",
    "per cent",
)
GENERIC_TOKENS = (
    "http",
    "ステータスコード",
    "status code",
    "statuscode",
    "成功フラグ",
    "success/error",
    "success or error",
    "exit code",
    "終了コード",
)


EXPLICIT_STATE_TOKENS = (
    "task state",
    "status.meaning",
    "status.unit",
    "status.range",
    "0-100",
    "0〜100",
    "windowsのメモリ使用率",
    "windows memory usage",
    "confirmed",
    "確定",
)
VALUE_INFERENCE_TOKENS = (
    "43.2",
    "from the number",
    "from the value",
    "looks like",
    "数値から",
    "この数字",
    "the number",
)
GENERAL_KNOWLEDGE_TOKENS = (
    "typically",
    "usually",
    "generally",
    "in general",
    "一般",
    "普通",
    "よくある",
    "http",
    "status code",
    "ステータスコード",
)


def classify_unit_reason(text, *, state_present=False):
    """
    なぜ % と判断したか。ラベルは LLM に渡さない。

    state_based       STATE または STATE にしかない意味を使った
    value_inference   43.2 などの数値から推測した
    general_knowledge 一般論
    unknown
    """
    haystack = _hay(text)
    explicit = _has(haystack, EXPLICIT_STATE_TOKENS)
    value = _has(haystack, VALUE_INFERENCE_TOKENS)
    general = _has(haystack, GENERAL_KNOWLEDGE_TOKENS)
    meaning = _has(haystack, MEMORY_TOKENS)
    if explicit:
        return "state_based"
    if value and meaning:
        return "state_based" if state_present else "value_inference"
    if value:
        return "value_inference"
    if meaning:
        return "state_based" if state_present else "general_knowledge"
    if general:
        return "general_knowledge"
    return "unknown"


def classify_status_unit(text, *, state_present=False):
    haystack = _hay(text)
    generic = _has(haystack, GENERIC_TOKENS)
    memory = _has(haystack, MEMORY_TOKENS)
    tool = _has(haystack, TOOL_TOKENS)
    unit = _has(haystack, PERCENT_TOKENS)
    return {
        "recognized_memory_usage": memory,
        "recognized_tool_status": tool,
        "unit_percent": unit,
        "generic_status": generic,
        "reason_class": classify_unit_reason(text, state_present=state_present),
    }


def all_recognized(labels):
    return bool(
        labels.get("recognized_memory_usage")
        and labels.get("recognized_tool_status")
        and labels.get("unit_percent")
    )
