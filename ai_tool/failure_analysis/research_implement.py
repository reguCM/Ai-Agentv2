"""Read-only Failure Record extractor for research implement results."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.failure_analysis.models import (
    FAILURE_RECORD_SCHEMA_VERSION,
    validate_failure_record,
)


DEFAULT_RESULTS_URI = "research/llm_benchmarks/research_implement_results.json"
EXTRACTOR_NAME = "research_implement_adapter"
EXTRACTOR_VERSION = "1"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _stable_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_record_id(run: Mapping[str, Any]) -> str:
    """Build an order-independent identifier without embedding the request."""

    explicit_id = run.get("run_id") or run.get("id")
    if isinstance(explicit_id, str) and explicit_id:
        return explicit_id
    identity = {
        "timestamp": _string_or_none(run.get("timestamp")),
        "profile": _string_or_none(run.get("profile")),
        "model": _string_or_none(run.get("model")),
        "request_sha256": hashlib.sha256(
            str(run.get("request") or "").encode("utf-8")
        ).hexdigest(),
        "fail_stage": _string_or_none(run.get("fail_stage")),
        "research_stop_reason": _string_or_none(run.get("research_stop_reason")),
        "error": _string_or_none(run.get("error")),
    }
    return f"sha256:{_stable_digest(identity)}"


def _ref(source_uri: str, record_index: int, field: str | None = None) -> dict[str, str]:
    pointer = f"/runs/{record_index}"
    if field is not None:
        pointer += f"/{field}"
    return {"uri": source_uri, "json_pointer": pointer}


def _logical_source_uri(source_path: Path, source_uri: str | None) -> str:
    """Separate the runtime path from the non-sensitive URI stored in records."""

    if source_uri is not None:
        return source_uri

    resolved = source_path.resolve()
    default_path = (_REPO_ROOT / DEFAULT_RESULTS_URI).resolve()
    if resolved == default_path:
        return DEFAULT_RESULTS_URI
    try:
        return resolved.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        path_digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()
        return f"external-source:sha256:{path_digest}"


def _to_failure_record(
    run: Mapping[str, Any],
    *,
    source_uri: str,
    record_index: int,
    extracted_at: str,
) -> dict[str, Any]:
    record_id = _source_record_id(run)
    failure_id = "fail_" + _stable_digest(
        {
            "source_type": "research_implement",
            "source_uri": source_uri,
            "record_id": record_id,
        }
    )
    record = {
        "schema_version": FAILURE_RECORD_SCHEMA_VERSION,
        "failure_id": failure_id,
        "source": {
            "type": "research_implement",
            "uri": source_uri,
            "record_id": record_id,
            "run_id": _string_or_none(run.get("run_id")),
        },
        "test_id": _string_or_none(run.get("test_id")),
        "timestamp": _string_or_none(run.get("timestamp")),
        "subject": {
            "model": _string_or_none(run.get("model")),
            "profile": _string_or_none(run.get("profile")),
            "component": None,
            "tool": None,
        },
        "outcome": {
            "ok": False,
            "failure_stage": _string_or_none(run.get("fail_stage")),
            "failure_type": "UNKNOWN",
            "stop_reason": _string_or_none(run.get("research_stop_reason")),
            "error": _string_or_none(run.get("error")),
        },
        "input_ref": (
            _ref(source_uri, record_index, "request") if "request" in run else None
        ),
        "output_ref": _ref(source_uri, record_index),
        "evidence": [
            _ref(source_uri, record_index, field)
            for field in ("ok", "fail_stage", "research_stop_reason", "error")
            if field in run
        ],
        "raw_refs": [_ref(source_uri, record_index)],
        "extracted_at": extracted_at,
        "extractor": {"name": EXTRACTOR_NAME, "version": EXTRACTOR_VERSION},
    }
    validate_failure_record(record)
    return record


def extract_research_implement_failures(
    results: Mapping[str, Any],
    *,
    source_uri: str = DEFAULT_RESULTS_URI,
    extracted_at: str | None = None,
) -> list[dict[str, Any]]:
    """Return Failure Records for runs whose ``ok`` value is exactly false."""

    runs = results.get("runs")
    if not isinstance(runs, list):
        raise ValueError("research implement results must contain a runs list")
    timestamp = extracted_at or datetime.now(timezone.utc).isoformat()
    failures: list[dict[str, Any]] = []
    for index, run in enumerate(runs):
        if not isinstance(run, Mapping) or run.get("ok") is not False:
            continue
        failures.append(
            _to_failure_record(
                run,
                source_uri=source_uri,
                record_index=index,
                extracted_at=timestamp,
            )
        )
    return failures


def load_research_implement_failures(
    path: str | Path,
    *,
    source_uri: str | None = None,
    extracted_at: str | None = None,
) -> list[dict[str, Any]]:
    """Read a canonical results file without modifying it and extract failures."""

    source_path = Path(path)
    with source_path.open("r", encoding="utf-8") as stream:
        results = json.load(stream)
    if not isinstance(results, Mapping):
        raise ValueError("research implement results must be a JSON object")
    return extract_research_implement_failures(
        results,
        source_uri=_logical_source_uri(source_path, source_uri),
        extracted_at=extracted_at,
    )
