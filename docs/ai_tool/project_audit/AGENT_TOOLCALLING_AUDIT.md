# Agent ↔ LLM Tool Calling Audit — Phase 1

**日付:** 2026-08-28  
**Git HEAD:** `32d7d12`  
**スコープ:** 読み取り専用監査（修正・commit なし）  
**Run:** `runs/ai_tool/20260828_171500_agent_observation_toolcalling_audit/`

---

## 1. 目的

現在の AI-Agent が **LLM Tool Calling について何を要求しているか** をコードと Git 履歴から確定する。

本監査は production code / Registry / System Prompt の **変更を行わない**。

---

## 2. Agent ↔ LLM 経路（確定）

```text
registry/tools.json (filesystem — WT at local run)
  → create_ollama_tools() [visibility==agent]
  → append_experimental_agent_tools() [read_url_text overlay]
  → ollama_tools_for_llm() [strip _meta]
  → chat(model=MODEL, messages, tools=...)
  → response.message.tool_calls[].function.{name, arguments}
  → execute_tool() / execute_experimental_agent_tool()
  → messages += {role:tool, tool_name, content: json.dumps(raw result)}
  → messages += response.message (assistant)
  → loop until no tool_calls
  → final response.message.content
```

**入口:** `agent.py`  
**LLM クライアント:** `tools/system/llm.py` → `ollama.Client.chat()`  
**モデル:** `get_llm_profile()` ← `config/pipeline.yaml` `active_model` または `AI_AGENT_MODEL`

---

## 3. Tool Schema

| 項目 | 仕様 |
|------|------|
| 生成 | `create_ollama_tools(registry)` — `agent.py` L141-184 |
| 公開条件 | `registry.tools[].visibility == "agent"` |
| 形式 | OpenAI-style `{type:function, function:{name, description, parameters}}` |
| parameters | registry `input` → `properties` + `required` |
| overlay | `read_url_text` — catalog 経由、Registry 未登録 |
| LLM 送信前 | `_agent_meta` / `_trial_meta` を除去 |

### HEAD vs WT（混同禁止）

| 層 | Agent 公開 Tool 数 | GPU/CPU 観測 Tool |
|----|-------------------|-------------------|
| **HEAD** (committed registry) | **1** | `get_gpu_processes` のみ |
| **WT** (local runtime registry) | **7** (+ overlay 8) | `get_gpu_status`, `get_gpu_processes`, `cpu_status` 含む |

`agent.py` は起動時に **WT** `registry/tools.json` を読む。

---

## 4. LLM Request

| 項目 | 値 |
|------|-----|
| API | Ollama Python `Client.chat(**kwargs)` |
| model | `get_llm_profile()["model"]` — 現在 `deepseek-coder-v2:16b` |
| messages | `[system: SYSTEM_PROMPT, user: USER_REQUEST, ...]` |
| tools | `ollama_tools_for_llm(tools)` |
| options | `num_predict`, `temperature`, `num_ctx` from profile |
| keep_alive | profile 既定 |

### SYSTEM_PROMPT（`agent.py` L745-785）

- 使える事実: ユーザー要求、STATE、検証済み環境、Tool 実行結果のみ
- 公開 Tool 一覧（search_web, read_url_text, file tools, **get_gpu_status / get_gpu_processes / cpu_status**）
- Web 調査手順（search_web vs read_url_text）
- ルール: 捏造禁止、schema 準拠、Registry 変更禁止

**VRAM unknown 明示ルール:** agent.py SYSTEM_PROMPT には **なし**（E2E harness のみ）

---

## 5. LLM Response

| 項目 | 処理 |
|------|------|
| tool_calls | `response.message.tool_calls` — Ollama ネイティブ API |
| name | `tool_call.function.name` |
| arguments | `tool_call.function.arguments` — dict または JSON 文字列 |
| content | tool loop 終了時の最終テキスト |
| 独自 parser | **なし**（XML `<tool_call>` 等は agent.py に存在しない） |

---

## 6. Tool Execution & Result Return

| 段階 | 実装 |
|------|------|
| 受信 | `for tool_call in response.message.tool_calls` |
| 正規化 | `normalize_arguments()` — JSON 文字列 parse |
| 実行 | `execute_tool()` — registry module import + gate |
| LLM 返却 | `role=tool`, `tool_name`, `content=json.dumps(raw result)` |
| stdout | `print_tool_result_for_stdout()` — LLM とは分離 |
| 要約 | `summarize_tool_result()` — **create_tool_proposal のみ**、観測 Tool には未使用 |

