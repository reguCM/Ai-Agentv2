"""開発 Policy のファイル配置。"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def policy_json_path() -> Path:
    return Path(__file__).resolve().parent / "development_policy.json"


def git_governance_json_path() -> Path:
    return Path(__file__).resolve().parent / "git_governance.json"


def git_governance_schema_path() -> Path:
    return Path(__file__).resolve().parent / "git_governance.schema.json"


def last_eval_path() -> Path:
    return _REPO / "runs" / "ai_tool" / "last_policy_eval.json"


def concept_definitions_path() -> Path:
    return _REPO / "docs" / "concepts" / "CONCEPT_DEFINITIONS.md"
