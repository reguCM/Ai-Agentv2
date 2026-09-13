"""Minimal environment policy wedge (v0). VERIFY_ONLY only — no Environment Strategy."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ai_tool.precondition_contract import STATUS_SATISFIED, Precondition

ENVIRONMENT_POLICY_VERIFY_ONLY = "VERIFY_ONLY"

KNOWN_ENVIRONMENT_POLICIES = frozenset({ENVIRONMENT_POLICY_VERIFY_ONLY})

_MUTATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python_version_change", re.compile(r"python\s+\d+\.\d+|upgrade\s+python|downgrade\s+python", re.I)),
    ("venv_rebuild", re.compile(r"recreate\s+venv|rebuild\s+venv|new\s+virtual\s?env", re.I)),
    ("global_pip_install", re.compile(r"pip\s+install\s+--user|global\s+pip\s+install", re.I)),
    ("cuda_change", re.compile(r"install\s+cuda|upgrade\s+cuda|pytorch\s+with\s+cuda", re.I)),
    ("docker_setup", re.compile(r"docker\s+(build|compose|run)|containerize", re.I)),
    ("wsl_setup", re.compile(r"\bwsl\b.*install|enable\s+wsl", re.I)),
    ("os_package_change", re.compile(r"apt\s+install|yum\s+install|choco\s+install", re.I)),
    ("path_mutation", re.compile(r"permanently\s+modify\s+PATH|setx\s+PATH", re.I)),
)


@dataclass
class EnvironmentPolicyGateResult:
    environment_policy: str
    may_continue: bool
    current_environment_verified: bool
    blocking_gaps: list[str] = field(default_factory=list)
    mutations_detected: list[str] = field(default_factory=list)
    mutations_executed: list[str] = field(default_factory=list)
    human_message: str = ""
    goal_text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "environment_policy": self.environment_policy,
            "may_continue": self.may_continue,
            "current_environment_verified": self.current_environment_verified,
            "blocking_gaps": self.blocking_gaps,
            "mutations_detected": self.mutations_detected,
            "mutations_executed": self.mutations_executed,
            "human_message": self.human_message,
            "goal_text": self.goal_text,
        }


def resolve_environment_policy(execution_context: Mapping[str, Any] | None) -> str:
    if not isinstance(execution_context, Mapping):
        return ENVIRONMENT_POLICY_VERIFY_ONLY
    direct = str(execution_context.get("environment_policy") or "").strip()
    if direct:
        return direct
    policy = execution_context.get("policy")
    if isinstance(policy, Mapping):
        nested = str(policy.get("environment_policy") or "").strip()
        if nested:
            return nested
    return ENVIRONMENT_POLICY_VERIFY_ONLY


def _blocking_gaps(preconditions: Sequence[Precondition]) -> list[str]:
    gaps: list[str] = []
    for item in preconditions:
        if not item.blocking:
            continue
        if item.evaluation.status != STATUS_SATISFIED:
            gaps.append(item.key)
    return gaps


def detect_environment_mutation_proposals(texts: Sequence[str]) -> list[str]:
    found: list[str] = []
    blob = "\n".join(str(t) for t in texts if str(t).strip())
    for label, pattern in _MUTATION_PATTERNS:
        if pattern.search(blob):
            found.append(label)
    return sorted(set(found))


def verify_only_blocks_auto_mutation(
    *,
    environment_policy: str,
    proposed_mutations: Sequence[str],
) -> tuple[bool, list[str]]:
    """Returns (blocked, detected_labels). Never executes mutations."""
    if environment_policy != ENVIRONMENT_POLICY_VERIFY_ONLY:
        return False, []
    detected = list(proposed_mutations)
    return bool(detected), detected


def format_verify_only_block_message(
    *,
    blocking_gaps: Sequence[str],
    preconditions: Sequence[Precondition],
    environment_policy: str,
) -> str:
    lines = [
        "現在の環境では、この実行を続行できません。",
        f"環境ポリシーは {environment_policy} です。環境の自動変更や修復は行っていません。",
    ]
    if blocking_gaps:
        lines.append("不足している項目:")
        by_key = {p.key: p for p in preconditions}
        for key in blocking_gaps:
            row = by_key.get(key)
            if row:
                lines.append(f"- {row.description}（{key}: {row.evaluation.status}）")
            else:
                lines.append(f"- {key}")
    lines.append("環境を整えたうえで再実行するか、将来の Environment Strategy フェーズで対応してください。")
    return "\n".join(lines)


def evaluate_verify_only_gate(
    *,
    environment_policy: str,
    preconditions: Sequence[Precondition],
    goal_text: str = "",
    derived_spec_texts: Sequence[str] | None = None,
) -> EnvironmentPolicyGateResult:
    """VERIFY_ONLY: verify current environment; never auto-mutate or repair."""
    policy = environment_policy or ENVIRONMENT_POLICY_VERIFY_ONLY
    gaps = _blocking_gaps(preconditions)
    verified = len(gaps) == 0
    mutations = detect_environment_mutation_proposals(derived_spec_texts or [])
    blocked_mutations, _ = verify_only_blocks_auto_mutation(
        environment_policy=policy,
        proposed_mutations=mutations,
    )

    may_continue = verified and not blocked_mutations
    human_message = ""
    if not verified:
        human_message = format_verify_only_block_message(
            blocking_gaps=gaps,
            preconditions=preconditions,
            environment_policy=policy,
        )
    elif blocked_mutations:
        human_message = (
            f"環境ポリシーは {policy} です。仕様に環境変更（"
            f"{', '.join(mutations)}"
            ")が含まれていますが、自動実行は行いません。仕様を見直してください。"
        )

    return EnvironmentPolicyGateResult(
        environment_policy=policy,
        may_continue=may_continue,
        current_environment_verified=verified,
        blocking_gaps=gaps,
        mutations_detected=mutations,
        mutations_executed=[],
        human_message=human_message,
        goal_text=goal_text,
    )


def merge_policy_into_precondition_bundle(
    bundle: dict[str, Any],
    execution_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    policy_block = dict(bundle.get("policy") or {})
    policy_block["environment_policy"] = resolve_environment_policy(execution_context)
    policy_block["verify_only_no_auto_mutation"] = True
    out = dict(bundle)
    out["policy"] = policy_block
    return out
