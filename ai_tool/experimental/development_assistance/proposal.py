"""Development Proposal generation (experimental PoC)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from ai_tool.experimental.development_assistance.requirement_gate import GateResult
from ai_tool.experimental.development_assistance.technology_candidate import TechnologyCandidate

ChatFn = Callable[..., Any]


def proposal_system_prompt() -> str:
    return """
あなたはTool開発補助アシスタントです（評価PoC）。

ルール:
- Web EvidenceとLLM知識を組み合わせ、Tool開発案を会話として提示する。
- Web情報を唯一の正解と決めない。不明点はUNKNOWNとして述べる。
- 候補間の差異・競合を潰さない。
- 総合点や機械的ランキングを作らない。
- 最終判断はユーザーに委ねる。
- EvidenceにないURL・バージョン・ライセンスを捏造しない。
- Custom Buildは設計選択肢として扱う。
""".strip()


@dataclass
class DevelopmentProposal:
    requirement: str
    research_performed: bool
    gate: dict[str, Any]
    queries: list[str]
    candidates: list[dict[str, Any]]
    environment: dict[str, Any]
    known: list[str]
    unknown: list[str]
    conflicts: list[dict[str, Any]]
    possible_approaches: list[str]
    recommendation: str
    open_questions: list[str]
    llm_body: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _collect_environment(candidates: list[TechnologyCandidate]) -> dict[str, Any]:
    merged: dict[str, set[str]] = {}
    for c in candidates:
        for k, v in c.environment.items():
            merged.setdefault(k, set()).add(v)
    return {k: sorted(v) if len(v) > 1 else next(iter(v)) for k, v in merged.items()}


def _collect_unknowns(candidates: list[TechnologyCandidate]) -> list[str]:
    out: set[str] = set()
    for c in candidates:
        out.update(c.unknowns)
    return sorted(out)


def proxy_proposal(
    requirement: str,
    gate: GateResult,
    candidates: list[TechnologyCandidate],
    envelope: dict[str, Any],
    *,
    queries: list[str] | None = None,
) -> DevelopmentProposal:
    """Deterministic proposal for offline CI."""
    web_cands = [c for c in candidates if c.type != "Custom Build"]
    custom = next((c for c in candidates if c.type == "Custom Build"), None)

    known: list[str] = []
    for c in web_cands:
        known.append(f"{c.name} ({c.type}): {c.description[:80]}")
        if c.version != "UNKNOWN":
            known.append(f"  version: {c.version}")
        if c.license != "UNKNOWN":
            known.append(f"  license: {c.license}")

    approaches: list[str] = []
    for c in web_cands[:3]:
        approaches.append(f"Use {c.name} ({c.type}) — source: {c.source_title or c.url or 'UNKNOWN'}")
    if custom:
        approaches.append("Custom Build — full control, higher cost")

    rec = "複数候補があります。用途と制約に応じてユーザーが選択してください。"
    if len(web_cands) == 1 and not custom:
        rec = f"{web_cands[0].name} を第一候補として検討可能。ただし不明点は追加確認が必要。"
    elif custom and len(web_cands) >= 1:
        rec = f"{web_cands[0].name} 等の既存利用と Custom Build の比較を推奨。"

    open_q: list[str] = []
    if envelope.get("conflicts"):
        open_q.append("Source間のバージョン/環境差異の確認")
    open_q.extend(_collect_unknowns(candidates))

    body_parts = [
        f"要求: {requirement}",
        f"Research: {'実施' if gate.decision == 'RESEARCH_REQUIRED' else '不要'}",
    ]
    for c in candidates:
        body_parts.append(f"候補 {c.candidate_id}: {c.name} ({c.type})")
    if envelope.get("difference_note"):
        body_parts.append(str(envelope["difference_note"]))

    return DevelopmentProposal(
        requirement=requirement,
        research_performed=gate.decision == "RESEARCH_REQUIRED",
        gate=gate.to_dict(),
        queries=queries or [],
        candidates=[c.to_dict() for c in candidates],
        environment=_collect_environment(candidates),
        known=known,
        unknown=_collect_unknowns(candidates),
        conflicts=envelope.get("conflicts") or [],
        possible_approaches=approaches,
        recommendation=rec,
        open_questions=open_q,
        llm_body="\n".join(body_parts),
    )


def build_development_proposal(
    requirement: str,
    gate: GateResult,
    candidates: list[TechnologyCandidate],
    envelope: dict[str, Any],
    *,
    queries: list[str] | None = None,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> DevelopmentProposal:
    if not llm_enabled or chat_fn is None:
        return proxy_proposal(requirement, gate, candidates, envelope, queries=queries)

    import time

    ctx = {
        "gate": gate.to_dict(),
        "queries": queries,
        "envelope": {
            k: envelope.get(k)
            for k in ("relation", "presentation_mode", "difference_note", "conflicts", "technology_candidates")
        },
    }
    messages = [
        {"role": "system", "content": proposal_system_prompt()},
        {
            "role": "user",
            "content": (
                f"REQUIREMENT: {requirement}\n"
                f"PROPOSAL_CONTEXT:\n{ctx}\n\n"
                "Development Proposal を構造化して会話的に提示してください。"
                "Recommendationは提案であり確定ではありません。"
            ),
        },
    ]
    started = time.perf_counter()
    resp = chat_fn(messages=messages, model=model)
    latency = round((time.perf_counter() - started) * 1000, 1)
    text = getattr(getattr(resp, "message", None), "content", None) or ""

    base = proxy_proposal(requirement, gate, candidates, envelope, queries=queries)
    base.llm_body = text.strip()
    return base


def proposal_to_dict(proposal: DevelopmentProposal) -> dict[str, Any]:
    return proposal.to_dict()
