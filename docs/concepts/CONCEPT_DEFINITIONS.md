# Concept Definitions

概念そのものの Origin / Current / Provisional / History を確認する入口。

- プロジェクト開始時の目的・構想の正本は `PROJECT_SPEC.md`。ここへ全文コピーしない。
- このファイルは Current の正本ではない。コードと矛盾したら `CURRENT / CODE DRIFT` とし、LLM がどちらが正しいか決めない。
- Origin と Current に上下関係は無い。新しいから正しい、初心だから正しい、とはしない。
- Origin へ回帰する変更は禁止しない。Origin 自体を「最初からこうだった」と書き換えることは禁止する。
- 全概念を先に登録しない。必要になったものだけ追記する。

## 使い方

| 欄 | 意味 |
| --- | --- |
| Origin | 出発時の意図。既存文書があれば参照のみ。無ければ `NOT_DETERMINED`。推測で埋めない |
| Current | 現在採用している概念上の意味。コードの代替ではない |
| Provisional | 未確定の仮定。正式 Current ではない |
| History | なぜ変わったか。Git 差分の代用ではない。Origin 回帰も「後退」と自動判定しない |
| Status | `CURRENT` / `PROVISIONAL` / `NOT_DETERMINED` など |
| 確認が必要になる条件 | 次に人間判断が要るきっかけ |

---

## プロジェクト Origin（参照）

```text
Origin: PROJECT_SPEC.md
  §1 Project Purpose
  §3 Core Design Principles
```

ここを Current で上書きしない。無効とも自動判定しない。

---

## correlation_id

```text
Concept: correlation_id

Origin:
  NOT_DETERMINED
  PROJECT_SPEC.md および既存のプロジェクト仕様書に定義は無い。推測で Origin を作らない。

Current:
  Chat ターンという作業単位を識別する。
  そのターン内で生成された LLM Proposal も同じ ID を使う。
  対象外（拡張しない）: API 単独 Proposal、human_revision、problem_record、
  Job、Implementation、Test。

Provisional: NONE

Status: CURRENT（上記範囲に限る）

確認が必要になる条件:
  上記対象外へ意味を広げるとき。
  Current とコードが食い違うとき（CURRENT / CODE DRIFT）。
  Origin 側の考え方へ戻すとき。

History:
  - 変更前: Chat ターンと Proposal がそれぞれ new_correlation_id() していた
    （同一対象かどうかは当時コード上未定義）
  - 変更後: Chat ターン開始時に 1 回生成し、propose_specification と
    Event / Session が同じ ID を使う
  - 変更時期: 2026-08-31
  - 変更理由: Chat ターンとその中の LLM Proposal を同一作業単位とする人間判断
  - きっかけ: 二重発行の調査。二重発行そのものをバグとはしなかった
  - 人間判断: あり（採用した事実。技術的正しさの証明ではない）
  - Origin との関係: Origin は NOT_DETERMINED のまま。Origin を書き換えずに Current を置いた
```

---

## implementation_id

```text
Concept: implementation_id

Origin: NOT_DETERMINED

Current: NONE

Provisional: NONE（仮定を正式化しない）

Status: NOT_DETERMINED

確認が必要になる条件:
  Proposal → Implementation を実際に接続するとき。
  作業単位か成果物単位かを決めるとき。
```

---

## test_run_id

```text
Concept: test_run_id

Origin: NOT_DETERMINED

Current: NONE

Provisional: NONE（仮定を正式化しない）

Status: NOT_DETERMINED

確認が必要になる条件:
  Proposal / Implementation → Test を実際に接続するとき。
  実行か結果かを決めるとき。
```

---

## original_goal

```text
Concept: original_goal

Origin: NOT_DETERMINED
  PROJECT_SPEC.md に Goal 正本の定義は見当たらない。推測で Origin を作らない。

Current: NONE

Provisional:
  ユーザーが最初に与えた Goal 原文。上書きしない。
  達成判定の正本の一部。effective_goal は保存せず、読み取り時に
  original_goal / explicit_conditions / explicit_constraints /
  user_confirmed_supplements から解釈する。
  LLM が推測した条件は Goal 正本へ追加しない。
  正本: docs/GOAL_COMPLETION_GATE_V0.md §2
  schema: ai_tool/mission_memory/schema/mission.schema.json

Status: PROVISIONAL

確認が必要になる条件:
  保存済み original_goal を後から書き換える提案が出たとき。
  effective_goal を保存したくなったとき。
  Current へ昇格するとき。
```

---

## execution_end_state

