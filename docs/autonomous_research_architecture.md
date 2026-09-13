# 自律型 Research / Agent アーキテクチャ再設計

**status:** Phase 1–5 実装済み / Phase 6 Memory Judge 実装（既定 OFF）  
**date:** 2026-08-20  
**根拠:** 現行コード経路と Step 2-1 / Step 2-2a / Phase 4.1 / Phase 5 の保存済み run  
**前提:** context overflow 暫定圧縮は互換層として維持。Phase 5 で Memory Recall が正経路

---

## 0. 設計思想（要約）

| 原則 | 内容 |
|---|---|
| History ≠ Prompt | 保存と LLM 提示を分離する |
| State 中心 | LLM は「今分かっていること」で次 Action を決める |
| 監督は必要時のみ | Partial Judge は局所、Global Judge はトリガー起動 |
| 解決済みは Context から外す | 削除 ≠ 忘却。History に残す |
| Budget = 配分 | 圧縮ではなく枠と headroom を明示する |

目標像:

> **LLM が全履歴を持っていなくても、自分が今何をすべきか判断できる Agent**

---

## 1. Current Architecture

### 1.1 全体フロー（④ `research_implement`）

```text
User request
  ├─ Case JSON → TaskState 直接注入
  └─ Clarity handoff（ベンチではスクリプト化 STATE）
        ↓
Proposal
  create_tool_proposal → ask_json(build_proposal_messages)
  validate_tool_spec / validate_proposal_completeness
        ↓
Research ↔ Judge loop  (max_research_rounds=10)
  for round:
    run_research
      local inventory + web search
      web_research → materials
      ask_json(build_web_candidate_messages)   # LLM: candidates
      [optional] exploration_retry
      research_verifier (subprocess)
      pack_research_result / split_findings
    merge_packed_research
    create_research_judgment → ask_json(build_research_judge_messages)
    normalize_judgment → apply_judgment(state)
    state.set_unresolved(research.unresolved)  # 置換
    evaluate_research_progress → IMPLEMENT | CONTINUE | STOP
    CONTINUE → prepare_followup_research
        ↓
Implementation（research_sufficient 時のみ）
  create_tool_implementation → ask_json(build_implement_messages)
  validate → register → test_tool → validate_tool_result
```

主要ファイル:

| 役割 | パス |
|---|---|
| ④エントリ / Judge ループ | `research/llm_benchmarks/research_implement.py` |
| `run_research` / `ask_json` | `research/llm_benchmarks/environment_benchmark.py` |
| Web materials | `tools/ai/tool_builder/web.py` |
| Message builders | `tools/ai/llm/adapter.py` |
| Judge materials / followup | `tools/ai/tool_builder/research_judge.py` |
| Pack / prior / rejected | `tools/ai/tool_builder/research_result.py` |
| STATE | `tools/ai/state/task_state.py` |
| Judgment → decisions | `tools/ai/state/decision_store.py` |
| Progress 機械判定 | `tools/system/tool_builder/research/progress.py` |
| Verifier | `tools/system/tool_builder/research/verify.py` |
| Context budget | `tools/ai/llm/context_budget.py` + `context_allocation.py` |
| Pipeline limits | `config/pipeline.yaml` |

### 1.2 重要な現行特性

1. **Judge は continue/stop を直接返さない。**  
   `satisfies_request` / `missing` を返し、機械側 `evaluate_research_progress` が IMPLEMENT / CONTINUE / STOP を決める。

2. **`STATE.unresolved` は蓄積ではなく置換。**  
   毎 Judge 後に `state.set_unresolved(research["unresolved"])`。  
   `merge_packed_research` も `unresolved` を最新ラウンド分で置換する。

3. **失敗履歴の蓄積は handoff 側。**  
   `prior_failures` / `rejected_commands` は `unresolved` + `insufficient_findings` から再構築され、ラウンドが進むと膨らむ。

4. **Verifier は LLM ではない。**  
   candidate 実行 → sample/error → confidence 付与 → pack。

---

## 2. Current Context Flow

### 2.1 共通組み立て

`adapter.build_json_messages`:

| 層 | 内容 |
|---|---|
| system | CONTRACT + JSON_SHAPE（state ありなら `STATE_CONTRACT` 追加） |
| user | `render_state(state)` + `render_materials(materials)` + optional `extra` |

Budget（現行）:

```text
budget_tokens = context_limit - num_predict - 128
budget_chars  = budget_tokens * 4
# deepseek_coder_v2_16b: 4096 - 2048 - 128 = 1920 tok → 7680 chars
```

### 2.2 LLM 呼び出しごとの入力

