"""Context Monitor 観測スキーマ（事実のみ。評価は aggregate / recalibration で後計算）。"""
from __future__ import annotations

SCHEMA_VERSION = 1

# 処理タイプ（Context 適性の区別用）
TASK_TYPES = frozenset(
    {
        "simple",
        "search_read",
        "list_read",
        "multi_read",
        "large_result",
        "unknown",
    }
)

EVALUATION_STATES = frozenset(
    {
        "insufficient_data",
        "accumulating",
        "ready_for_review",
    }
)

RECALIBRATION_STATUSES = frozenset(
    {
        "none",
        "candidate",
        "recalibration_recommended",
    }
)

# Tool Calling 失敗分類（P2-10）
FAILURE_TYPES = frozenset(
    {
        "TOOL_CALL_NOT_GENERATED",
        "TOOL_CALL_PARSE_FAILED",
        "TOOL_EXECUTION_FAILED",
        "TIMEOUT",
        "CONTEXT_LIMIT",
        "GPU_RESOURCE_INSUFFICIENT",
        "UNKNOWN",
        "NONE",
    }
)

RECOVERY_STRATEGIES = frozenset(
    {
        "none",
        "retry_same_context",
        "increase_context",
        "decrease_context",
        "reduce_tool_result",
        "narrow_search_scope",
        "change_search_scope",
        "change_tool_strategy",
        "retry_with_explicit_tool_instruction",
        "retry_with_specialist_model",
        "human_review",
    }
)

CONFIDENCE_LEVELS = frozenset(
    {
        "HIGH",
        "MEDIUM",
        "LOW",
        "UNKNOWN",
    }
)

# Agent 判断 vs Evidence Ranking 比較（P2-13）
RANKING_VS_AGENT = frozenset(
    {
        "MATCH",
        "DIFFERENT",
        "NO_RANKING",
    }
)

CONTEXT_EXPANSION_GATE_STATUS = frozenset(
    {
        "BLOCKED",
        "ALLOWED",
    }
)

AGENT_EVALUATION_SCHEMA_VERSION = 1
