# 開発状態Checkpoint — Cursor引継ぎ記録

更新日: 2026-09-04（P2-16.9〜P2-18 履歴 Checkpoint）
対象: Tool Result Contract / Agent Task Runtime / Safe Development Workspace

> **重要:** 以下のGit状態、SHA、件数、次フェーズは 2026-09-04 時点の履歴値であり、現在値ではない。
> 作業再開時は`git rev-parse HEAD`、`git branch --show-current`、`git status --short`で実測し、
> 現在Repositoryの実態を優先する。

## 現在状態追記 — 2026-09-08（H4 Core）

人間が **H4 Core を完了承認**した。H4 Core ≠ H4 製品全体。merge / push / promote は別指示。

正本:

- 層1: `docs/prds/help-system-h4-selection-core.md`
- 層2: `docs/tech-specs/help-system-h4-selection-core.md`
- 層3: `docs/prds/help-system-h4-selection-core-decision-log.md`
- H4-1（第一段階、H4 Core に包含）: `docs/prds/help-system-h4-stage-1.md`

独立 ToDo（H4 Core 外。**設計・実装未着手**。Core の Q4–Q6 を再開しない）:

1. **Task / Action Ownership** — User Goal / Task Capability / Internal Action の分離。1 Task の内部分解と Sub-Agent 所有。複数 CapabilityResolution の Task 単位への畳み。
2. **Tool Gap → Tool Builder Bridge** — Tool 非依存の Capability 認識。Gap 後の作成可能性評価、既存 Tool 組合せ、Proposal / Builder 接続、Human Gate。`_RULES` 復活はしない。

詳細は層1 PRD「独立 ToDo」。次 Goal の設計 Packet はまだ作らない。

本文書の 2026-09-04 Checkpoint（SHA / 件数 / P2-19 候補）は履歴。上書きしない。

## 現在状態追記 — 2026-09-08（Skills 正式採用）

Human Decision: 評価した 5 Skills を標準開発資産として正式採用した。評価 checkpoint `4951af9` は amend しない。

採用: `grill-me` / `write-prd` / `tech-spec` / `graph-engineering` / `planning-and-task-breakdown`

正本: `.agents/skills/PROVENANCE.md`  
互換 Adapter: `.cursor/rules/skill-namespace-compat.mdc`（`eval-` 一時名称は廃止。Skill 本文は変更しない）

交換・補強・追加は、実案件で不足・挙動不一致・冗長性・再現性不足が確認された場合に検討する。

## 現在状態追記 — 2026-09-09（通常運用レイアウト / Sandbox parent）

通常運用の作業場所:

- 本体 / Stable: `D:\AI-Agent` @ `stabilize/tool-result-contract` `f538a94`
- 開発: `D:\AI-Agent-worktrees\current-dev` @ `dev/current`
- KEEP（今回対象外）: `D:\AI-Agent-data`（Docker / URロボット通信データ）

Dedicated Sandbox parent は `config/sandbox_workspace.json`（必要なら環境変数 `AI_AGENT_SANDBOX_PARENT`）。既定は `D:\AI-Agent-worktrees\sandboxes`。`parent.parent / AI-Agent-sandboxes` のパス算術は使わない。

独立 ToDo（未着手）: wip branch `wip/tool-result-contract-20260908` @ `a52c979` の unique ファイル（`semantic_*`、設計 Map、メモ）を Stable へ救出するか。worktree は退役済み。branch ref は保持。

## 現在状態追記 — 2026-09-09（Phase 2 Cleanup）

常設構成:

- `D:\AI-Agent` — Stable 本体
- `D:\AI-Agent-worktrees` — `current-dev` / `sandboxes` / `archive`
- `D:\AI-Agent-data` — Docker / UR通信関連データ（未操作）

退役済み（フォルダ削除）: 旧 `tool-result-contract` worktree 残殻、`tool-result-contract-stabilize` 残殻、`D:\AI-Agent-sandboxes`、`D:\AI-Agent-grok-sandbox`。unique 記録は `D:\AI-Agent-worktrees\archive`。Git Guard example は `repo: "."`。branch 削除・push・promote はしていない。

## 現在状態追記 — 2026-09-09（Auto Upgrade System v0 / Validation Gate + Q36）

実験継続を人間が承認。Production Runtime へは未統合。push / promote なし。