**Git 履歴:** 004c6de から LLM には raw JSON、stdout のみ summarize — **FOUND_CURRENT**

---

## 7. Final Answer

- Tool loop 終了後の `response.message.content` をそのまま出力
- 観測 Tool 結果に対する後処理・数値推測ロジック **なし**
- `create_tool_proposal` 時のみ JSON 検証リトライ

---

## 8. 依存性分類

| 分類 | 該当 |
|------|------|
| **MODEL_INDEPENDENT** | Tool schema 生成、normalize_arguments、SYSTEM_PROMPT 構造、raw result 返却 |
| **OLLAMA_DEPENDENT** | `Client.chat(tools=...)`, `response.message.tool_calls`, `role=tool` message 形式 |
| **MODEL_DEPENDENT** | モデルが tool calling API を実装していること（実行時） |
| **QWEN_SPECIFIC** | agent.py 内 **NOT FOUND** |
| **UNKNOWN** | Pipeline active model と tool capability の整合保証方法 |

---

## 9. Qwen3 依存性

### agent.py / tools/system/llm.py

- `qwen` 文字列参照: **なし**
- Qwen 固有 XML / thinking タグ parser: **なし**
- `<tool_call>` 形式: Git 履歴 **NEVER_FOUND**

### リポジトリ全体

- `qwen3:8b` は research / E2E / env override で使用
- NH 系実験・過去 agent ログで qwen3:8b 使用 **OBSERVED**
- これは **運用上のモデル選択** であり、agent コードの Qwen 固有 protocol **ではない**

**判定:** Agent Tool Calling 実装は **OLLAMA_DEPENDENT + MODEL_DEPENDENT（capability）**。**QWEN_SPECIFIC 処理は FOUND されず。**

---

## 10. DeepSeek-Coder-V2 問題（原因未確定）

### OBSERVED

| # | 観測 | 分類 |
|---|------|------|
| 1 | `deepseek-coder-v2:16b` + Ollama tools → HTTP 400 `does not support tools` | OBSERVED (E2E run) |
| 2 | `qwen3:8b` + 同一 schema → tool_calls 成功 4/4 | OBSERVED (E2E run) |
| 3 | `config/pipeline.yaml` active_model = deepseek_coder_v2_16b | OBSERVED |
| 4 | agent.py に tool capability 事前チェックなし | OBSERVED |

### UNKNOWN（断定禁止）

- DeepSeek モデル自体が tool calling 非対応なのか
- Ollama モデルカード / 配布形式の問題か
- Agent schema / prompt が原因か → **400 メッセージは model capability を示唆、schema 起因とは未確認**

---

## 11. Legacy Response Rules 調査

| ルール | 状態 |
|--------|------|
| Ollama native tool_calls | **FOUND_CURRENT** (004c6de~) |
| role=tool + tool_name + JSON content | **FOUND_CURRENT** (004c6de~) |
| XML `<tool_call>` 形式 | **NEVER_FOUND** |
| LLM へ JSON テキストで tool call を返せ指示 | **NEVER_FOUND** (main loop) |
| create_tool_proposal JSON-only | **FOUND_CURRENT** (提案 path のみ) |
| summarize_tool_result を LLM に返す | **FOUND_LEGACY** — 004c6de でも LLM には raw。stdout のみ summarize → 実質 NEVER for LLM path |

---

## 12. Human Review Required

1. Pipeline `active_model` と Tool Calling capability 整合
2. Registry HEAD vs WT（visibility=agent の範囲）
3. `get_gpu_status` HEAD 固定値 vs WT 実測 — どちらを production とするか
4. SYSTEM_PROMPT への VRAM unknown 明示ルール追加の要否

---

## 関連

- [OBSERVATION_TOOL_MATRIX.md](./OBSERVATION_TOOL_MATRIX.md)
- [SPEC_DRIFT_ANALYSIS.md](./SPEC_DRIFT_ANALYSIS.md)
- [../agent_integration/GPU_PROCESS_E2E.md](../agent_integration/GPU_PROCESS_E2E.md)
