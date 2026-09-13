# Goal Completion Gate 仮仕様 v0

**内部ID:** `goal_completion_gate_v0`
**状態:** PROVISIONAL / 仮採用
**記録日:** 2026-09-10
**正本:** 本ファイル。System規則ではない。概念入口は `docs/concepts/CONCEPT_DEFINITIONS.md`。

この仕様は、自然文Goalの完全な自動達成判定方式が確立するまでの
暫定的な運用仕様とする。

実運用・E2Eから事例を集め、
後からSystem規則へ昇格・修正できるものとする。


# 1. 目的

Agent Execution終了時に、

「ユーザーのGoalを達成したと判断してよいか」

を無理に推測せず、

- 達成
- 一時停止
- 続行必要
- 未完了終了

の既存4状態へ安全に接続する。

既存仕様だけでは達成判定を一意に決められない場合は、
勝手に完了・未完了を確定しない。


# 2. Goalの正本

Goal達成判定で参照する正本は以下。

- original_goal
  - ユーザーが最初に与えたGoal原文
  - 上書きしない

- explicit_conditions
  - ユーザーが明示した条件

- explicit_constraints
  - ユーザーが明示した制約

- user_confirmed_supplements
  - Grill等によってユーザーが後から確定した補足

LLMが推測した条件をGoal正本へ追加しない。

現在有効なGoalは、
これらを読み取り時に合わせて解釈する。


# 3. Execution終了時に参照する実績

Goalと比較する材料は、確認済みのものだけを使用する。

候補:

- 今回の確定成果
- Evidence
- 確認済みObservation
- 未解決事項
- 成果物（接続後）
- stop_reason
- Execution終了時点の状態

Tool成功そのもの、
Task completeそのもの、
final_synthesis.readyそのもの、
gate_answer.verifiedそのものを
Goal達成と同一視しない。

これらは判定材料には使用できる。

Task Runtime の完了（T1 の Evidence、T2 の answer produced、
G1 の all tasks complete）は、Mission の Goal 達成判定とは別である。
Human に Goal の意味を聞いている間も、既存の Completion 規則は止めない。


# 4. 仮の判定順

Execution終了
↓
[1] 既存System規則だけでGoal達成を機械的に確定できるか
│
├─ YES
│    → 達成
│
└─ NO / 判定規則なし
     ↓
[2] 人間回答・承認などを実際に待っているか
│
├─ YES
│    → 一時停止
│
└─ NO
     ↓
[3] 安全で合理的な次のAction / 調査 / 検証 / Recoveryが
    明確に残っているか
│
├─ YES
│    → 続行必要
│
└─ NO / 一意に判断できない
     ↓
[4] Goalの意味または完了認定に人間仕様が不足しているか
│
├─ YES
│    → 勝手に状態を確定しない
│    → 選択肢と推奨を提示してHumanへ質問
│    → 質問待ちは「一時停止」として扱える
│
└─ NO
     ↓
[5] 現状これ以上進める合理的手段がない
     → 未完了終了


# 5. Humanへ戻す条件

以下では自動的に達成 / 未完了終了を決めない。

- 同じ事実から複数の妥当なGoal完了解釈が成立する
- 人間仕様に完了規則が存在しない
- 既決仕様どうしが衝突する
- 新しい仕様を作らなければ判定できない
- ユーザーの意図によって結果が変わる
- Local LLM / Judgeが十分な確信を持てない

Humanへ戻す場合は、
単に「分かりません」とせず、

- 確認済み事実
- 何が未決なのか
- 選択肢
- 推奨案と理由

を提示する。


# 6. 重要な区別

UNKNOWN
≠
確認した結果「存在しない」

NOT_APPLICABLE
≠
未確認

Action失敗
≠
Goal未達

Task完了
≠
Goal達成

Execution終了
≠
Mission終了

Goal未達
≠
自動的に未完了終了


# 7. README.md事例

Goal:
「README.mdがワークスペースにあるか確認して、
ファイルの先頭1行を報告してください」

