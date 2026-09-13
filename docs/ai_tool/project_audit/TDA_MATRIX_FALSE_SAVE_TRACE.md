# Matrix 誤保存原因追跡 — 10 / 16 / 20 GB

**日付:** 2026-08-31  
**依頼:** 既存 Matrix の RTX 3060 / VRAM capacity（8 / 10 / 12 / 16 / 20 GB）について、保存経路を実データから遡る。訂正・削除・上書きはしない。  
**実行主体（調査・実装・テスト・Report）:** Cursor  
**追跡 actor:** `matrix_pipeline`（Local LLM には接続していない。原因推定に LLM は使っていない）  
**Run:** `runs/ai_tool/20260831_092800_matrix_false_save_trace`  
**Server:** `LocalAgentChat/0.14`  
**判定:** `PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Chat Research: **NOT CONNECTED**  
Chat Matrix Write: **NOT OBSERVED**  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**  
既存 Matrix レコードの削除・訂正・上書き: **していない**

成功条件は「10 GB の原因を特定すること」ではない。実データから経路を追跡し、原因と「追跡できない」を区別すること。

---

## 1. 対象レコード

`runs/matrix/records.jsonl` は調査前後で同一。sha256 `e68126296978ad04e6caf5904c229b600ffc37455028724a0ae15007d1a50324`（15756 bytes）。件数 38。VRAM capacity は 7 行（比較用の後続 ingest の 8 / 12 GB 重複を含む）。

今回の追跡対象（既存。新規架空データは作っていない）:

| record_id | value | ingest_id | source_title | source_url |
|-----------|-------|-----------|--------------|------------|
| mr-d01f270a1a45 | 8 GB | ing-20260830_234959-9e6ae956 | RTX 3060 | https://en.wikipedia.org/wiki/RTX_3060 |
| mr-9ef26e060032 | 10 GB | ing-20260830_234129-88aad4e7 | RTX 3060 | https://en.wikipedia.org/wiki/RTX_3060 |
| mr-5056e75f629a | 12 GB | ing-20260830_234959-9e6ae956 | RTX 3060 | https://en.wikipedia.org/wiki/RTX_3060 |
| mr-43089f3d9495 | 16 GB | ing-20260830_234129-88aad4e7 | RTX 5000 | https://en.wikipedia.org/wiki/RTX_5000 |
| mr-7be71a20ed81 | 20 GB | ing-20260830_234129-88aad4e7 | RTX 4000 | https://en.wikipedia.org/wiki/RTX_4000 |

8 GB / 12 GB の比較対象は、後続 ingest かつ既存 verify が MATCH の上記 2 件。同一値の後続コピー（`mr-29c00a9a0113` / `mr-263fa6a28404`）もある。問題 ingest の VRAM は 10 / 16 / 20 GB の 3 件のみ。

LLM: 各レコードの provenance に LLM は無い。経路追跡も LLM を呼び出していない。

---

## 2. 各レコードの source URL

上表のとおり。16 GB の採用 URL は Wikipedia `RTX_5000`。20 GB は `RTX_4000`。8 / 10 / 12 GB は `RTX_3060`。

---

## 3. Search / Fetch / Extract / Normalize / Matrix Write

追跡は再 fetch しない。`last_ingest.json` は後の ingest で上書き済み。問題 ingest `ing-20260830_234129-88aad4e7` の Event ログは残っていない。

同一 ingest の `source_url` から Search の title/URL だけ復元した。hits 配列・snippet 本文は **omitted**。

| 段階 | 8 GB | 10 GB | 12 GB | 16 GB | 20 GB |
|------|------|-------|-------|-------|-------|
| SEARCH | observed_from_records（title/URL 5 件。snippets omitted） | 同（7 件） | 同（5 件） | 同（7 件） | 同（7 件） |
| FETCH | observed_from_record（provenance に fetch。本文 omitted） | 同 | 同 | 同 | 同 |
| EXTRACT | entity=query=title=RTX 3060。excerpt に 8 GB なし | entity=query=title=RTX 3060。excerpt に 10 GB なし | entity=query=title=RTX 3060。excerpt に 12 GB なし | **query entity=RTX 3060 / source_title=RTX 5000**。excerpt に 16 GB なし | **query entity=RTX 3060 / source_title=RTX 4000**。excerpt に 20 GB なし |
| NORMALIZE | NOT OBSERVED | NOT OBSERVED | NOT OBSERVED | NOT OBSERVED | NOT OBSERVED |
| MATRIX_WRITE | 当該 JSONL 行 | 当該 JSONL 行 | 当該 JSONL 行 | 当該 JSONL 行 | 当該 JSONL 行 |
| VERIFY | 既存 MATCH | 既存 NOT_FOUND | 既存 MATCH | 既存 NOT_FOUND | 既存 NOT_FOUND |

問題 ingest の Search 復元 titles: RTX 3060, RTX 5000, RTX 4000, RTX 2000, RTX A6000, RTX2000, RTX100。

8 / 12 GB ingest の Search 復元 titles: RTX 3060, RTX 5000, RTX 4000, RTX 2000, RTX A6000。VRAM 行の source は RTX 3060 のみ。

コード上（保存時の extract）: `entity = entity_from_query(query)` を hit ごとに付ける。Normalize 専用 Event は保存されていない。

---

## 4. 16 GB の原因

**CAUSE: ENTITY_SOURCE_MISMATCH**

確認できた事実:

- query / record.entity = RTX 3060
- 採用 source URL / title = Wikipedia RTX 5000
- 同一 ingest の Search 復元に RTX 5000 URL が含まれる
- Matrix Write の最終値 = entity RTX 3060, value 16 GB, source_url wiki/RTX_5000
- 既存 verify = NOT_FOUND（RTX 3060 として 16 GB を支持する記述は、後の照合で出典ページ上に確認できなかった）

混同箇所: Extract が query 由来の Entity を、source_title が RTX 5000 の hit に付けた。Source Selection がその URL を RTX 3060 レコードの出典にした。

確認できなかったこと: snippet 本文、fetch 本文、16 GB が取れた文字位置。excerpt 先頭 160 文字に 16 GB は無い。Search が「誤り」だったかは **NOT DETERMINED**（関連 Wikipedia が返った事実だけが確認できる）。

---

## 5. 20 GB の原因

**CAUSE: ENTITY_SOURCE_MISMATCH**

16 GB と同様。source は Wikipedia RTX 4000。Write 最終値 = entity RTX 3060, value 20 GB, source_url wiki/RTX_4000。

---

## 6. 10 GB の原因

```text
CAUSE: NOT DETERMINED
```

確認できた事実:

- query / entity / source_title / source_url はいずれも RTX 3060
- excerpt に 10 GB は含まれない
- 既存 verify = NOT_FOUND
- provenance に LLM は無い。手動入力の記録も無い

以下はいずれも **確定していない**（決め打ち禁止）: Search の誤り、Wikipedia の誤り、Extract の誤り、Normalize の誤り、Entity 紐付けの誤り、手動入力、Cursor 由来。

数値の根拠箇所は、保存 excerpt にも ingest Event にも無い。

---

## 7. 実際に観測できた範囲

- 5 件の record フィールド（entity / value / source_url / source_title / query / provenance / ingest_id / excerpt）
- 同一 ingest の cited_by からの Search title/URL 復元
- provenance 文字列に fetch が含まれること
- extract.py の `entity_from_query` が全 hit に query entity を付けること
- 既存 verify.jsonl の MATCH / NOT_FOUND
- 16 / 20 GB の Entity と source_title の不一致
- ブラウザ処理タブの「経路を追跡」（`POST /api/matrix/trace`）
- `runs/matrix/last_trace.json`（Matrix 本体とは別）
- records.jsonl の sha256 不変

---

## 8. 観測できなかった範囲

| 項目 | 判定 |
|------|------|
| 問題 ingest の元 Search Event（hits 配列・snippet・backends） | NOT OBSERVED（last_ingest 上書き） |
| fetch 本文 / wikitext 全文 | omitted |
| 10 / 16 / 20 GB が excerpt より長い blob のどこから取れたか | NOT DETERMINED |
| Normalize 専用 Event | NOT OBSERVED |
| 10 GB の原因分類 | NOT DETERMINED |
| Search が「誤り」だったこと | NOT DETERMINED |
| LLM による保存・原因推定 | 未使用 |
| Cursor live | NOT OBSERVED |

架空の Search / Fetch Event は作っていない。無い段階は NOT OBSERVED / omitted。

---

## 9. Matrix 本体が変更されていないこと

追跡前後の `records.jsonl`:

- sha256: `e68126296978ad04e6caf5904c229b600ffc37455028724a0ae15007d1a50324`
- bytes: 15756
- 10 / 16 / 20 GB の既存値は残存
- 8 / 12 GB の MATCH 事実は verify.jsonl のまま（今回 verify し直していない）

調査結果の保存先: `runs/matrix/last_trace.json`、本 Report、本 Run。`verify.jsonl` への追記もしていない。

---

## 10. ブラウザで確認できる場所

処理タブ → Matrix パネル → 属性検索（entity RTX 3060 / attribute VRAM capacity）→ 各レコードの **経路を追跡**。

表示:

```text
[MATRIX_RECORD]
    ↓
