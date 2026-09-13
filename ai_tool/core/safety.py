from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_tool.core.models import ToolDescriptor

SafetyVerdict = Literal["allow", "deny", "human_required"]


@dataclass
class SafetyDecision:
    verdict: SafetyVerdict
    reason: str
    checks: dict[str, bool]

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "checks": self.checks,
        }


def evaluate_tool_safety(
    descriptor: ToolDescriptor,
    *,
    allow_write: bool = False,
    allow_modify: bool = False,
    trust_external: bool = False,
) -> SafetyDecision:
    """Mechanical safety gate — does not call LLM."""
    checks = {
        "status_available": descriptor.status in ("available", "adopt_candidate", "experimental"),
        "risk_acceptable": descriptor.risk_level != "high",
        "execution_mode_allowed": True,
        "external_trusted": descriptor.provider == "local" or trust_external,
    }

    if descriptor.status == "disabled":
        return SafetyDecision("deny", "tool_disabled", checks)

    if descriptor.execution_mode == "write" and not allow_write:
        checks["execution_mode_allowed"] = False
        return SafetyDecision("human_required", "write_mode_requires_approval", checks)

    if descriptor.execution_mode == "modify" and not allow_modify:
        checks["execution_mode_allowed"] = False
        return SafetyDecision("human_required", "modify_mode_requires_approval", checks)

    if descriptor.provider != "local" and not trust_external:
        checks["external_trusted"] = False
        return SafetyDecision("human_required", "external_tool_requires_explicit_trust", checks)

    if descriptor.risk_level == "high":
        return SafetyDecision("human_required", "high_risk_tool", checks)

    if descriptor.provider != "local":
        return SafetyDecision("human_required", "external_tool_default_confirm", checks)

    return SafetyDecision("allow", "local_read_low_risk", checks)
