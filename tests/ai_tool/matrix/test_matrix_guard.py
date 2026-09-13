"""Entity / Source 保存前チェック。records.jsonl の誤レコードは retraction で除外する。"""
from __future__ import annotations

from datetime import datetime, timezone

from ai_tool.matrix.extract import source_entity_mismatch
from ai_tool.matrix.ingest import ingest_web_to_matrix
from ai_tool.matrix.models import MatrixRecord
from ai_tool.matrix.retract import (
    CAUSE_UNKNOWN,
    REASON_MISMATCH,
    REASON_UNSUPPORTED,
    retract_matrix_record,
)
from ai_tool.matrix.store import MatrixStore, load_retracted_ids, search_records
from ai_tool.matrix.verify import records_bytes


def _search_ok(_query=None, **_k):
    return {
        "query": _query,
        "hits": [
            {
                "title": "GeForce RTX 3060 Graphics Cards",
                "url": "https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3060-3060ti/",
                "snippet": "The GeForce RTX 3060 features 12 GB of GDDR6 memory (VRAM) for high-definition gaming.",
            }
        ],
        "backends_tried": ["mock"],
        "error": None,
    }


def _search_mismatch(_query=None, **_k):
    return {
        "query": _query,
        "hits": [
            {
                "title": "RTX 5000",
                "url": "https://en.wikipedia.org/wiki/RTX_5000",
                "snippet": "The RTX 5000 workstation GPU includes 16 GB of GDDR6 VRAM.",
            },
            {
                "title": "RTX 4000",
                "url": "https://en.wikipedia.org/wiki/RTX_4000",
                "snippet": "The RTX 4000 features 20 GB of GDDR6 VRAM.",
            },
            {
                "title": "RTX 3060",
                "url": "https://en.wikipedia.org/wiki/RTX_3060",
                "snippet": "The GeForce RTX 3060 features 12 GB of GDDR6 memory VRAM.",
            },
        ],
        "backends_tried": ["mock"],
        "error": None,
    }


def test_a_aligned_source_still_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    result = ingest_web_to_matrix("RTX 3060 VRAM", search_fn=_search_ok, store=store)
    types = [e.get("type") for e in result["events"]]
    assert types.index("search") < types.index("extract")
    assert "entity_source_check" in types
    assert "matrix_write" in types
    write = next(e for e in result["events"] if e["type"] == "matrix_write")
    assert write["status"] == "success"
    vram = [r for r in result["records"] if r["attribute"] == "VRAM capacity"]
    assert vram[0]["value"] == "12 GB"
    assert vram[0]["source_title"].find("3060") >= 0
    assert "web_search" in vram[0]["provenance"]
    assert "extract" in vram[0]["provenance"]
    assert "matrix_write" in vram[0]["provenance"]
    assert result["llm_used"] is False
    assert "research" not in types


