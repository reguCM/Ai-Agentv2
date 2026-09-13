"""Matrix 質問利用。本番 JSONL へ偽データを混ぜない。Chat 経路ではない。"""
from __future__ import annotations

from datetime import datetime, timezone

from ai_tool.matrix.ask import ask_matrix, parse_question
from ai_tool.matrix.models import MatrixRecord
from ai_tool.matrix.store import MatrixStore, search_records
from tests.ai_tool.matrix.test_matrix_store import _search


def _rec(**kwargs) -> MatrixRecord:
    base = dict(
        record_id="mr-ask",
        entity="RTX 3060",
        attribute="VRAM capacity",
        value="12 GB",
        source_url="https://en.wikipedia.org/wiki/RTX_3060",
        source_title="RTX 3060",
        observed_at=datetime.now(timezone.utc).isoformat(),
        provenance="web_search → fetch → extract → matrix_write",
        ingest_id="ing-ask",
        query="RTX 3060",
        excerpt="GeForce RTX 3060 (12 GB)",
    )
    base.update(kwargs)
    return MatrixRecord(**base)


def _search_4060(_query=None, **_k):
    return {
        "query": _query,
        "hits": [
            {
                "title": "RTX 4060",
                "url": "https://en.wikipedia.org/wiki/RTX_4060",
                "snippet": "The GeForce RTX 4060 features 8 GB of GDDR6 memory VRAM.",
            }
        ],
        "backends_tried": ["mock"],
        "error": None,
    }


def test_parse_vram_and_price():
    vram = parse_question("RTX 3060のVRAM容量を教えて")
    assert vram["parsed"] is True
    assert vram["needed"] == [{"entity": "RTX 3060", "attribute": "VRAM capacity"}]
    price = parse_question("RTX 3060の現在の中古価格を教えて")
    assert price["needed"] == [{"entity": "RTX 3060", "attribute": "used price"}]


def test_1_matrix_sufficient(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_rec())
    out = ask_matrix("RTX 3060のVRAM容量を教えて", store=store, requested_by="cursor")
    assert out["decision"] == "SUFFICIENT"
    assert out["web_search_count"] == 0
    assert out["llm_used"] is False
    assert "12 GB" in out["answer"]
    assert "https://en.wikipedia.org/wiki/RTX_3060" in out["answer"]
    types = [e["type"] for e in out["events"]]
    assert types[0] == "question"
    assert "matrix_search" in types
    assert "sufficient" in types
    assert "search" not in types
    assert "research" not in types


def test_2_matrix_insufficient_price(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_rec())
    out = ask_matrix("RTX 3060の現在の中古価格を教えて", fallback=True, store=store)
    assert out["decision"] == "INSUFFICIENT"
    assert out["web_search_count"] == 0
    assert any(e["type"] == "ingest_skip" for e in out["events"])


def test_3_and_4_insufficient_search_write(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_rec())
    out = ask_matrix(
        "RTX 4060のVRAM容量を教えて",
        fallback=True,
        store=store,
        search_fn=_search_4060,
        wiki_fn=lambda title: {
            "ok": True,
            "title": "RTX 4060",
            "main_text": "The GeForce RTX 4060 features 8 GB of GDDR6 memory VRAM.",
        },
        fetch_fn=lambda _u: (_ for _ in ()).throw(AssertionError("wiki 以外")),
        requested_by="cursor",
    )
    assert out["decision"] == "SUFFICIENT"
    assert out["web_search_count"] == 1
    assert any(e["type"] == "search" for e in out["events"])
    assert any(e["type"] == "entity_source_check" for e in out["events"])
    assert any(e["type"] == "matrix_write" and e.get("status") == "success" for e in out["events"])
    vram = search_records(store.all_records(), entity="RTX 4060", attribute="VRAM capacity")
    assert any(r["value"] == "8 GB" for r in vram)
    assert all(r.get("provenance") for r in vram)
    assert all(r.get("source_url") for r in vram)


