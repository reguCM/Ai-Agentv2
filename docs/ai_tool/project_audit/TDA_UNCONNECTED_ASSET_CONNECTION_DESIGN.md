# 未接続資産の実用経路設計

**日付:** 2026-08-31  
**依頼:** コードはあるが Local Agent の通常 Chat 経路に未接続の機能を調査し、どう使うかを設計する。承認まで実装しない。  
**実行主体:** Cursor（調査・設計のみ）  
**Chat 実測:** 今回なし（既存 Session / 既存 Report を根拠にする。観測のための Tool 再実行はしていない）  
**Run:** `runs/ai_tool/20260831_080000_unconnected_asset_connection_design`  
**判定:** `ARCHITECTURE_READY`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Research: **NOT CONNECTED**  
Matrix Write: **NOT OBSERVED**（関数が無い）  
Production 変更: **0**  
Registry / `AGENT_VISIBLE_DEFAULT` / Chat UI: **未変更（設計のみ）**

成功条件は未接続機能を公開することではない。差を分類し、接続方針を決めること。

---

## 現在の実行経路（確認済み）

### 通常 Chat（実用経路）

```text
User（ブラウザ）
  → Chat UI POST /api/chat
  → run_chat_turn（agent.py は import しない）
  → Local LLM（tools.system.llm.chat / Ollama）
  → LLM が Tool を選択
  → _execute_agent_tool（Registry + Chat 専用 trust）
  → TOOL_RESULT を LLM へ戻す
  → Final Answer
```

観測: ターン単位 `correlation_id`、`requested_by=user`、Tool は `actor=local_agent` / `source=session`、LLM は `actor=local_llm` / `source=ollama`。

### いま通っている実用 Tool

`AGENT_VISIBLE_DEFAULT`（プロンプトと Chat trust の auto_allow）:

`get_gpu_status` / `get_gpu_processes` / `cpu_status` / `get_cpu_status` / `get_system_summary` / `search_web` / `read_url_text`

ブラウザ実測済み（既存 Session）: `get_system_summary`、`get_gpu_status`、`search_web`。`read_url_text` は公開済み。単独実測は本設計では再実行していない。

### Search の現在形（基準）

```text
User → Local Agent → Local LLM → search_web → Search Result → Answer
```

`search_web` は Discovery のみ。材料化しない。`build_research_record` を呼ばない。

LLM は同一ターンで `read_url_text` を続けて選べる（複数 Tool round）。これは既に Tool 列であり、Research Workflow ではない。

### Chat が TDA を「触っている」ように見えるが接続していない点

- `research_store_from_session()` は **常に空の `ResearchStore()`**
- `_memory_overlay` は Experimental Adapter の表示用。ResearchRecord 全件は LLM に渡さない
- `classify_request` の route `research` / `development` はラベルのみ。実行は `_chat_turn` のまま（`tool_creation` だけ別）
- 毎ターン `research_record` Event は `saved=False` 固定。実行したように見せない

### Production `agent.py`

Chat とは別ループ。`visibility=agent` を Ollama へ出す。プロンプトに `list_files` / `read_file` / `search_files` が残っているが、**現行 `registry/tools.json` には無い**。本設計は Chat 実用経路を対象にする。`agent.py` は変更しない。

---

## 層の定義（混同しない）

| 層 | 意味 |
|----|------|
| コード存在 | リポジトリに実装がある |
| Registry | `registry/tools.json` にエントリがある |
| Agent 公開（Registry） | `visibility: agent`。Ollama schema の候補 |
| Chat 公開意図 | `AGENT_VISIBLE_DEFAULT` と SYSTEM_PROMPT に載る |
| 実行可能 | Chat が選べば `_execute_agent_tool` が関数を呼ぶ（trust の confirm は Chat では `"y"` 固定） |
| 実測済み | ブラウザ Chat で LLM が選び、Session Event がある |

**スキーマ漏れ:** Chat の `llm_tools` は `build_production_agent_tools()` のため **Registry `visibility=agent` の全件**を LLM に渡す。`get_system_time` / `get_memory_status` はプロンプトに無いが schema には載る。選ばれれば実行される。これは「公開した」とは数えない。意図した公開集合は `AGENT_VISIBLE_DEFAULT` の 7 件。

