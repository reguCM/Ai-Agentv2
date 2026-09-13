# Specification Drift Analysis

**Phase:** Agent Observation / Tool Calling Cross Audit — Phase 1  
**Git HEAD:** `32d7d12`

---

## 1. 比較軸

```text
Original / Legacy intent
        ↓
Git history
        ↓
Current implementation (HEAD vs WT)
        ↓
Current tests / migration specs
        ↓
Current E2E
```

---

## 2. Agent Tool Calling

| 項目 | Legacy (004c6de) | Current (HEAD agent.py) | Drift |
|------|------------------|-------------------------|-------|
| Tool schema | registry → Ollama function | 同左 + visibility filter + experimental overlay | **NONE** (additive overlay) |
| tool_calls API | Ollama native | 同左 | **NONE** |
| Tool result to LLM | raw JSON | raw JSON | **NONE** |
| SYSTEM_PROMPT | 短い版 | Web 手順 + read_url_text + observation tools 列挙 | **DOCUMENTATION_DRIFT** (拡張) |
| Tool capability validation | なし | なし | **NONE** |
| active_model | profile 分離前 | deepseek_coder_v2_16b | **MODEL_DEPENDENCY** (pipeline vs capability) |

---

## 3. get_gpu_status

| 層 | HEAD | WT | Migration spec | Drift |
|----|------|-----|----------------|-------|
| Implementation | 固定値 dict | nvidia-smi 実測 | 実測契約 | **IMPLEMENTATION_DRIFT** (HEAD vs WT) |
| Registry visibility | なし | agent | agent (WT) | **INTERFACE_DRIFT** (HEAD registry) |
| observation_source | なし | real | real | **REGISTRY_DRIFT** |
| Tests | test_gpu_real_observation (WT path) | migration tests | spec aligned to WT | **TEST_DRIFT** vs HEAD impl |

**Legacy intent (Registry description):** GPU 基本状態 — WT description は nvidia-smi 実測を明記。

---

## 4. get_gpu_processes

| 層 | HEAD (82c40db) | WT | E2E | Drift |
|----|----------------|-----|-----|-------|
| Implementation | nvidia-smi measured dict | 同左 | PASS | **NONE** |
| Registry visibility | agent | agent | exposed | **NONE** |
| Output shape | dict (not list) | 同左 | Human approved | **NONE** (post-adoption) |
| VRAM per process | often unknown | 33/33 unknown @ audit | PARTIAL documented | **NONE** — known limitation |

---

## 5. cpu_status

| 層 | HEAD | WT | Migration spec | Drift |
|----|------|-----|----------------|-------|
| Implementation | CIM LoadPercentage | 同左 | 同左 | **NONE** |
| Registry visibility | なし (HEAD) | agent (WT) | agent (WT) | **REGISTRY_DRIFT** |
| Output fields | `{status}` only | 同左 | LoadPercentage only | **NONE** |
| observation_source in output | なし | なし | NOT_PROVIDED OK | **DOCUMENTATION_DRIFT** (registry metadata vs output) |

---

## 6. Registry HEAD vs WT（横断）

| Tool | HEAD visibility | WT visibility |
|------|-----------------|---------------|
| get_gpu_processes | agent | agent |
| get_gpu_status | (none) | agent |
| cpu_status | (none) | agent |
| search_web, file tools | (none) | agent |

**影響:** 同一 `agent.py` でも **commit 済み registry では GPU プロセス Tool のみ LLM 公開**。ローカル WT では 7 Tool 公開。

**分類:** **INTERFACE_DRIFT** + **REGISTRY_DRIFT** — Human Review 必要。

---

## 7. E2E vs Agent SYSTEM_PROMPT

| 項目 | agent.py | E2E harness |
|------|----------|-------------|
| VRAM unknown 禁止ルール | なし | あり (`gpu_process_e2e.py`) |
| Tool 使い分け GPU | 一覧のみ | 詳細 routing note |

**分類:** **DOCUMENTATION_DRIFT** — E2E は harness 側で補完。Agent 本番 prompt との差異。

---

## 8. DeepSeek 400 事象

| 仮説 | 証拠 | 判定 |
|------|------|------|
| Model capability | 400 message "does not support tools" | OBSERVED — 有力 |
| Ollama packaging | 未調査 | UNKNOWN |
| Agent schema | qwen3 同 schema で成功 | OBSERVED — schema 単独原因とは考えにくい |
| System prompt | 変更なしで qwen 成功 | OBSERVED |
| Parser | Ollama native API | OBSERVED |
| 過去仕様削除 | tool_calls path 004c6de から存在 | OBSERVED — 削除説は弱い |

**総合:** **MODEL_DEPENDENCY** + **UNKNOWN**（Ollama/model card 詳細）

---

## 9. Drift サマリ

| 分類 | 件数 | 例 |
|------|------|-----|
| IMPLEMENTATION_DRIFT | 1 | gpu_status HEAD 固定 vs WT 実測 |
| REGISTRY_DRIFT | 1 | HEAD 1 tool vs WT 7 tools visibility |
| DOCUMENTATION_DRIFT | 2 | SYSTEM_PROMPT 拡張; cpu metadata vs output |
| TEST_DRIFT | 1 | gpu tests assume WT impl |
| MODEL_DEPENDENCY | 1 | active_model tool calling |
| OLLAMA_DEPENDENCY | 1 | 全 tool loop |
| INTERFACE_DRIFT | 1 | registry visibility scope |
| UNKNOWN | 2 | DeepSeek root cause; pipeline policy |

---

## 10. 修正候補（実施せず）

詳細は `runs/ai_tool/20260828_171500_agent_observation_toolcalling_audit/findings.json`

| ID | 要約 | Human Review |
|----|------|--------------|
| F1 | active_model tool calling 整合 | **REQUIRED** |
| F2 | Registry HEAD/Wt visibility | **REQUIRED** |
| F3 | gpu_status HEAD 固定値 | **REQUIRED** |
| F4 | VRAM unknown 調査 | 次 Phase（interface 変更時 HR） |
| F5 | SYSTEM_PROMPT unknown ルール | **REQUIRED** (if changed) |
| F6 | cpu_status observation_source output | **REQUIRED** (if changed) |

---

## STOP

本 Phase では drift を **記録のみ**。修正・Registry commit・prompt 変更は次 Phase / Human Review へ。
