# GLOSSARY — 人間向け用語集

`diagnostic_framework` で使われる **プロジェクト固有概念** の説明。英単語の直訳ではなく、本リポジトリでの役割を説明する。

**採用状態の読み方:** `adopt` = KB上の採用記録 / `experimental` = 実験のみ / `unknown` = 未確定  
**本番:** ここに書かれたパイプラインは **暫定・experimental** が多く、本番 Agent には未接続。

---

## 概念の流れ（experimental 暫定）

```text
問題材料
  → [Mechanical Compression]  (NH12-2)
  → [Mechanical Prefill]      (NH10)
  → Observation (Fixed Slots) (NH9, Small LLM)
  → Mechanical Mapping        (NH7)
  → Fingerprint / features    (NH5)
  → Gate                      (NH8–NH11)
  → [Large LLM slot audit]    (NH9–10, 必要時のみ)
  → Mechanical Validator
  → Selector                  (NH5)
  → HUMAN_REVIEW              (必要時)
```

---

## 混同防止表

| A | B | 違い |
|---|---|------|
| **Observation** | **Fingerprint** | Observation=観測事実の記録。Fingerprint=それを機械的に特徴量化したもの（Selector入力）。 |
| **Evidence** | **Observation** | Evidence=証拠オブジェクト/4分類ラベル/slot引用。Observation=ログ等からの観測スロット。 |
| **FACT** | **Observation** | FACT=4分類の「仕様・コードから確認」。Observation=slot 体系の別語彙。 |
| **Observation** | **Inference** | Observation=材料に根拠あり。Inference=推論であり確定事実ではない。 |
| **Fingerprint** | **Selector** | Fingerprint=問題の特徴。Selector=特徴から**手法**を選ぶ器。 |
| **Goal** | **Claim** | Goal=目標エンティティ。Claim=検証可能な主張単位（State実験）。 |
| **Claim** | **Hypothesis** | いずれも State 要素。Hypothesis=検証中の仮説、Claim=主張。 |
| **State** | **History** | State=現行の Goal/Claim 等。History=SUPERSEDED 等の過去。 |
| **ACTIVE** | **SUPERSEDED** | ACTIVE=現在有効。SUPERSEDED=置換済み過去値（再Active制限あり）。 |
| **SUPERSEDED** | **REOPEN** | REOPEN=evidence 付き例外再活性化。通常の ACTIVE 化とは別。 |
| **Gate** | **Validator** | Gate=エスカレーション判断。Validator=安全性・制約の機械検証。 |
| **Selector** | **Validator** | Selector=診断**手法**選択。Validator=安全・遷移の可否。 |
| **Small LLM** | **Large LLM** | Small=Observation 中心。Large=HIGH slot 訂正のみ（全体診断しない）。 |
| **Safety** | **Accuracy** | Safety=危険な自動判断ゼロ。Accuracy=gold 一致等（HUMAN_REVIEW は Safety 成功のことがある）。 |
| **False Accept** | **False Reject** | FA=危険なのに通した。FR=安全なのに拒否した。 |
| **Ranking** | **Filter** | Filter=hit化・重複除去等前段。Ranking=並べ替え・件数制限。 |
| **Collect** | **Ranking** | Collect/API→hit 化。Ranking=その後の score/limit 処理。 |
| **stdout** | **LLM output** | stdout=表示用要約。handoff=Agent messages への実データ渡し。 |
| **exists** | **content** | 件数・存在だけでは不十分。snippet 内容の有無が別問題（NH11）。 |
| **Mechanical Mapping** | **LLM inference** | Mapping=決定的変換。LLM inference=推論（slot/Fingerprint 直接生成は NH7 以降非推奨）。 |
| **SUPPORTED** | **ACTIVE** | SUPPORTED=仮説の実験評価。ACTIVE=State の有効状態。 |
| **adopt** | **SUPPORTED** | adopt=catalog 上の採用ラベル。SUPPORTED=その回の実験結果。 |

---

## 診断系

### Observation（観測）

- **一言:** 材料から読み取った事実を、固定スキーマに記録したもの。
- **詳しい意味:** NH9 以降は 28 の Fixed Slot に `OBSERVED` / `NOT_OBSERVED` / `UNKNOWN` で埋める。NH7 以前は LLM が Fingerprint を直接出して精度が低かった。
- **なぜ必要か:** LLM の自由記述だと捏造・取りこぼしが増えるため、観測と特徴量化を分離する。
- **何と区別:** Fingerprint、Inference、Evidence(4分類)。
- **状態:** experimental（NH7–NH12）
- **例:** `stdout_present=OBSERVED` は runtime_log に `[OBSERVED]` 行がある根拠。

### Fingerprint（問題指紋）

- **一言:** Selector が手法を選ぶための **特徴量辞書**。
- **詳しい意味:** `suspect_ranking_vs_filter` 等の boolean features。NH7 以降は Observation → Mechanical Mapping でのみ生成。
- **なぜ必要か:** 「この問題は ranking 疑いか」「reopen 要求か」を機械的に表現する。
- **状態:** experimental
- **変遷:** NH6 LLM 直出し(低精度) → NH7 Mapping(推奨)

