# Development Test Safety — S4 Runtime Gate Architecture (READ-ONLY)

**Date:** 2026-09-12  
**Scope:** `TEST_EXECUTION` only. No runtime wiring in S4.

---

## 1. Safety chain（コード確認）

### 実装フロー

```text
Test Plan
  → tools/test_safety/validator.py :: evaluate_test_plan()
      → 推論: LEVEL_*, safety_dimensions, relevant_unknowns, warnings
      → _advisory_gate_mirror()  ※ shadow_gate を import
  → TEST_SAFETY_EVALUATION（recommended_gate_decision は助言フィールド）

TEST_SAFETY_EVALUATION
  → tools/test_safety/shadow_gate.py :: evaluate_shadow_gate()
  → TEST_SAFETY_SHADOW_GATE（S3; execution_authoritative=false）

CLI:
  run_test_safety_validator.py  |  run_test_safety_shadow_gate.py
```

### 依存方向

| コンポーネント | 依存先 | 備考 |
|----------------|--------|------|
| `validator` | `shadow_gate.decide_gate_from_evaluation`, `_postflight_required` | 評価生成の末尾のみ |
| `shadow_gate` | evaluation packet / evaluation dict | Validator 本体に非依存 |
| `comparison` | validator + shadow_gate 出力 | S3 証跡のみ |
| Task Runtime / chat | **test_safety 未接続** | NOT_CONNECTED |

「Gate Decision Engine」という独立パッケージ名は **存在しない**。決定ロジックの単一実装は `shadow_gate.py` の `decide_gate_from_evaluation()`。

---

## 2. Decision Logic の正本 — **Pattern B（単一エンジン、二経路）**

### Pattern A（facts only / gate only）ではない

Validator は依然として `recommended_gate_decision` / `gate_blocked_reasons` を出力するが、これは **Gate ルールの複製ではなく** `_advisory_gate_mirror()` 経由で **同一関数** を呼ぶ。

```155:166:tools/test_safety/validator.py
def _advisory_gate_mirror(
    evaluation: dict[str, Any],
    warnings: list[str],
) -> tuple[str, list[str], bool, bool, str]:
    """Mirror Shadow Gate for S2 advisory fields only; authoritative gate is separate."""
    from test_safety.shadow_gate import _postflight_required, decide_gate_from_evaluation

    decision, blocked, _, human, human_reason = decide_gate_from_evaluation(
        evaluation, validator_warnings=warnings
    )
    postflight_git = _postflight_required(evaluation)
    return decision, blocked, postflight_git, human, human_reason
```

**正本:** `tools/test_safety/shadow_gate.py` — `decide_gate_from_evaluation()`（ルール）+ `evaluate_shadow_gate()`（パケット + fail-safe）。

Runtime 接続時の **authoritative** 判定もこの関数（またはその薄い wrapper）を呼ぶべき。Validator 内に第二の判定表を増やさない。

---

## 3. CURRENT_RUNTIME_EXECUTION_PATH

### 3.1 Chat / Agent Tool 経路（主要 Active Path）

```text
run_chat_turn (agent_turn.py)
  → ChatTaskOrchestrator (task_orchestration.py)
  → _execute_agent_tool()
      → authorize_tool_execution()  [tools/system/agent_tool_gate.py]
      → registry tool function
```

- **Runtime Authority（Policy 文言）:** `docs/DEVELOPMENT_TEST_POLICY.md` § Runtime Authority Boundary — `Proposal → Runtime Authority → Executable Action → Tool`
- **コード上の `RequiredFirstAction` / `ExecutionOrderConstraint` / `authorize_action_proposal`:** **NOT_FOUND**（シンボル・型・関数として未実装。Policy の将来拘束の記述のみ）

### 3.2 Task 実行ブロック（Safety 以外）

```text
task_execution_guard.task_execution_blocked()
  → task_superseded / upstream_supersession / premise_revalidation
```

`TaskStatus.BLOCKED` / `GoalStatus.BLOCKED` は `tools/ai/task_runtime.py` に enum あり。Safety Gate とは無関係。

### 3.3 Agent 評価用バッチ（観測）

`ai_tool/agent_test_runner.py` — `run_chat_turn` 系の記録・採点。**pytest を Safety 前に挟む処理はない**。`subprocess` は主に `git` メタデータ取得。

