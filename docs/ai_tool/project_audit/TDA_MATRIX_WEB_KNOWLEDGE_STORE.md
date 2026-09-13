# Matrix Web Knowledge Store ― 最小実装・実測

**日付:** 2026-08-31  
**依頼:** Web Search → 構造化 → Matrix 保存 → LLM なし機械検索 → ブラウザ表示、を最小経路として成立させる  
**実行主体（調査・実装・テスト・Report）:** Cursor  
**実行主体（ブラウザ操作）:** Cursor が Chat UI を操作。Matrix ingest の actor は `matrix_pipeline`。Local Agent LLM には実装させていない  
**Run:** `runs/ai_tool/20260831_085200_matrix_web_knowledge_store`  
**Server:** `LocalAgentChat/0.12`  
**Session（新規取得確認）:** `cs-20260830_235229-bee86c`  
**判定:** `PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Chat 経路の Research: **NOT CONNECTED**  
Chat 経路の Matrix Write: **NOT OBSERVED**（会話送信では書いていない。正しい）  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**（`agent.py` / `pipeline.yaml` / `search_web` 本体は未変更）

成功条件は「LLM に回答させること」ではない。保存した知識を LLM なしで機械的に取り出せること。

---

## 調査結果（実装前に確認した既存コード）

TDA `ResearchRecord` を Matrix として流用していない。責務が違う。

| 既存 | 場所 | 今回の扱い |
|------|------|------------|
| `search_web` | `tools/system.network.search_web` | **再利用**（呼び出しのみ。本体の大規模変更なし） |
| `read_url_text` | `ai_tool.experimental.read_url.reader` | Wikipedia 以外の HTML フォールバック。表を落とす正規化がある |
| `ResearchRecord` | `ai_tool.experimental.development_assistance.research_record` | **不採用**。requirement / candidates / version_facts の封筒であり、entity-attribute-value ではない |
| `ResearchStore` | TDA experimental | **不採用**。Chat からも呼ばない |
| `run_standard_workflow` | TDA experimental | **不採用**。Chat / Matrix から呼ばない |
| Registry / `AGENT_VISIBLE_DEFAULT` | Chat Tool 公開 | **未接続のまま**。Matrix は Chat Tool にしない |
| Session Event | `activity.py` / `agent_turn.py` | Chat ターンは従来どおり。Matrix は別 Event 列 |
| 開発タブ | `dev_cases.py` | slug に `matrix` があれば kind `matrix` |
| 処理タブ | Chat の「処理を見る」 | Chat ターンでは `[MATRIX_WRITE] NOT OBSERVED` を維持。Matrix パネルは別 |

停止条件（Production 変更、Search 大規模変更、LLM 必須、Research と責務衝突で大規模設計へ進む）には当たらなかった。Matrix は JSONL 追記で足りた。新しい Graph DB / Vector DB は使っていない。

---

## データモデル

`ai_tool/matrix/models.py` の `MatrixRecord`:

```text
record_id
entity
attribute
value
source_url
source_title
observed_at
provenance
ingest_id
query
excerpt（最大 160 文字。hits / 本文全文は置かない）
```

ストアは `runs/matrix/records.jsonl` への**追記のみ**。同一 entity の新情報は旧 record を消さない。

---

## 実測した経路

```text
User / Trigger（処理タブ「Web → Matrix」または Cursor の ingest 呼び出し）
  → search_web（既存）
  → 必要なら Wikipedia wikitext fetch（HTML 表が落ちるため）
  → extract / normalize（正規表現。LLM なし）
  → matrix_write（JSONL 追記）
  → GET /api/matrix/search（機械検索）
```

Chat の通常回答経路（`POST /api/chat`）には接いでいない。

### Web Search が何を取得したか

クエリ `RTX 3060`（`RTX 3060 VRAM` はこの環境で 0 hits になりやすい）:

- backends: duckduckgo / wikipedia-ja / wikipedia-en
- **hit_count: 5**
- snippet はほぼタイトルのみ（VRAM 数値なし）
- 先頭 URL: `https://en.wikipedia.org/wiki/RTX_3060`（リダイレクト先は GeForce RTX 30 series）

`read_url_text` の `main_text` には RTX 3060 の 12 GB が隣接しない。Wikipedia HTML 正規化が infobox / 表を落とすため。Matrix ingest は Wikipedia URL に限り **wikitext API** を読む（Search 本体は変更していない）。wikitext に `GeForce RTX 3060 (8 GB)` と `GeForce RTX 3060 (12 GB)` があることを確認してから抽出した。

### ブラウザ ingest（処理タブ）

- ingest_id: `ing-20260830_235148-6f6ac13e`
- correlation_id: `mx-20260830_235148-69f452e1`
- requested_by: `user`
- executed_by / actor: `matrix_pipeline`
- source: `matrix`
- llm_used: **false**
- research: **NOT_CONNECTED**
- Event（実行したものだけ）: `SEARCH` → `FETCH`（`fetch_kind: wikipedia_wikitext`）→ `EXTRACT / NORMALIZE` → `MATRIX_WRITE` → `MATRIX_RESULT`
- この ingest の保存件数: **7**（VRAM 8 GB / 12 GB + cited_by 5）

`[RESEARCH]` は出していない。Chat 側の「処理を見る」にある `[RESEARCH] NOT CONNECTED` は Chat ターン用であり、Matrix パネルには出していない。

---

## Matrix に何件保存したか / 何件取得できたか

| 対象 | 件数 | 根拠 |
|------|------|------|
| JSONL 全 record | **38** | `MatrixStore().all_records()` |
| ブラウザ ingest 1 回の write | **7** | last_ingest `count: 7` |
| `GET /api/matrix/search?q=RTX+3060` | **38** | ブラウザ機械検索 |
| entity=RTX 3060, attribute=VRAM capacity | **7** | ブラウザ属性検索 |
| そのうち value=12 GB | **2** | 追記 2 回（Cursor ingest + ブラウザ ingest）。上書きしていない |