[SEARCH]
    ↓
[FETCH]
    ↓
[EXTRACT]
    ↓
[NORMALIZE]   ← 保存 Event が無いため status: NOT OBSERVED
    ↓
[MATRIX_WRITE]
    ↓
[VERIFY]
```

CAUSE 行: `ENTITY_SOURCE_MISMATCH` / `ALIGNED_SOURCE` / `NOT DETERMINED`。llm_used: false。records_unchanged: true。

開発タブ: 本 Run / Report / Test A–G。Machine Test: NOT AVAILABLE。

---

## 11. Cursor が実行した Test / Report

Cursor Report: `tests/ai_tool/chat_interface` + `tests/ai_tool/matrix` **80 passed**。

| ID | 判定 |
|----|------|
| A | PASS（records バイト不変） |
| B | PASS（8 / 12 GB の既存 MATCH 事実を維持） |
| C | PASS（10 / 16 / 20 GB を保持） |
| D | PASS（16 / 20 GB の Entity 取り違え経路） |
| E | PASS（10 GB は NOT DETERMINED） |
| F | PASS（無い Search backends を生成しない） |
| G | PASS（処理タブ用 Event。research を出さない） |

本 Report: `docs/ai_tool/project_audit/TDA_MATRIX_FALSE_SAVE_TRACE.md`

---

## 12. Machine Test の有無

**NOT AVAILABLE**（JUnit XML なし。80 はコピーしない）。

---

## 13. Git 差分

コミットしていない。`runs/matrix/records.jsonl` は git status に出ていない（内容も変更していない）。

今回追加・変更（本体以外）:

- `ai_tool/matrix/trace.py`（新）
- `ai_tool/matrix/store.py` / `paths.py` / `__init__.py`
- `ai_tool/chat_interface/server.py`（`/api/matrix/trace`, `/api/matrix/last_trace`）
- `ai_tool/chat_interface/static/index.html` / `app.js` / `app.css`
- `tests/ai_tool/matrix/test_matrix_trace.py`（新）
- `tests/ai_tool/chat_interface/test_matrix_api.py`
- 本 Report / Run
- `runs/matrix/last_trace.json`

未変更: `agent.py`, `pipeline.yaml`, `search_web` 本体, `AGENT_VISIBLE_DEFAULT`, `ResearchRecord`, `runs/matrix/records.jsonl`。

---

## 14. Run ID

`20260831_092800_matrix_false_save_trace`

---

## 実測表

| Value | Source | 実際の対象 | 原因 | 判定 |
| ----- | ------ | ---------- | ---- | ---- |
| 8 GB | https://en.wikipedia.org/wiki/RTX_3060 | RTX 3060 | —（ALIGNED_SOURCE。既存 verify MATCH） | 正常 |
| 10 GB | https://en.wikipedia.org/wiki/RTX_3060 | RTX 3060（title/URL 一致） | NOT DETERMINED | 調査結果 |
| 12 GB | https://en.wikipedia.org/wiki/RTX_3060 | RTX 3060 | —（ALIGNED_SOURCE。既存 verify MATCH） | 正常 |
| 16 GB | https://en.wikipedia.org/wiki/RTX_5000 | RTX 5000 | Entity Linking + Source Selection | 調査結果 |
| 20 GB | https://en.wikipedia.org/wiki/RTX_4000 | RTX 4000 | Entity Linking + Source Selection | 調査結果 |

---

## 次に修正すべき箇所

今回は修正しない。確認できた原因箇所だけ列挙する。

16 GB / 20 GB:

- Entity Linking（query の Entity を、source_title が異なる hit に付けている）
- Source Selection（RTX 5000 / RTX 4000 の URL を RTX 3060 の VRAM 出典として採用している）

10 GB:

- 修正箇所は挙げない。CAUSE: NOT DETERMINED

Search / Extract（数値抽出） / Normalize は、今回の実データでは原因として確定していない。