### 3.4 開発者が叩く pytest

シェル / CI → `python -m pytest` — **Task Runtime 外**。Test Safety Validator / Shadow Gate **未接続**。

### 3.5 Research Pipeline Gate（別系統）

`tools/ai/state/execution_gate.py` — 生成コード安全性。**Test Safety とは非統合**（`agent_tool_gate.py` コメントでも明示）。

---

## 4. AVAILABLE_AUTHORIZATION_PRIMITIVES

|  primitive | 場所 | 用途 | TEST_EXECUTION |
|------------|------|------|----------------|
| `authorize_tool_execution` | `tools/system/agent_tool_gate.py` | Tool 名 + trust store | 汎用 Tool；test 専用ではない |
| `decide_execution_gate` | `tools/ai/state/execution_gate.py` | Research 実行 | 別ドメイン |
| `task_execution_blocked` | `ai_tool/task_execution_guard.py` | タスク supersede / premise | テスト計画 Safety ではない |
| `AgentTaskRuntime.should_execute` | `tools/ai/task_runtime.py` | 同一 tool+args の evidence 重複抑制 | ループ抑制の一部 |
| `ActionRecord` | `tools/ai/task_runtime.py` | `action_id`, `type`, `tool_name`, `arguments` | 元アクション保持の器 |
| `accept_semantic_followup` → `EXECUTABLE` + `action` | `task_orchestration.py` | 単一 follow-up action | パターン参考 |
| H4 `pending_action` inject | tests / help selection | `read_file` 等 1 件 | TEST 一般化ではない |
| Human UI 状態 | `AWAITING_HUMAN`（grill / decision_change_gate）, `AWAITING_HUMAN_APPROVAL`（recovery） | 人間待ち | Safety 専用状態ではない |
| `apply_human_decision` | `tools/ai/state/safety_assessment.py` | Research assessment | Test Safety 未接続 |
| Shadow Gate packet | `TEST_SAFETY_SHADOW_GATE` | PASS/BLOCKED 記録 | S3 のみ、非 authoritative |

**`authorization_dependency` / `pending_action`（Safety 用）/ `safety_evaluation_ref` フィールド:** スキーマ上 **NOT_IMPLEMENTED**（S4 では新規フィールドを作らない方針どおり未作成）。

---

## 5. Runtime 接続候補の比較

| Option | 概要 | 統合性 | 元 Action 保持 | 現状ギャップ |
|--------|------|--------|----------------|--------------|
| **A — Test Runner 入口** | `pytest` 直前に Validator+Gate | 単純；CI/手動に直結 | シェルコマンド＝plan；Runtime 外 | Task / Chat と二重世界 |
| **B — Action Authorization** | `ActionRecord.type=TEST_EXECUTION` を `authorize_*` 前に評価 | `agent_tool_gate` と同型の「実行前認可」 | `ActionRecord.arguments` に commands を保持可能 | `TEST_EXECUTION` type **未存在**；gate は tool 名ベース |
| **C — Required First Action** | 元アクションを suspend；先に safety check action | **DEVELOPMENT_TEST_POLICY** の Authority モデルと一致 | 元 Proposal を別 ID で保持し、完了後 resume | **RequiredFirstAction 未実装**；最大の接続工数 |

### RECOMMENDED_CONNECTION_POINT

**主推奨: Option C（Policy 整合）を Lifecycle の正とし、最初の実装 wedge は Option A または B の明示 Adapter**

1. **Canonical lifecycle（設計正本）** — Option C  
   `Execution Request (TEST_EXECUTION)` → `Required safety evaluation` → `Authorization` → `Resume original` → `Execute` → `Postflight` → `Closure`

2. **First runtime wedge（実装順）** — Option A + B の合成  
   - **Wedge-A:** `agent_test_runner` / 明示「run tests」エントリ（人間・CI スクリプト）で `evaluate_test_plan` + **authoritative** `evaluate_shadow_gate`（`execution_authoritative=true` に昇格した別パケット型は将来）を記録してから subprocess。  
   - **Wedge-B:** Chat が `run_tests` 相当 Tool を呼ぶ日に、`_execute_agent_tool` の直前で **同一 Gate 関数**を呼ぶ Adapter（Tool 名 allowlist: test runner tool のみ）。