VRAM capacity の value 集合（ストア全体）:

```text
8 GB, 10 GB, 12 GB, 16 GB, 20 GB
```

- **8 GB / 12 GB:** Wikipedia wikitext の `RTX 3060 (N GB)`。出典 URL は wikipedia RTX_3060。これは実測できた知識。
- **10 / 16 / 20 GB:** 初期に HTML 本文から誤抽出した過去 record。追記ストアのため削除していない。`observed_at` と `source` で区別できる。自動訂正は今回の範囲外。

属性検索で 12 GB は取得できる。同時に過去の誤抽出も返る。これは上書き禁止の仕様どおり。

---

## LLM なしで取得できたか

できた。

- ingest: `llm_used: false`
- 検索 API: `llm_used: false`
- Chat LLM は Matrix 検索・書き込みに使っていない
- 新規 Session `cs-20260830_235229-bee86c` のあと、会話履歴が空（「まだ処理がありません。」）でも属性検索 7 件・12 GB あり。**Session 履歴ではなく Matrix ファイルから取得した。**

---

## provenance

最新の 12 GB record 例:

```text
entity: RTX 3060
attribute: VRAM capacity
value: 12 GB
source_url: https://en.wikipedia.org/wiki/RTX_3060
observed_at: 2026-08-30T23:51:50.848376+00:00
provenance: web_search → fetch → extract → matrix_write
```

snippet / wikitext 全文は保存していない。excerpt は最大 160 文字。

---

## ブラウザでどこまで見えるか

### 処理タブ（必須）

- Matrix パネル: Web → Matrix / 機械検索 / 属性検索
- 実 Event: SEARCH / FETCH / EXTRACT / NORMALIZE / MATRIX_WRITE / MATRIX_RESULT
- 保存内容: record_id / entity / attribute / value / source / source_url / observed_at / provenance
- actor / source / correlation_id / status / requested_by / executed_by
- Chat 会話の処理列: `[MATRIX_WRITE] NOT OBSERVED`（このターンで書いていないため）

### 開発タブ

既存の Run / Report / Test / Git を維持。本 Run の Test 詳細は observations `tests` の A–G。

### 未接続・未観測

| 項目 | 判定 |
|------|------|
| Cursor live | NOT OBSERVED |
| Cursor → Local Agent | NOT_CONNECTED |
| Chat → ResearchRecord | NOT CONNECTED |
| Chat → Matrix Write | NOT OBSERVED |
| LLM による Matrix 検索・要約 | 未実装（今回対象外） |
| Local Agent への Matrix Tool 公開 | していない |
| Machine Test（JUnit XML） | NOT AVAILABLE |

---

## Test / PASS 詳細（Cursor Report。pytest XML ではない）

| ID | 内容 | 判定 | 根拠 |
|----|------|------|------|
| A_WebSearch | 実 Search | PASS | hit_count 5、omitted hits |
| B_Extraction | 機械抽出 | PASS | wikitext から 8 GB / 12 GB。LLM なし |
| C_MatrixWrite | 保存 | PASS | MATRIX_WRITE count 7。未実行なら非表示 |
| D_MatrixRead | q=RTX 3060 | PASS | 38 件、LLM なし |
| E_Provenance | 出典・日時 | PASS | source_url / observed_at / provenance |
| F_NewSessionRetrieval | 新規 Session | PASS | `cs-20260830_235229-bee86c` でも属性検索 7 件 |
| G_Update | 上書きしない | PASS | 旧 10/16/20 と新 8/12 が共存。observed_at が複数 |

モック pytest（実 Web なし）: `tests/ai_tool/matrix` + `test_matrix_api.py` を含む `tests/ai_tool/chat_interface` + `tests/ai_tool/matrix` で **65 passed**（Cursor 実行。Machine Test にはコピーしない）。

---

## Cursor が何を変更したか / Local Agent が何を実行したか

### Cursor

- 新モジュール `ai_tool/matrix/`（models / store / extract / ingest / paths）
- Chat UI: `GET /api/matrix/search`, `GET /api/matrix/last`, `POST /api/matrix/ingest`
- 処理タブの Matrix パネル（会話送信では書かない）
- テスト `tests/ai_tool/matrix/`, `tests/ai_tool/chat_interface/test_matrix_api.py`
- 本 Report / Run
- `activity.py` の Chat 向け注記（Matrix は `/api/matrix` の別経路）

### Local Agent

- Chat UI プロセスが HTTP を受けた（ingest の requested_by=user）
- 実装・抽出・保存ロジックは Local LLM ではなく `matrix_pipeline`
- 通常 Chat ターンでは Matrix に書いていない
- `agent.py` は実行していない

### Git

コミットしていない（依頼なし）。今回追加の未追跡: `ai_tool/matrix/`, `runs/matrix/`, 上記テスト、Chat UI 一式（リポジトリ上もともと未追跡）。`agent.py` / `pipeline.yaml` は未変更。

---

## 判定理由

Web 取得 → Matrix 保存 → LLM なし機械検索 → 12 GB と出典・日時の取得 → ブラウザで実 Event 確認、まで実測できた。新規 Session からも Matrix ファイルで取れた。Chat 通常経路には接いでいない。

残っている制限（推測ではない）:

- Search snippet だけでは 12 GB が取れない（この環境のヒットがタイトルのみ）
- Wikipedia HTML では表が落ちるため wikitext に頼った
- 初期 HTML 誤抽出（10/16/20 GB）は追記のまま残っている