| Call | Builder | MATERIALS 主要キー | STATE | Context |
|---|---|---|---|---|
| Clarity | `build_clarity_messages` | `target_request`, `conversation` | ○ | project_context |
| Proposal | `build_proposal_messages` | request, environment, registry, rules… | ○ | — |
| **Web candidate** | `build_web_candidate_messages` | `items`, `search_results`, `inventory`, `rejected_commands`, `prior_failures`, `judge_reason`, `followup_questions`, `route_hints`, `exploration_hints`, `rules`… | ○（**unresolved 含む**） | — |
| **Research Judge** | `build_research_judge_messages` | `target_request`, `output`, `usable_findings`, `insufficient_findings`, `unresolved`, `judging_hints` | ○（**unresolved 再掲**） | — |
| Implementation | `build_implement_messages` | `proposal`, `research_result`, `insufficient_findings`, `rules`… | ○ | — |

### 2.3 1 Research ラウンドあたりの LLM 回数（現行）

| 状況 | 回数 |
|---|---:|
| 通常 | Web candidate 1 + Judge 1 = **2** |
| exploration retry | +1 → **3** |
| JSON retry | 各 +1 |

実測（Step 2-2a `cpu_temperature` 10r）: `llm_calls=28`（平均約 2.8/round）。

---

## 3. Information Classification

### 3.1 分類表

| データ | 現行の扱い | あるべき分類 | 備考 |
|---|---|---|---|
| `STATE.task` / `decisions` | Current State | **Current State** | 確定事項。通常は維持 |
| `STATE.unresolved` | Current State（実体は最新失敗のコピー） | **Current State（未解決のみ）** | 解決済みは外す。全文 stderr は History |
| `STATE.facts` / `constraints` | Current State | **Current State** | |
| `usable_findings` | packed research + Judge materials | **Current State（確定根拠）** | 実装根拠。件数制限で削らない方針を維持 |
| `insufficient_findings` | packed research + Judge materials | **History + Summary** | 「試したが不十分」の蓄積。LLM には要約のみ |
| `reference_findings` | packed research | **History / optional Summary** | |
| `prior_failures` | Temporary Handoff → Prompt Material | **History → Recent Event 抽出** | 毎回フル再掲しない |
| `rejected_commands` | Temporary Handoff → Prompt Material | **Current State（禁止集合）または Recent** | 短い `{command,args}` のみ常時可 |
| `judge_reason` | Temporary Handoff | **Recent Event / Summary** | 最新 1 件で足りる |
| `search_results` | Prompt-only Material | **Prompt-only（当該 Action）** | ラウンド局所。永続不要 |
| `route_hints` / `exploration_hints` | Prompt-only | **Prompt-only** | テンプレート。State にしない |
| `judging_hints` | Prompt-only | **Prompt-only（Partial/Global 別）** | |
| `followup_questions` / `missing` | Temporary Handoff | **Current State（open questions）** | unresolved と統合候補 |
| pipeline `research_rounds_detail` | ベンチ History | **Persistent History** | 既にログとして保存 |
| diagnosis / overflow | ベンチ診断 | **Persistent History** | |

### 3.2 重複マップ（現行）

| 情報 | Web candidate | Judge | Implementation | History/log |
|---|---|---|---|---|
| STATE.unresolved | ○ | ○ | ○ | ○ |
| MATERIALS.unresolved | — | ○（compact） | ○（research_result 内） | ○ |
| prior_failures | ○ | — | — | handoff |
| rejected_commands | ○ | — | — | handoff |
| judge_reason | ○ | （reason 原文） | — | judgments[] |
| usable_findings | — | ○ | ○ | ○ |
| insufficient_findings | （prior の源） | ○ | ○ | ○ |

**問題の本質:** 同一失敗が `STATE.unresolved` / MATERIALS.unresolved / prior_failures / rejected_commands / judge_reason として、**異なる形で同時に LLM へ載る**。

---

## 4. Proposed Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                        User Goal                            │
│              (request + confirmed decisions)                │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Current State                           │
│  goal / decisions / open_questions / usable_facts           │
│  banned_actions (short) / resource counters                 │
└────────────────────────────┬────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │   Autonomous Action Loop    │
              │                             │
              │  Plan next Action           │
              │    ↓                        │
              │  Tool / Candidate / Search  │
              │    ↓                        │
              │  Verify (machine)           │
              │    ↓                        │
              │  Partial Judge (local)      │
              │    ↓                        │
              │  State Update + History Append
              │    ↓                        │
              │  Escalation? ──no──► Loop   │
              └──────────────┬──────────────┘
                             │ yes
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Global Judge (trigger-based)                   │
│  goal satisfied? / pivot? / implement? / stop? / escalate?  │
└──────────────┬──────────────────────────────┬───────────────┘
               │ continue                     │ done
               ▼                              ▼
        Update State / Policy          Implementation
        (Summary refresh)              → Tool register/test
                                       → Completion
