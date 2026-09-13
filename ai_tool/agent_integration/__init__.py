"""Agent Tool Discovery — non-destructive integration with AI-TOOL Layer (Phase 1)."""

from ai_tool.agent_integration.discovery import (
    AgentToolDiscoveryAdapter,
    discover_tools,
    get_tool_descriptor,
)
from ai_tool.agent_integration.hook import (
    AgentDiscoveryHookRecord,
    AgentDiscoveryHookResult,
    run_agent_discovery_hook,
    safe_run_agent_discovery_hook,
)
from ai_tool.agent_integration.models import AgentDiscoveredTool, DiscoveryResult
from ai_tool.catalog.review import (
    HumanReviewRecord,
    HumanReviewResult,
    apply_human_review,
    get_reviewable_tool,
)

from ai_tool.agent_integration.trial import ExperimentalTrialResult, run_experimental_trial
from ai_tool.agent_integration.production_bridge import (
    append_experimental_agent_tools,
    get_experimental_agent_exposure,
)

__all__ = [
    "AgentDiscoveredTool",
    "AgentDiscoveryHookRecord",
    "AgentDiscoveryHookResult",
    "AgentToolDiscoveryAdapter",
    "append_experimental_agent_tools",
    "DiscoveryResult",
    "ExperimentalTrialResult",
    "HumanReviewRecord",
    "HumanReviewResult",
    "apply_human_review",
    "discover_tools",
    "get_reviewable_tool",
    "get_experimental_agent_exposure",
    "get_tool_descriptor",
    "run_agent_discovery_hook",
    "run_experimental_trial",
    "safe_run_agent_discovery_hook",
]
