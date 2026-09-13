# Matrix 利用・再調査フォールバック実験

**日付:** 2026-08-31  
**依頼:** Matrix を知識 DB として使い、十分なら Matrix だけで答え、不足なら既存 Web Search → Validation → 保存 → 回答し、2 回目は Web Search を省略できるかを実測する。高度な Agent 化はしない。  
**実行主体（調査・実装・テスト・Report・ブラウザ操作）:** Cursor  
**ask / ingest actor:** `matrix_pipeline`（検索・保存は機械側。LLM は整理と不足列挙のみ）  
**Run:** `runs/ai_tool/20260831_100000_matrix_ask_fallback`  
**Server:** `LocalAgentChat/0.16`  
**静的:** `app.js?v=018` / `app.css?v=018`  
**判定:** `PARTIAL_PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Chat 経路の Research: **NOT CONNECTED**  
Chat 経路の Matrix Write: **NOT OBSERVED**  
Chat → Matrix ask: **NOT_CONNECTED**（処理タブの専用ボタンのみ。会話送信では呼ばない）  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**（`agent.py` / `pipeline.yaml` / `search_web` 本体 / `AGENT_VISIBLE_DEFAULT` は未変更）  
Git commit: **していない**

主目的「同じ情報を何度も Web 検索しなくてよいか」は **実測できた**。  
副目的「LLM が不足を認識して再調査へ進ませる」は、機械テストではできた。ライブ LLM は不足を文章では述べたが、構造化 `missing` は空のままだった。

---

## Phase 0（実装前調査）

再利用できた既存経路:

| 既存 | 場所 | 今回 |
|------|------|------|
| Matrix Search | `search_records` / `GET /api/matrix/search` | 質問時の Record 取得に再利用 |
| ingest | `ingest_web_to_matrix` | 不足かつ `VRAM capacity` のときだけ呼ぶ |
| `search_web` | `tools.system.network.search_web` | ingest 内部。新検索エンジンは作らない |
| Entity / Source validation | ingest の `entity_source_check` | 通す。Search 生ヒットは保存しない |
| provenance / source_url / observed_at | `MatrixRecord` | 維持 |
| verify | `verify_matrix_record` | 既存ログがあれば回答に付ける。無ければ `NOT OBSERVED` |
| Event | `events.event` | ask 専用列。Chat Session には混ぜない |
| extract | `extract_records_from_hits` | **VRAM capacity + cited_by のみ**。価格抽出は無い |

接続されていなかったもの（今回も Chat には繋がない）:

- `run_chat_turn` → Matrix（**維持して NOT_CONNECTED**）
- Matrix Tool を `AGENT_VISIBLE_DEFAULT` に載せる（**載せない**）
- 価格 attribute の extract（**新抽出器は作らない** → `ingest_skip` / `NOT CONNECTED`）
- 質問 → 十分/不足のオーケストレーション（**今回追加:** `ask_matrix`）

十分性の機械判定（今回実装）:

- Entity + Attribute が取れている
- 値が空でない
- `source_url` が空でない
- verify 結果はあれば表示。無いことは不足理由にしない
- 古さでは落とさない

---

## 実装（最小接続）

新規: `ai_tool/matrix/ask.py`、`POST /api/matrix/ask`、`GET /api/matrix/last_ask`、処理タブ「Matrix で答える」。

作らなかったもの: Matrix 再設計、ResearchRecord 統合、Matrix 専用 LLM、自動上書き/削除、Search 本文の無制限保存、価格抽出器、`SCAN_CHARS` 拡大、Production Workflow 変更。

---

## 実測できたこと

### A. Matrix だけで回答（LLM なし）

質問: `RTX 3060のVRAM容量を教えて`（fallback なし）

- decision: `SUFFICIENT`
- web_search_count: **0**
- Event: `question` → `matrix_search` → `sufficient` → `answer`
- 値: 8 GB / 12 GB（既存。出典 `https://en.wikipedia.org/wiki/RTX_3060`）
- ブラウザ処理タブでも `decision: SUFFICIENT web_search_count: 0`

### B. Matrix 不足を機械検出

質問: `RTX 3060の現在の中古価格を教えて`（fallback あり）

- decision: `INSUFFICIENT`
- web_search_count: **0**
- Event: `ingest_skip`（既存 extract が `used price` を保存しない）
- ブラウザでも `decision: INSUFFICIENT web_search_count: 0`

### C–F. 不足 → 既存 ingest → 保存後の回答 → 2 回目は Search 省略

題材は **RTX 3080 VRAM**（実 Web。偽データ投入なし）。

1 回目 `RTX 3080のVRAM容量を教えて` fallback あり:

```text
question → matrix_search → insufficient → search → fetch → extract
→ normalize → entity_source_check → matrix_write → matrix_result
→ matrix_search → sufficient → answer
```

- web_search_count: **1**
- ingest: `ing-20260831_011350-38f06688`
- 保存 VRAM: `mr-0b782e02598d` / RTX 3080 / 12 GB / `https://en.wikipedia.org/wiki/RTX_3080`
- provenance: `web_search → fetch → extract → matrix_write`
- verify: **MATCH**（ページ上の記述確認。正しさの確定ではない）

2 回目（同じ質問、fallback あり）:

- decision: `SUFFICIENT`
- web_search_count: **0**
- Event に `search` なし
- ブラウザ（処理タブ、不足時再調査チェック ON）でも `SUFFICIENT` / `web_search_count: 0`

これによって「Web 検索結果を Matrix に蓄積し、次回の検索を省略できる」は **成立した**。

### テスト 1–10（tmp_path。本番 JSONL へ偽データを入れない）

`tests/ai_tool/matrix/test_matrix_ask.py` および HTTP ask。  
Cursor 実行: `tests/ai_tool/chat_interface` + `tests/ai_tool/matrix` で **96 passed**。

モック経路では RTX 4060 VRAM の insufficient → search → write → 2 回目 search なし、不一致出典は VRAM 非保存、LLM モックの不足列挙 → ingest まで確認した。

### G. LLM 整理（モック）

モック `chat_fn` で 3060 と 4060 の Record を整理し、回答に両方の VRAM を含めた。LLM は検索・保存していない。

### H. LLM 不足列挙（モック）

モックが `missing: RTX 4060 / VRAM capacity` を返し、機械側が既存 ingest を実行した。

---

## RTX 4060 ライブで起きたこと（推測していない）

同じ実験の最初に `RTX 4060のVRAM容量を教えて` を fallback 付きで 2 回実行した。

観測:

- Wikipedia `RTX_4060` は title `GeForce RTX 40 series` に解決
- fetch は成功（wikitext、`SCAN_CHARS=8000`）
- その 8000 文字では既存 `_vram_values(..., "RTX 4060")` が **空**
- 全文（約 78k）では 8 GB / 16 GB が取れる。16 GB 側の窓には `RTX 4060 Ti` が含まれる
- Search ヒット由来の `cited_by` のみ保存。VRAM capacity は **保存されていない**
- そのため 2 回目も `INSUFFICIENT` のまま web_search_count **1**（省略条件を満たさない）

extract / `SCAN_CHARS` は今回変更していない。40 シリーズ頁の切り詰めと Ti 部分一致を、推測で「直した」ことにしない。

VRAM 再利用のライブ実証は、既存 extract が 8000 文字内で値を返す **RTX 3080** で行った。

---

## 観測できなかったこと（NOT OBSERVED）

- Cursor のライブ状態
- ライブ G の `llm_summary`（`qwen3:8b` の Event は success だが summary は null）
- ライブ H の構造化 `llm_missing`（空配列。文章上は 4060 不足に言及）
- 価格 Record（extract 対象外）
- RTX 4060 の VRAM Record（ライブ ingest では書いていない）
- 比較経路 A（Chat で Web Search → LLM。本実験では Chat に Matrix を繋いでいないため未実行）
- MATCH の「原因」（verify の cause は既存どおり `NOT_OBSERVED` のことがある）

---

## 接続されていないこと（NOT CONNECTED）

- Chat 通常回答 → Matrix
- Cursor → Local Agent
- ResearchRecord / Research path
- `used price` → ingest（`ingest_skip`）
- 新しい検索エンジン
- Matrix を `AGENT_VISIBLE_DEFAULT` に載せる経路
- 処理タブの会話処理欄（本実験のブラウザ操作では「まだ処理がありません。」Chat ターンを起こしていない）

---

## 推測していないこと（NOT DETERMINED）

- ライブ LLM が JSON `summary` / `missing` を満たさなかった理由（thinking タグの有無などは見ていない）
- RTX 3060 の過去 10 GB の発生原因（前回どおり触らない）
- 40 シリーズ全文から 16 GB を RTX 4060 に付けることが常に誤いかどうか（今回保存していない）

---

## Matrix への影響

`records.jsonl` は追記のみ。削除・上書きなし。既存 8/12 GB は検索に残る。10/16/20 GB は retraction 維持で通常検索に出ない。

実験開始前 sha256: `110ec17959663fa10852e7e5b612f227a032df93de3a5bde7c360419cb0a8bc5`（17630 bytes）  
終了時 sha256: `d69afc8455cbc127753325616189c74738f1e9fa5e30a9849cff69e530eb4269`（20120 bytes）