---

## 未接続・接続済み一覧

凡例: 実測は Chat ブラウザ。Cursor pytest / 開発タブ案件は Cursor 作業であり Local Agent 実測ではない。

### 1. Observation Tool

| 機能 | コード | Registry | Agent公開 vis=agent | Chat公開意図 | 実行可能 | Chat実測 | 現在の用途 | 分類 |
|------|--------|----------|---------------------|--------------|----------|----------|------------|------|
| get_gpu_status | あり | あり | あり | あり | あり | あり | 単体 GPU 実測 | A 維持 |
| get_gpu_processes | あり | あり | あり | あり | あり | （本設計で再測せず） | GPU プロセス | A 維持 |
| get_cpu_status | あり | あり | あり | あり | あり | summary 内 OBSERVED RESULT | 構造化 CPU | A 維持 |
| cpu_status | あり | あり | あり | あり | あり | 単独実測なし | Legacy 文字列 | D 廃止候補（公開は維持してよい） |
| get_system_summary | あり | あり | あり | あり | あり | あり | 時刻/CPU/メモリ/GPU 合成 | A 維持 |
| get_system_time | あり | あり | あり | **なし** | schema 経由なら可 | 子呼び出し NOT OBSERVED。Cursor 開発案件としては PASS | summary の部品 | C 部品。Chat 単独公開はしない |
| get_memory_status | あり | あり | あり | **なし** | schema 経由なら可 | 同上 | summary の部品 | C 部品。単独公開は価値があれば後で（GPU 単独の対） |

### 2. Search / Fetch（同一機能にしない）

| 機能 | コード | Registry | Chat公開 | 実行可能 | Chat実測 | 現在の用途 | 分類 |
|------|--------|----------|----------|----------|----------|------------|------|
| search_web（Agent 公開） | `tools.system.network.search_web` | vis=agent | あり | あり | あり | Discovery。hits 本文は Event 非保存 | A 維持 |
| Search 結果の整理 | LLM の最終回答 | なし | — | — | 回答として観測 | Tool ではない | A 維持（LLM 責務） |
| read_url_text | `ai_tool.experimental.read_url` だが Registry 登録済み | vis=agent | あり | あり | 公開済み。本設計では再測せず | Fetch / Evidence | A 維持 |
| Tool Builder `research.web.search_web` | あり | pipeline 系 | なし | Chat から呼ばない | なし | MS Learn 等。公開 search_web とは分離 | C |
| ファイル保存（Chat Session JSON） | `save_session` | — | — | 会話状態のみ | あり | 会話永続化。Research ではない | A 維持 |
| ファイル保存（Research / Matrix） | **無い** | なし | なし | なし | なし | — | D。作らない |

### 3. Research / Matrix（実体を分けた）

| 機能 | コード存在 | Registry | Chat接続 | 実行 | 実測 | 実体 | 分類 |
|------|------------|----------|----------|------|------|------|------|
| ResearchRecord | `research_record.py` | なし | NOT CONNECTED | TDA harness / `add_from_run` のみ | Chat では未実行 | TDA 用 envelope（candidates / version_facts / license） | C |
| ResearchStore | 同ファイル。in-memory | なし | Chat は空 store | TDA のみ | なし | インデックス。Knowledge Core ではない | C |
| build_research_record | あり | なし | 呼ばない | TDA | なし | run_result から Record を組む | C |
| run_standard_workflow | `standard_workflow.py` | なし | 呼ばない | `run_tda_*` | なし | Tool 開発支援 Workflow | C |
| Facet discovery / reuse / gate | development_assistance 多数 | なし | overlay 表示のみ | TDA | なし | TDA Operating Model | C |
| classify route `research` | `classify.py` | — | ラベルのみ。実行は chat | — | 意図表示 | 誤って Research 実行とは言えない | D（接続しない） |
| Registry `research_tool` 等 7 件 | あり | **pipeline（vis 無し）** | AGENT_VISIBLE に無い | Tool Builder | Chat なし | blocked 実装の調査材料 | C |
| Matrix Write（調査結果の保存先） | **無い** | なし | — | — | NOT OBSERVED | 評価用 capability matrix は別名 | D。新設しない |
| Chat → Search → ResearchRecord | 呼び出し無し | — | NOT CONNECTED | — | — | — | D。接続しない |
| ResearchRecord → Matrix | 呼び出し無し | — | — | — | NOT OBSERVED | — | D |

