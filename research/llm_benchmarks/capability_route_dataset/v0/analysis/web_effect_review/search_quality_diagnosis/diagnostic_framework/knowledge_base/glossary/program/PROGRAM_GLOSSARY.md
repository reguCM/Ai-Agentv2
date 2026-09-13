# PROGRAM_GLOSSARY — プログラム実装者向け用語集

実装・デバッグ時に「概念 → データ → 生成 → 消費 → 変更権限」を追うための辞書。  
**存在しない構造は記載しない。** 未実装は `未実装` / `experimental` / `unknown` と明記。

機械可読版: `../glossary.json`  
人間向け: `../human/GLOSSARY.md`

---

## パイプライン（experimental、本番未接続）

```text
materials (dict)
  → mechanical_compression (NH12-2)     [optional]
  → mechanical_prefill (NH10)           [optional]
  → fixed_slots (NH9)                   LLM or mechanical
  → map_slots_to_features (NH7/NH9)     features dict
  → evaluate_uncertainty / shadow_gate  gate result
  → large slot audit (NH9-10)           [if HIGH]
  → mechanical_validator (NH1-4)
  → NH5Selector.select()                method_id
  → HUMAN_REVIEW                        [if required]
```

---

## Observation / Fixed Slot

### 概念
ログ・コード等から読み取った観測を、固定スキーマの slot に格納する。

### データ
```json
{
  "slot_name": {
    "status": "OBSERVED | NOT_OBSERVED | UNKNOWN",
    "value": true | false | null,
    "confidence": "low | medium | high",
    "evidence_reference": "prefill:runtime_log | ..."
  }
}
```

- **スキーマ定義:** `selector/experiments/nh9/slots.json`
  - `slots`: 全28 slot 名リスト
  - `core_slots`: 材料不足判定用コア集合
- **status 集合:** `STATUSES = {"OBSERVED", "NOT_OBSERVED", "UNKNOWN"}` (`fixed_slots.py`)

### 生成
| 経路 | ファイル | 変更者 |
|------|----------|--------|
| Small LLM | `nh9/prompts/small_observe.md` → `extract_json()` → `normalize_slots()` | LLM 出力を normalize のみ |
| Mechanical Prefill | `nh10/mechanical_prefill.py` | ルールのみ |
| Compression→Mapping | `nh12_2/map_to_observation.py` | ルールのみ |

### 消費
- `map_slots_to_features()` → features (`fixed_slots.py`)
- `evaluate_uncertainty()` / `material_hints()` (`nh8/uncertainty_gate.py`)
- `apply_material_safety_locks()` (`nh8/uncertainty_gate.py`)

### 変更してよい
- 実験 runner が slot JSON を書き込む
- Prefill / Compression が UNKNOWN→OBSERVED を機械補完

### 変更してはいけない
- LLM が slot 以外の Fingerprint を直接生成（NH7 設計違反）
- Validator が観測事実を捏造

---

## Fingerprint / Feature

### 概念
Selector 入力となる boolean/enum 特徴量辞書。

### データ
- **スキーマ:** `selector/experiments/nh6/feature_schema.json`
- **実行時:** `features: dict[str, bool | str | int]` — `map_slots_to_features()` 出力

例（実在キー、schema 参照）:
- `suspect_ranking_vs_filter`
- `reopen_requested`
- `state_change_requested`

### 生成
- `selector/experiments/nh7/observation_mapper.py`（NH7）
- `selector/experiments/nh9/fixed_slots.py::map_slots_to_features`（NH9+）

### 消費
- `selector/experiments/nh5/nh5_selector.py::NH5Selector.select()`
- `selector/experiments/nh5/rules.json` — `required_features` マッチ

### 変更してよい
- Mechanical Mapping 関数のみ（決定的変換）

### 変更してはいけない
- LLM が features を直接出力（NH6 方式は `experimental_not_recommended`）
- Selector が features を書き換えてから自分で選ぶ（循環）

---

## Evidence（3系統）

### (A) 4分類ラベル — adopt
- **定義:** `knowledge_base/method_catalog.json` → `evidence_four_classes`
- **値:** `FACT`, `OBSERVED`, `INFERENCE`, `UNKNOWN`（主張・レポート用）
- **生成:** 診断レポート・LLM 出力ラベル
- **消費:** 人間レビュー、FINDINGS F004 参照

### (B) State Evidence オブジェクト — experimental
- **生成/消費:** NH3/NH4 validator 実験（`evidence_id`, `exists`, `content`）
- **本番 State 本体:** 変更禁止（実験のみ）

### (C) slot.evidence_reference — experimental
- **型:** `str` — 例 `prefill:runtime_log`
- **生成:** `mechanical_prefill.py`, LLM slot 出力
- **消費:** 監査ログ、人間レビュー

### 混同禁止
- `OBSERVED`（4分類）≠ `status: OBSERVED`（slot）
- Compression `FACT`（NH12-2）≠ 4分類 `FACT`

---

## Selector

### 概念
features から診断手法 ID を機械選択。

### データ
```python
# nh5_selector.py 戻り値（概略）
{
  "selected_method": "method_id",
  "status": "adopt|experimental|...",
  "rejected_methods": [...],
  "selection_reason": "...",
  "reuse": bool
}
```

- **レジストリ:** `selector/experiments/nh5/method_registry.json`
- **ルール:** `selector/experiments/nh5/rules.json`
- **カタログ:** `knowledge_base/method_catalog.json`

### 生成
`NH5Selector.select(features, context)` — `nh5_selector.py`

### 消費
実験 runner、評価スクリプト

### 変更してよい
- 実験用 `rules.json` / `method_registry.json`

