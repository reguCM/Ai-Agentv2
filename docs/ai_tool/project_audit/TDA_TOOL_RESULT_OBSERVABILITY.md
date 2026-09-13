# Tool Result 観測性

**日付:** 2026-08-31  
**依頼:** Event / 「処理を見る」 / 開発タブから、LLM が選んだ Tool と実際の戻り値を追跡できるようにする  
**実行主体（コード変更）:** Cursor  
**実行主体（Chat 実測）:** ブラウザ → Local Agent → Local LLM → Tool  
**Run:** `runs/ai_tool/20260831_004500_tool_result_observability`  
**Session:** `cs-20260830_153526-7f5d25`  
**モデル:** `qwen3:8b`  
**Server:** `LocalAgentChat/0.9`  
**判定:** `PASS`

Cursor live status: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**

---

## 調査：分岐点

`agent_turn.py` の Tool 実行直後:

- **LLM へ:** `json.dumps(result)`（全文）
- **Event / Session へ:** 以前は `summarize_tool_result` がトップの `ok` / `status` / `error` だけを残し、`sections` を捨てていた

今回もこの分離は維持する。Event に無制限 dump はしない。

---

## 変更前後

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| Event の get_system_summary | `{ok, status, error}` | 戻り値にある time/cpu/memory/gpu の安全スカラー |
| COMPOSE | なし | 戻り値の `sections` キーがあるときだけ |
| 子 TOOL_CALL | なし | なし（再実行しない。関数名は戻り値に無いので作らない） |
| LLM へ渡す JSON | raw result | **未変更** |
| search_web Event | query / hit_count / titles | 本文 `hits` は omitted のまま |
| agent.py / Tool 本体 | — | **未変更** |

---

## 実測

| 項 | 入力 | Tool Call | Event |
|----|------|-----------|-------|
| A | こんにちは | なし | Tool Result を出さない |
| B | GPUの状態を教えて | `get_gpu_status` | temperature / vram 等 |
| C | 今のPCのシステム状態を教えて | `get_system_summary` | COMPOSE + sections |
| D | その中でメモリ使用量は？ | なし | `tools: []` / Tool Call: NONE |

子 Tool の個別実行 Event は **NOT_OBSERVED**。合成結果の `sections` は **REAL**。
