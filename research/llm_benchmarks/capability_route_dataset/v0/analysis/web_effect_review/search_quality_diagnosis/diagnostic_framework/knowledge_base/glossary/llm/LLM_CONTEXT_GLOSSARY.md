# LLM_CONTEXT_GLOSSARY — LLM向けプロジェクト固有概念

小型LLM・大型LLMに渡すコンテキスト。一般英語の意味ではなく、**本プロジェクトでの境界**を優先する。

短縮版: `LLM_QUICK_REFERENCE.md`  
機械可読: `../glossary.json`

---

## グローバルルール

```
DO:
- 材料（ログ・コード・JSON）に根拠がある事実のみ Observation slot に書く
- UNKNOWN は UNKNOWN のまま残す
- 4分類ラベル（FACT/OBSERVED/INFERENCE/UNKNOWN）は根拠の強さを正確に使う
- Large LLM は HIGH と判定された slot の訂正のみ行う（NH9-10）

DO NOT:
- Fingerprint / features を直接推測・出力しない（Mapping は機械側）
- Evidence ID や観測内容を捏造しない
- UNKNOWN を推測で埋めない
- 本番コード修正・自動 fix を実行しない
- Gate / Escalation / Selector の判断を LLM が代替しない
- SUPPORTED（実験結果）を「本番採用済み」と解釈しない
```

---

## 混同防止（必読）

```
Observation ≠ Fingerprint
  Observation = 観測事実の slot 記録
  Fingerprint = Observation から機械 Mapping で得る features
  LLM は Fingerprint を直接作らない

Evidence ≠ Observation
  Evidence = 証拠オブジェクト / 4分類ラベル / slot 内引用
  Observation = 固定 slot 体系の観測記録

OBSERVED (4-class) ≠ OBSERVED (slot status)
  同名だが別体系。文脈で区別する

Gate ≠ Validator
  Gate = エスカレーション（Large/HUMAN）の機械判断
  Validator = 安全性・State 遷移の機械検証

Selector ≠ Validator
  Selector = 診断手法の選択
  Validator = 実行可否・安全の検証

Safety ≠ Accuracy
  Safety = unsafe_accept=0, 捏造=0 が最優先
  Accuracy = gold 一致。safe_HUMAN_REVIEW は Accuracy↓でも Safety OK

SUPPORTED ≠ ACTIVE
  SUPPORTED = 仮説の実験評価
  ACTIVE = State の有効状態

stdout ≠ LLM handoff
  stdout = 表示用要約（件数が嘘のことがある）
  handoff = Agent への実データ JSON

exists ≠ content
  件数・存在だけでは snippet 内容の有無は分からない（NH11）

Mechanical Mapping ≠ LLM inference
  Mapping = 決定的変換（コード側）
  LLM inference = 推論（slot 観測は可、features 直接生成は不可）
```

---

## 診断系

### Observation
```
TERM: Observation
日本語名: 観測

DEFINITION:
ログ・コード・実測から読み取った事実を、固定 slot スキーマに記録したもの。

ROLE:
Fingerprint 生成の入力。Safety の根拠境界。

DO:
- 各 slot に status: OBSERVED | NOT_OBSERVED | UNKNOWN
- evidence_reference に材料上の根拠を示す（分かる場合）
- 材料に無いことは UNKNOWN

DO NOT:
- 原因・修正方法・診断手法名を slot に書く
- Fingerprint を出力する
- 推測を OBSERVED にする

RELATED:
Fingerprint, Fixed Slot, Mechanical Mapping, Evidence

EXAMPLE:
stdout_present=OBSERVED は runtime_log に該当記述がある場合のみ。

STATUS:
experimental (NH7-NH12)
```

### Fingerprint
```
TERM: Fingerprint
日本語名: 問題指紋

DEFINITION:
Observation を機械的に boolean features へ変換した Selector 入力。

ROLE:
手法選択のための問題特徴表現。

DO:
- （LLM は通常触らない）機械 Mapping の結果として参照のみ

DO NOT:
- LLM が suspect_ranking_vs_filter 等を直接推測出力
- Observation を飛ばして Fingerprint を作る

RELATED:
Observation, Selector, Feature, Mechanical Mapping

STATUS:
experimental。NH6 の LLM 直出しは experimental_not_recommended
```