### 変更してはいけない
- **本番** `selector/selector.py`, `selector/rules.json`（今回作業の制約）

---

## Gate / Escalation

### 概念
Large LLM 呼び出し・HUMAN_REVIEW 等へのエスカレーションを機械判定。

### データ（NH8 uncertainty_gate）
```python
evaluate_uncertainty(slots, materials) -> {
  "level": "LOW | MEDIUM | HIGH | UNKNOWN",  # NH11 shadow 拡張
  "reasons": [...],
  "escalate_large": bool,
  "escalate_human": bool,
}
```

- **ルール:** `selector/experiments/nh8/rules.json`
- **Shadow:** `selector/experiments/nh11/shadow_gate.py`

### 生成
- `uncertainty_gate.py::evaluate_uncertainty`
- `shadow_gate.py`（NH11 real-log shadow）

### 消費
- NH9-12 runner が Large LLM 呼び出し可否を決定
- 評価: `missed_escalation`, `unnecessary_escalation`

### 変更してよい
- Gate ルール JSON（実験領域）

### 変更してはいけない
- LLM にエスカレーション可否を自由判断させる（NH8 設計: "LLM does not choose escalation"）

---

## Validator

### 概念
State 遷移・REOPEN・Evidence 存在の機械検証。

### データ — experimental（NH1-4）
- `ACTIVE`, `SUPERSEDED`, `REOPEN` 遷移結果
- `evidence.exists`, `evidence.content` チェック

### 生成
NH3/NH4 実験 validator モジュール

### 消費
State 更新実験の pass/fail

### 本番
State 管理本体は変更禁止。実験コードのみ参照。

---

## Mechanical Mapping / Prefill / Compression

| 層 | 入力 | 出力 | 主要ファイル |
|----|------|------|--------------|
| **Compression** | `materials` | 10 compression slots (`FACT/PRESENT/ABSENT/UNKNOWN`) | `nh12_2/mechanical_compression.py` |
| **Prefill** | materials + partial slots | 補完 slots | `nh10/mechanical_prefill.py` |
| **Mapping** | slots | features | `nh7/observation_mapper.py`, `nh9/fixed_slots.py` |

### Compression slot（NH12-2）
- **スキーマ:** `nh12_2/COMPRESSION_SCHEMA.md`
- **status:** `FACT | PRESENT | ABSENT | UNKNOWN`（Observation slot とは別体系）

### 変更してよい
- ルール関数・パターンマッチ

### 変更してはいけない
- Compression で原因推測・手法名出力（NH12-2 設計違反）

---

## State ライフサイクル

| 状態 | 意味 | 実験 |
|------|------|------|
| `ACTIVE` | 現在有効な Goal/Claim | NH1-2 |
| `SUPERSEDED` | 置換済み過去値 | NH2 |
| `REOPEN` | evidence+reason 付き再活性化 | NH2 条件 D |

### 評価ラベル（別体系）
`SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED` — 仮説・実験結果のみ。State status ではない。

---

## search_web 診断

### Route
- **概念:** API → collect → ranking → return → handoff
- **参照:** `knowledge_base/DIAGNOSTIC_WORKFLOW.md`, FINDINGS

### Ranking / Filter
- **Filter:** hit 化、重複除去、score 閾値（前段）
- **Ranking:** score ソート、`limit` 適用（後段）
- **feature 例:** `suspect_ranking_vs_filter`

### stdout vs LLM handoff
| 項目 | フィールド/場所 | 注意 |
|------|-----------------|------|
| stdout | 表示用テキスト | 件数ラベル≠実 return（A06） |
| handoff | Agent messages JSON | 診断の実データ |
| dumps | 実験保存 JSON | `runs/*/dumps/` |

---

## Sidecar

### 概念
本番経路に並行して動く診断・Shadow 実行層。

### データ
- Shadow run 出力: `runs/<timestamp>/nh11_real_shadow/` 等
- Gate 結果・slot スナップショットを本番と分離保存

### 状態
`experimental` — 本番 Agent 未接続

---

## 評価メトリクス

| メトリクス | 定義 | 参照実験 |
|-----------|------|----------|
| `unsafe_accept` / False Accept | 危険な自動通過 | NH10+ |
| `false_reject` / False Reject | 不要な拒否 | NH10+ |
| `safe_HUMAN_REVIEW` | 安全だが人間送り | NH11 |
| `material_shortage` | core_slots が UNKNOWN 過多 | NH12-1/2 |
| `large_call_rate` | Large LLM 呼び出し率 | NH9-12 |

---

## JSON / ファイル索引

| 用途 | パス |
|------|------|
| 手法カタログ | `knowledge_base/method_catalog.json` |
| Slot 定義 | `selector/experiments/nh9/slots.json` |
| Feature 定義 | `selector/experiments/nh6/feature_schema.json` |
| Selector ルール | `selector/experiments/nh5/rules.json` |
| Gate ルール | `selector/experiments/nh8/rules.json` |
| Compression スキーマ | `selector/experiments/nh12_2/COMPRESSION_SCHEMA.md` |
| Observation スキーマ | `selector/experiments/nh12_2/OBSERVATION_SCHEMA.md` |
| 機械可読辞書 | `knowledge_base/glossary/glossary.json` |

---

## 未実装 / unknown

- 本番 Agent への Shadow 自動接続 — **未実装**
- LLM 自律 Selector（H-SEL）— **proposed / unknown**
- Fixed Slot 最小集合の確定（H-NH12-2-2）— **unknown**
- Observation LLM 完全不要化（H-NH12-2-3）— **仮説・未検証**