### 4. Tool Builder / 開発支援

| 機能 | コード | Registry | Chat | 分類 |
|------|--------|----------|------|------|
| Chat route `tool_creation` | `create_tool_proposal` を呼ぶ | proposal は pipeline | 設計材料のみ。Registry 書込なし | C（Chat に提案だけ残す。公開 Tool にしない） |
| create_tool_implementation 等 | あり | pipeline | 出さない | C |
| register_tool | あり | pipeline | プロンプトが禁止 | C |
| development_job | Session 上の薄い記録 | — | 開発タブ用。Cursor 起動しない | C |
| 開発タブ / Run / Report / Test 表示 | Chat UI | — | 読み取り。Cursor 成果物 | C |

### 5. Experimental（Registry 外または別系統）

| 機能 | コード | Registry | 分類 |
|------|--------|----------|------|
| scoped_read | `ai_tool/experimental/scoped_read` | なし（catalog draft） | D / C。Chat に出さない |
| experimental overlay | `_EXPERIMENTAL_AGENT_TOOL_IDS` 空 | read_url は Registry へ卒業済み | 維持（空） |
| UR program validator | experimental | なし | C 専用ドメイン |
| conversation_resolution | experimental | なし | C |
| mechanical_verification | experimental | なし | C |
| liba_demo_tool | experimental | なし | C / D |
| MCP catalog `mcp:get_current_time` | catalog | tools.json と別 | D |
| list_files / read_file / search_files | `tools/file/workspace` | **現行 tools.json に無い**。trust collection と agent.py プロンプトに残渣 | D。Chat へ再公開しない |

---

## 「何に使うべきか」

Local Agent の通常利用は **今の PC 状態を測る** と **Web を探して答える** である。TDA Standard Workflow は **Tool を作る前の技術調査**（候補・版・ライセンス・再利用）である。後者を前者に載せると、ユーザーの「調べて」が Tool 開発案件になる。

Chat で調査依頼が必要なとき、既に:

```text
search_web →（必要なら）read_url_text → LLM が回答
```

があり、続きの質問は **会話履歴** で足りる（メモリ再質問で Tool 無しが実測済み）。TDA ResearchRecord のフィールド（technology_candidates 等）は汎用 Web 回答の保存先として型が違う。

Matrix は保存先 Tool として存在しない。Session JSON が会話を保存している。調査結果専用ストアは、読み出す Chat 経路が無いなら作らない。

---

## Search → Research → Matrix の比較

前提: 毎 Search の後に自動 Research / Write はしない。実行していない処理を出さない。

| 案 | 責務 | 観測 | 判定 |
|----|------|------|------|
| 0. 現状維持 | search_web は Discovery。整理は LLM。保存は Session 会話 | SEARCH / TOOL_* のみ。RESEARCH NOT CONNECTED | **推奨（当面）** |
| 1. search_web に Research を内包 | Tool 契約破壊（材料化しない） | 親1回に内部処理が埋もれる | 却下 |
| 2. 別 Tool `research_*` を Chat 公開し LLM に順番選択 | TDA Record を Chat に出すことになる | TOOL_CALL は追えるが型が違う | 却下（作ったから公開） |
| 3. Local Agent が Search 後に必ず Workflow | ユーザー Q&A を TDA 化する | 未実行 WRITE を出しやすい | 却下 |
| 4. Matrix を Tool にする | 保存先が無いのに Tool を先に作る | 偽 WRITE | 却下 |
| 5. Matrix を Store 層にする | 正しい層だが、Chat の読取需要が無い | WRITE は Store API の実呼び出し時だけ | 需要が出るまで D |
| 6. 将来の明示 Workflow「調査して残す」 | ユーザーが保存を求めたときだけ。**新しい Chat 用 envelope**（TDA ResearchRecord を流用しない） | RESEARCH / WRITE は実際の関数呼び出し後だけ | 保留。今は実装しない |