```

### 4.1 レイヤ責務

| レイヤ | 責務 | LLM? |
|---|---|---|
| **History Store** | 全イベント永続（command/args/stderr/judge/route） | いいえ |
| **Current State** | 「今」正しい最小スナップショット | 読取専用で提示 |
| **Summary** | 長い History の圧縮ビュー（必要時 refresh） | 任意（定期 or トリガー） |
| **Action Loop** | 候補生成・実行・検証 | 一部（候補生成など） |
| **Partial Judge** | 局所判定・State patch | 小さい LLM または規則 |
| **Global Judge** | 終了・方針転換・実装遷移 | 必要時のみ LLM |
| **Retriever** | History から当該 Action 用の断片を引く | いいえ（規則 / 類似度） |

### 4.2 「保存」と「提示」の分離

```text
Event occurs
  → ALWAYS append to History
  → ALWAYS update State (add / resolve / ban)
  → SOMETIMES refresh Summary
  → ONLY IF needed: retrieve N recent/relevant events into Prompt
```

---

## 5. Partial Judge / Global Judge

### 5.1 現行 Judge の責務分解

現行 `RESEARCH_JUDGE` が担っているもの:

| 責務 | 現行 | 提案 |
|---|---|---|
| 今回の finding は要求を満たすか | ○ `satisfies_request` | **Global**（または usable 昇格時のみ） |
| 何が足りないか (`missing`) | ○ | **Partial**（open_questions 更新） |
| reason 文章 | ○ | Partial（短い） / Global（レビュー時） |
| proposed_decisions | ○ | Partial（低リスク） / Global（方針変更） |
| Research 継続/停止 | 機械 progress | **機械 + Global トリガー** |
| candidate 選択 | 間接 | Partial（verify 後） |
| Implementation 遷移 | 機械 + satisfies | **Global** |
| Context 管理 | なし（結果的に肥大） | **非 LLM（State 規則）** |

### 5.2 Partial Judge

**役割:** 1 Action の結果だけを見て State を更新する。

入力（小さく）:

- Current State（要約版で可）
- 今回の Action 定義
- Verify 結果（ok / sample / error 要約）
- 該当する open_question 1 件

出力例:

```json
{
  "action_valid": true,
  "verify_ok": true,
  "state_patches": [
    {"op": "add_usable", "finding_ref": "..."},
    {"op": "resolve_question", "id": "q1"},
    {"op": "ban_action", "command": "...", "args": []}
  ],
  "new_open_questions": [],
  "escalation": null
}
```

呼び出し: **毎 Action 後**（規則で足りる場合は LLM 省略可）。

### 5.3 Global Judge

**役割:** ゴール整合・終了・方針変更・実装遷移。

入力:

- User Goal
- Current State（全体）
- Summary（短）
- Escalation 理由 + 関連 Recent Events（少数）

出力例:

```json
{
  "goal_satisfied": false,
  "decision": "continue|implement|pivot|stop|ask_user",
  "reason": "...",
  "policy_updates": [],
  "proposed_decisions": []
}
```

### 5.4 Global Judge 起動条件（監督トリガー）

| トリガー | 例 |
|---|---|
| 類似失敗連続 | 同一 `command_key` または同一 error class が N 回 |
| 新規未解決 | open_questions が増えた |
| State 大変化 | usable 追加、単位/意味の decision 変更 |
| 実装準備 | usable が要求をカバーしそう |
| 目的達成候補 | Partial が `goal_maybe_met` |
| リソース逼迫 | rounds / tool runs / chars / time が閾値 |
| 停滞 | stagnation detector（現行 progress 相当） |
| 判断不能 | Partial が `escalation: "unsure"` |
| 定期レビュー | 毎 K actions（保険） |

**毎ターン Global Judge は呼ばない。**

---

## 6. Context Budget Model

### 6.1 配分案（Web Action / Candidate 例）

Budget 例: **7680 chars**（現行 deepseek profile）

| 枠 | 配分 | 毎回? | 備考 |
|---|---:|---|---|
| System contract | 1200 | 固定 | 段階的に短縮可（別 Phase） |
| Goal | 200 | 毎回 | request + meaning/unit |
| Current State | 800 | 毎回 | decisions + usable 要約 + banned 短リスト |
| Open questions | 400 | 毎回 | 未解決のみ |
| Recent Events | 600 | 毎回 | **直近 1〜3** または retrieve 結果 |
| Summary | 400 | 任意 | Global 時は厚く、通常は薄く/省略 |
| Action-local materials | 1200 | 当該のみ | search_results / inventory 断片 |
| Safety / constraints | 300 | 毎回 | |
| **Reserved headroom** | **800** | 常時空 | overflow 直詰め禁止 |
| JSON shape / misc | 余白 | | |
| **合計上限** | **≤6880 + 800 headroom** | | |

Judge（Global）例:

| 枠 | 配分 |
|---|---:|
| System | 1500 |
| Goal + State | 1200 |
| Summary | 600 |
| Escalation evidence | 800 |
| Headroom | 800 |

### 6.2 毎回渡さないもの（明示）

| 渡さない | 代わり |
|---|---|
| 全 `prior_failures` | Recent 1〜3 / retrieve |
| 長い stderr 全文 | History に保存。Prompt は 80〜120 字要約 |
| 重複する STATE.unresolved + MATERIALS.unresolved | **State 側の open_questions のみ** |
| 古い `judge_reason` 全文 | 最新要約 or Summary 1 行 |
| 全 `search_results` 履歴 | 当該 Action の top-k のみ |
| 全 `insufficient_findings` 詳細 | Summary「不採用 N 件」+ banned list |
| exploration_hints 長文 | 空検索時のみ短ヒント |

### 6.3 Overflow 方針

1. **headroom を切って送らない**（Phase 4 正式化: `actual_headroom >= 800`）
2. 超過時は hints → retrieve 件数 → Summary 退避 → Action 延期 / Global 起動
3. 「圧縮して押し込む」は互換層として残し、通常経路では使わない

---

## 7. History / State / Summary Model

### 7.1 三層

```text
History   = 何が起きたか（完全、追記のみ）
State     = 現在どうなっているか（最新の真実）
Summary   = 過去の重要事項の圧縮ビュー（再生成可能）
```

### 7.2 History レコード例

```json
{
  "id": "evt_042",
  "ts": "...",
  "type": "verify_fail",
  "action": {"command": "powershell", "args": ["..."]},
  "result": {"ok": false, "error_class": "property_not_found", "error_preview": "..."},
  "related_question_ids": ["q_cpu_temp"],
  "judge_local": {"action_valid": true, "ban": true}
}
```

### 7.3 Current State 例

```json
{
  "goal": {"request": "...", "metric": "温度", "unit": "C"},
  "decisions": {"status.meaning": "WindowsのCPU温度"},
  "usable_facts": [{"id": "f1", "summary": "...", "evidence_ref": "evt_010"}],
  "open_questions": [{"id": "q_cpu_temp", "text": "CPU温度の取得方法が未確認"}],
  "banned_actions": [{"command": "powershell", "args_digest": "..."}],
  "resource": {"actions": 7, "verifies": 12, "global_reviews": 1}
}
```

### 7.4 解決済みの扱い

```text
open_question が解決
  → State.open_questions から除去
  → History に resolve イベント
  → usable_facts へ昇格（該当時）
  → Summary に「q_cpu_temp resolved by evt_010」1 行（任意）