| record_id | entity | attribute | value | source_url | ingest_id |
|-----------|--------|-----------|-------|------------|-----------|
| mr-ffdef32880e0 | RTX 4060 | cited_by | RTX 4060 | wikipedia RTX_4060 | ing-20260831_010859-3fb0b61f |
| mr-d21c4a06bf21 | RTX 4060 | cited_by | RTX A6000 | wikipedia RTX_A6000 | 同上 |
| mr-5d7dfc5912df | RTX 4060 | cited_by | RTX 4060 | wikipedia RTX_4060 | ing-20260831_010902-bd650716 |
| mr-8dd04432ff72 | RTX 4060 | cited_by | RTX A6000 | wikipedia RTX_A6000 | 同上 |
| mr-68f32e9fa99a | RTX 3080 | cited_by | RTX 3080 | wikipedia RTX_3080 | ing-20260831_011350-38f06688 |
| mr-0b782e02598d | RTX 3080 | VRAM capacity | 12 GB | wikipedia RTX_3080 | 同上 |

既存 RTX 3060 VRAM 8/12 GB 行は変更していない。  
verify MATCH は `verify.jsonl` 追記。records.jsonl は verify では変わらない。

---

## Web Search

ask 経路で実際に `search` Event が付いた回数（ライブ）:

| 実行 | query | 回数 | 結果 |
|------|-------|------|------|
| 4060 VRAM 1 回目 | RTX 4060 | 1 | cited_by のみ。VRAM 不足のまま |
| 4060 VRAM 2 回目 | RTX 4060 | 1 | 同上（省略条件未達） |
| 3080 VRAM 1 回目 | RTX 3080 | 1 | VRAM 12 GB 保存 |
| 3080 VRAM 2 回目以降（CLI / ブラウザ） | — | **0** | Matrix のみ |
| 3060 VRAM / 中古価格 / LLM 比較 | — | **0** | |

合計 **3** 回。2 回目の 3080 では実行していない。

---

## LLM

| 項目 | 実測 |
|------|------|
| 機械経路 A–F | 未使用 |
| モック G/H | `mock-llm`。整理と missing 列挙。Tool 選択なし。検索・保存は機械 |
| ライブ G `RTX 3060とRTX 3080ってどっちがいい？` | 使用した。model `qwen3:8b`。Event success。summary **null**。web 0。decision SUFFICIENT。Record 7 件を機械回答に使用 |
| ライブ H `RTX 3060とRTX 4060ってどっちがいい？` | 使用した。model `qwen3:8b`。summary あり（4060 の情報が取れない旨）。`llm_missing` は空。fallback なし。decision INSUFFICIENT。web 0 |
| Tool 選択 | LLM は Tool を選んでいない。Matrix Search / ingest は `ask_matrix` が実行 |
| Chat ターン | 起こしていない |

---

## 比較（取れた範囲）

| 経路 | 回答 | Web Search | Matrix | 出典 | 再利用 |
|------|------|------------|--------|------|--------|
| A. Web → LLM（Chat） | **NOT CONNECTED**（未実行） | — | — | — | — |
| B. Matrix → 機械 | できた（3060 VRAM / 3080 2 回目） | 0 | 1+ | wikipedia URL | 3080 2 回目で確認 |
| C. Matrix → LLM | ライブ G は SUFFICIENT。summary は NOT OBSERVED | 0 | 2 entity | 既存 Record | Matrix 利用あり |
| D. 不足 → Web → Matrix → 回答 | 3080 1 回目でできた | 1 | 検索→保存→再検索 | RTX_3080 MATCH | 直後の 2 回目は Search なし |

回答品質の優劣は採点していない（主観を書かない）。

---

## 成功条件

| 条件 | 結果 |
|------|------|
| A Matrix だけで答える | 実測 PASS |
| B INSUFFICIENT 検出 | 実測 PASS |
| C 不足時に既存 search_web | 実測 PASS（3080。4060 ライブは Search したが必要 VRAM は未保存） |
| D Validation を通して保存 | 実測 PASS（3080 VRAM。4060 は cited_by のみ） |
| E 保存情報で回答 | 実測 PASS |
| F 2 回目は不要な Search 省略 | 実測 PASS（3080） |
| G LLM が複数 Record を整理 | モック PASS。ライブ summary **NOT OBSERVED** |
| H LLM が不足を要求 | モック PASS。ライブは文章のみ。構造化 missing **NOT OBSERVED** |

判定を PASS にしない理由は G/H のライブ構造化が取れていないこと。機械経路と「検索省略」は成立している。

---

## 次にやらないこと

Matrix を Local Agent の常用知識基盤にする設計、Chat 統合、価格抽出、40 シリーズ全文スキャン、自動訂正は今回の範囲外。
