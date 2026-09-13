# Tool 内部呼び出し観測の最小検証

**日付:** 2026-08-31  
**依頼:** 既存 Tool が内部で別の Tool / 関数を呼んだ事実を、再実行・推測なしで記録・表示できるか確定する  
**実行主体（調査・Report）:** Cursor  
**実行主体（Chat 実測）:** ブラウザ → Local Agent → Local LLM → Tool  
**Run:** `runs/ai_tool/20260831_014200_tool_internal_call_observation`  
**Session:** `cs-20260830_163757-0e5d36`  
**モデル:** `qwen3:8b`  
**Server:** `LocalAgentChat/0.11`  
**判定:** `PARTIAL_PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Research: **NOT CONNECTED**  
Matrix Write: **NOT OBSERVED**  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**

成功条件は「内部 Tool を必ず観測可能にすること」ではない。現行アーキテクチャで、どこまで実際の Tool 内部処理を観測できるかを確定すること。

観測のための Tool 再実行はしていない。コードから子 Tool 名を推測して Event を作っていない。

---

## Phase 1：実コード調査

### A. `get_system_summary` の内部呼び出し

`tools/system/summary/get_system_summary.py` は Registry / `_execute_agent_tool` を通さない。Python 関数を直接呼ぶ。

```text
get_system_summary()
  → get_system_time()     # import した関数
  → get_cpu_status()
  → get_memory_status()
  → get_gpu_status()
  → return { sections: { time, cpu, memory, gpu }, observation_source: composed }
