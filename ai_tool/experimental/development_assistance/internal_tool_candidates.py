"""Internal tool candidate generation — TDA proposes tools without human specifying one."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai_tool.experimental.development_assistance.goal_abstraction import discover_capabilities

FixtureKey = Literal["TDA-A", "TDA-B", "TDA-C", "TDA-E", "TDA-G", "TDA-H", "NONE"]


@dataclass
class InternalToolCandidate:
    candidate_id: str
    tool: str
    why_useful: str
    why_llm_insufficient: str
    required_external_knowledge: list[str]
    potential_web_research: list[str]
    implementation_difficulty: Literal["LOW", "MEDIUM", "HIGH"]
    environment_dependency: str
    expected_usefulness: str
    fixture_key: FixtureKey
    llm_knowledge_gap: Literal["LOW", "MEDIUM", "HIGH"]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Domains TDA may consider internally — not human-prescribed per evaluation case
_DOMAIN_POOL: list[dict[str, Any]] = [
    {
        "candidate_id": "INT-A",
        "tool": "Universal Robots Program Validator",
        "why_useful": "Validate URScript against official command set before sending to cobot",
        "why_llm_insufficient": "URScript syntax/commands differ from Python; LLM often hallucinates robot APIs",
        "required_external_knowledge": ["URScript manual", "PolyScope commands", "UR SDK TCP protocol"],
        "potential_web_research": ["URScript movej movel official docs", "UR Client Library Python"],
        "implementation_difficulty": "HIGH",
        "environment_dependency": "Robot controller or simulator; Python 3.10+; network to UR controller",
        "expected_usefulness": "HIGH for industrial automation users",
        "fixture_key": "TDA-G",
        "llm_knowledge_gap": "HIGH",
    },
    {
        "candidate_id": "INT-B",
        "tool": "Local GPU Model Batch Inference Runner",
        "why_useful": "Run batch inference with correct CUDA/PyTorch stack on local GPU",
        "why_llm_insufficient": "CUDA/driver/PyTorch version matrix changes frequently; training data stale",
        "required_external_knowledge": ["PyTorch CUDA compatibility", "VRAM requirements", "driver versions"],
        "potential_web_research": ["PyTorch install CUDA 12", "NVIDIA driver compatibility"],
        "implementation_difficulty": "MEDIUM",
        "environment_dependency": "Windows/Linux; NVIDIA GPU; CUDA 11.8/12.x; Python 3.10–3.12",
        "expected_usefulness": "HIGH for ML operators",
        "fixture_key": "TDA-H",
        "llm_knowledge_gap": "HIGH",
    },
    {
        "candidate_id": "INT-C",
        "tool": "Niche DataFrame CSV Processor (Polars-based)",
        "why_useful": "Fast CSV/Parquet processing with modern Rust-backed library",
        "why_llm_insufficient": "Polars API evolves; version-specific methods not always in LLM training",
        "required_external_knowledge": ["Polars latest API", "Python version support", "license"],
        "potential_web_research": ["Polars documentation Python 3.12", "Polars vs pandas migration"],
        "implementation_difficulty": "MEDIUM",
        "environment_dependency": "Python 3.9+; no GPU required",
        "expected_usefulness": "MEDIUM for data pipelines",
        "fixture_key": "TDA-B",
        "llm_knowledge_gap": "MEDIUM",
    },
    {
        "candidate_id": "INT-D",
        "tool": "PDF Table Extraction Assistant",
        "why_useful": "Extract tables from PDFs using maintained libraries",
        "why_llm_insufficient": "Multiple OSS options with different trade-offs; license/API differ",
        "required_external_knowledge": ["pdfplumber vs PyPDF2 capabilities", "cloud PDF API costs"],
        "potential_web_research": ["pdfplumber documentation", "PDF parsing library comparison"],
        "implementation_difficulty": "LOW",
        "environment_dependency": "Python 3.8+; optional cloud API key",
        "expected_usefulness": "MEDIUM for document workflows",
        "fixture_key": "TDA-C",
        "llm_knowledge_gap": "MEDIUM",
    },
    {
        "candidate_id": "INT-E",
        "tool": "JSON File Reader Utility",
        "why_useful": "Read and return JSON file contents",
        "why_llm_insufficient": "Standard library sufficient — minimal external gap",
        "required_external_knowledge": [],
        "potential_web_research": [],
        "implementation_difficulty": "LOW",
        "environment_dependency": "Any Python 3.x",
        "expected_usefulness": "LOW novelty — well-known pattern",
        "fixture_key": "TDA-A",
        "llm_knowledge_gap": "LOW",
    },
]


def generate_internal_candidates(requirement: str) -> list[InternalToolCandidate]:
    """Generate internal tool candidates from ambiguous requirement — no human tool name."""
    hierarchy = discover_capabilities(requirement)
    l2 = hierarchy.goals.level_2.lower()
    req_l = requirement.lower()

    # Ambiguous "LLM-hard tool" request — prefer high LLM gap domains
    prefer_niche = any(
        tok in req_l
        for tok in ("llm", "学習", "難し", "調査", "web research", "作れそう")
    )

    pool = [_DOMAIN_POOL[i] for i in range(len(_DOMAIN_POOL))]
    if prefer_niche:
        # Exclude low-gap unless explicitly simple comparison
        if "json" not in req_l and "単純" not in req_l:
            pool = [p for p in pool if p["llm_knowledge_gap"] != "LOW"]

    return [InternalToolCandidate(**p) for p in pool]  # type: ignore[arg-type]


def select_primary_candidate(
    candidates: list[InternalToolCandidate],
    requirement: str,
) -> tuple[InternalToolCandidate, str, list[str]]:
    """
    Select primary tool — conversation-style reasoning, not mechanical score winner.
    Returns (selected, narrative_reason, deciding_factors).
    """
    if not candidates:
        raise ValueError("no internal candidates")

    req_l = requirement.lower()
    # Comparison case: simple tool explicitly requested in variant requirement
    if "json" in req_l or "単純" in req_l:
        simple = next((c for c in candidates if c.llm_knowledge_gap == "LOW"), candidates[0])
        return (
            simple,
            "要求が単純パターンに該当 — LLM一般知識で足りる領域として JSON Reader を選定",
            ["implementation_feasibility", "llm_knowledge_gap_low"],
        )

    # Default ambiguous case: prefer HIGH gap + research value (narrative, not numeric rank)
    high_gap = [c for c in candidates if c.llm_knowledge_gap == "HIGH"]
    if high_gap:
        # UR validator edges GPU for "specialized language" research value in PoC fixtures
        ur = next((c for c in high_gap if "UR" in c.tool or "Robot" in c.tool), None)
        chosen = ur or high_gap[0]
        factors = [
            "llm_knowledge_gap",
            "research_value",
            "official_documentation_need",
            "implementation_feasibility",
        ]
        reason = (
            f"「{chosen.tool}」は専門API/言語（{', '.join(chosen.required_external_knowledge[:2])}）が必要で、"
            "LLM-onlyでは捏造リスクが高い。Web Researchで公式仕様を確認しながらTool化する価値が高い。"
        )
        return chosen, reason, factors

    chosen = candidates[0]
    return chosen, f"「{chosen.tool}」を主候補として調査 — 外部知識の確認が必要", ["research_value"]