get_system_summary（既存 Tool の合成）と Search→Research→Write は別物である。前者は同期の観測合成。後者は段階・保存・再利用があり **Workflow** 向き。Chat の既定には置かない。

---

## 観測条件（接続する場合の前提）

壊さない:

- `requested_by` / `executed_by` / `actor` / `source` / `model` / `correlation_id`
- 実行した TOOL_CALL / TOOL_RESULT / SEARCH だけ表示
- RESEARCH / WRITE は **実際に関数が呼ばれたときだけ**
- Cursor 内部を Local Agent に見せない
- Git dirty や「Search のあとファイルが変わった」から因果を作らない
- 子 Tool 名をソース推測で INTERNAL Event にしない

将来 Workflow を足すなら、段階ごとに Event を分け、未実行は `NOT CONNECTED` / `NOT OBSERVED` のままにする。巨大 Tool 1 本にまとめない。

---

## 責務

| 主体 | やる | やらない |
|------|------|----------|
| Cursor | 調査・実装・pytest・Report | Chat の Tool 選択・実行を自分の成果にしない |
| Local Agent | 要求の受信、trust、Tool 実行、Event | TDA harness、Cursor ライブ |
| Local LLM | Tool 選択、回答の整理 | 全 Memory 整理、未渡与の ResearchRecord 利用 |

「Cursor が作った」と「Local LLM が選んで使った」は別列で残す。

---

## 推奨案

1. **Chat 実用経路は現状の 7 Tool + 会話履歴で足りる。** Search のあとに TDA Research / Matrix を接続しない。
2. **TDA ResearchRecord / standard_workflow / Facet 系は Cursor 専用の Tool 開発支援のまま残す。**
3. **Matrix Write は作らない。** 需要は Session 履歴と、将来の明示保存 Workflow で足りるか先に決める。
4. **最初の実装スライスは新機能ではなく漏れの閉鎖。** Chat の `llm_tools` を `AGENT_VISIBLE_DEFAULT` に一致させる。プロンプト・trust・schema を同じ 7 件にする。`get_system_time` / `get_memory_status` は vis=agent のまま Registry に置き、合成の部品とする（Production agent.py は触らない）。
5. **get_memory_status の Chat 単独公開は任意の第2スライス。** GPU 単独と同じユーザー価値があるときだけ。作ったからではない。

---

## 推奨する最小実装スライス（承認後）

**Slice 0（推奨・最小）:** Chat `run_chat_turn` が LLM に渡す tools を `AGENT_VISIBLE_DEFAULT` でフィルタする。trust とプロンプトと一致させる。新 Tool・Research・Matrix・UI 構造は触らない。観測回帰テストを足す。

まだやらない: `AGENT_VISIBLE_DEFAULT` への time/memory 追加、search_web 変更、ResearchRecord 接続、Matrix 新設、agent.py / pipeline.yaml。

---

## 今回実装しないもの

- 上記すべて（本案件は設計のみ）
- Registry 公開集合の変更
- Chat UI / Timeline / Search 本体 / 既存 Tool 本体

---

## 次の案件候補（承認待ち）

1. Slice 0: Chat schema を `AGENT_VISIBLE_DEFAULT` に揃える  
2. （任意）`get_memory_status` を Chat 公開し、メモリ単独の LLM 選択を実測  
3. （任意）`cpu_status` をプロンプトから外し `get_cpu_status` へ寄せる（廃止は急がない）  
4. Research/Matrix を Chat に繋ぐ案件は **出さない**（本設計で却下）

---

## 停止条件

1. 未接続資産を一覧化した  
2. 現在の実行経路を確認した  
3. Research / Matrix の実体と未実装を分けた  
4. 複数案を比較した  
5. 最小スライスを決めた  
6. 実装していない  

**判定: ARCHITECTURE_READY**
