# Matrix 保存情報と出典ページの照合・観測

**日付:** 2026-08-31  
**依頼:** Matrix に保存された値が、記録された出典ページに存在するかを人間がブラウザから確認できるようにする。自動訂正・削除・上書き・LLM 判断はしない。  
**実行主体（調査・実装・テスト・Report）:** Cursor  
**照合 actor:** `matrix_pipeline`（Local LLM には接続していない）  
**Run:** `runs/ai_tool/20260831_091200_matrix_source_verify`  
**Server:** `LocalAgentChat/0.13`  
**判定:** `PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Chat Research: **NOT CONNECTED**  
Chat Matrix Write: **NOT OBSERVED**  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**  
既存 Matrix レコードの削除・訂正: **していない**

成功条件は「値が正しいと自動判断できること」ではない。出典取得と MATCH / NOT_FOUND / FETCH_ERROR / NOT_AVAILABLE を追跡できること。

---

## Phase 1：既存レコード

`runs/matrix/records.jsonl` は 38 件。VRAM capacity は 7 件。データモデルは変更していない。

照合対象（既存。新規架空データは作っていない）:

| record_id | value | source_url | provenance |
|-----------|-------|------------|------------|
| mr-5056e75f629a | 12 GB | https://en.wikipedia.org/wiki/RTX_3060 | web_search → fetch → extract → matrix_write |
| mr-9ef26e060032 | 10 GB | https://en.wikipedia.org/wiki/RTX_3060 | 同上 |
| mr-43089f3d9495 | 16 GB | https://en.wikipedia.org/wiki/RTX_5000 | 同上 |
| mr-7be71a20ed81 | 20 GB | https://en.wikipedia.org/wiki/RTX_4000 | 同上 |
| mr-d01f270a1a45 | 8 GB | https://en.wikipedia.org/wiki/RTX_3060 | 同上 |

照合経路: `source_url → fetch（Wikipedia は wikitext）→ page_supports_fact`。LLM なし。CAUSE は常に **NOT_OBSERVED**（原因の確定はしない）。

照合ログは `runs/matrix/last_verify.json` と `verify.jsonl`。`records.jsonl` は追記も上書きもしていない。

---

## 照合結果（実測）

`records.jsonl` の sha256 は照合前後で同一: `e68126296978ad04e6caf5904c229b600ffc37455028724a0ae15007d1a50324`（15756 bytes）。

| Value | Source URL | 結果 | 意味（確定しないこと） |
|-------|------------|------|------------------------|
| 12 GB | wikipedia RTX_3060 | **MATCH** | 出典テキスト上に支持する記述を確認した。正しさの自動確定ではない |
| 8 GB | wikipedia RTX_3060 | **MATCH** | 同上 |
| 10 GB | wikipedia RTX_3060 | **NOT_FOUND** | 取得できたが支持記述を確認できなかった。誤り確定ではない |
| 16 GB | wikipedia RTX_5000 | **NOT_FOUND** | 同上 |
| 20 GB | wikipedia RTX_4000 | **NOT_FOUND** | 同上 |
| （今回なし） | — | FETCH_ERROR | pytest のみ |
| （source_url 空） | — | NOT_AVAILABLE | pytest のみ |

10 / 16 / 20 GB のレコードは **残した**。表示上も「間違い」とは書いていない。

---

## ブラウザ

処理タブ Matrix パネル:

- 属性検索でレコード表示
- **出典ページを開く**（人間確認、`source_url` を別タブ）
- **照合する**（機械確認、`POST /api/matrix/verify`）
- Event: `[MATRIX_RECORD]` → `[FETCH]` → `[MATRIX_VERIFY]` → `[VERIFY_RESULT]`
- actor `matrix_pipeline` / source `matrix` / correlation `mv-...`

Chat の「処理を見る」は会話 Event。照合は Matrix パネル側。

開発タブ: 本 Run / Report / Test A–G。Machine Test: NOT AVAILABLE。

---

## テスト

Cursor Report: `tests/ai_tool/chat_interface` + `tests/ai_tool/matrix` **72 passed**。

| ID | 判定 |
|----|------|
| A_MATCH | PASS |
| B_NOT_FOUND | PASS |
| C_FETCH_ERROR | PASS |
| D_NOT_AVAILABLE | PASS |
| E_NoMutate | PASS |
| F_RerunSafe | PASS |
| G_SearchRegression | PASS |

Machine Test: **NOT AVAILABLE**（JUnit XML なし。72 はコピーしない）。

---

## Cursor が変更したファイル

- `ai_tool/matrix/verify.py`（新）
- `ai_tool/matrix/extract.py`（`page_supports_fact`）
- `ai_tool/matrix/store.py` / `paths.py` / `__init__.py`
- `ai_tool/chat_interface/server.py`（`/api/matrix/verify`, `/api/matrix/last_verify`）
- `ai_tool/chat_interface/static/index.html` / `app.js` / `app.css`
- `tests/ai_tool/matrix/test_matrix_verify.py`（新）
- `tests/ai_tool/chat_interface/test_matrix_api.py`
- 本 Report / Run
- `runs/matrix/last_verify.json` / `verify.jsonl`（照合ログ。records ではない）

未変更: `agent.py`, `pipeline.yaml`, `search_web` 本体, `AGENT_VISIBLE_DEFAULT`, `ResearchRecord`, `runs/matrix/records.jsonl` の内容。

Git: コミットしていない。

---

## 未観測

| 項目 | 判定 |
|------|------|
| 10/16/20 GB が「間違い」であることの確定 | していない（禁止） |
| 12 GB が「正しい」ことの確定 | していない（MATCH ≠ 正しさ） |
| 原因（Search / Fetch / Extract / 出典） | CAUSE: NOT_OBSERVED |
| LLM 照合 | 未接続 |
| Cursor live | NOT OBSERVED |
