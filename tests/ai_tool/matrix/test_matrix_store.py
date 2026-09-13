"""Matrix 機械テスト。実 Web / LLM は使わない。"""
from __future__ import annotations

from ai_tool.matrix.extract import entity_from_query, extract_records_from_hits
from ai_tool.matrix.ingest import ingest_web_to_matrix
from ai_tool.matrix.store import MatrixStore, search_records

HITS_VRAM = [
    {
        "title": "GeForce RTX 3060 Graphics Cards",
        "url": "https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3060-3060ti/",
        "snippet": "The GeForce RTX 3060 features 12 GB of GDDR6 memory (VRAM) for high-definition gaming.",
    },
    {
        "title": "RTX 3060 specs overview",
        "url": "https://example.test/rtx-3060-specs",
        "snippet": "VRAM capacity: 12GB GDDR6. Other chips differ.",
    },
    {
        "title": "GPU buyer's note RTX 3060",
        "url": "https://example.test/buyer-note",
        "snippet": "A popular mid-range card. No capacity number here.",
    },
]


def _search(_query=None, **_k):
    return {"query": _query, "hits": list(HITS_VRAM), "backends_tried": ["mock"], "error": None}


def test_entity_from_query_rtx():
    assert entity_from_query("RTX 3060 VRAM") == "RTX 3060"
    assert entity_from_query("rtx3060 capacity") == "RTX 3060"


def test_extract_makes_multiple_records_not_one_answer(tmp_path):
    drafts = extract_records_from_hits(query="RTX 3060 VRAM", hits=HITS_VRAM)
    facts = [d for d in drafts if d["attribute"] == "VRAM capacity"]
    mentions = [d for d in drafts if d["attribute"] == "cited_by"]
    assert len(facts) >= 2
    assert {d["value"] for d in facts} == {"12 GB"}
    assert len(mentions) == 3
    assert all("snippet" not in d for d in drafts)


def test_a_through_g_mocked_search(tmp_path, monkeypatch):
    store = MatrixStore(tmp_path / "records.jsonl")
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))

    first = ingest_web_to_matrix(
        "RTX 3060 VRAM",
        search_fn=_search,
        store=store,
        requested_by="cursor",
    )
    # A_WebSearch / B_Extraction / C_MatrixWrite
    types = [e.get("type") for e in first["events"]]
    assert "search" in types
    assert "extract" in types
    assert "matrix_write" in types
    assert "matrix_result" in types
    assert "research" not in types
    assert first["llm_used"] is False
    assert first["ok"] is True
    assert len(first["records"]) >= 2
    vram = [r for r in first["records"] if r["attribute"] == "VRAM capacity"]
    assert vram
    assert vram[0]["value"] == "12 GB"
    assert vram[0]["provenance"] == "web_search → extract → matrix_write"
    assert vram[0]["source_url"].startswith("http")
    assert vram[0]["observed_at"]

    # D_MatrixRead / C attribute / E provenance
    rows = store.all_records()
    by_q = search_records(rows, q="RTX 3060")
    assert by_q
    by_attr = search_records(rows, entity="RTX 3060", attribute="VRAM capacity")
    assert by_attr
    assert any(r["value"] == "12 GB" for r in by_attr)
    sample = by_attr[0]
    assert sample["source_url"]
    assert sample["observed_at"]
    assert sample["provenance"]

    first_ids = {r["record_id"] for r in first["records"]}

    # G_Update: 新しい ingest は旧 record を消さない
    def _search_new(_query=None, **_k):
        return {
            "query": _query,
            "hits": [
                {
                    "title": "Later note",
                    "url": "https://example.test/later",
                    "snippet": "RTX 3060 VRAM 8 GB in a hypothetical SKU.",
                }
            ],
            "backends_tried": ["mock"],
            "error": None,
        }

    second = ingest_web_to_matrix(
        "RTX 3060 VRAM",
        search_fn=_search_new,
        store=store,
        requested_by="cursor",
    )
    assert second["ok"]
    all_rows = store.all_records()
    assert {r["record_id"] for r in all_rows} >= first_ids
    values = {r["value"] for r in all_rows if r["attribute"] == "VRAM capacity"}
    assert "12 GB" in values
    assert "8 GB" in values
    times = {r["observed_at"] for r in all_rows if r["attribute"] == "VRAM capacity"}
    assert len(times) >= 2

    # F_NewSessionRetrieval: store は session に紐づかない
    other = MatrixStore(tmp_path / "records.jsonl")
    again = search_records(other.all_records(), q="RTX 3060")
    assert again
    assert any(r["record_id"] in first_ids for r in again)