def test_5_and_6_second_query_skips_search(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    first = ask_matrix(
        "RTX 4060のVRAM容量を教えて",
        fallback=True,
        store=store,
        search_fn=_search_4060,
        wiki_fn=lambda title: {
            "ok": True,
            "title": "RTX 4060",
            "main_text": "The GeForce RTX 4060 features 8 GB of GDDR6 memory VRAM.",
        },
        fetch_fn=lambda _u: (_ for _ in ()).throw(AssertionError("wiki 以外")),
    )
    assert first["web_search_count"] == 1
    second = ask_matrix(
        "RTX 4060のVRAM容量を教えて",
        fallback=True,
        store=store,
        search_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("2回目は search しない")),
    )
    assert second["decision"] == "SUFFICIENT"
    assert second["web_search_count"] == 0
    assert "8 GB" in second["answer"]
    assert not any(e["type"] == "search" for e in second["events"])


def test_7_invalid_source_not_written(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")

    def search(_query=None, **_k):
        return {
            "query": _query,
            "hits": [
                {
                    "title": "RTX 5000",
                    "url": "https://en.wikipedia.org/wiki/RTX_5000",
                    "snippet": "The RTX 5000 includes 16 GB of GDDR6 VRAM.",
                }
            ],
            "backends_tried": ["mock"],
            "error": None,
        }

    out = ask_matrix(
        "RTX 4060のVRAM容量を教えて",
        fallback=True,
        store=store,
        search_fn=search,
        wiki_fn=lambda _t: (_ for _ in ()).throw(AssertionError("不一致出典は fetch しない")),
        fetch_fn=lambda _u: (_ for _ in ()).throw(AssertionError("不一致出典は fetch しない")),
    )
    assert out["decision"] == "INSUFFICIENT"
    assert not any(r["attribute"] == "VRAM capacity" for r in store.all_records())


def test_8_9_provenance_and_events(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_rec())
    out = ask_matrix("RTX 3060のVRAM容量を教えて", store=store)
    rec = out["records"][0]
    assert rec["provenance"]
    assert rec["source_url"]
    assert rec["observed_at"]
    types = [e["type"] for e in out["events"]]
    assert "matrix_search" in types
    assert "answer" in types
    assert out["chat_path"] == "NOT_CONNECTED"


def test_llm_organize_and_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_rec())

    def chat(**_k):
        return {
            "model": "mock-llm",
            "message": {
                "content": '{"summary": "3060のVRAMはある。4060のVRAMが不足。", "missing": [{"entity": "RTX 4060", "attribute": "VRAM capacity"}]}'
            },
        }

    out = ask_matrix(
        "RTX 3060とRTX 4060ってどっちがいい？",
        fallback=True,
        use_llm=True,
        chat_fn=chat,
        store=store,
        search_fn=_search_4060,
        wiki_fn=lambda title: {
            "ok": True,
            "title": "RTX 4060",
            "main_text": "The GeForce RTX 4060 features 8 GB of GDDR6 memory VRAM.",
        },
        fetch_fn=lambda _u: (_ for _ in ()).throw(AssertionError("wiki 以外")),
    )
    assert out["llm_used"] is True
    assert out["llm_model"] == "mock-llm"
    assert out["decision"] == "SUFFICIENT"
    assert "12 GB" in out["answer"]
    assert "8 GB" in out["answer"]
    assert any(e["type"] == "llm" and e.get("status") == "success" for e in out["events"])


def test_10_existing_search_regression(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(_rec())
    rows = search_records(store.all_records(), entity="RTX 3060", attribute="VRAM capacity")
    assert any(r["value"] == "12 GB" for r in rows)
    from ai_tool.matrix.ingest import ingest_web_to_matrix

    ingest_web_to_matrix("RTX 3060 VRAM", search_fn=_search, store=store)
    again = search_records(store.all_records(), q="RTX 3060")
    assert again