確認済み事実:
- 完全な親ディレクトリ一覧を取得
- README.mdが存在しない

ここからは、

A:
存在しないことを確認・報告できたためGoal達成

B:
先頭1行を報告できないためGoal未達

の2解釈が成立した。

既存人間仕様にこの完了規則が無かったため、
Agentは勝手にA/Bを確定せずHumanへ質問する。

この挙動を仮仕様の基準例とする。


# 8. 4状態との関係

正式なMission状態は以下4つのみ。

- achieved
- paused
- needs_continuation
- ended_incomplete

「未判定」は5番目の状態ではない。

判定不能時は、

execution_end_state_judgment = not_judged

として保持し、
必要ならHumanへ質問する。

Human回答後に判定可能になったら、
同じmission_idで新しいExecutionとして再開する。


# 9. 自動化の優先順位

判断主体は原則として次の順。

1. Systemで機械的に確定できる
   → Systemが決定

2. 確定済み人間仕様とEvidenceを使えばAIが一意に判断できる
   → AIが判断

3. 仕様が不足・競合・曖昧
   → Humanへ質問

Human判断を必要以上に増やさない。
ただし未確定仕様をAIが勝手に補完して減らさない。


# 10. 自力回復とHELP

一度失敗しただけではHumanへ上げない。

Goal未達で、

- 新しい合理的なActionがある
- 前回と異なるRecoveryがある
- 安全に検証できる
- 既決仕様を変更しない

場合は、一定範囲で自力継続を許可する。

以下では自力継続を停止する。

- 同じ失敗を繰り返す
- 進展がない
- Regressionが発生する
- 既決仕様変更が必要
- 人間判断が必要
- 安全範囲を超える

この場合はHELP / Grill / Humanへ移行する。


# 11. 仮仕様から正式仕様への昇格

Humanへ質問した完了判断を事例として記録する。

同種の判断が繰り返され、
一般化可能であることが確認できた場合、

Human判断
↓
仮ルール
↓
E2E / 回帰テスト
↓
System規則

へ昇格させる。

一件の判断だけから一般規則を作らない。


# 12. 現在の未接続

この仮仕様を置いても、以下はまだ完成扱いにしない。

- 自然文Goalの一般的な自動達成判定
- needs_continuation の一般判定
- ended_incomplete の一般判定
- Human回答後の一般的なMission再開Bridge
- Approval再開Bridge
- artifact_refs
- Chat以外のAgent入口

未接続部分は未接続として明示したまま運用する。


# 13. v0 で接続した最小経路（PROVISIONAL）

README専用のA/B分岐は持たない。

接続した一般経路:

- Execution終了時、既存仕様で Goal Completion を一意に判定できない場合、Humanへ判断を求める。
- 質問の選択肢は Mission の 4 状態。推奨は自動確定しない。
- `execution_end_state_judgment = not_judged`
- `goal_achievement_performed = false`
- 検索対象の conversation Grill がある場合はそちらを優先する

v0 の起動に使う確認済み事実（仮）:

- 完全な親ディレクトリ一覧から、要求で指名した path が欠けている
- そのとき既存 System 規則は achieved / ended_incomplete を一意確定しない

Human には内部4状態を選ばせない。聞くのは Goal の意味 / 完了条件である。

v0 で接続した再開ケース:

- case: named_path_omitted_from_complete_listing
- Human が「不在確認で Goal 完了」と確定 → System が achieved
- Human が「中身を報告できなければ完了ではない」と確定 → System が ended_incomplete
- それ以外の回答 → 未対応停止。Mission 状態は確定しない

同じ mission_id で新しい execution を書く。original_goal は上書きしない。
完了条件の Human 確定は user_confirmed_supplements / explicit_conditions へ残す。

最初の E2E ケースは README.md 欠落事例。

Human回答後の一般的な Mission 再開 Bridge、Approval 再開、その他の Goal 解釈は未接続。