```text
Concept: execution_end_state

Origin: NOT_DETERMINED

Current: NONE

Provisional:
  Mission の正式終了状態は achieved / paused / needs_continuation /
  ended_incomplete の4つのみ。「未判定」は5番目の状態ではない。
  判定不能時は execution_end_state_judgment = not_judged として保持し、
  execution_end_state は置かない。
  Goal 達成判定を行ったときだけ goal_achievement_performed = true。
  正本: docs/GOAL_COMPLETION_GATE_V0.md §8
  schema: ai_tool/mission_memory/schema/execution.schema.json

Status: PROVISIONAL

確認が必要になる条件:
  質問待ちを paused にするか not_judged のままにするかを固定するとき。
  Chat Task complete / gate_answer.verified を Goal 達成と同一視する提案が出たとき。
  Current へ昇格するとき。
```

---

## Goal Completion Gate

```text
Concept: Goal Completion Gate

Origin: NOT_DETERMINED

Current: NONE

Provisional:
  Agent Execution 終了時に、Goal 達成を推測で確定せず、
  既存4状態へ安全に接続する暫定運用。
  既存仕様で一意判定できないときは Human へ質問する一般経路。
  README専用A/B分岐は持たない。選択肢は 4 状態。
  v0 起動: 完全一覧から要求指名 path が欠ける。最初の E2E は README 事例。
  正本: docs/GOAL_COMPLETION_GATE_V0.md
  未接続は同ファイル §12。一般自動達成判定は完成扱いにしない。

Status: PROVISIONAL

確認が必要になる条件:
  Chat の Task complete / 回答表示を Goal 達成と見なす実装に進むとき。
  README 事例を System 規則へ昇格するとき（一件だけでは昇格しない）。
  CODE が本 Provisional と食い違うとき（CURRENT / CODE DRIFT ではない。
  Current が無いので PROVISIONAL / CODE DRIFT）。
```

---

## dev_skill_registry

```text
Concept: dev_skill_registry

Origin: NOT_DETERMINED

Current: NONE

Provisional:
  Cursor / Codex 向け採用 Development Skill の機械カタログ。
  正本は registry/skills.json。Skill 本文は .agents/skills/**/SKILL.md にあり、
  Registry へ複製しない。
  alias 解決、標準合成（compositions）、output_contract 参照を持つ。
  imported Skill 本文は採用方針により変更しない。
  schema: registry/schema/skills.schema.json
  採用記録: .agents/skills/PROVENANCE.md

Status: PROVISIONAL

確認が必要になる条件:
  development_policy.json の canonical_files へ昇格するとき。
  Local Agent が Skill 本文を直接読む契約を足すとき。
  alias 正本を .cursor/rules から Registry へ移すとき。
```

---

## goal_handoff_packet

```text
Concept: goal_handoff_packet

Origin: NOT_DETERMINED

Current: NONE

Provisional:
  Dev Skill 合成の成果を実装フェーズへ渡す単一の機械可読 JSON。
  正本インスタンスは docs/handoffs/{handoff_id}.json。
  契約は registry/schema/goal_handoff.schema.json（handoff_version 0.1）。
  人間向け説明: docs/specs/GOAL_HANDOFF_V0.md
  発行 Skill: goal-handoff（ローカル provisional）
  Mission Memory の mission.json、Runtime TaskRecord、spec_proposal とは別契約。
  runtime_boundary.production_connected は v0 で false 固定。
  status=ready は人間承認後のみ。

Status: PROVISIONAL

確認が必要になる条件:
  Production Chat / Mission Memory が Packet を読む接続を足すとき。
  handoff_version を上げ、既存 Packet の互換を変えるとき。
  planning-and-task-breakdown の task と Runtime TaskRecord を同一視する提案が出たとき。
  PROVISIONAL から Current へ昇格するとき。
```

---

## runtime_task_in_progress

```text
Concept: runtime_task_in_progress

Origin: NOT_DETERMINED

Current:
  Runtime Task の in_progress は、current task として選択済みで実行可能な状態を表す。
  in_progress だけでは、その Task に対する実 Action の開始または存在を意味しない。
  実行開始の正本は Action 履歴とする。
  TASK_STARTED event は pending 状態の Task に Action を記録する経路でのみ発生するため、
  全経路における実行開始を表すイベントではない。

Evidence:
  tools/ai/task_runtime.py: TaskStatus / AgentTaskRuntime.record_action
  ai_tool/goal_handoff_runtime_bridge.py: build_handoff_task_records
  ai_tool/production_verification_acceptance.py: advance_runnable_handoff_task
  tests/ai_tool/test_production_verification_acceptance.py:
    test_task_completion_evidence_advances_next_handoff_task_without_executing_it

Status: CURRENT (observed code contract)

確認が必要になる条件:
  in_progress を「最初の Action が開始済み」の意味へ変更するとき。
  ready などの新しい Task 状態を導入するとき。
  TASK_STARTED を全実行経路共通の開始イベントへ変更するとき。
```