**推奨しない:** Shadow Gate CLI を pytest hook に黙って入れるだけ（Runtime Authority / evidence 連鎖が切れる）。

---

## 6. ORIGINAL_ACTION_PRESERVATION

**既存で使える表現**

- `ActionRecord`: `action_id`, `task_id`, `type`, `tool_name`, `arguments` — 元の test command を `arguments` に格納する設計は可能（**新フィールド不要**）。
- Orchestrator の `accept_semantic_followup` は `record["action"]` を破棄せず返す（単一 executable）。

**推奨セマンティクス（S5+ 実装時、フィールド追加なし案）**

- 元アクション = `ActionRecord` 1 件（status は runtime がまだ持たない → `result_status=null` で pending 扱い）。
- Safety チェック = **別** `ActionRecord`（`type`: 例 `test_safety_evaluation`、tool: 内部関数 or read-only CLI）を先に `record_action`。
- Resume = Runtime が「current action」ポインタを元アクションに戻す（**現状ポインタ型 API は未確認** → `NOT_DETERMINED`、要 Orchestrator 拡張）。

**禁止:** Gate PASS 後に LLM へ test 計画を再生成させる（Plan B 化）。

---

## 7. PASS_RESUME_SEMANTICS

| 役割 | 主体 | 挙動 |
|------|------|------|
| **Gate** | `decide_gate_from_evaluation` → PASS | **authorization granted** のみ（pytest は呼ばない） |
| **Executor** | 既存 Tool / subprocess runner / pytest | 元 `ActionRecord` の実行 |

Resume トリガー候補（既存優先）:

1. Safety check `ActionRecord` が `result_status=success` + shadow/authoritative gate packet が PASS  
2. Runtime event `SAFETY_AUTHORIZED`（**新 event — 将来**；S4 では未追加）  
3. 単純 wedge では「gate PASS 記録済み JSON path」を executor が読む（暫定、Runtime 統合前）

**Gate は Executor を import しない**（S3 方針維持）。

---

## 8. BLOCKED_SEMANTICS

Shadow Gate `BLOCKED` を Runtime に載せるとき:

| 項目 | 推奨 |
|------|------|
| Test 実行 | **しない** |
| 元 Action を `FAILED` | **しない**（Safety 未解消 ≠ テスト失敗） |
| Task 状態 | 既存 `TaskStatus.BLOCKED` または Human 系 `AWAITING_HUMAN` を **理由コードで使い分け** |
| `BLOCKED_WAITING_FOR_SAFETY_RESOLUTION` | **NOT_FOUND** — 新 enum は S5 人間判断まで避け、まず `task_events` / `agent_runtime_events` に `reason` + `blocked_reasons[]` を載せる |
| 保持 | `blocked_reasons`, `evaluation_ref`, `gate_packet` 参照 |
| 解消 | Plan 修正 → 再評価；Relevant UNKNOWN 解消；Human Approval（将来） |

Fail-safe（invalid evaluation）も **authorization denied** 扱い（S3 `INVALID_OR_UNVERIFIED_EVALUATION` と同型）。

---

## 9. HUMAN_APPROVAL_BOUNDARY

現 Gate ルール（`shadow_gate.py`）:

- `human_approval_required=true` と `gate_decision=BLOCKED` が **同時**になり得る（external / network / credentials 系）。
- `human_approval_required=true` かつ **policy 上実行可能**（例: L3 live LLM「条件付き」）のケースは、Shadow では `BLOCKED` にしていない場合あり — **WAITING と BLOCKED の分離は未確定**。

**S4 推奨（Approval Runtime なし）**

| 状況 | gate_decision | Runtime 表示（既存流用） |
|------|---------------|---------------------------|
| 安全上実行不可（prohibited / relevant UNKNOWN） | BLOCKED | `TaskStatus.BLOCKED` + reasons |
| 禁止ではないが Human Approval 必須 | BLOCKED **または** PASS+`human_approval_required` | **`AWAITING_HUMAN`** / `AWAITING_HUMAN_APPROVAL`（recovery 系）— **同一扱いにしない** |
| L2 controlled + PASS | PASS | 自動 resume 可 |

**OPEN:** `EXTERNAL_UNBOUNDED` を BLOCKED と WAITING_HUMAN_APPROVAL のどちらに寄せるか（S1 Decision 6 + S5 Human）。

