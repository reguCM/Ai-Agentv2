# Research / Matrix 実経路の内部観測

**日付:** 2026-08-31  
**依頼:** 既存の Search → Research → Matrix 経路が実コードにあるかを確認する。無い経路は作らない。  
**実行主体（調査・表示変更）:** Cursor  
**Chat 実測:** 既存 Session の再表示のみ。Research を無理に呼び出していない。  
**Run:** `runs/ai_tool/20260831_011500_research_matrix_path_audit`  
**Session（表示確認）:** `cs-20260830_155245-1aacd5`  
**Server:** `LocalAgentChat/0.11`  
**判定:** `NOT_CONNECTED`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**

成功条件は Research / Matrix が使えるようになることではない。経路の有無を分けて観測すること。

---

## Phase 1–2：分類

| 項目 | 判定 | 根拠 |
|------|------|------|
| Search が実際に実行された | **REAL** | Chat `search_web` → `tools.system.network.search_web`。前回 Session でも観測済み |
| Research 処理が実際に呼ばれた | **NOT_CONNECTED** | `ResearchRecord` / `ResearchStore.add_from_run` / `run_standard_workflow` は TDA に存在する。Chat は呼ばない |
| Matrix Write が実際に呼ばれた | **NOT_OBSERVED** | Research 保存先としての Matrix Write 関数・Registry Tool は無い |
| Search のあとにファイルが変わった | 因果に使わない | 未使用 |

### A. Chat から実行可能

```text
User → Local Agent → Local LLM → search_web → Search Result → Final Answer
```

これだけ。`search_web` は材料化しない（本体コメントどおり）。`build_research_record` を呼ばない。

### B. コードはあるが Chat から到達しない（NOT CONNECTED）

| 実装 | 場所 | 呼び出し元 |
|------|------|------------|
| `ResearchRecord` / `ResearchStore` | `ai_tool/experimental/development_assistance/research_record.py` | TDA harness |
| `build_research_record` / `add_from_run` | 同上 | `standard_workflow.py` の FULL_WEB_RESEARCH 時 |
| `run_standard_workflow` | `standard_workflow.py` | `run_tda_*` / experimental harness のみ |
| `research_store_from_session` | `chat_session.py` | **常に空の `ResearchStore()` を返す** |
| Registry `research_tool` / `research_executor` / `web_research` | `registry/tools.json` | Tool Builder。`AGENT_VISIBLE_DEFAULT` に無い |

`agent.py` も `run_standard_workflow` を呼ばない。Chat `agent_turn.py` も呼ばない。

### C. 実装が無い（NOT OBSERVED）

- Research 保存先としての **Matrix Write**（Registry に matrix 名の Tool なし）
- `search_web` → `ResearchRecord` の呼び出し
- `Research` → `Matrix Write` の呼び出し
- Chat が通る `RESEARCH_PROCESS` / `RESEARCH_RESULT` 実行

別名の「matrix」（capability / version / environment / test matrix）は評価用ドキュメント・ハーネスであり、Chat の整理結果保存先ではない。

### 呼び出し関係（実コード）

```text
Chat search_web ──×──► ResearchRecord     NOT CONNECTED
TDA run_standard_workflow ──► ResearchStore.add_from_run   （Chat 外）
ResearchRecord ──×──► Matrix Write        NOT OBSERVED
```

別系統: `tools.system.tool_builder.research.executor` は Tool Builder 用 `research.web.search_web` を呼ぶ。Agent 公開 `search_web` とは明示的に分離されている。

---

## 実測で通った経路

Research 系入力で無理に呼び出していない（到達不能がコード上確定しているため）。

既存 Session を 0.11 で再表示:

```text
User → Local Agent → Local LLM → search_web → SEARCH_RESULT → Final Answer
Research: NOT CONNECTED
Matrix Write: NOT OBSERVED
```

Search 後に Research Process / Matrix Write が走ったようには表示していない。

---

## Event に追加した項目

実行したかのように見せる `RESEARCH_PROCESS` / `RESEARCH_RESULT` / 成功した `MATRIX_WRITE` は **作っていない**。

追加したのは到達不能の観測だけ。

- activity `RESEARCH_PATH` `status: NOT_CONNECTED`（Chat が TDA Research を呼ばなかった）
- activity 要約 `research_path` / `matrix_write`
- pipeline `research_path` ステップ
- 表示の分離: Research vs Matrix Write

既存 `RESEARCH_WRITE` `NOT_OBSERVED` と Search 観測は維持。Search hits 本文は保存しない。

---

## ブラウザ

処理を見る / 開発タブ:

- `[RESEARCH] NOT CONNECTED`
- `[MATRIX_WRITE] NOT OBSERVED`
- 開発: `Research: NOT_CONNECTED　Matrix Write: NOT_OBSERVED`
- `[RESEARCH_PATH]` 行あり。`RESEARCH_PROCESS` 実行行は無し

---

## 完了報告 14 項

1. **Research 実装:** `ai_tool/experimental/development_assistance/research_record.py`（Record/Store）。書き込みは `standard_workflow.py` の `add_from_run`。Registry の Tool Builder research_* は別系統。
2. **Matrix 実装:** Research 保存用の Matrix Write は **無い**。評価用 matrix のみ。
3. **Search → Research:** Chat 経路には **呼び出し無し**（NOT CONNECTED）。
4. **Research → Matrix:** **呼び出し無し**（NOT OBSERVED）。
5. **Chat → Local Agent から到達:** Search のみ可。Research/Matrix は不可。
6. **実測経路:** Search → Final Answer。Research は未呼び出し。
7. **Event 追加:** `RESEARCH_PATH` NOT_CONNECTED。実行イベントは追加していない。
8. **ブラウザ:** 上記ラベル。
9. **残る NOT OBSERVED / NOT CONNECTED:** Research 経路 NOT CONNECTED。Matrix Write NOT OBSERVED。Cursor → Local Agent NOT CONNECTED。Cursor live NOT OBSERVED。
10. **Cursor pytest:** `tests/ai_tool/chat_interface` **56 passed**（Cursor Report。機械 XML ではない）。
11. **Machine Test:** **NOT AVAILABLE**
12. **Run / Report:** `runs/ai_tool/20260831_011500_research_matrix_path_audit` / 本ファイル
13. **変更:** `activity.py`, `events.py`, `agent_turn.py`, `static/app.js`, `server.py`（0.11）, `test_activity.py`, `test_tool_observation.py`
14. **未変更:** `agent.py`, `pipeline.yaml`, Production, `search_web` 本体, 既存 Tool 本体, `research_record.py`, `standard_workflow.py`, Cursor API, Research/Matrix 新規機能

---

## テスト

| 項 | 結果 |
|----|------|
| A Research 実行 Event | 経路が Chat に無いため、実行 Event は出さない（正しい） |
| B Matrix Write 成功/失敗 | 関数が無いため観測対象外。NOT OBSERVED |
| C 同一 correlation_id | Search は既存どおりターン単位。Research 実行が無いので Search/Research/Matrix の三者揃いは無い |
| D 存在しない処理を生成しない | `RESEARCH_PROCESS` / `RESEARCH_RESULT` 無し |
| E Search 回帰 | 既存 search_web 観測テスト通過 |
