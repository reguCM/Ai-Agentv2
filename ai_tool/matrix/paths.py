"""Matrix ファイル配置。Session JSON とは別。"""
from __future__ import annotations

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def matrix_dir() -> Path:
    override = str(os.environ.get("AI_AGENT_MATRIX_DIR") or "").strip()
    if override:
        return Path(override)
    return _REPO / "runs" / "matrix"


def records_path() -> Path:
    return matrix_dir() / "records.jsonl"


def last_ingest_path() -> Path:
    return matrix_dir() / "last_ingest.json"


def last_verify_path() -> Path:
    return matrix_dir() / "last_verify.json"


def verify_log_path() -> Path:
    return matrix_dir() / "verify.jsonl"


def last_trace_path() -> Path:
    return matrix_dir() / "last_trace.json"


def retractions_path() -> Path:
    return matrix_dir() / "retractions.jsonl"


def last_ask_path() -> Path:
    return matrix_dir() / "last_ask.json"
