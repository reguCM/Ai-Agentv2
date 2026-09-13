# ARCHITECTURE — 暫定アーキテクチャ

本書は **確定設計ではない**。NH1〜NH14 の実験結果から導いた暫定構造の説明である。

実装の一次ソースは `FW/selector/experiments/` および各 `FW/runs/` を参照。

---

## 全体像

```text
┌─────────────────────────────────────────────────────────┐
│ 入力: 実ログ / masked_inputs / シミュレーションケース      │
└───────────────────────────┬─────────────────────────────┘
                            ↓
              ┌─────────────────────────┐
              │ Mechanical Compression   │  NH12-2
              │ (ログ・API応答の圧縮)     │
              └─────────────┬───────────┘
                            ↓
              ┌─────────────────────────┐
              │ Observation              │  NH7, NH9
              │ 固定 slot への構造化      │
              └─────────────┬───────────┘
                            ↓
              ┌─────────────────────────┐
              │ Mechanical Mapping       │  NH7, NH9
              │ Observation → Fingerprint│
              └─────────────┬───────────┘
                            ↓
              ┌─────────────────────────┐
              │ Mechanical Prefill       │  NH10
              │ high_slot 理由の機械補完   │
              └─────────────┬───────────┘
                            ↓
              ┌─────────────────────────┐
              │ Validator                │  NH3, NH11
              │ 変更・状態の安全適用可否   │
              └─────────────┬───────────┘
                            ↓
              ┌─────────────────────────┐
              │ Gate                     │  NH8〜NH11
              │ 小型LLMのみで進めてよいか  │
              └─────────────┬───────────┘
                            ↓
              ┌─────────────────────────┐
              │ Selector                 │  NH5
              │ 診断手法・委譲先の選択     │
              └─────────────┬───────────┘
                            ↓
         ┌──────────────────┴──────────────────┐
         ↓                                      ↓
  SELF_RESOLVED                          UNKNOWN / HUMAN /
  (自己解決候補)                          EXTERNAL_HELP
```

---

## Observation

**「何が観測されたか」** を構造化して記録する層。

- LLM は固定 slot（例: `runtime_log`, `api_response`, `code_context`）へ抽出
- FACT / OBSERVED / INFERENCE / UNKNOWN の証拠境界を維持（EXP-007）
- Mechanical Compression（NH12-2）で材料不足（material_shortage）を先に解消
- Glossary 常時投入は推奨しない（NH13）

**実装参照:** `FW/selector/experiments/nh12_2/`, `nh7/`, `nh9/`

---

## Fingerprint

**「問題をどのような特徴として表現するか」** の層。

- カテゴリ・症状・証拠パターンなどの構造化特徴
- LLM 直出し（NH6）より、Observation からの機械 mapping（NH7）の方が安定
- gold observation からの復元はシミュレーションで 100%（NH7 条件 E）

**実装参照:** `FW/selector/experiments/nh6/`, `nh7/`, `nh9/`

---

## Mechanical Mapping

LLM に最終判断させず、ルールで Observation → Fingerprint を生成する部分。

- `map_slots_to_features()` 等の deterministic 変換
- NH7 で NH6 直出しより優位（fp 83% vs 43%）
- NH14 でも LLM 0 回で Fingerprint 生成

**設計意図:** LLM の推論ブレを Fingerprint 層から排除し、監査可能性を上げる。

---

## Validator

**「この変更・状態は安全に適用可能か」** を判定する層。

- NH1〜NH4: State 遷移制約、Evidence 実在、content validation
- NH11: `shadow_validator.py` — 実ログ Shadow で validation_ok 12/12（NH14）
- unsafe_accept = 0 を必須ゲートとする

**禁止:** Validator を通さない auto_fix。

---

## Gate

**「ここから先を小型 LLM だけで処理してよいか」** を決める層。

- slot 欠落・content_empty・不確実性 → HIGH / UNKNOWN
- HIGH は大型 LLM 再観測または HUMAN_REVIEW / EXTERNAL_HELP へ
- NH8: 常時大型より large call 削減（2 vs 10）かつ missed=0
- NH10: Mechanical Prefill で H ケースの Gate 誤判定を修正

**実装参照:** `FW/selector/experiments/nh8/`, `nh10/`, `nh11/shadow_gate.py`

---

## Selector

**「状況に応じてどの手法を使うか」** を選ぶ層。

- 現時点は **ルールベース**（NH5）。LLM 自律選択は未検証
- 出力例: `LARGE_LLM`, `HUMAN_REVIEW`, `mechanical_validator_priority`, `hard_reject`
- NH14 では `executed=false` の Shadow 実行（本番適用なし）
- Gate が `LARGE_LLM` を出しても NH14 では `EXTERNAL_HELP` に remap

**実装参照:** `FW/selector/experiments/nh5/`, `FW/knowledge_base/SELF_DIAGNOSIS_SELECTOR.md`

---

## External Help

自力で安全に確定できない場合の引き渡し境界。

```text
UNKNOWN / HIGH uncertainty
  ↓
必要材料の整理（OBSERVATION, FINGERPRINT, GATE, SELECTOR, EVIDENCE, CODE_CONTEXT）
  ↓
SUMMARY.md + request.json
  ↓
Cursor / 人間等へ委譲（手動）
```

- NH14 で 12 件中 5 件が EXTERNAL_HELP、7 件 SELF_RESOLVED
- **自動送信機能は実装しない**（凍結方針）
- 因果確定は External Help 受け手の責務

**実装参照:** `FW/selector/experiments/nh14/external_help.py`

---

## EXP 系（NH 以前）との関係

NH 以前の EXP-001〜010 は `search_web` 診断の入力設計・証拠境界・モデル比較を確立した。

| 概念 | 由来 |
|------|------|
| 証拠4分類 | EXP-007 |
| route 分解 | EXP-006 |
| N2 経路存在ゲート | EXP-008 |
| 大型 LLM エスカレーション候補 | EXP-010 |

これらは NH パイプラインの **上流の診断手法** として method_catalog に登録されている。

---

## 本番との境界

| コンポーネント | 本番 | フレームワーク |
|---------------|------|---------------|
| Agent | `agent.py` | 変更禁止 |
| Tool / Manager | `tools/` | 変更禁止 |
| Selector | 本番 Selector | `FW/selector/` は実験用 Shadow |
| search_web | 本体 | 変更禁止 |

フレームワークは **研究・Shadow 評価** のみ。本番統合は凍結後の利用需要発生時に検討。
