# Research / Search / Matrix 保存の観測

**日付:** 2026-08-31  
**依頼:** Search / Research / 保存をブラウザから追跡する。Cursor 内部状態の監視はしない。  
**実行主体（コード変更）:** Cursor  
**実行主体（Chat 実測）:** ブラウザ → Local Agent → Local LLM → search_web  
**Run:** `runs/ai_tool/20260831_010000_search_research_observation`  
**Session:** `cs-20260830_155245-1aacd5`  
**モデル:** `qwen3:8b`  
**Server:** `LocalAgentChat/0.10`  
**判定:** `PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**

---

## Phase 1：実装前調査

推測（Git dirty、経過時間、検索後のファイル変更）は使っていない。Session / Event / コード上に存在する情報だけ。

### A. すでに観測できていたもの

- `search_web` が実際に Tool Call されたとき: Session `tools[]`、`tool_select` / `tool_call` / `tool_result`、`web_search` Event
- `observe_tool_result("search_web")`: `query`, `hit_count`, `omitted: ["hits"]`、短い `titles`
- activity 投影: `SEARCH`（query / hit_count / status / actor / source / requested_by / executed_by / correlation_id / model）
- `read_url_text`: `url_fetch` + activity `URL_FETCH`（url, status）。本文 omitted
- 同一ターン複数 Tool は `tools[]` の順。`correlation_id` はターン単位 `ac-...`
- `final_answer`
- 毎ターン `research_record` Event（`saved=False` 固定）と activity `RESEARCH_WRITE`（`NOT_OBSERVED`）
- Chat Session JSON の `save_session` は会話状態の永続化であり、Research / Matrix ではない

### B. 取得できるが Event / UI が薄かったもの

- `search_web` 戻り値の `hits` 本文（意図的に Event 非保存。今回も保存しない）
- `backends_tried`, `fetch_limit`, `return_limit`, `candidates_collected`
- `enrich_web_tool_result` が付ける `web_status.overall`（LLM には渡る）
- 生 `web_search` Event に `hit_count` が無かった
- 「処理を見る」が search を `[SEARCH]` とラベルしていなかった

### C. 現在も取得不能なもの

- Agent Chat からの ResearchRecord / Matrix 実書き込み（`research_store_from_session()` は空 store。`research_saved` は常に `False`）
- Cursor 内部 Search / 未保存バッファ / 思考
- Cursor → Local Agent 接続
- 「LLM が情報を整理した」独立 Event
- 検索後のファイル変更からの因果 `Search → Matrix Write`
- Chat 経路以外の Cursor 案件 Research を、この Session の Local Agent 実行と結ぶこと

---

## 実装方針（最小）

新しい Core は作っていない。既存 Event / Session / Timeline に、観測済みフィールドと表示ラベルだけを足した。

存在しない RESEARCH PROCESSING / WRITE は生成しない。無い段階は `NOT OBSERVED`。

---

## 実測（REAL。Cursor が報告しただけではない）

Session `cs-20260830_155245-1aacd5` / モデル `qwen3:8b`

| 項 | 入力 | 観測 |
|----|------|------|
| A | こんにちは | Tool / Search なし。WRITE: NOT OBSERVED。cid `ac-20260830_155342-83568300` |
| B | RTX 3060 を search_web で調べて | `TOOL_CALL search_web`。query `NVIDIA RTX 3060 公式 VRAM容量`。hit_count **0**（空検索。Event は存在）。SEARCH_FAILED。cid `ac-20260830_155505-20b1ca01` |
| C | 同一返答で search_web を 2 回 | 同一 cid `ac-20260830_155701-4cc657e2`。search_index 1 `Python 3.14 release date` / 2 `Ollama qwen3 model size` |
| D | Search → Answer | `final_answer` が同じ cid に存在。LLM がヒット 0 件と回答 |
| E | 実保存があるときだけ WRITE | Agent Chat に保存経路が無い。WRITE Event（saved=true）は **出なかった** |
| F | 保存なし | `[WRITE] NOT OBSERVED` / `research_record.saved=false` |
| G | Actor / Source / Model | LLM: `LOCAL_LLM` / `ollama` / `qwen3:8b`。Search/Tool: `LOCAL_AGENT` / `session`。Cursor live は混ぜていない |

空検索は「Search が無かった」ではない。`search_web` は実行され、`hit_count: 0` と `omitted: hits` が残った。

ブラウザ表示（処理 / 開発タブ）:

```text
User
↓
Local Agent
↓
Local LLM : qwen3:8b
↓
[TOOL_CALL] search_web
query: ...
hit_count: 0
↓
[SEARCH]
query / hit_count / search_index
↓
[SEARCH_RESULT]
status: error
web_status: SEARCH_FAILED
omitted: hits
↓
[RESEARCH / PROCESSING] NOT OBSERVED
↓
[WRITE] NOT OBSERVED
↓
Final Answer
```

---

## Cursor Report と REAL の分離

| 層 | 内容 |
|----|------|
| REAL | 上記 Session Event / ブラウザ表示 / `runs/chat_ui/sessions/cs-20260830_155245-1aacd5.json` |
| CURSOR REPORT | 本ファイルと pytest 56 passed（`tests/ai_tool/chat_interface`）。コード変更の実行主体は Cursor |
| MACHINE TEST | **NOT AVAILABLE**（pytest.xml / junit.xml なし） |

この表示機能そのものの開発主体は **CURSOR**。  
ブラウザから Local Agent が search_web を走らせた実行主体は **LOCAL_AGENT / LOCAL_LLM**。混同しない。

---

## 変更したファイル

- `ai_tool/chat_interface/tool_observation.py` — backends / web_status_overall 等。hits 本文は omitted
- `ai_tool/chat_interface/agent_turn.py` — `web_search` に hit_count。pipeline に research_saved
- `ai_tool/chat_interface/events.py` — SEARCH / SEARCH_RESULT / WRITE NOT_OBSERVED ステップ
- `ai_tool/chat_interface/activity.py` — SEARCH に search_index / backends / layer=real
- `ai_tool/chat_interface/static/app.js` — 処理を見る / 開発タブ表示。`hit_count: 0` が消えないよう escapeHtml 修正
- `ai_tool/chat_interface/server.py` — `LocalAgentChat/0.10`
- `tests/ai_tool/chat_interface/test_activity.py`
- `tests/ai_tool/chat_interface/test_tool_observation.py`

## 未変更ファイル

- `agent.py`（大規模変更なし）
- `pipeline.yaml`
- Production Workflow
- `search_web` / `read_url_text` 本体
- Cursor API / ライブ監視
- ResearchRecord / Matrix 保存経路（存在しないため作っていない）

---

## 完了報告 13 項

1. **観測できる Research / Search / Write:** Search は実際の `search_web` のみ。Write は毎ターン `NOT_OBSERVED`（saved=false）。Research processing 独立 Event は無い。
2. **観測できないもの:** Cursor 内部、未保存バッファ、思考、Matrix 実書き込み、Cursor→Local Agent 接続、Search→Write 因果。
3. **変更ファイル:** 上記。
4. **未変更ファイル:** 上記。
5. **実際の Event:** `tool_call` / `tool_result` / `web_search` / `llm` / `final_answer` / `research_record(saved=false)`。activity `SEARCH` / `RESEARCH_WRITE`。
6. **correlation_id:** A `ac-20260830_155342-83568300` / B `ac-20260830_155505-20b1ca01` / C `ac-20260830_155701-4cc657e2`
7. **actor / source / model:** Local LLM = `local_llm` / `ollama` / `qwen3:8b`。Tool/Search = `local_agent` / `session`。requested_by=`user`。
8. **ブラウザ表示:** 会話の「処理を見る」、処理タブ、開発タブ「Local Agent 処理」。SEARCH query/hit_count/search_index、WRITE NOT OBSERVED。
9. **Cursor Report テスト:** pytest `tests/ai_tool/chat_interface` **56 passed**。これは Cursor 報告であり機械 XML ではない。
10. **Machine Test:** **NOT AVAILABLE**
11. **Cursor → Local Agent:** **NOT_CONNECTED**
12. **Cursor live status:** **NOT OBSERVED**
13. **Production 変更:** **なし**