Experimental Gate に保持している一般則（Q番号 allowlist なし）:

1. `cardinality_index_or_head_select`（Gate 1）— Q31 由来
2. `polarity_fork_unclosed`（Gate 2）— Q2 由来
3. `shared_keyword_family_prefer`（Gate 1）— Q36 由来。Avoid したうえで unnegated prefer する混合文は FAIL

Validation Gate: `research/auto_upgrade_system/validation_gate.py`

- `packets/hidden_eval.json` は evaluator のみ。adopted 本文を Local に送らない
- AUTO かつ danger_if / rejected 極の unnegated adopt を false AUTO として stage confirm で落とす
- 前回 Holdout 5（`runs/20260908T223431Z`）の Q36 AUTO は、この Gate なら confirm FAIL になることをテストで確認

独立 Upgrade Case Q36（標準経路 1→確認→5→確認→target→holdout）:

- runner: `research/auto_upgrade_system/run_q36_case.py`
- 正本 run: `research/auto_upgrade_system/runs/20260908T224940Z/`
- Human Review: 同梱 `HUMAN_REVIEW.md`（推奨 Adopt、production_candidate=false）
- Q36: AUTO → REVIEW（Gate 1 FAIL）。true AUTO 脱落なし。Holdout 5（Q33/Q37/Q41/Q23/Q42）は AUTO かつ false_auto=0
- LLM は呼んでいない

次段階（未実施）: 上位 LLM による Failure分析 → Upgrade分類 → Candidate生成 の自動 Loop。今回は検討対象として記録するだけ。

## 現在状態追記 — 2026-09-09（名称整理: テスト改善ループ）

人間向け表示名: **テスト改善ループ**
内部ID: `test_improvement_loop`
正本 path: `research/test_improvement_loop/`

旧名称 `Auto Upgrade System v0` / 旧 path `research/auto_upgrade_system/` は互換 alias。import と `runs/` junction を残し、過去 Run・HUMAN_REVIEW・Before/After は書き換えない。

Q2 / Q31 / Q36 と Experimental 一般則 3 件は維持。上位 LLM 自動分析 Loop は未着手。Production / push / promote なし。

## 現在状態追記 — 2026-09-09（2資産を一区切りとして凍結）

新しい実験はしていない。文書化のみ。

人間向け入口: `docs/SYSTEM_ASSET_INDEX.md`

- Local LLM Human-Judge代替 仮仕様 v0 → `research/llm_benchmarks/h4_decision_maker_bench/HUMAN_JUDGE_PROXY_V0.md`
- テスト改善ループ v0 凍結 → `research/test_improvement_loop/V0_FREEZE.md`
- Grill v0（人間向け） → `docs/GRILL_V0.md`

次回改善時は Index から正本を開く。Production / push / promote なし。

## 現在状態追記 — 2026-09-09（凍結資産の Git 保全 / Grill v0 文書）

checkpoint `2ffecf7` は保持。実装・tests・互換 shim と代表 Run を別 commit で保全。Grill 実験コードは未着手。

## 現在状態追記 — 2026-09-09（Chat入口 / pending read / Grill観察研究）

履歴 Checkpoint の「Grill 実験コードは未着手」は、当時の Human Grill v0 文書化時点の記録。上書きしない。以降の確認済み事実は本追記を優先する。

**現行 Chat Production 入口:** `ai_tool/chat_interface/agent_turn.py` の `run_chat_turn`。Chat UI（`ai_tool/run_chat_ui.py` / `server.py`）も同じ。`agent.py` は別入口として残る。廃止ではない。

**search → pending read:** Production 一般 Runtime として、search hit → pending observation/read → Help で `workspace_file_read` 確認 → Runtime が `read_file` を注入する経路がある（H4 Core）。実 qwen3:14b / `run_chat_turn` で search → pending read → Runtime 注入 → 次 LLM → Final を 1 回観測（Session `cs-20260909_051350-be4359`）。これは search hit 後の追加観測を補助する Runtime bridge であり、意味的に次に読む対象を判断する機構ではない。Grill の代替でもない。

**Grill観察研究:** `research/grill_observation_v0/`。Semantic Need → System First → 解決不能時 Grill → System Retry を実施済み。`grill_system_retry_v0` Run `20260909T055809Z` は Capability / Help / Tool 選択まで成立。Grill は Tool を直接実行せず、Harness 独自の意味→Tool mapping も使わず、Tool 選択は既存 System。判定は PARTIAL（既存 research 公開集合の制約で Tool 実行未完走）。Production 統合・E2E完成ではない。