```

**Context から消す ≠ システムから忘れる。**

### 7.5 Retrieve / Memory Recall 方針

History 全体を渡さず、**Rule-based Memory Recall Policy**（Phase 5 / 5.1）が断片を選ぶ:

| 条件 | Recall |
|---|---|
| `fresh`（新規問題・失敗≤1） | 過去履歴 **0〜1** preview |
| `related`（同一 question 失敗 2 回） | 関連 fail **1〜2** |
| `repeating`（error_class / command_family / open_question ループ + **情報非増加**） | 代表 **1〜2** + banned 要約 + **PIVOT REQUIRED** hint（増量しない） |
| Global / `escalation` | Summary + 関連 evidence **3〜5** |
| Implementation | usable の evidence のみ |

関連度スコア（規則）: open_question 紐づけ > error_class > command_family > 直近ラウンド。  
exact command 再実行は `banned_actions` に委譲（Recall の主目標にしない）。  
閾値未満は Prompt に載せない（History には残す）。

Phase 6: 規則が候補（最大 8）を絞った後、**Memory Judge LLM** が 0〜3 件を選択。失敗時は Phase 5 bundle にフォールバック。

---

## 8. Resource / Safety Model（暴走防止）

Global Judge を毎ターン呼ばなくても制御する手段:

| 機構 | 内容 | 既存との関係 |
|---|---|---|
| **Stagnation detector** | missing 同一 + 新 finding なしが連続 | 現行 `evaluate_research_progress` を拡張 |
| **Duplicate action detector** | `command_key` / args digest の再提案禁止 | 現行 `rejected_commands` + filter |
| **State transition validation** | usable 昇格条件（sample 数値・単位整合） | Verifier + 規則強化 |
| **Resource budget** | max actions / verifies / wall time / chars | `pipeline.yaml` を Action 単位に再定義 |
| **Confidence threshold** | low は State に入れない | 現行 split_findings |
| **Action cooldown** | 同一系統の探索にクールダウン | 新規 |
| **Escalation trigger** | §5.4 | 新規（Global の起動条件） |
| **Periodic global review** | 毎 K actions | 保険 |
| **Goal lock** | decisions（user confirmed）は Agent が上書き不可 | 現行 `apply_judgment` の上書き制限に近い |
| **Write scope** | 実装は proposal.path のみ。無関係ファイル禁止 | 実装契約 |
| **No silent pivot** | 要求メトリクス変更は ask_user または Global | Clarity 方針の延長 |

想定される暴走と対策:

| 暴走 | 主対策 |
|---|---|
| 無限 Research | resource budget + stagnation + Global stop |
| 同じ Tool 反復 | banned_actions + duplicate detector |
| 同じ失敗反復 | error_class 集約 + cooldown |
| 不要 Tool 生成 | Global のみ implement 許可 |
| 無関係探索 | open_questions に紐づかない Action を拒否 |
| 過剰コード変更 | path allowlist + diff size limit |
| Goal drift | goal lock + Global レビュー |

---

## 9. Migration Plan

現行を壊さず段階移行する。

### Phase 1 — History / State 分離（低リスク）

- History ストアを追加（既存 `research_rounds_detail` / judgments を正規化）
- `STATE.unresolved` を **open_questions + 短い失敗要約** に再定義
- 長い stderr は History のみ
- **Prompt 変更は最小**（まず保存モデルを分離）
- 現行 overflow 暫定圧縮は維持

**完了条件:** History に全 verify/judge が残り、State JSON が短くなる（cpu overflow 時 state 2244→目標 <800）。

### Phase 2 — Partial Judge 導入

- Verify 後に Partial Judge（または規則ベース patch）を挿入
- `missing` / ban / usable 昇格を Partial の出力に寄せる
- 現行 Research Judge は当面 Global 兼用のまま残す（二重運用）

**完了条件:** 局所更新が State patch 経由になり、Judge materials から raw unresolved 二重載荷を減らせる。

### Phase 3 — Global Judge を trigger-based 化

- 毎ラウンド Judge をやめ、トリガー時のみ Global
- 通常ラウンド: Candidate LLM + Verify + Partial（±規則）
- `evaluate_research_progress` を escalation ルータに統合

**完了条件:** 健全ケースで LLM 呼び出し/ラウンドが 2〜3 → **1〜1.5** 程度に低下。

### Phase 4 — Context budget 再設計（正式化済み）

- 枠配分 + reserved headroom **800** を実装
- Prompt builder が枠超過時に補助情報から削減（hints → Recent → Retriever → search）
- 中核（goal / state / open_questions / usable_findings）は保護
- **通常経路:** allocated 送信（`AI_AGENT_CONTEXT_ALLOC_LIVE=0` で legacy に戻せる）
- 暫定圧縮（Step 1〜2-2a）は互換層として維持（削除は Phase 5）

**完了条件:** overflow を予算配分違反として早期検知し、`actual_headroom >= 800` を維持。

### Phase 5 — Rule-based Memory Recall + 旧 handoff 削除

- `prepare_followup_research` は items / followup_questions のみ（PF/RC/reason 再掲をやめる）
- `memory_recall.py`: RecallMode + 関連度スコア + RecallBundle
- Prompt の過去失敗は RecallBundle → 互換キー `prior_failures` に短 preview
- 機械禁止は `state.banned_actions` を正（`filter_rejected_candidates`）
- 暫定圧縮は互換層として維持
- **通常経路:** `AI_AGENT_MEMORY_RECALL=0` で旧 handoff に戻せる

**完了条件:** Web / Global が §6 枠 + headroom に収まり、同一失敗の無意味反復が減る（基準値）。

### Phase 5.1 — repeating 再設計（pivot Recall）

分析結果: exact `command_key` 再実行は稀。主無駄は `error_class` 再発・open_question ループ・command_family 再探索。

- repeating 判定: **error_class / command_family / open_question ループ + 情報非増加**
- exact command 再実行は **banned_actions に委譲**（Recall の主目標にしない）
- prior_failures **増量禁止**（repeating 時代表 1〜2 件）
- Prompt 本体は **PIVOT REQUIRED** hint（停滞クラス / family / 未変化の質問）

**完了条件:** repeating が「同じ原因を回っている」ときにだけ発火し、pivot を促す。

### Phase 5.1 の扱い（2026-08-20 制御比較後）

- **正式化しない**（現状維持）
- exact command 反復は banned_actions が主抑制
- 主無駄は error_class / open_question / command_family
- 5.1 は family 反復を一部減少させたが、no_gain_fraction / usable 改善は未確認
- headroom は維持（圧迫ケースあり）。**Recall 件数増を主目的にしない**

参考基線: `research/llm_benchmarks/baselines/phase4_phase5_reference/`  
制御比較: `research/llm_benchmarks/phase_compare_controlled/`

### Phase KSS-0 — Knowledge Source Selection（観測のみ）

目的: Memory Recall をさらに複雑化せず、「どこから情報を得る価値が高いか」を**計測・保存**する。

候補 source: `state` / `history` / `external_research` / `llm_reasoning` / `experiment`

| 記録 | 内容 |
|---|---|
| `known_coverage` | 既知知識の探索カバレッジ（正解率ではない） |
| source values | 各知識源の相対価値（**自動切替なし**） |
| evidence 軸 | source_reliability / relevance / claim_support / independent_confirmation / implementation_precedent |
| action value 構成 | expected_information_gain / success_probability / evidence_confidence / applicability / repetition_risk 等（**Decision 禁止**） |
| calibration | Proposal → Action → Actual（success / usable gain / info gain） |

- Env: `AI_AGENT_KNOWLEDGE_SOURCE_OBS=1` で観測 ON（既定 OFF）
- Prompt 非載荷。Phase 4 `actual_headroom >= 800` を維持
- 閾値による自動実行・Web 常時強制・Phase 5.1 正式化は**非目標**

**完了条件（第一段階）:** predicted → actual の校正データが蓄積できること（成功率向上は求めない）。

### Phase KSS-1 — Decision Observability / Confidence Calibration

目的: LLM の自己評価 confidence が、成功・情報増加・Source 選択を予測できているかを測る（**行動は変更しない**）。

| 記録 | 内容 |
|---|---|
| confidence 5項目 | problem / solution / source / action / expected_information_gain（欠落は missing≠0） |
| preferred_source | LLM 自己申告（自動切替なし） |
| outcome | success / useful_failure / zero_information_failure（`no_gain` 再利用） |
| provenance | decision_id ↔ result ↔ History |
| 重点指標 | `high_confidence_zero_gain_rate` / high-confidence stuck |

- Env: `AI_AGENT_KSS1_OBS=1`（既定 OFF）
- Web candidate CONTRACT に optional `observation`（記録専用・行動指示ではない）
- 実行前に observation を候補から剥がす → verifier 経路は従来と同一
- 自動 HELP / Web 強制 / 上位 LLM / filtering / Phase 5.1 正式化は禁止

**完了条件:** confidence↔outcome を provenance 付きで対応でき、既存 pipeline の行動を変えない。

### Phase KSS-1.1 — Decision Evidence Audit

KSS-1 で LLM 自己申告 coverage=0 を確認したため、**自己申告 confidence を正式信頼度にしない**。

代わりに既存判断の根拠を写す:

- verifier high/low、finding bucket、progress action/reason
- judge source（llm / live_skip）、escalation、filter 棄却数
- no_gain / KSS-0 coverage（再利用）
- evidence_level ∈ {high,medium,low,missing}（既存ラベルのみ）

Env: `AI_AGENT_KSS11_OBS=1`。mapping: `docs/kss11_decision_evidence_mapping.md`。

**完了条件:** decision→evidence→threshold→final を History/round_details から再構成できる。ルーティングは実装しない。

### Phase KSS-1.2 — Verifier/Rule 校正 + Web↔decision 紐付け監査

KSS-1.1 の写しを使い、**既存 Verifier/Rule → progress / case outcome** の校正表をオフライン生成する。あわせて Web hit ↔ 候補/実行の紐付けギャップを監査する。

- 校正: `research/llm_benchmarks/kss12_calibration.py`（KSS-1.1 実験ディレクトリを再分析）
- 観測拡張（行動不変）: `tools/ai/state/web_decision_link.py`
  - `web_hits[].score`（既存 `hit_score`）
  - candidate↔hit の token overlap リンク
- Env: `AI_AGENT_KSS12_OBS=1`（未設定時は `AI_AGENT_KSS11_OBS` を継承）
- **routing / confidence 閾値は実装しない**

**完了条件:** verifier label→progress と web link_coverage / audit_gaps がレポートに残る。閾値導入はしない。

### Phase KSS-1.3 — 探索価値・情報利得の観測基盤

各 research round について、新しい URL/ソース/語彙、candidate↔hit 接続、既存 `information_gain`/`no_gain`、その後の成功・失敗を後から照合できる観測を追加する。

- モジュール: `tools/ai/state/exploration_value.py`
- 分析: `research/llm_benchmarks/kss13_analyze.py`
- ベンチ: `research/benchmarks/kss/_kss13_measurement_bench.py` → `research/llm_benchmarks/knowledge_source_obs/kss13_*/`
- Env: `AI_AGENT_KSS13_OBS=1`
- **単一 exploration_value スコア / routing / confidence 閾値は作らない**
- 取得不能は `missing`（`docs/kss13_exploration_value.md`）

**完了条件:** round 観測 + success/fail 比較 + 仮説1〜5の暫定評価が report に残る。行動経路は不変。

### Phase KSS-1.4 — 情報喪失点 + discarded hit 答え存在性

Research チェーン（search→…→final）で情報がどこで落ちたかを観測し、kept/dropped hit に `answer_presence`（direct/core/lead/related/none/unknown）を付ける。

- `tools/ai/state/information_loss.py`
- `tools/ai/state/web_answer_presence.py`（heuristic; LLM Judge は分離・既定 OFF）
- 分析: `research/llm_benchmarks/kss14_analyze.py`
- ベンチ: `research/benchmarks/kss/_kss14_measurement_bench.py` → `knowledge_source_obs/kss14_*/`
- **routing / should_continue_web / confidence は実装しない**
- 歴史データに dropped が無い場合は `missing`（捏造しない）

**完了条件:** trajectory・喪失分類・answer_presence 集計と「routing に十分なデータか」の明示。

### Phase KSS-1.5 — Discarded hit 実測 + 人手監査

Live で `kept/dropped` を同一検索集合として保存し、人手監査ワークシートを生成する。

- `tools/ai/state/web_hit_partition.py`
- executor に `obs_hit_partition`（filter 不変）
- ベンチ: `research/benchmarks/kss/_kss15_measurement_bench.py` → `knowledge_source_obs/kss15_*/`
- 出力: `summary.json`, `report.md`, `human_audit_dataset.json`, `human_audit_worksheet.md`
- LLM Judge は人手ラベル後（既定 OFF）
- **routing しない**。過去データから dropped を捏造しない。

### Phase KSS-1.5.1 — Human audit ground truth

KSS-1.5 live（例: `kss15_20260820_160911`）を**上書きせず**、dropped 全件 + 失敗ケース kept(core unique URL) の人手監査テンプレートを作る。

- `research/benchmarks/kss/_kss151_human_audit.py` → `knowledge_source_obs/kss151_*/`
- `human_audit_status=pending` の間 `routing_ready=false`
- heuristic / `dropped_answer_rate` を確定精度として扱わない
- `answer_present` ≠ run success

### Phase 6 — Partial LLM / Memory Judge

- Memory Judge: 規則候補≤8 から 0〜3 件を LLM 選択（History 全件は読まない）
- Partial LLM: verify 直後の StatePatch（Memory Judge と別呼び出し）
- 失敗時は Phase 5 rule bundle にフォールバック
- Phase 5 を基準値として Δ（rounds / repeat rate / llm_calls）を測る

**完了条件:** 「LLM なしでもここまで」と「Memory Judge の追加価値」を分離して示せる。

### 移行時の非目標（各 Phase 共通）

- PASS/FAIL 基準の変更を同時にやらない
- Judge 契約の大幅書き換えと State モデル変更を同一 PR に混ぜない
- 5 基準ケースで overflow・rounds・llm_calls を回帰観測

---

## 10. Quantitative Estimate

根拠: Step 2-1 overflow run（`cpu_temperature`, 2026-08-20T06:06）と Step 2-2a 10r run（同ケース, 07:32）。LLM 再実行なし。

### 10.1 現行実測

| 指標 | Step 2-1 overflow | Step 2-2a 10r |
|---|---|---|
| 停止理由 | context_overflow @ research_6 | max_research_rounds |
| estimated / budget | **7738 / 7680** | overflow なし |
| system / user | 1816 / 5922 | （健全時 web ≈5.0k total） |
| STATE render | ≈2186（unresolved ≈1757） | final state ≈490（unresolved 0） |
| llm_calls | 13 | **28** |
| rounds / judgments | 5 完了 + 6 目で失敗 | 10 / 10 |
| research_input 成長 | — | 257 → ≈1900 ch（PF/RC） |

健全時の目安:

- Web candidate ≈ **4.3k–5.4k ch/round**（avg ≈5.0k）
- Judge ≈ **5.5–6.0k ch/round**（insufficient 蓄積後）
- Judge system だけでも ≈3507（Web system の約 1.9×）

### 10.2 方式比較（cpu_temperature 想定）

前提: 10 Action で Research 終了または上限。

| 方式 | LLM 回/Action | LLM 回/10 Actions | Prompt ch/回（概算） | 累積 Prompt ch（概算） | 備考 |
|---|---:|---:|---:|---:|---|
| **A. 現行** | 2〜3 | 20〜30 | Web 5.0k + Judge 5.9k | **≈110k–160k** | 実測 28 calls |
| **B. State 中心**（履歴フル廃止、Recent 1） | 2 | 20 | Web ≈3.5–4.5k + Judge ≈4.0k | **≈75k–85k** | Judge 毎ラウンド維持 |
| **C. Partial + Global** | 1〜1.2（通常）+ Global 2〜3 回 | **12〜15** | Action ≈3.5k / Global ≈5.0k | **≈50k–60k** | 監督はトリガーのみ |

Overflow 直前（7738）を B/C の slim prompt にした場合の再構成見積:

| | chars |
|---|---:|
| 実測フル | 7738 |
| State + unresolved + Recent 1 | **≈4666** |
| 削減 | **≈3072（約 40%）** |
| budget 7680 に対する余裕 | **≈3014**（headroom 800 を確保しても余裕） |

### 10.3 「解決済みを Context から除去」の効果

| 状況 | unresolved 寄与 | 除去の効果 |
|---|---|---|
| cpu 10r（最終 unresolved 空） | ≈0 | PF/RC 側が主因。**Recent 制限**が効く |
| overflow 失敗時 | state の **~78%**（1757/2244） | stderr 全文を History へ移すだけで **user から ~1.5k+** 削減可 |
| disk / gpu_vram | state の ~53% | open_questions 化で同様 |

件数制限（max_rounds=10, stagnation=3）への影響:

- Context から解決済みを外しても **無限 Research は止まらない**（別途 resource / stagnation が必要）
- ただし「ラウンドを重ねるほど必ず overflow」という結合は弱まる  
  → 制限値を「安全のためのハードキャップ」に戻し、実質は State 品質と escalation で止められる

### 10.4 解釈

1. **最大の無駄は「同じ失敗の多表現同時提示」**であり、文字圧縮より情報アーキテクチャの問題。  
2. **長い Research でも STATE.unresolved が空なら overflow しない**（2-2a）。肥大の主因は handoff（PF/RC）と、別ランでの **エラー全文の State 混入**。  
3. Partial/Global 分離は、累積 Prompt と呼び出し回数の両方を削る（概算 **半減前後**）。  
4. headroom 付き予算配分は、7738 級の再発を構造的に防ぐ。

---

## 11. 判断基準への回答

| 問い | 回答 |
|---|---|
| 同じ情報を何度も LLM へ渡す必要があるか？ | **基本不要。** State の単一ソース + Recent/Retrieve で足りる |
| 履歴を大量に渡せば自律性が上がるか？ | **仮定しない。** 正確な Current State の方が重要 |
| いつ History を見せるか？ | escalation・類似失敗・実装根拠の確認時に限定 retrieve |
| 暫定圧縮の位置づけ | Phase 1–4 の間は維持。Phase 5 で旧 handoff と共に整理 |

---

## 12. 次の実装に進むときの推奨順

1. **Phase 1 のみ**（History 正規化 + unresolved の短い open_questions 化）を最初の実装 PR にする  
2. 5 基準ケースで `state` 文字数・overflow・llm_calls を計測  
3. 効果が確認できてから Phase 2（Partial）へ  

本ドキュメントは設計・調査のみ。コード変更・LLM 実行・ケース再実行は行っていない。

---

## Appendix A — 現行定数早見

| 定数 | 値 | 場所 |
|---|---|---|
| `max_research_rounds` | 10 | `config/pipeline.yaml` |
| `max_research_stagnation` | 3 | 同上 |
| `max_tool_rounds` | 5 | 同上 |
| Candidate search results (prompt) | 3 / snippet 160 | `web.py` |
| Judge reason (candidate) | 240 | `web.py` |
| prior_failures truncate | q120 / e200 / f200 | `research_result.py` |
| Context budget | `(limit - predict - 128) * 4` | `context_budget.py` |
| Reserved headroom | **800** chars | `context_allocation.py` |
| Context alloc live | 既定 ON（`LIVE=0` でオフ） | `context_allocation.py` |
| Memory recall | 既定 ON（`MEMORY_RECALL=0` で旧 handoff） | `memory_recall.py` |
| Memory Judge | 既定 OFF（`MEMORY_JUDGE=1` で ON） | `memory_judge.py` |
| VERIFY_TIMEOUT / MAX_OUTPUT | 15s / 2000 | `verify.py` |

## Appendix B — 関連実測タイムスタンプ

| ラベル | timestamp | ケース |
|---|---|---|
| Step 2-1 POST overflow | 2026-08-20T06:06:12 | cpu_temperature |
| Step 2-2a | 2026-08-20T07:29:16〜07:38:56 | 5 基準ケース |
