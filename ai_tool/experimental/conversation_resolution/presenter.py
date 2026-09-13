"""User-facing presentation layer (experimental — not Production stdout)."""
from __future__ import annotations

from ai_tool.experimental.conversation_resolution.models import (
    Candidate,
    ConversationState,
    PresentationMode,
    UserFacingPresentation,
)


def format_citation(c: Candidate) -> dict[str, str]:
    return {
        "candidate_id": c.candidate_id,
        "source_title": c.source_title,
        "url": c.url,
        "label": c.label,
    }


def build_presentation(
    state: ConversationState,
    *,
    llm_body: str,
    difference_note: str = "",
) -> UserFacingPresentation:
    mode = state.presentation_mode
    citations: list[dict[str, str]] = []
    candidates_shown: list[str] = []
    source_links: list[dict[str, str]] = []
    body = llm_body.strip()

    if mode == "SINGLE":
        if state.candidates:
            c = state.candidates[0]
            citations.append(format_citation(c))
            source_links.append({"title": c.source_title, "url": c.url, "candidate_id": c.candidate_id})
        headline = "回答"
    elif mode == "MERGED":
        for c in state.candidates[:2]:
            citations.append(format_citation(c))
            source_links.append({"title": c.source_title, "url": c.url, "candidate_id": c.candidate_id})
        headline = "回答（複数ソースを統合）"
        if difference_note and difference_note not in body:
            body = f"{body}\n\n（補足）{difference_note}"
    elif mode in ("MULTI", "UNRESOLVED"):
        headline = "この点については情報源によって差があります"
        blocks: list[str] = []
        if difference_note:
            blocks.append(difference_note)
        for c in state.candidates:
            candidates_shown.append(c.candidate_id)
            citations.append(format_citation(c))
            source_links.append({"title": c.source_title, "url": c.url, "candidate_id": c.candidate_id})
            blocks.append(f"{c.label}:\n  {c.claim}\n  出典: {c.source_title} ({c.url})")
        body = "\n\n".join(blocks) if not llm_body else f"{llm_body}\n\n" + "\n\n".join(blocks)
    else:
        headline = "回答"

    return UserFacingPresentation(
        headline=headline,
        body=body,
        mode=mode,
        candidates_shown=candidates_shown,
        citations=citations,
        difference_note=difference_note,
        source_links=source_links,
    )


def format_source_navigation(candidate: Candidate) -> str:
    return (
        f"候補 {candidate.label} の出典:\n"
        f"  タイトル: {candidate.source_title}\n"
        f"  URL: {candidate.url}\n"
        f"  根拠抜粋: {candidate.claim[:300]}"
    )