def test_ingest_does_not_emit_research_events(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")
    result = ingest_web_to_matrix("RTX 3060 VRAM", search_fn=_search, store=store)
    types = [e.get("type") for e in result["events"]]
    assert "RESEARCH" not in types
    assert "research" not in types
    assert result["research"] == "NOT_CONNECTED"


def test_fetch_used_when_snippet_has_no_vram(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")

    def search(_query=None, **_k):
        return {
            "query": _query,
            "hits": [
                {
                    "title": "NVIDIA GeForce RTX 3060",
                    "url": "https://www.nvidia.com/rtx-3060",
                    "snippet": "GeForce RTX 3060 graphics card.",
                }
            ],
            "backends_tried": ["mock"],
            "error": None,
        }

    def fetch(url):
        return {
            "ok": True,
            "url": url,
            "title": "NVIDIA GeForce RTX 3060",
            "main_text": "The GeForce RTX 3060 features 12 GB of GDDR6 memory VRAM for gaming.",
        }

    result = ingest_web_to_matrix(
        "RTX 3060 VRAM",
        search_fn=search,
        fetch_fn=fetch,
        store=store,
        requested_by="cursor",
    )
    types = [e.get("type") for e in result["events"]]
    assert "fetch" in types
    assert "matrix_write" in types
    vram = [r for r in result["records"] if r["attribute"] == "VRAM capacity"]
    assert vram[0]["value"] == "12 GB"
    assert "fetch" in vram[0]["provenance"]
    assert "main_text" not in str(result["records"])


def test_extract_paren_gb_from_wikitext_nbsp():
    drafts = extract_records_from_hits(
        query="RTX 3060",
        hits=[
            {
                "title": "GeForce RTX 30 series",
                "url": "https://en.wikipedia.org/wiki/RTX_3060",
                "snippet": (
                    "| midrange = GeForce RTX 3060 (8&nbsp;GB)|GeForce RTX 3060 (12&nbsp;GB)"
                    "|GeForce RTX 3060 Ti|GeForce RTX 3080 10 GB"
                ),
            }
        ],
    )
    values = {d["value"] for d in drafts if d["attribute"] == "VRAM capacity"}
    assert values == {"8 GB", "12 GB"}
    assert "10 GB" not in values


def test_wikipedia_wikitext_fetch_when_html_would_miss(tmp_path):
    store = MatrixStore(tmp_path / "records.jsonl")

    def search(_query=None, **_k):
        return {
            "query": _query,
            "hits": [
                {
                    "title": "RTX 3060",
                    "url": "https://en.wikipedia.org/wiki/RTX_3060",
                    "snippet": "RTX 3060",
                }
            ],
            "backends_tried": ["mock"],
            "error": None,
        }

    def wiki(title):
        assert title == "RTX_3060"
        return {
            "ok": True,
            "title": "GeForce RTX 30 series",
            "main_text": "GeForce RTX 3060 (8&nbsp;GB)|GeForce RTX 3060 (12&nbsp;GB)",
        }

    def fetch(_url):
        raise AssertionError("Wikipedia URL は HTML fetch しない")

    result = ingest_web_to_matrix(
        "RTX 3060",
        search_fn=search,
        fetch_fn=fetch,
        wiki_fn=wiki,
        store=store,
        requested_by="cursor",
    )
    kinds = [e.get("fetch_kind") for e in result["events"] if e.get("type") == "fetch"]
    assert kinds == ["wikipedia_wikitext"]
    values = {r["value"] for r in result["records"] if r["attribute"] == "VRAM capacity"}
    assert values == {"8 GB", "12 GB"}
    assert all(r["source_url"].startswith("https://en.wikipedia.org/wiki/RTX_3060") for r in result["records"] if r["attribute"] == "VRAM capacity")