### Evidence（証拠）

- **一言:** 文脈により (A)4分類ラベル (B)State の E-xx オブジェクト (C)slot 内引用。
- **なぜ必要か:** 主張の根拠境界。捏造抑制（F004）。
- **状態:** 4分類は adopt、State Evidence は experimental

### FACT / OBSERVED / INFERENCE / UNKNOWN（4分類）

- **一言:** 主張・ログ記述の **根拠の強さ** ラベル（EXP-007）。
- **注意:** slot の `OBSERVED` とは **別体系**（同名異義）。

---

## Selector 系

### Selector（選択器）

- **一言:** features から **診断手法 ID** を選ぶルールエンジン（現状 LLM ではない）。
- **なぜ必要か:** 問題ごとに N2 経路ゲート、コード読解、HUMAN_REVIEW 等を使い分ける。
- **状態:** experimental（NH5+）、本番 `selector.py` は conditional

### Method Catalog（診断手法カタログ）

- **一言:** 手法の登録簿。`method_catalog.json`。
- **状態:** adopt（KB 参照用）

---

## State 系

### Goal / Claim / Hypothesis

- **一言:** Cognitive State の要素。更新・SUPERSEDED・REOPEN 実験の対象。
- **状態:** experimental（NH1–NH4）

### ACTIVE / SUPERSEDED / REOPEN

- **一言:** State ライフサイクル状態。仮説評価の SUPPORTED とは無関係。
- **REOPEN:** evidence+reason 付き例外（NH2 条件 D 等）

---

## エスカレーション系

### Gate（ゲート）

- **一言:** Large / HUMAN へ上げるかを **機械** 判断。N2 / uncertainty / shadow 等複数種。
- **なぜ必要か:** Selector だけでは不確実性・材料不足を扱いきれない（NH8+）。
- **NH11:** LOW / MEDIUM / HIGH / UNKNOWN

### HUMAN_REVIEW

- **一言:** 人間確認へ送る **安全停止**。失敗ではなく制御（NH11-3）。
- **状態:** experimental

### Small LLM / Large LLM

- **Small:** Observation slot 抽出（例 qwen3:8b）
- **Large:** HIGH slot 訂正のみ（例 qwen3:14b）。全体診断はしない（NH9）

---

## search_web 診断系

### Route / Ranking / Filter

- **Route:** API→collect→ranking→return→handoff の経路
- **Ranking:** スコア・limit による並べ替え
- **Filter:** hit 化・重複除去・score フィルタ等の前段

### stdout / LLM handoff

- **stdout:** 表示用。「検索結果1」ラベルと実 return 件数は別（A06）。
- **handoff:** Agent messages への JSON 渡し。診断の本丸。

---

## 機械処理系

### Mechanical Mapping / Prefill / Compression

| 用語 | 段階 | 役割 |
|------|------|------|
| **Compression** (NH12-2) | LLM 前 | ログ→10 compression slots、原因推測なし |
| **Prefill** (NH10) | Observation 前後 | 材料から slot をルール補完 |
| **Mapping** (NH7) | Observation 後 | slots→features |

---

## 評価系

### Safety / Accuracy

- **Safety 優先:** unsafe_accept=0, auto_fix=0, fabricated=0
- **Accuracy:** Selector gold 一致等。`safe_HUMAN_REVIEW` は Accuracy↓でも Safety OK

### material_shortage（材料不足）

- NH12-1: trace 欠落で 29/30
- NH12-2 Compression: 0/30（core slots 抽出成功）

---

## 実験評価ラベル

| ラベル | 意味 |
|--------|------|
| SUPPORTED | 実験範囲で再現 |
| PARTIALLY_SUPPORTED | 条件付き |
| UNSUPPORTED | 単独では不支持 |
| experimental | 本番未採用 |

---

## NH1–NH12 との対応（概要）

| 実験 | 主に生まれた概念 |
|------|------------------|
| EXP-007 | Evidence 4分類 |
| EXP-008 | N2 Gate |
| NH1–NH4 | State, ACTIVE/SUPERSEDED/REOPEN, Validator |
| NH5 | Selector + features |
| NH7 | Observation→Mapping |
| NH8 | Uncertainty Gate, Escalation |
| NH9 | Fixed Slots, Large 限定 |
| NH10 | Mechanical Prefill, high_slots, Safety/Accuracy 分離 |
| NH11 | Shadow Mode, real log |
| NH12-2 | Mechanical Compression |

---

## 未確定（UNKNOWN として扱う）

- Fixed Slot の最小集合（H-NH12-2-2）
- Observation LLM 不要の機械判定（H-NH12-2-3）
- LLM 自律 Selector（H-SEL）
- 本番への Shadow 経路接続タイミング

---

機械可読版: `glossary.json`  
実装者向け: `program/PROGRAM_GLOSSARY.md`  
LLM向け: `llm/LLM_CONTEXT_GLOSSARY.md`, `llm/LLM_QUICK_REFERENCE.md`