研究上の Grill 役割（Production 契約ではない）: 意味分解専用に限定せず、現在進めない未解決点を掘り、System が再処理を開始できる情報を増やす。

**Grill Grounding 比較:** 同一 Goal で研究用 Grill Prompt の Grounding 部分だけを追加した Run `20260909T061247Z`。Baseline の未確認具体化（商品名・価格・在庫等）は消え、場所・形式・アクセス方法を不明として保持し、不足を次の確認事項として扱った。研究観察ラベル GROUNDED。1 比較 Run。Production Rule ではない。全 Runtime 共通 Rule としても未確定。

**Completion / Final（同一 Production 実 Run で観測）:** Completion 条件 UNKNOWN、Task / Goal は in_progress、`final_synthesis_context.ready = false` のまま終了したケースを確認。`gate_answer` は未確認表示を付けるが、Final Answer 内 Claim と Tool Result の文単位突合は行わない。Tool Result に無い workspace 固有 Claim も観測された。Evidence Judge / Claim Judge / Completion 新 Rule は未実装・未採用。本追記は観測の記録であり、新設計ではない。

**未統合のまま:** Production Grill Phase、System 不能 → Grill → Retry の Production 接続、Completion UNKNOWN → Grill の正式 handoff、Grounding の Production Rule 化、Evidence / Claim Judge。

人間向け入口: `docs/SYSTEM_ASSET_INDEX.md`（Human Grill と Grill観察研究を別項）。

## 現在状態追記 — 2026-09-10（Goal Completion Gate 仮仕様 v0）

人間が **Goal Completion Gate 仮仕様 v0** を PROVISIONAL / 仮採用した。System規則ではない。一般自動達成判定は完成扱いにしない。

正本: `docs/GOAL_COMPLETION_GATE_V0.md`
概念入口: `docs/concepts/CONCEPT_DEFINITIONS.md`（`original_goal` / `execution_end_state` / `Goal Completion Gate`）

確認済みコード事実（実装追加ではない）:

- Chat Production の Mission Memory 書き込みは `goal_achievement_performed = false`、通常終了は `execution_end_state_judgment = not_judged`（`ai_tool/mission_memory/chat_persist.py`）。Goal達成判定は **NOT_CONNECTED**。
- `HUMAN_GRILL` / `APPROVAL_REQUIRED` のときだけ `judged` + `execution_end_state = paused`。
- 完全一覧から要求指名ファイルが欠けることは、既存 Task 条件 `relevant evidence observed` の Observation 材料になりうる。Goal達成条件の追加ではない（`task_orchestration.py`）。
2026-09-10 追記: Human には Goal 完了条件を聞き、接続済み回答だけ System が Mission 状態へ写す。同一 mission_id で再判定する。未対応回答は停止。README 欠落が第1 E2E。正本 §13。

未接続は正本 §12 のまま（自然文の一般自動達成、needs_continuation / ended_incomplete の一般判定、Human回答後の再開 Bridge を含む）。

## 現在状態追記 — 2026-09-10（Dev Skill Registry / Goal Handoff）

**Dev Skill Registry** と **Goal Handoff Packet v0.1** を追加した。PROVISIONAL。Production Runtime 未接続。

正本:

- 機械カタログ: `registry/skills.json`（schema: `registry/schema/skills.schema.json`）
- Handoff 契約: `registry/schema/goal_handoff.schema.json`
- 人間向け仕様: `docs/specs/GOAL_HANDOFF_V0.md`
- 採用記録: `.agents/skills/PROVENANCE.md`
- ローカル provisional Skill: `.agents/skills/goal-handoff/SKILL.md`
- 例: `docs/handoffs/examples/goal-handoff-example.json`

採用済み imported Skill 本文（5件）は変更していない。`goal-handoff` はローカル新規。

標準合成（機械正本）: `standard-feature-dev` =
`write-prd` → `graph-engineering` → `tech-spec` → `planning-and-task-breakdown` → `goal-handoff`

確認済み（2026-09-10 実測）:

