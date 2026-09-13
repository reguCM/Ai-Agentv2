"""経路追跡。records.jsonl を変更せず、無い証拠から原因を作らない。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ai_tool.matrix.models import MatrixRecord
from ai_tool.matrix.store import MatrixStore
from ai_tool.matrix.trace import CAUSE_ALIGNED, CAUSE_MISMATCH, CAUSE_UNKNOWN, trace_matrix_record
from ai_tool.matrix.verify import records_bytes


def _rec(**kwargs) -> MatrixRecord:
    base = dict(
        record_id="mr-x",
        entity="RTX 3060",
        attribute="VRAM capacity",
        value="12 GB",
        source_url="https://en.wikipedia.org/wiki/RTX_3060",
        source_title="RTX 3060",
        observed_at=datetime.now(timezone.utc).isoformat(),
        provenance="web_search → fetch → extract → matrix_write",
        ingest_id="ing-test",
        query="RTX 3060",
        excerpt="RTX 3060 The GeForce RTX 30 series",
    )
    base.update(kwargs)
    return MatrixRecord(**base)


def _seed_bad_ingest(store: MatrixStore) -> None:
    ingest = "ing-bad"
    store.append(_rec(record_id="mr-cite-3060", attribute="cited_by", value="RTX 3060", excerpt=None, ingest_id=ingest))
    store.append(
        _rec(
            record_id="mr-cite-5000",
            attribute="cited_by",
            value="RTX 5000",
            source_url="https://en.wikipedia.org/wiki/RTX_5000",
            source_title="RTX 5000",
            excerpt=None,
            ingest_id=ingest,
        )
    )
    store.append(
        _rec(
            record_id="mr-16",
            value="16 GB",
            source_url="https://en.wikipedia.org/wiki/RTX_5000",
            source_title="RTX 5000",
            excerpt="RTX 5000 The GeForce RTX 50 series of consumer graphics cards",
            ingest_id=ingest,
        )
    )
    store.append(
        _rec(
            record_id="mr-20",
            value="20 GB",
            source_url="https://en.wikipedia.org/wiki/RTX_4000",
            source_title="RTX 4000",
            excerpt="RTX 4000 The GeForce RTX 40 series is a family",
            ingest_id=ingest,
        )
    )
    store.append(
        _rec(
            record_id="mr-10",
            value="10 GB",
            excerpt="RTX 3060 The GeForce RTX 30 series is a suite of graphics processing units",
            ingest_id=ingest,
        )
    )


def _seed_aligned(store: MatrixStore, log_dir: Path) -> None:
    store.append(_rec(record_id="mr-8", value="8 GB", excerpt="RTX 3060 {{short description"))
    store.append(_rec(record_id="mr-12", value="12 GB", excerpt="RTX 3060 {{short description"))
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "verify.jsonl").write_text(
        '{"record_id":"mr-8","result":"MATCH"}\n{"record_id":"mr-12","result":"MATCH"}\n',
        encoding="utf-8",
    )


def test_a_trace_does_not_mutate_records(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    _seed_bad_ingest(store)
    before = records_bytes(store)
    trace_matrix_record("mr-16", store=store, requested_by="cursor")
    trace_matrix_record("mr-10", store=store, requested_by="cursor")
    assert records_bytes(store) == before


def test_b_aligned_8_12_keep_match_fact(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    _seed_aligned(store, tmp_path)
    eight = trace_matrix_record("mr-8", store=store, requested_by="cursor")
    twelve = trace_matrix_record("mr-12", store=store, requested_by="cursor")
    assert eight["cause"] == CAUSE_ALIGNED
    assert twelve["cause"] == CAUSE_ALIGNED
    assert eight["last_verify"] == "MATCH"
    assert twelve["last_verify"] == "MATCH"
    assert {r["value"] for r in store.all_records()} >= {"8 GB", "12 GB"}


def test_c_keeps_10_16_20(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    _seed_bad_ingest(store)
    trace_matrix_record("mr-16", store=store)
    values = {r["value"] for r in store.all_records() if r["attribute"] == "VRAM capacity"}
    assert values == {"10 GB", "16 GB", "20 GB"}


def test_d_16_and_20_entity_mismatch_path(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    _seed_bad_ingest(store)
    sixteen = trace_matrix_record("mr-16", store=store, requested_by="cursor")
    twenty = trace_matrix_record("mr-20", store=store, requested_by="cursor")
    assert sixteen["cause"] == CAUSE_MISMATCH
    assert sixteen["source_title_entity"] == "RTX 5000"
    assert sixteen["entity_from_query"] == "RTX 3060"
    assert sixteen["actual_source_target"] == "RTX 5000"
    assert twenty["cause"] == CAUSE_MISMATCH
    assert twenty["source_title_entity"] == "RTX 4000"
    types = [e["type"] for e in sixteen["events"]]
    assert types[:6] == ["matrix_record", "search", "fetch", "extract", "normalize", "matrix_write"]
    normalize = next(e for e in sixteen["events"] if e["type"] == "normalize")
    assert normalize["status"] == "NOT OBSERVED"
    search = next(e for e in sixteen["events"] if e["type"] == "search")
    assert "RTX 5000" in search["titles"]
    assert "snippets" in search["omitted"]
    extract = next(e for e in sixteen["events"] if e["type"] == "extract")
    assert extract["entity_source_mismatch"] is True


def test_e_10gb_not_determined(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    _seed_bad_ingest(store)
    ten = trace_matrix_record("mr-10", store=store, requested_by="cursor")
    assert ten["cause"] == CAUSE_UNKNOWN
    assert ten["source_title_entity"] == "RTX 3060"
    assert ten["entity_source_mismatch"] is False
    assert ten["excerpt_contains_value"] is False


def test_f_does_not_invent_search_backends(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_rec(record_id="mr-lonely", ingest_id="ing-only-me"))
    out = trace_matrix_record("mr-lonely", store=store)
    search = next(e for e in out["events"] if e["type"] == "search")
    assert "backends_tried" not in search
    assert search.get("omitted")


def test_g_events_for_processing_tab(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    _seed_bad_ingest(store)
    out = trace_matrix_record("mr-16", store=store)
    types = [e["type"] for e in out["events"]]
    assert "matrix_record" in types
    assert "search" in types
    assert "fetch" in types
    assert "extract" in types
    assert "normalize" in types
    assert "matrix_write" in types
    assert "verify_result" in types
    assert out["llm_used"] is False
    assert "research" not in types