```

戻り値のキーは **`time` / `cpu` / `memory` / `gpu`**。関数名 `get_system_time` 等は戻り値に無い。

### B. 観測可能な実行単位

Chat の Event 生成点は `agent_turn.py` の `_execute_agent_tool` の前後だけ。

| 単位 | 親（LLM が選んだ Tool） | 子（合成関数内） |
|------|-------------------------|------------------|
| `tool_call` Event | あり | なし |
| `log_tool_call` | 親名のみ | なし |
| 独自 `correlation_id` | ターンの `ac-...` を共有 | なし |
| 独自 `execution_id` | なし（ターン相関のみ） | なし |
| `actor` / `source` | `local_agent` / `session` | 記録されない |

子関数は親の Python スタック上で動くだけであり、親・子を関連付ける execution identity は無い。

### C. Event 生成位置

- **実行前:** `tool_select` / `tool_call`（LLM が返した Tool 名のみ）
- **実行後:** 戻り値に `sections` があるときだけ `compose`（キー名。関数名ではない）→ `tool_result`

`TOOL_INTERNAL_CALL` 型はコードに存在しない。

### D. 限界の分類

| 情報 | 判定 |
|------|------|
| 親 Tool の TOOL_CALL | **REAL** |
| 親 Tool の TOOL_RESULT | **REAL** |
| 子 Tool の実際の呼び出し（独立 Event） | **NOT OBSERVED** |
| 子 Tool の戻り値（親 `sections` 内のスカラー） | **OBSERVED RESULT** |
| 子 Tool の execution identity | **NOT OBSERVED** |
| Research | **NOT CONNECTED** |
| Matrix Write | **NOT OBSERVED** |
| Cursor live | **NOT OBSERVED** |

`time` → `get_system_time` はソースを読めば分かるが、実行結果には関数名が無い。推測で子 Event を足すことは禁止したため **NOT OBSERVED**。

---

## Phase 2：最小実装

観測可能な実行コンテキストから、独立した内部呼び出しを安全に記録できない。

そのため **観測基盤・既存 Tool 本体・`agent.py` / `pipeline.yaml` は変更していない。**

偽の `[INTERNAL]` / `[TOOL_INTERNAL_CALL]` は出さない。既存の COMPOSE 表示を維持する。

```text
[TOOL_CALL] get_system_summary
[COMPOSE] sections: time, cpu, memory, gpu
independent_tool_calls: false
[TOOL_RESULT] ...
```

理想形（個別呼び出しが実測できる場合）は今回の実行経路では到達不能。

---

## Phase 3：ブラウザ実測

Session `cs-20260830_163757-0e5d36`。観測のための再実行はしていない。

| 項 | 入力 | Tool Call | Event | 表示 |
|----|------|-----------|-------|------|
| A | 今のPCのシステム状態を教えて | `get_system_summary` のみ | `tool_call` ×1 / `compose` / `tool_result`。子名なし | `[COMPOSE] sections: time, cpu, memory, gpu`。`[INTERNAL]` なし |
| B | GPUの状態だけ教えて | `get_gpu_status` のみ | `compose` なし。親単独 | `[Tool Call] get_gpu_status` → `[Tool Result]` |
| C | さっきのシステム状態のメモリ使用量をもう一度教えて | **なし** (`tools: []`) | `tool` status `none` | 「Tool は使いませんでした」。履歴から回答 |

C の回答は A の `used_mb: 29696` / 45% と一致。Tool は再実行されていない。

---

## Phase 4：観測結果の分類

### REAL

- A の親 `TOOL_CALL` / `TOOL_RESULT`（`get_system_summary`）
- A の `COMPOSE`（戻り値の `sections` キー `time, cpu, memory, gpu`）
- B の親 `TOOL_CALL` / `TOOL_RESULT`（`get_gpu_status`）
- 各ターンの `correlation_id` / `actor` / `source` / `model`
- C で Tool が無かったこと

### OBSERVED RESULT

- A の `sections.time` / `cpu` / `memory` / `gpu` のスカラー（例: `used_mb: 29696`, GPU temperature 62）
- B の GPU スカラー（temperature 61, utilization 97, vram_used 7828）
- C の回答が A のメモリ値を再利用したこと

### NOT OBSERVED

- 子の独立 `TOOL_CALL` / `TOOL_INTERNAL_CALL`
- 子の独立戻り値 Event
- 子の `execution_id` / 子専用 `correlation_id`
- `[INTERNAL] get_system_time` 等の表示
- Cursor live status

### NOT CONNECTED

- Chat → ResearchRecord
- Cursor → Local Agent

---

## UI

「処理を見る」「開発」タブの構造は維持。内部呼び出しが実測できないため `[INTERNAL]` は出していない。

開発タブの当該 Session 処理にも `[COMPOSE] sections: time, cpu, memory, gpu` と `independent_tool_calls: false` が出る。`[TOOL_INTERNAL_CALL]` は無い。

Research / Matrix / Cursor live の既存表示は維持。

---

## Test

新規テストは追加していない。既存 `tests/ai_tool/chat_interface/test_tool_observation.py` が今回の判定を固定している。

| 条件 | 既存テスト |
|------|------------|
| A. 親の既存観測が壊れない | `test_gpu_observation_from_real_execute` / compose テスト |
| B. 内部呼び出しが実測可能な場合に親と区別 | 現行では実測不能。compose は親 `tool_call` と別 Event |
| C. 観測できない場合に偽の内部 Event を生成しない | `get_system_time not in obs` / `tool_call` count == 1 |
| D. correlation_id / actor / source | compose `executed_by == local_agent` |
| E. Chat / Tool / Search 観測 | 同ディレクトリの既存テスト |

Cursor Report: `tests/ai_tool/chat_interface` **56 passed**（実行主体 Cursor。Local Agent 実行ではない）。

JUnit XML は無い。Machine Test: **NOT AVAILABLE**。

---

## 変更範囲

| ファイル | 今回 |
|----------|------|
| `agent.py` / `pipeline.yaml` / 既存 Tool 本体 | 未変更 |
| Research / Matrix / Cursor API | 未変更 |
| `events.py` / `activity.py` / `agent_turn.py` / `tool_observation.py` / UI | 未変更（偽 INTERNAL を足さないため） |
| Report / Run | 本ファイルと `runs/ai_tool/20260831_014200_tool_internal_call_observation` |