def test_b_mismatch_16_and_20_not_written(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")

    def wiki(title):
        assert title == "RTX_3060"
        return {
            "ok": True,
            "title": "RTX 3060",
            "main_text": "The GeForce RTX 3060 features 12 GB of GDDR6 memory VRAM.",
        }

    result = ingest_web_to_matrix(
        "RTX 3060",
        search_fn=_search_mismatch,
        wiki_fn=wiki,
        fetch_fn=lambda _url: (_ for _ in ()).throw(AssertionError("wiki 以外を fetch しない")),
        store=store,
    )
    values = {r["value"] for r in result["records"] if r["attribute"] == "VRAM capacity"}
    assert "16 GB" not in values
    assert "20 GB" not in values
    assert "12 GB" in values
    check = next(e for e in result["events"] if e["type"] == "entity_source_check")
    assert check["entity_source_mismatch_count"] >= 2
    reasons = {row["reason"] for row in check["rejected"]}
    assert "ENTITY_SOURCE_MISMATCH" in reasons
    stored = {r["value"] for r in store.all_records() if r["attribute"] == "VRAM capacity"}
    assert stored == {"12 GB"}
    assert source_entity_mismatch("RTX 3060", "RTX 5000", "https://en.wikipedia.org/wiki/RTX_5000")


def test_c_existing_8_12_search_not_broken(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    now = datetime.now(timezone.utc).isoformat()
    for rid, val in (("mr-keep-8", "8 GB"), ("mr-keep-12", "12 GB")):
        store.append(
            MatrixRecord(
                record_id=rid,
                entity="RTX 3060",
                attribute="VRAM capacity",
                value=val,
                source_url="https://en.wikipedia.org/wiki/RTX_3060",
                source_title="RTX 3060",
                observed_at=now,
                provenance="web_search → fetch → extract → matrix_write",
                ingest_id="ing-keep",
                query="RTX 3060",
                excerpt="GeForce RTX 3060 (8 GB)|GeForce RTX 3060 (12 GB)",
            )
        )
    found = search_records(store.all_records(), entity="RTX 3060", attribute="VRAM capacity")
    assert {r["value"] for r in found} == {"8 GB", "12 GB"}


def test_d_unsupported_10gb_on_matching_source_not_written(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")

    def search(_query=None, **_k):
        return {
            "query": _query,
            "hits": [
                {
                    "title": "RTX 3060",
                    "url": "https://en.wikipedia.org/wiki/RTX_3060",
                    "snippet": "The GeForce RTX 3060 has 10 GB of GDDR6 VRAM in this snippet.",
                }
            ],
            "backends_tried": ["mock"],
            "error": None,
        }

    def wiki(title):
        assert title == "RTX_3060"
        return {
            "ok": True,
            "title": "RTX 3060",
            "main_text": "GeForce RTX 3060 (8 GB)|GeForce RTX 3060 (12 GB)",
        }

    result = ingest_web_to_matrix(
        "RTX 3060",
        search_fn=search,
        wiki_fn=wiki,
        fetch_fn=lambda _url: (_ for _ in ()).throw(AssertionError("wiki 以外を fetch しない")),
        store=store,
    )
    values = {r["value"] for r in result["records"] if r["attribute"] == "VRAM capacity"}
    assert "10 GB" not in values
    assert values == {"8 GB", "12 GB"}
    check = next(e for e in result["events"] if e["type"] == "entity_source_check")
    assert any(row["reason"] == "VALUE_NOT_SUPPORTED" and row["value"] == "10 GB" for row in check["rejected"])


def test_e_retract_hides_from_search_without_rewriting_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    now = datetime.now(timezone.utc).isoformat()
    store.append(
        MatrixRecord(
            record_id="mr-bad-16",
            entity="RTX 3060",
            attribute="VRAM capacity",
            value="16 GB",
            source_url="https://en.wikipedia.org/wiki/RTX_5000",
            source_title="RTX 5000",
            observed_at=now,
            provenance="web_search → fetch → extract → matrix_write",
            ingest_id="ing-bad",
            query="RTX 3060",
            excerpt="RTX 5000",
        )
    )
    before = records_bytes(store)
    out = retract_matrix_record(
        "mr-bad-16",
        reason=REASON_MISMATCH,
        cause=REASON_MISMATCH,
        note="test",
        store=store,
        requested_by="cursor",
    )
    assert out["ok"] is True
    assert records_bytes(store) == before
    assert "mr-bad-16" in load_retracted_ids()
    hidden = search_records(store.all_records(), entity="RTX 3060", attribute="VRAM capacity")
    assert hidden == []
    still = store.get_by_id("mr-bad-16")
    assert still is not None
    assert still["value"] == "16 GB"


def test_retract_10gb_keeps_cause_not_determined(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(
        MatrixRecord(
            record_id="mr-bad-10",
            entity="RTX 3060",
            attribute="VRAM capacity",
            value="10 GB",
            source_url="https://en.wikipedia.org/wiki/RTX_3060",
            source_title="RTX 3060",
            observed_at=datetime.now(timezone.utc).isoformat(),
            provenance="web_search → fetch → extract → matrix_write",
            ingest_id="ing-10",
            query="RTX 3060",
            excerpt="RTX 3060 The GeForce RTX 30 series",
        )
    )
    out = retract_matrix_record(
        "mr-bad-10",
        reason=REASON_UNSUPPORTED,
        cause=CAUSE_UNKNOWN,
        store=store,
    )
    assert out["cause"] == CAUSE_UNKNOWN
    assert out["reason"] == REASON_UNSUPPORTED