| 場所 | branch | HEAD |
|---|---|---|
| `D:\AI-Agent` | `stabilize/tool-result-contract` | `531cdd4` |
| `D:\AI-Agent-worktrees\dev-current` | `dev/current` | `531cdd4` |

関連テスト: `tests/registry/test_skills_registry.py` — 2 passed（Registry / 例 Packet の Schema 検証）。

**Policy Manifest 追記（2026-09-10）:** `development_policy.json` の `canonical_files` に `registry/skills.json`、`docs/specs/GOAL_HANDOFF_V0.md`、`docs/SYSTEM_ASSET_INDEX.md` を追加。alias 正本は Registry、`skill-namespace-compat.mdc` は Cursor ミラーへ追随。

**NOT_CONNECTED（意図的）:**

- Production Chat / Mission Memory / Goal Completion Gate から Handoff Packet を読む経路
- Local Agent が Skill 本文または Handoff Packet を読む契約

旧 `D:\AI-Agent-worktrees\current-dev` は worktree 再作成時に登録解除。未コミット作業のコピーは `D:\AI-Agent-worktrees\archive\current-dev-wip-search-20260910` に退避。現行開発 worktree は `dev-current`。

概念入口: `docs/concepts/CONCEPT_DEFINITIONS.md`（`goal_handoff_packet` / `dev_skill_registry`）。

## Checkpoint作成時のGit状態（履歴）

- Worktree: `D:\AI-Agent-worktrees\tool-result-contract`
- Branch: `stabilize/tool-result-contract`
- HEAD: `21071420059c1e0c2692f672676ccc0082bb15fc`
- staged: 0件
- unstaged tracked: 21件
- untracked: 本文書追加後19件（別途`.pytest-temp-p2168b/`へのアクセス警告あり）
- gitlink（mode 160000）: 0件
- Production未反映
- masterへのmerge / pushは未実施

このCheckpoint作成時点では、実装は未commit差分に含まれていた。`reset`、`clean`、
`restore`、古いHEADへの巻き戻しを行わないこと。

### Checkpointへ含めない要確認差分

以下はP2-16.9〜P2-18の実装とは分けて扱う。

- `runs/ai_tool/context_monitor/observations.jsonl`: 実行時観測ログ。約3.2MB。
- `runs/ai_tool/last_policy_eval.json`: テストまたは実行による状態更新。
- `.pytest-temp-p2168b/`: 過去pytestの一時ディレクトリ。現在の環境ではアクセス警告あり。
- `research/llm_benchmarks/.../R_fail_empty_hits/SUMMARY.md`: 長いパスにある削除差分。P2実装との関係は未確認。

これらを一括stageしない。必要性を人間が判断するまで削除・復元もしない。

## 完了済みフェーズ

### P2-16.9 Capability Resolution / Tool Gap Bridge

- Taskから必要Capabilityを機械的に抽出
- Capability Indexと`registry/tools.json`のagent visibilityを照合
- equivalent Capabilityを探索
- 確認済みEvidenceがある場合だけTool Gapを確定
- read-only Capabilityを既存Action Bridgeへ接続
- 不足CapabilityはHuman Approval待ちとして記録

### P2-17 Safe Development Workspace

- `SandboxSession`とSandbox identityを追加
- relative path限定のPath Guardを追加
- absolute path、`..`、resolve escapeを拒否
- symlink / junction経由のSandbox外escapeを拒否
- Production Rootとの分離をRuntimeで確認

### P2-17.1 Dedicated Sandbox Session

- Sessionごとに`S-<UUID>`をRuntime側で生成
- `<sandbox-parent>/S-<UUID>`へ専用linked worktreeを作成
- Git Base（HEAD）とWorkspace Base（現在の実作業snapshot）を分離
- tracked変更、tracked削除、非ignoreのuntrackedをSandboxへ反映
- 元Worktreeのbranch、HEAD、status不変を前後確認
- 作成失敗時は専用worktreeと一時branchだけを回収

### P2-18 Safe Mutation Tools

- `create_file`: Dedicated Sandbox内でのみ新規UTF-8ファイルを作成
- `edit_file`: 既存UTF-8ファイルの単一exact replacement
- 既存ファイル上書き、複数一致、decode不能、binaryを拒否
- LLM schemaへ`session_id`や`sandbox_root`を公開しない
- Agent executorがRuntime所有Sessionをhidden引数として注入
- Mutationをhash、path、action、timestamp付きで記録
- Mutation Evidenceは`OBSERVED`として保存
- Tool成功または編集成功だけではTaskをCOMPLETEにしない

