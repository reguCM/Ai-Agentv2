"""仕様候補の保存先。Session JSON や Matrix とは別。"""
from __future__ import annotations

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def spec_proposal_dir() -> Path:
    override = str(os.environ.get("AI_AGENT_SPEC_PROPOSAL_DIR") or "").strip()
    if override:
        return Path(override)
    return _REPO / "runs" / "spec_proposals"


def proposals_path() -> Path:
    return spec_proposal_dir() / "proposals.jsonl"


def last_proposal_path() -> Path:
    return spec_proposal_dir() / "last_proposal.json"
