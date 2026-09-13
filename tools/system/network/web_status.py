"""Machine-readable Web pipeline status (independent of LLM natural language).

Derives structured status from search_web / read_url_text tool results.
Does NOT infer status from LLM self-reports.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SearchLayerCode = Literal["SUCCESS", "EMPTY", "ERROR", "BLOCKED", "NOT_RUN"]
FetchLayerCode = Literal["SUCCESS", "FAILED", "NOT_RUN"]
ExtractionLayerCode = Literal["READY", "INSUFFICIENT", "FAILED", "NOT_RUN"]
EvidenceLayerCode = Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_RUN"]

OverallWebStatus = Literal[
    "SUCCESS",
    "PARTIAL",
    "NO_EVIDENCE",
    "SEARCH_FAILED",
    "FETCH_FAILED",
    "EXTRACTION_FAILED",
    "NOT_APPLICABLE",
    "UNKNOWN",
]

FailureCause = Literal[
    "search_empty",
    "search_error",
    "search_blocked",
    "fetch_failed",
    "extraction_failed",
    "no_evidence",
    "partial_mixed",
    "none",
]


@dataclass
class LayerStatus:
    search: SearchLayerCode = "NOT_RUN"
    fetch: FetchLayerCode = "NOT_RUN"
    extraction: ExtractionLayerCode = "NOT_RUN"
    evidence: EvidenceLayerCode = "NOT_RUN"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class WebStatusSnapshot:
    """Structured status for one tool invocation."""

    tool: str
    layers: LayerStatus
    overall: OverallWebStatus
    failure_cause: FailureCause
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "layers": self.layers.to_dict(),
            "overall": self.overall,
            "failure_cause": self.failure_cause,
            "details": self.details,
        }


def _quality(result: dict[str, Any]) -> dict[str, Any]:
    q = result.get("quality")
    return q if isinstance(q, dict) else {}


def derive_search_status(result: dict[str, Any]) -> WebStatusSnapshot:
    """Classify search_web result."""
    layers = LayerStatus()
    details: dict[str, Any] = {
        "hit_count": 0,
        "error": result.get("error"),
        "backends_tried": result.get("backends_tried"),
    }
    if result.get("blocked_by_agent_tool_gate"):
        layers.search = "BLOCKED"
        return WebStatusSnapshot(
            tool="search_web",
            layers=layers,
            overall="SEARCH_FAILED",
            failure_cause="search_blocked",
            details=details,
        )
    hits = result.get("hits")
    hit_list = hits if isinstance(hits, list) else []
    details["hit_count"] = len(hit_list)
    if result.get("error") and not hit_list:
        layers.search = "ERROR"
        return WebStatusSnapshot(
            tool="search_web",
            layers=layers,
            overall="SEARCH_FAILED",
            failure_cause="search_error",
            details=details,
        )
    if not hit_list:
        layers.search = "EMPTY"
        return WebStatusSnapshot(
            tool="search_web",
            layers=layers,
            overall="SEARCH_FAILED",
            failure_cause="search_empty",
            details=details,
        )
    layers.search = "SUCCESS"
    return WebStatusSnapshot(
        tool="search_web",
        layers=layers,
        overall="PARTIAL",
        failure_cause="none",
        details=details,
    )


def derive_fetch_status(result: dict[str, Any]) -> WebStatusSnapshot:
    """Classify read_url_text result."""
    layers = LayerStatus()
    quality = _quality(result)
    warnings = list(quality.get("warnings") or [])
    main_text = str(result.get("main_text") or "")
    details: dict[str, Any] = {
        "url": result.get("url"),
        "ok": result.get("ok"),
        "fact_ready": quality.get("fact_ready"),
        "main_text_len": len(main_text),
        "warnings": warnings,
        "error": result.get("error"),
    }

    if result.get("ok") is False:
        layers.fetch = "FAILED"
        return WebStatusSnapshot(
            tool="read_url_text",
            layers=layers,
            overall="FETCH_FAILED",
            failure_cause="fetch_failed",
            details=details,
        )

    layers.fetch = "SUCCESS"
    extraction_ok = bool(quality.get("extraction_success"))
    fact_ready = bool(quality.get("fact_ready"))
    body_reached = bool(quality.get("body_reached"))

    if not extraction_ok or len(main_text.strip()) < 10:
        layers.extraction = "FAILED"
        return WebStatusSnapshot(
            tool="read_url_text",
            layers=layers,
            overall="EXTRACTION_FAILED",
            failure_cause="extraction_failed",
            details=details,
        )

    boilerplate = "main_text_looks_like_boilerplate_or_metadata" in warnings
    truncated_before_body = "raw_fetch_truncated_before_main_content" in warnings
    body_uncertain = "main_text_present_but_body_region_uncertain" in warnings

    if fact_ready:
        layers.extraction = "READY"
        layers.evidence = "AVAILABLE"
        return WebStatusSnapshot(
            tool="read_url_text",
            layers=layers,
            overall="SUCCESS",
            failure_cause="none",
            details=details,
        )

    if boilerplate or truncated_before_body or (not body_reached and body_uncertain):
        layers.extraction = "FAILED"
        return WebStatusSnapshot(
            tool="read_url_text",
            layers=layers,
            overall="EXTRACTION_FAILED",
            failure_cause="extraction_failed",
            details=details,
        )

    layers.extraction = "INSUFFICIENT"
    layers.evidence = "UNAVAILABLE"
    return WebStatusSnapshot(
        tool="read_url_text",
        layers=layers,
        overall="NO_EVIDENCE",
        failure_cause="no_evidence",
        details=details,
    )


def derive_web_status(tool_name: str, result: dict[str, Any]) -> WebStatusSnapshot:
    if tool_name == "search_web":
        return derive_search_status(result)
    if tool_name == "read_url_text":
        return derive_fetch_status(result)
    return WebStatusSnapshot(
        tool=tool_name,
        layers=LayerStatus(),
        overall="NOT_APPLICABLE",
        failure_cause="none",
    )


@dataclass
class WebSessionTracker:
    """Accumulates web tool attempts across an agent session."""

    snapshots: list[WebStatusSnapshot] = field(default_factory=list)

    def record(self, tool_name: str, result: Any) -> WebStatusSnapshot | None:
        if tool_name not in ("search_web", "read_url_text"):
            return None
        if not isinstance(result, dict):
            return None
        snap = derive_web_status(tool_name, result)
        self.snapshots.append(snap)
        return snap

    def web_tools_used(self) -> bool:
        return bool(self.snapshots)

    def aggregate(self) -> dict[str, Any]:
        if not self.snapshots:
            return {
                "overall": "NOT_APPLICABLE",
                "failure_cause": "none",
                "layers": LayerStatus().to_dict(),
                "search_attempts": 0,
                "fetch_attempts": 0,
                "fetch_success_count": 0,
                "fetch_fact_ready_count": 0,
                "snapshots": [],
            }

        search_snaps = [s for s in self.snapshots if s.tool == "search_web"]
        fetch_snaps = [s for s in self.snapshots if s.tool == "read_url_text"]

        fetch_success = sum(1 for s in fetch_snaps if s.layers.fetch == "SUCCESS")
        fetch_ready = sum(1 for s in fetch_snaps if s.overall == "SUCCESS")
        fetch_failed = sum(1 for s in fetch_snaps if s.overall == "FETCH_FAILED")
        extraction_failed = sum(1 for s in fetch_snaps if s.overall == "EXTRACTION_FAILED")
        no_evidence = sum(1 for s in fetch_snaps if s.overall == "NO_EVIDENCE")

        search_empty = any(s.failure_cause == "search_empty" for s in search_snaps)
        search_error = any(s.failure_cause == "search_error" for s in search_snaps)
        search_blocked = any(s.failure_cause == "search_blocked" for s in search_snaps)
        search_success = any(s.layers.search == "SUCCESS" for s in search_snaps)

        overall: OverallWebStatus
        failure_cause: FailureCause = "none"

        if fetch_ready >= 1:
            if fetch_ready < len(fetch_snaps) or (search_snaps and fetch_failed):
                overall = "PARTIAL"
                failure_cause = "partial_mixed"
            else:
                overall = "SUCCESS"
        elif fetch_snaps:
            if fetch_failed == len(fetch_snaps):
                overall = "FETCH_FAILED"
                failure_cause = "fetch_failed"
            elif extraction_failed >= 1 and no_evidence == 0:
                overall = "EXTRACTION_FAILED"
                failure_cause = "extraction_failed"
            elif no_evidence >= 1:
                overall = "NO_EVIDENCE"
                failure_cause = "no_evidence"
            elif extraction_failed >= 1:
                overall = "EXTRACTION_FAILED"
                failure_cause = "extraction_failed"
            else:
                overall = "NO_EVIDENCE"
                failure_cause = "no_evidence"
        elif search_snaps:
            if search_blocked:
                overall = "SEARCH_FAILED"
                failure_cause = "search_blocked"
            elif search_empty or search_error:
                overall = "SEARCH_FAILED"
                failure_cause = "search_empty" if search_empty else "search_error"
            elif search_success:
                overall = "SEARCH_FAILED"
                failure_cause = "fetch_failed"
            else:
                overall = "SEARCH_FAILED"
                failure_cause = "search_error"
        else:
            overall = "UNKNOWN"

        layers = LayerStatus()
        if search_snaps:
            layers.search = search_snaps[-1].layers.search
        if fetch_snaps:
            last_fetch = fetch_snaps[-1]
            layers.fetch = last_fetch.layers.fetch
            layers.extraction = last_fetch.layers.extraction
            layers.evidence = last_fetch.layers.evidence

        return {
            "overall": overall,
            "failure_cause": failure_cause,
            "layers": layers.to_dict(),
            "search_attempts": len(search_snaps),
            "fetch_attempts": len(fetch_snaps),
            "fetch_success_count": fetch_success,
            "fetch_fact_ready_count": fetch_ready,
            "snapshots": [s.to_dict() for s in self.snapshots],
        }


def observation_fields_from_session(session: WebSessionTracker) -> dict[str, Any]:
    """Fields compatible with Failure Diagnosis ObservationBundle extension."""
    agg = session.aggregate()
    last_search = next((s for s in reversed(session.snapshots) if s.tool == "search_web"), None)
    last_fetch = next((s for s in reversed(session.snapshots) if s.tool == "read_url_text"), None)
    return {
        "web_status_overall": agg.get("overall"),
        "web_status_failure_cause": agg.get("failure_cause"),
        "web_status_layers": agg.get("layers"),
        "search_hit_count": (last_search.details.get("hit_count") if last_search else None),
        "fetch_fact_ready": (
            last_fetch.details.get("fact_ready") if last_fetch else None
        ),
        "fetch_ok": (last_fetch.details.get("ok") if last_fetch else None),
        "fetch_warnings": (
            list(last_fetch.details.get("warnings") or []) if last_fetch else []
        ),
    }


def observation_from_web_session(session: "WebSessionTracker", *, execution_id: str = "web_session") -> dict[str, Any]:
    """Build ObservationBundle-compatible fields from WebSessionTracker (Failure Diagnosis bridge)."""
    fields = observation_fields_from_session(session)
    agg = session.aggregate()
    tool_calls: dict[str, int] = {}
    for snap in session.snapshots:
        tool_calls[snap.tool] = tool_calls.get(snap.tool, 0) + 1
    return {
        "execution_id": execution_id,
        "source": "web_status_session",
        "tool_calls": tool_calls,
        "tool_selection_trace": list(tool_calls.keys()) or None,
        "search_hit_count": fields.get("search_hit_count"),
        "fetch_ok": fields.get("fetch_ok"),
        "fetch_fact_ready": fields.get("fetch_fact_ready"),
        "fetch_warnings": list(fields.get("fetch_warnings") or []),
        "grounding_metadata": {
            "web_status_overall": fields.get("web_status_overall"),
            "web_status_failure_cause": fields.get("web_status_failure_cause"),
            "web_status_layers": fields.get("web_status_layers"),
        },
        "empty_search_in_trace": agg.get("failure_cause") == "search_empty",
        "eval_harness_direct_execution": True,
    }


def user_visible_status_message(aggregate: dict[str, Any]) -> str | None:
    """System-generated Web status notice (not LLM-authored)."""
    overall = aggregate.get("overall")
    if overall in (None, "NOT_APPLICABLE", "SUCCESS"):
        return None
    labels = {
        "PARTIAL": "Web検索結果：一部のみ取得（根拠は限定的です）",
        "NO_EVIDENCE": "Web検索結果：ページは取得しましたが、質問に必要な根拠が見つかりませんでした",
        "SEARCH_FAILED": "Web検索結果：検索結果を取得できませんでした",
        "FETCH_FAILED": "Web検索結果：ページの取得に失敗しました",
        "EXTRACTION_FAILED": "Web検索結果：ページは取得しましたが、本文の抽出に失敗しました",
        "UNKNOWN": "Web検索結果：状態を確定できませんでした",
    }
    return labels.get(str(overall), labels["UNKNOWN"])