## それ以前の重要な実装

- Tool Result Contract v1のproducer / consumer統一
- Runtime `TOOL_PARTIAL`
- Requirement DecompositionとCompletion Coverage
- Tool Expectation Hint
- Progress / Stagnation / structured stop reason
- Local Review Loop
- 日本語Run要約
- Concept ResolutionとInformation Certainty
- Timing BreakdownとFinal LLM Lifecycle記録

## 現在のSandbox構造

```text
Production Root
D:\AI-Agent
  └─ Productionへの直接writeは禁止

開発Worktree
D:\AI-Agent-worktrees\current-dev
  └─ 人間 / Cursor / Codexが現在の未commit実装を保持

現行 worktree（2026-09-10 追記。上図の `current-dev` は履歴）:
`D:\AI-Agent-worktrees\dev-current` @ `dev/current`

Dedicated Sandbox Root
D:\AI-Agent-worktrees\sandboxes\S-<session-id>
  └─ Local Agent専用linked worktree（設定: config/sandbox_workspace.json）
```

Runtimeが所有するSession情報:

- `session_id`
- `sandbox_root`
- `session_kind=DEDICATED`
- `branch`
- `base_head`
- `current_head`
- `git_base`
- `workspace_base`
- `status`
- `created_at`
- `production_applied=false`

P2-18 Mutation Toolは`session_kind=DEDICATED`以外を拒否する。P2-17で利用した通常開発Worktree型SessionをMutation先にはできない。Production反映は将来の専用Promotion経路だけで扱う。

## テスト結果

P2-18単体:

- 22 passed
- 1 skipped

P2-18の広範囲関連回帰:

- 258 passed
- 2 skipped

Dedicated Session必須Gate追加後の最終関連回帰:

- 175 passed
- 2 skipped

確認対象にはP2-17 / 17.1、Tool Result Contract、Registry、P2-16.9、Runtime、Agent Loop、Recorder、Human Summaryを含む。

SkipはWindows環境でsymlink作成権限が利用できないテストであり、Path Guardのsymlink / junction escape拒否ロジック自体は実装済み。

## Checkpoint適性

P2-16.9〜P2-18の実装コードには、確認した範囲でTODO、FIXME、`breakpoint()`、`pdb.set_trace()`等の途中デバッグコードはない。関連回帰も成功している。

ただし、working tree全体をそのまま一括commitしてはならない。上記の実行ログ、一時ディレクトリ、由来未確認の削除差分を除外し、P2関連コード・Registry・tests・設計資料だけを明示的にstageする必要がある。選択的stage前の人間確認を経れば、完成checkpointとしてcommit可能な状態である。

## 既知の制限

- `run_pytest`未実装
- `run_python_compile`未実装
- general shell / unrestricted `run_command`なし
- `apply_patch`、delete、move、renameなし
- Promotion Executorなし
- Production writeなし
- Mutation rollbackなし
- UTF-8テキストとexact replacementのみ
- symlink / junctionの実テストはWindows権限に依存
- Dedicated Sandboxの長期保持、一覧、期限切れ回収は未実装

## Checkpoint作成時点の次フェーズ候補（履歴）

次は`P2-19 Safe Verification Tools`。

候補:

- 制約付き`run_python_compile`
- 許可済みTest Patternだけを実行する制約付き`run_pytest`

Dedicated Sandbox内だけで実行し、固定された引数、timeout、出力上限、Runtime記録を必須とする。general shellやunrestricted `run_command`へ広げない。

## Cursorが最初に確認すること

1. この文書を履歴Checkpointとして読む。
2. worktree、branch、HEAD、staged / unstaged / untracked、diffを実Repositoryと照合する。
3. 別AIの変更があれば巻き戻さず、現在Repository上で完了済みか未完かを判断する。
4. `docs/DEVELOPMENT_TEST_POLICY.md`に基づいてREUSE / SPOT_CHECK / RERUNを判断し、必要範囲だけ検証する。
5. 最新の正本仕様・ユーザー指示と実態が一致することを確認してから、現在の次工程へ進む。
6. Git操作は`docs/GIT_OPERATION_POLICY.md`に従い、一括stageを避ける。