---

## 10. POSTFLIGHT_BINDING

現状:

- Validator: `postflight_git_check_required`
- Gate packet: `required_postflight.postflight_git_check_required`
- **Postflight 実行コード:** NOT_CONNECTED（Validator の `_git_readonly_snapshot` は評価時 read-only のみ）

**推奨ライフサイクル（設計）**

```text
Preflight authorization (PASS)
  → Execute TEST_EXECUTION
  → If required_postflight.postflight_git_check_required:
        run git status/diff adapter (read-only)
  → postflight_result を evidence / run record に保存
  → Run closure（postflight 必須なら未完了 = NOT_CLOSED）
```

既存 `agent_test_runner._git_metadata` / Validator `_git_readonly_snapshot` を **Postflight Adapter 候補**として再利用可能（実装は S5+）。

---

## 11. STALE_EVALUATION_PROTECTION

**現状:** `test_plan_hash` / `command hash` / evaluation と action の bind — **NOT_IMPLEMENTED**。

**推奨（新フィールドなしで開始可能）**

- `evaluation_ref`（既存 Gate packet）に `generated_at` + `validator_id` + evaluation packet の `test_plan.commands` を含める（evaluation 全文は evidence に保存）。
- Authorization 時に **byte-stable JSON hash** of `test_plan`（commands + declared_*）を計算し、`ActionRecord.arguments` または event payload に `plan_fingerprint` を載せる（S5 で schema 化）。
- Resume 時: fingerprint 不一致 → 再 Validator **必須**（古い PASS 無効）。

**既存類似:** `should_execute` は tool 重複のみ。Plan 変更検知は別 concern。

---

## 12. LOOP_PREVENTION

候補（既存優先 + Gate 拡張）:

| 机制 | 状態 |
|------|------|
| `evaluation_ref` + `action_id` 1:1 authorization 記録 | 設計推奨、未実装 |
| 同一 `action_id` に対し Gate を 1 回のみ authoritative | 設計推奨 |
| `should_execute`（evidence_gain 重複） | 接続済み（Tool 重複用） |
| Safety check を別 `action_id` にする | Required First Action パターンで自然に二重 Gate 回避 |

**禁止パターン:** PASS 後に毎ターン再 `evaluate_test_plan` して同じ pytest を再ブロック — fingerprint + `authorized_for_action_id` 状態で抑止。

---

## 13. EVIDENCE_BINDING

**推奨関連（S5+ 実装；既存構造流用）**

```text
action_id (TEST_EXECUTION pending)
  ↔ safety_action_id (evaluation run)
  ↔ TEST_SAFETY_EVALUATION (evidence / runs/...json)
  ↔ TEST_SAFETY_SHADOW_GATE or AUTHORITATIVE_GATE_PACKET
  ↔ execution_started / execution_result (ActionRecord.result_status)
  ↔ postflight_result (git snapshot diff)
```

既存フック:

- `AgentTaskRuntime.record_action` / `add_evidence` / `emit_event`
- `agent_test_runner.record_run` — run 単位 JSON（拡張候補）
- S3 `build_comparison_evidence` — 参考（Human expected 比較）

---

## 14. RECOMMENDED_RUNTIME_ARCHITECTURE

```text
                    ┌─────────────────────────┐
                    │  Execution Request      │
                    │  (TEST_EXECUTION)       │
                    │  ActionRecord (pending) │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  Safety Adapter         │
                    │  evaluate_test_plan()   │
                    │  evaluate_shadow_gate() │
                    │  [authoritative flag]   │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │ BLOCKED         │ PASS            │
              ▼                 ▼                 │
     Task BLOCKED /          Authorization        │
     AWAITING_HUMAN          + plan_fingerprint   │
     (reasons kept)          + evaluation_ref     │
              │                 │                 │
              │                 ▼                 │
              │         Resume original Action    │
              │         (same action_id/args)     │
              │                 │                 │
              │                 ▼                 │
              │            Executor (pytest)      │
              │                 │                 │
              │                 ▼                 │
              │     Postflight (if required)      │
              │                 │                 │
              └─────────────────┴──► Run Closure  │
```

