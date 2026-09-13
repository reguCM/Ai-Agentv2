# get_system_summary を Local Agent 公開集合へ 1 件追加（実経路）

**日付:** 2026-08-31  
**依頼:** `get_system_summary` のみを Local Agent の公開 Tool 集合へ追加し、ブラウザ Chat から LLM が自律選択・実行できるかを実測する  
**実行主体（コード変更）:** Cursor（Local Agent はこの接続変更・実装をしていない）  
**実行主体（Chat 実測）:** ブラウザのユーザー入力 → Local Agent → Local LLM → Tool  
**Run:** `runs/ai_tool/20260831_002000_get_system_summary_agent_exposure`  
**Session:** `cs-20260830_151119-eb42b3`  
**モデル:** `qwen3:8b`（Chat UI で選択。`pipeline.yaml` は未変更）  
**Server:** `LocalAgentChat/0.8`  
**Production 変更:** 0（`agent.py` / `pipeline.yaml` / 既存 Tool 本体 / `get_system_summary` 本体 / Registry 構造 は未変更）  
**判定:** `PARTIAL_PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**

---

## 判定理由

公開・選択・実行・回答までは確認できた。一方で Event 上の Tool Result は `get_system_summary` について `{ok, status, error}` までしか見えず、内部子 Tool（`get_system_time` / `get_cpu_status` / `get_memory_status` / `get_gpu_status`）の個別 Event は存在しない。推測で表示していない。

そのため **PASS ではなく PARTIAL_PASS**。

---

## 観測表

| 項 | 入力 | LLM が選んだ Tool | 実際の Tool Call | 回答に実測を使ったか |
|----|------|-------------------|------------------|----------------------|
| A | 今のPCのシステム状態を教えて | `get_system_summary` | あり（success） | あり |
| B | 今のPCの状態を簡単に確認して | `get_system_summary` | あり（success） | あり |
| C | GPUの状態だけ教えて | `get_gpu_status` | あり（success） | あり（正しい区別） |
| D | その中でメモリ使用量は？ | なし | なし（履歴利用） | あり（A の数値を再利用） |

「available だから使った」ではない。A/B/C は Session の `tool_select` / `tool_call` / `tool_result` が存在する。D は `tools: []` かつ Event `tool status=none`。

---

## 未変更

`agent.py` / `pipeline.yaml` / `get_gpu_status` / `get_gpu_processes` / `cpu_status` / `get_cpu_status` / `search_web` / `read_url_text` / `get_system_summary` 本体 / Registry 構造 / Research / Matrix / Cursor API / Development Timeline 基本設計 / 新しい Core
