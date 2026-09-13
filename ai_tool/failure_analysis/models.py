"""Failure Record v1 validation.

The schema is intentionally small in Phase 1. Source-specific payloads stay in
their canonical result files and are referenced rather than copied here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


FAILURE_RECORD_SCHEMA_VERSION = "failure-record/v1"


class FailureRecordValidationError(ValueError):
    """Raised when an extracted record does not satisfy Failure Record v1."""


def validate_failure_record(record: Mapping[str, Any]) -> None:
    """Validate the required Phase 1 invariants for a Failure Record v1."""

    if not isinstance(record, Mapping):
        raise FailureRecordValidationError("failure record must be an object")
    if record.get("schema_version") != FAILURE_RECORD_SCHEMA_VERSION:
        raise FailureRecordValidationError(
            f"schema_version must be {FAILURE_RECORD_SCHEMA_VERSION!r}"
        )
    if not isinstance(record.get("failure_id"), str) or not record["failure_id"]:
        raise FailureRecordValidationError("failure_id must be a non-empty string")

    source = record.get("source")
    if not isinstance(source, Mapping):
        raise FailureRecordValidationError("source must be an object")
    if not isinstance(source.get("type"), str) or not source["type"]:
        raise FailureRecordValidationError("source.type must be a non-empty string")

    outcome = record.get("outcome")
    if not isinstance(outcome, Mapping):
        raise FailureRecordValidationError("outcome must be an object")
    if outcome.get("ok") is not False:
        raise FailureRecordValidationError("outcome.ok must be false")

    extractor = record.get("extractor")
    if not isinstance(extractor, Mapping):
        raise FailureRecordValidationError("extractor must be an object")
    for field in ("name", "version"):
        if not isinstance(extractor.get(field), str) or not extractor[field]:
            raise FailureRecordValidationError(
                f"extractor.{field} must be a non-empty string"
            )
