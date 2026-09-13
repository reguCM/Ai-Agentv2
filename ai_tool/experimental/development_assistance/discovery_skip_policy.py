"""Experimental skip policy for Facet Discovery — not a Reasoning Core.

Classifies DISCOVERY_REQUIRED | DISCOVERY_OPTIONAL | DISCOVERY_SKIP
without judging feasible/safe/correct.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from ai_tool.experimental.development_assistance.goal_abstraction import abstract_goals
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchStore

DiscoveryMode = Literal["DISCOVERY_REQUIRED", "DISCOVERY_OPTIONAL", "DISCOVERY_SKIP"]
PolicyName = Literal["A", "B", "C", "D"]

_SKIP_PATTERNS = (
    r"とは何ですか",
    r"とはなに",
    r"for文を教えて",
    r"コードを書いて",
    r"関数を作って",
    r"jsonを辞書に変換",
    r"csvを読み込むコード",
    r"jsonを読むコード",
)

_REQUIRED_SIGNALS = (
    r"調べ",
    r"research",
    r"最新",
    r"version",
    r"バージョン",
    r"python\s*3\.",
    r"cuda\s*1",
    r"環境",
    r"対応",
    r"\bapi\b",
    r"apiを",
    r"ライセンス",
    r"license",
    r"比較",
    r"どちら",
    r"どっち",
    r"実行できる",
    r"動かせ",
    r"作れそう",
    r"tool化",
    r"前に調べた",
    r"場合だけ",
    r"使えるのか",
    r"注意点",
    r"不足",
    r"再評価",
    r"windows",
    r"rtx",
    r"3060",
    r"virtualbox",
    r"5\.1[57]",
)

_FOLLOW_SIGNALS = (
    r"もう少し",
    r"その場合",
    r"なら？",
    r"では？",
    r"どうなる",
    r"使いたい",
    r"前の結果",
    r"さっき",
)

_AMBIGUOUS = (
    r"その環境なら",
    r"さっきの方法を別の環境",
    r"これtoolにできる",
    r"そのpython版",
    r"前のやつ",
    r"別の方法",
)

_IMPLICIT_OPS = (
    r"人間が",
    r"途中で操作",
    r"止められる",
    r"操作できる",
    r"一緒に使える",
)

_UNKNOWN_DOMAIN = (
    r"foobar",
    r"特殊な装置",
)


@dataclass
class DiscoveryPolicyDecision:
    mode: DiscoveryMode
    policy: PolicyName
    invoked: bool
    reasons: list[str]
    unknown_domain: bool = False
    clarification_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_skip(req: str) -> bool:
    lower = req.lower()
    if re.search(r"調べて|research", lower):
        return False
    return any(re.search(p, lower) for p in _SKIP_PATTERNS)


def _has_required_signal(req: str) -> bool:
    lower = req.lower()
    return any(re.search(p, lower) for p in _REQUIRED_SIGNALS)


def _is_follow(req: str) -> bool:
    return any(re.search(p, req.lower()) for p in _FOLLOW_SIGNALS)


def _is_ambiguous(req: str) -> bool:
    lower = req.lower()
    return any(re.search(p, lower) for p in _AMBIGUOUS)


def _is_implicit_ops(req: str) -> bool:
    return any(re.search(p, req.lower()) for p in _IMPLICIT_OPS)


def _is_unknown_domain(req: str) -> bool:
    return any(re.search(p, req.lower()) for p in _UNKNOWN_DOMAIN)


def classify_discovery(
    requirement: str,
    *,
    policy: PolicyName,
    store: ResearchStore | None = None,
) -> DiscoveryPolicyDecision:
    """Decide whether to invoke Facet Discovery. Does not emit a verdict."""
    store = store or ResearchStore()
    gate = assess_research_requirement(requirement)
    skip = _is_skip(requirement)
    signal = _has_required_signal(requirement)
    follow = _is_follow(requirement)
    ambiguous = _is_ambiguous(requirement)
    unknown = _is_unknown_domain(requirement)
    implicit_ops = _is_implicit_ops(requirement)
    goals = abstract_goals(requirement)
    goal_researchy = bool(goals.level_3_justified) and not skip

    if policy == "A":
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_REQUIRED",
            policy="A",
            invoked=True,
            reasons=["always"],
            unknown_domain=unknown,
            clarification_required=ambiguous or unknown,
        )

    if policy == "B":
        if gate.decision == "RESEARCH_REQUIRED":
            return DiscoveryPolicyDecision(
                mode="DISCOVERY_REQUIRED",
                policy="B",
                invoked=True,
                reasons=["gate research required"],
                unknown_domain=unknown,
                clarification_required=ambiguous,
            )
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_SKIP",
            policy="B",
            invoked=False,
            reasons=["gate llm-only"],
            unknown_domain=unknown,
            clarification_required=False,
        )

    if policy == "C":
        if skip:
            return DiscoveryPolicyDecision(
                mode="DISCOVERY_SKIP", policy="C", invoked=False, reasons=["skip pattern"]
            )
        if unknown:
            return DiscoveryPolicyDecision(
                mode="DISCOVERY_OPTIONAL",
                policy="C",
                invoked=True,
                reasons=["unknown domain"],
                unknown_domain=True,
                clarification_required=True,
            )
        if ambiguous:
            return DiscoveryPolicyDecision(
                mode="DISCOVERY_OPTIONAL",
                policy="C",
                invoked=True,
                reasons=["ambiguous follow-up"],
                clarification_required=True,
            )
        if implicit_ops:
            return DiscoveryPolicyDecision(
                mode="DISCOVERY_OPTIONAL",
                policy="C",
                invoked=True,
                reasons=["implicit operations cue; do not assert required"],
                clarification_required=True,
            )
        if signal:
            return DiscoveryPolicyDecision(
                mode="DISCOVERY_REQUIRED", policy="C", invoked=True, reasons=["requirement signal"]
            )
        if follow and store.records:
            return DiscoveryPolicyDecision(
                mode="DISCOVERY_OPTIONAL",
                policy="C",
                invoked=True,
                reasons=["follow-up with store"],
            )
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_SKIP", policy="C", invoked=False, reasons=["no research signal"]
        )

    # Policy D: Gate + Goal + store/capability situation + signals; skip patterns win.
    # Does not call discover_facets to decide (that would be circular).
    if skip:
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_SKIP", policy="D", invoked=False, reasons=["skip pattern"]
        )
    if unknown:
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_OPTIONAL",
            policy="D",
            invoked=True,
            reasons=["unknown domain"],
            unknown_domain=True,
            clarification_required=True,
        )
    if ambiguous:
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_OPTIONAL",
            policy="D",
            invoked=True,
            reasons=["clarification"],
            clarification_required=True,
        )
    if implicit_ops:
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_OPTIONAL",
            policy="D",
            invoked=True,
            reasons=["implicit operations cue; do not assert required"],
            clarification_required=True,
        )
    required = gate.decision == "RESEARCH_REQUIRED" or signal or (follow and bool(store.records)) or goal_researchy
    if required:
        return DiscoveryPolicyDecision(
            mode="DISCOVERY_REQUIRED",
            policy="D",
            invoked=True,
            reasons=["gate/signal/store follow-up"],
        )
    return DiscoveryPolicyDecision(
        mode="DISCOVERY_SKIP", policy="D", invoked=False, reasons=["no combined need"]
    )


def environment_switch(previous_env: str, requirement: str) -> dict[str, Any]:
    """Do not apply Docker envelopes to VirtualBox (metadata, not a graph)."""
    req = requirement.lower()
    drop: list[str] = []
    if previous_env == "docker" and re.search(r"virtualbox|vbox", req):
        drop = ["docker", "storage", "gpu_passthrough", "network_ports"]
    if previous_env == "virtualbox" and "docker" in req:
        drop = ["virtualbox"]
    return {
        "switched": bool(drop),
        "drop_facets": drop,
        "do_not_apply_prior_env": bool(drop),
    }