- **Decision 正本:** `shadow_gate.decide_gate_from_evaluation`
- **接続点:** まず Runner wedge；並行設計で Orchestrator Authority（Option C）
- **分離:** Gate ≠ Executor

---

## 15. Safety Gate Failure（Runtime 設計）

| 失敗 | Runtime authorization |
|------|------------------------|
| Validator crash | **denied**（記録 `SAFETY_EVALUATION_FAILED`） |
| Invalid schema / unknown version | **denied**（S3 fail-safe 同等） |
| Missing evidence | **denied** |
| Shadow vs authoritative 混同 | authoritative 未昇格時は従来 Human review（現状 Shadow のみ） |

---

## 16. Final Verdict Fields

```text
CURRENT_RUNTIME_EXECUTION_PATH:
  Chat: run_chat_turn → orchestrator → _execute_agent_tool → authorize_tool_execution → tool.
  Tests: shell/CI pytest and agent_test_runner WITHOUT test_safety gate (NOT_CONNECTED).
  Policy names RequiredFirstAction / ExecutionOrderConstraint: DOCUMENTED_ONLY, NOT_CONNECTED in code.

AVAILABLE_AUTHORIZATION_PRIMITIVES:
  authorize_tool_execution, task_execution_blocked, ActionRecord, should_execute,
  AWAITING_HUMAN / AWAITING_HUMAN_APPROVAL, apply_human_decision (research-only),
  TEST_SAFETY_* packets (shadow non-authoritative).

RECOMMENDED_CONNECTION_POINT:
  Lifecycle: Option C (Required First Action pattern per DEVELOPMENT_TEST_POLICY).
  First wedge: Option A (runner entry) + Option B adapter at _execute_agent_tool for a dedicated test-runner tool.

ORIGINAL_ACTION_PRESERVATION:
  Reuse ActionRecord.arguments for commands; separate safety ActionRecord; no LLM re-plan on resume.

PASS_RESUME_SEMANTICS:
  Gate grants authorization only; existing executor runs pytest; optional SAFETY_AUTHORIZED event (future).

BLOCKED_SEMANTICS:
  Do not execute; do not mark test FAILED; use TaskStatus.BLOCKED or AWAITING_HUMAN with reasons;
  no BLOCKED_WAITING_FOR_SAFETY_RESOLUTION symbol today.

HUMAN_APPROVAL_BOUNDARY:
  Do not equate BLOCKED with WAITING_HUMAN_APPROVAL; use AWAITING_HUMAN* for approval-pending when not safety-forbidden.

POSTFLIGHT_BINDING:
  Carry required_postflight through run; closure blocked until postflight_done when flag true;
  reuse git readonly snapshots as adapter.

STALE_EVALUATION_PROTECTION:
  plan_fingerprint at authorize time; mismatch forces re-evaluation (NOT_IMPLEMENTED).

LOOP_PREVENTION:
  One authoritative gate per action_id + evaluation_ref; avoid re-gating on resume.

EVIDENCE_BINDING:
  action_id ↔ evaluation_ref ↔ gate packet ↔ execution_result ↔ postflight via runtime events + run artifacts.

RECOMMENDED_RUNTIME_ARCHITECTURE:
  See §14 diagram; single decision source shadow_gate; authoritative packet type in S5+.

IMPLEMENTATION_READY:
  false  (architecture + wedge plan ready; Runtime/Task/Orchestrator unchanged per S4)

OPEN_DECISIONS:
  1) AUTHORITATIVE gate packet vs shadow packet promotion
  2) BLOCKED vs AWAITING_HUMAN for approval-only cases (L3 conditional, external)
  3) Where plan_fingerprint lives (ActionRecord.arguments vs event only)
  4) Orchestrator "current action" resume API (missing today)
  5) CI: runner wedge vs Task Runtime for TEST_EXECUTION
  6) Whether to register TEST_EXECUTION as tool vs internal runner only
```

```text
READY_FOR_RUNTIME_GATE_DESIGN:
  true   (this document)

AUTO_CONNECT_RUNTIME:
  false  (Human Review required; S4 READ-ONLY complete)
```

---

## 17. S4 実施確認

- コード変更: **なし**
- pytest BLOCK: **なし**
- RequiredFirstAction / ExecutionOrderConstraint: **変更なし**
- P2b / CI / development_policy: **触らない**
