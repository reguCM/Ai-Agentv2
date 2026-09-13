"""Matrix 出典照合。実 Web / LLM は使わない。既存 JSONL を上書きしない。"""
from __future__ import annotations

from datetime import datetime, timezone

from ai_tool.matrix.models import MatrixRecord
from ai_tool.matrix.store import MatrixStore, search_records
from ai_tool.matrix.verify import records_bytes, verify_matrix_record


def _record(**kwargs) -> MatrixRecord:
    base = dict(
        record_id="mr-test",
        entity="RTX 3060",
        attribute="VRAM capacity",
        value="12 GB",
        source_url="https://www.nvidia.com/rtx-3060",
        source_title="NVIDIA GeForce RTX 3060",
        observed_at=datetime.now(timezone.utc).isoformat(),
        provenance="web_search → fetch → extract → matrix_write",
        ingest_id="ing-test",
        query="RTX 3060",
        excerpt="The GeForce RTX 3060 features 12 GB of GDDR6",
    )
    base.update(kwargs)
    return MatrixRecord(**base)


def _page(text: str, *, ok: bool = True, error: str | None = None):
    def fetch(_url):
        return {"ok": ok, "title": "NVIDIA GeForce RTX 3060", "main_text": text, "error": error}

    return fetch


def test_a_match(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_record())
    result = verify_matrix_record(
        "mr-test",
        store=store,
        fetch_fn=_page("The GeForce RTX 3060 features 12 GB of GDDR6 memory VRAM."),
        requested_by="cursor",
    )
    assert result["result"] == "MATCH"
    assert result["llm_used"] is False
    assert result["cause"] == "NOT_OBSERVED"
    types = [e.get("type") for e in result["events"]]
    assert types == ["matrix_record", "fetch", "matrix_verify", "verify_result"]
    assert "research" not in types
    assert result["records_unchanged"] is True


def test_b_not_found(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_record())
    result = verify_matrix_record(
        "mr-test",
        store=store,
        fetch_fn=_page("RTX 3060 is a mid-range GPU. No capacity number here."),
        requested_by="cursor",
    )
    assert result["result"] == "NOT_FOUND"
    assert "間違い" not in str(result).replace("誤り確定ではない", "")


def test_c_fetch_error(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_record())
    result = verify_matrix_record(
        "mr-test",
        store=store,
        fetch_fn=_page("", ok=False, error="timeout"),
        requested_by="cursor",
    )
    assert result["result"] == "FETCH_ERROR"


def test_d_not_available(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_record(source_url=""))
    result = verify_matrix_record("mr-test", store=store, fetch_fn=_page("unused"), requested_by="cursor")
    assert result["result"] == "NOT_AVAILABLE"
    types = [e.get("type") for e in result["events"]]
    assert "fetch" not in types


def test_e_and_f_do_not_mutate_records(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_record(record_id="mr-keep", value="10 GB"))
    before = records_bytes(store)
    first = verify_matrix_record(
        "mr-keep",
        store=store,
        fetch_fn=_page("RTX 3060 (12 GB) only."),
        requested_by="cursor",
    )
    second = verify_matrix_record(
        "mr-keep",
        store=store,
        fetch_fn=_page("RTX 3060 (12 GB) only."),
        requested_by="cursor",
    )
    assert first["result"] == "NOT_FOUND"
    assert second["result"] == "NOT_FOUND"
    assert records_bytes(store) == before
    rows = store.all_records()
    assert len(rows) == 1
    assert rows[0]["value"] == "10 GB"
    assert rows[0]["record_id"] == "mr-keep"


def test_g_search_still_works(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_record(record_id="mr-a", value="12 GB"))
    store.append(_record(record_id="mr-b", value="8 GB", source_url="https://en.example/rtx"))
    verify_matrix_record("mr-a", store=store, fetch_fn=_page("RTX 3060 features 12 GB of GDDR6 VRAM."))
    rows = search_records(store.all_records(), entity="RTX 3060", attribute="VRAM capacity")
    assert {r["value"] for r in rows} == {"12 GB", "8 GB"}
    assert search_records(store.all_records(), q="RTX 3060")
