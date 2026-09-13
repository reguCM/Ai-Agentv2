"""Hierarchical goal abstraction for Capability Discovery (Phase E)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CapabilityClass = Literal["Tool", "Middleware", "Core", "Experimental"]
ObsDecision = Literal["REUSE", "RECORD", "DEFER", "INVESTIGATE", "EXPERIMENTAL", "REJECT"]


@dataclass
class DerivedCapability:
    name: str
    description: str
    capability_class: CapabilityClass
    existing_alternative: str
    decision: ObsDecision
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalHierarchy:
    request: str
    level_0: str
    level_1: str
    level_2: str
    level_3: str = ""
    level_3_justified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HierarchicalDiscovery:
    goals: GoalHierarchy
    derived_capabilities: list[DerivedCapability] = field(default_factory=list)
    rejected_ideas: list[str] = field(default_factory=list)
    future_ideas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goals": self.goals.to_dict(),
            "derived_capabilities": [d.to_dict() for d in self.derived_capabilities],
            "rejected_ideas": self.rejected_ideas,
            "future_ideas": self.future_ideas,
        }


# Pattern-based abstraction — not philosophical; stops at Level 2 unless justified
_PATTERNS: list[dict[str, Any]] = [
    {
        "match": re.compile(r"同じ.*(文章|入力|リクエスト).*(llm|渡さ|送信)", re.I),
        "l0": "Duplicate Inputを検出したい",
        "l1": "不要なLLM処理を減らしたい",
        "l2": "LLMへの入力を最適化し、不要な処理・コスト・遅延を減らしたい",
        "l3": "AgentがLLMへ渡す情報を必要最小限かつ適切な状態に管理したい",
        "l3_ok": True,
        "derived": [
            ("Duplicate Guard", "Middleware", "requirement_gate heuristic overlap", "REUSE", "Gate signals overlap"),
            ("Input Normalization", "Middleware", "none in TDA", "RECORD", "Related but not built"),
            ("Cache", "Middleware", "ResearchStore partial", "RECORD", "Research Reuse is narrower cache"),
            ("Context Reuse", "Experimental", "ResearchState + ResearchRecord", "REUSE", "Phase E envelope"),
            ("Knowledge Base", "Core", "ResearchStore in-memory", "REJECT", "Dedicated DB not needed"),
        ],
    },
    {
        "match": re.compile(r"python\s*3\.\d+|環境|cuda|gpu", re.I),
        "l0": "環境条件に合うTool/ライブラリを調べたい",
        "l1": "現在の環境で利用可能なToolを選定",
        "l2": "Tool開発に適した環境・依存関係・候補を決定",
        "l3": "将来のTool開発で再利用可能な技術・環境調査資産を蓄積",
        "l3_ok": True,
        "derived": [
            ("Research Record", "Experimental", "research_record.py", "REUSE", "Phase E envelope"),
            ("Research Reuse", "Experimental", "research_reuse.py", "REUSE", "Partial reuse flow"),
            ("Environment Profiler", "Experimental", "decision_factors + UserConstraints", "REUSE", "Phase D"),
            ("Version Matrix Core", "Core", "VersionFact", "REJECT", "Dedicated matrix unnecessary"),
        ],
    },
    {
        "match": re.compile(r"urscript|universal robot|polyscope", re.I),
        "l0": "専門ロボット言語/APIのToolを調査",
        "l1": "公式仕様に基づくTool設計材料を得る",
        "l2": "LLM一般知識との混同を避けつつ仕様決定",
        "l3": "専門領域の調査結果を将来の同領域Tool開発に再利用",
        "l3_ok": True,
        "derived": [
            ("API Existence Observation", "Experimental", "api_observation.py", "REUSE", "Phase D"),
            ("Research Reuse", "Experimental", "research_reuse.py", "REUSE", "Same-domain reuse"),
            ("Mechanical API Validator", "Core", "none", "REJECT", "Mechanical Answer prohibited"),
        ],
    },
    {
        "match": re.compile(r"polars|pdf|toolx|dataframe|dataframeLib|調べ", re.I),
        "l0": "技術候補をWebから調査したい",
        "l1": "Tool開発のための候補・仕様材料を集める",
        "l2": "調査結果を将来のTool開発意思決定に再利用可能な資産として保持",
        "l3": "Agentの調査資産を横断的に再利用し再検索を減らす",
        "l3_ok": True,
        "derived": [
            ("Research Reuse Search", "Experimental", "assess_reuse()", "REUSE", "Phase E primary"),
            ("Knowledge Base", "Core", "ResearchStore in-memory", "REJECT", "Database Core deferred"),
            ("Vector DB / RAG", "Core", "token matching", "REJECT", "Embedding not measured needed"),
        ],
    },
    {
        "match": re.compile(r"json.*読|csv.*読|テキスト", re.I),
        "l0": "一般的なファイル処理Toolを作りたい",
        "l1": "既知パターンでToolを設計",
        "l2": "過剰なWeb Researchを避ける",
        "l3": "",
        "l3_ok": False,
        "derived": [
            ("Requirement Gate", "Experimental", "requirement_gate.py", "REUSE", "RESEARCH_NOT_REQUIRED"),
            ("Research Reuse", "Experimental", "assess_reuse no match", "REUSE", "Correctly skips"),
        ],
    },
]


def abstract_goals(requirement: str) -> GoalHierarchy:
    """Level 0–2 standard; Level 3 only when system benefit clear."""
    for p in _PATTERNS:
        if p["match"].search(requirement):
            return GoalHierarchy(
                request=requirement,
                level_0=p["l0"],
                level_1=p["l1"],
                level_2=p["l2"],
                level_3=p["l3"] if p.get("l3_ok") else "",
                level_3_justified=bool(p.get("l3_ok")),
            )
    return GoalHierarchy(
        request=requirement,
        level_0=requirement[:80],
        level_1="Tool開発要求を満たす",
        level_2="調査・選定・仕様決定を支援",
    )


def discover_capabilities(requirement: str) -> HierarchicalDiscovery:
    """Derive capabilities from goal hierarchy — evaluate, do not implement."""
    goals = abstract_goals(requirement)
    derived: list[DerivedCapability] = []
    rejected: list[str] = []
    future: list[str] = []

    matched_pattern = None
    for p in _PATTERNS:
        if p["match"].search(requirement):
            matched_pattern = p
            break

    if matched_pattern:
        for name, cls, alt, decision, reason in matched_pattern.get("derived", []):
            dc = DerivedCapability(
                name=name,
                description=f"Derived from L2: {goals.level_2}",
                capability_class=cls,  # type: ignore[arg-type]
                existing_alternative=alt,
                decision=decision,  # type: ignore[arg-type]
                reason=reason,
            )
            derived.append(dc)
            if decision == "REJECT":
                rejected.append(f"{name}: {reason}")
            elif decision == "RECORD":
                future.append(name)

    # Always surface Research Reuse if Level 3 justified and not already listed
    if goals.level_3_justified and not any(d.name == "Research Reuse" for d in derived):
        derived.append(
            DerivedCapability(
                name="Research Reuse",
                description=goals.level_3,
                capability_class="Experimental",
                existing_alternative="research_reuse.py",
                decision="REUSE",
                reason="Level 3 goal surfaces cross-session research asset reuse",
            )
        )

    return HierarchicalDiscovery(goals=goals, derived_capabilities=derived, rejected_ideas=rejected, future_ideas=future)
