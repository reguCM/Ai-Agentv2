# EXPERIMENT_PLAN — NH10

**run_id:** `20260827_163000`  
**目的:** Gate理由↔high_slots 対応、Mechanical Prefill、Accuracy/Safety/HUMAN_REVIEW 分離評価。

## 絶対条件

本番コード変更禁止。NH1–NH9 上書き禁止。auto_fix NOT_ALLOWED。

## NH9 からの継続課題

- H: Gate=LOW で features 空 → 止まれない
- high_slots=[] なのに reasons あり
- I: HUMAN_REVIEW を Selector gold 不一致で FAIL 扱い

## 条件

A=NH9-C reuse / B=明示 high_slots / C=Prefill / D=Prefill+Large(HIGHのみ)

## モデル（Condition D のみ）

qwen3:14b T=0 ctx=8192。Observation は NH9 small 保存結果を再利用。