### Evidence
```
TERM: Evidence
日本語名: 証拠

DEFINITION:
文脈により (A) FACT/OBSERVED/INFERENCE/UNKNOWN ラベル
(B) State の E-xx オブジェクト (C) slot.evidence_reference

DO:
- 材料にある証拠のみ引用
- 4分類を根拠の強さに合わせて使う

DO NOT:
- 存在しない Evidence ID を invent
- INFERENCE を FACT/OBSERVED と偽る

STATUS:
4分類=adopt、State Evidence=experimental
```

### FACT / OBSERVED / INFERENCE / UNKNOWN（4分類）
```
DEFINITION:
主張・記述の根拠強度。EXP-007 / method_catalog evidence_four_classes。

DO:
- コードに明示 → FACT
- ログ・実測で直接確認 → OBSERVED（4分類）
- 推論 → INFERENCE
- 不明 → UNKNOWN

DO NOT:
- slot status OBSERVED と混同しない
```

---

## Selector / Gate

### Selector
```
TERM: Selector
DEFINITION: features から診断手法 ID を機械選択（NH5）。
DO NOT: LLM が手法を自由に選んで本番を変更する
STATUS: experimental
```

### Gate
```
TERM: Gate
DEFINITION: Large LLM / HUMAN_REVIEW へのエスカレーションを機械判定。
LEVEL: LOW | MEDIUM | HIGH | UNKNOWN (NH11 shadow)

DO NOT:
- LLM に escalate 可否を判断させる（NH8 設計）
- Gate の代わりに Validator を使う

STATUS: experimental
```

### HUMAN_REVIEW
```
TERM: HUMAN_REVIEW
DEFINITION: 人間確認への安全停止。失敗ラベルではない（NH11-3）。
DO NOT: HUMAN_REVIEW をエラーとして隠す・無視する
STATUS: experimental
```

### Small LLM / Large LLM
```
Small LLM:
  ROLE: Observation slot 抽出（例 qwen3:8b）
  DO NOT: 全体診断・本番修正

Large LLM:
  ROLE: HIGH と判定された slot の訂正のみ（例 qwen3:14b）
  DO NOT: 全 slot 再生成・Fingerprint 直接出力・Gate 判断
STATUS: experimental
```

---

## 機械処理層

### Mechanical Mapping
```
入力: fixed_slots
出力: features dict
実装: nh7/observation_mapper.py, nh9/fixed_slots.py
LLM はこの変換を行わない
```

### Mechanical Prefill (NH10)
```
入力: materials + partial slots
出力: ルールで補完された slots
原因推測なし
```

### Mechanical Compression (NH12-2)
```
入力: materials (runtime_log 等)
出力: 10 compression slots (FACT/PRESENT/ABSENT/UNKNOWN)
DO NOT: 原因・手法・Fingerprint を出力
```

---

## State 系

### ACTIVE / SUPERSEDED / REOPEN
```
ACTIVE: 現在有効
SUPERSEDED: 置換済み（通常は再 ACTIVE 不可）
REOPEN: evidence + reason 付き例外再活性化

DO NOT: SUPPORTED と混同
STATUS: experimental (NH1-4)
```

### Goal / Claim / Hypothesis
```
State 実験の cognitive 要素。
Claim/Hypothesis の更新は Validator 経由（実験領域）。
```

---

## search_web

### Route / Collect / Filter / Ranking
```
Route: API→collect→ranking→return→handoff の経路
Filter: hit 化・重複除去（前段）
Ranking: スコア・limit（後段）
Collect: API 結果の hit 化
```

### stdout / LLM handoff
```
stdout: 表示用。「検索結果 N 件」は実 return と一致しないことがある
LLM handoff: messages への JSON。診断はこちらを見る
```

---

## 評価ラベル

### SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED
```
仮説・実験の評価結果。本番採用を意味しない。

### Safety / False Accept / False Reject
```
Safety 最優先: unsafe_accept=0
False Accept: 危険なのに通した
False Reject: 安全なのに拒否した
```

---

## Shadow Mode (NH11)
```
本番と並行する診断実行。出力は runs/ に保存。
本番 Agent には書き込まない。
```

---

## UNKNOWN の扱い

```
slot UNKNOWN、Gate UNKNOWN、用語定義 unknown は「未確定」を意味する。
LLM は UNKNOWN を推測で解消しない。
未確定概念例: Fixed Slot 最小集合、LLM 自律 Selector、本番 Shadow 接続時期
```
