# GLOSSARY_REPORT — 用語辞書整備報告

作成日: 2026-08-28  
対象: `diagnostic_framework/knowledge_base/glossary/`

---

## 1. 整理した語数

| 成果物 | 内容 |
|--------|------|
| `glossary.json` | **40 語**（`build_glossary.py` 生成） |
| `human/GLOSSARY.md` | 優先語彙 + 混同防止表 + NH 対応 + UNKNOWN 一覧 |
| `program/PROGRAM_GLOSSARY.md` | 実装パイプライン・JSON 構造・ファイル索引 |
| `llm/LLM_CONTEXT_GLOSSARY.md` | TERM/DO/DO NOT 形式の LLM 向け定義 |
| `llm/LLM_QUICK_REFERENCE.md` | プロンプト先頭用短縮版 |

### glossary.json 収録語（40）

Observation, Fingerprint, Evidence, FACT, OBSERVED, INFERENCE, UNKNOWN, Claim, Hypothesis, Goal, Selector, Feature, Method Catalog, Gate, Escalation, Small LLM, Large LLM, HUMAN_REVIEW, Mechanical Mapping, Mechanical Prefill, Fixed Slot, Mechanical Compression, Validator, Safety, Accuracy, False Accept, False Reject, ACTIVE, SUPERSEDED, REOPEN, Route, Ranking, Filter, LLM handoff, stdout, Sidecar, SUPPORTED, Shadow Mode, material_shortage, high_slots

---

## 2. 重要だった概念

1. **Observation → Fingerprint 分離（NH7）** — LLM 直出し fingerprint の精度問題を解く中核設計
2. **Fixed Slot + Mechanical Mapping（NH9）** — 観測の構造化と Selector 入力の決定性
3. **Gate と Validator の役割分離（NH8+）** — エスカレーション vs 安全検証
4. **Safety / Accuracy 分離（NH10-11）** — `safe_HUMAN_REVIEW` は Safety 成功であり Accuracy 失敗ではない
5. **Evidence 3系統** — 4分類 / State オブジェクト / slot 引用の同名異義
6. **Mechanical Compression（NH12-2）** — material_shortage 解消、LLM 前の決定的圧縮層
7. **Shadow Mode（NH11）** — 本番非改変で real log 診断

---

## 3. まだ曖昧な概念（UNKNOWN 明示）

| 概念 | 状態 | 備考 |
|------|------|------|
| Fixed Slot 最小集合 | unknown | H-NH12-2-2、28→削減は未確定 |
| Observation LLM 不要化 | 仮説 | H-NH12-2-3、NH12-2 B で一部有望だが未一般化 |
| LLM 自律 Selector | proposed | H-SEL、本番未実装 |
| 本番 Shadow 接続 | 未実装 | Sidecar 設計のみ |
| `high_slots` 最終定義 | experimental | NH10 以降で運用中だが schema 固定ではない |
| Problem Fingerprint（NH6 LLM 直） | experimental_not_recommended | 歴史的経路、現行設計と矛盾 |

---

## 4. 既存実験との対応（NH1–NH12）

| 実験 | 主概念 | glossary 反映 |
|------|--------|---------------|
| EXP-007 | Evidence 4分類 | FACT, OBSERVED, INFERENCE, UNKNOWN |
| EXP-008 | N2 Gate | Gate |
| NH1–NH4 | State, Validator, REOPEN | ACTIVE, SUPERSEDED, REOPEN, Claim, Goal |
| NH5 | Selector | Selector, Feature, Method Catalog |
| NH6 | LLM fingerprint（非推奨） | Fingerprint evolution 欄 |
| NH7 | Observation 分離 | Observation, Mechanical Mapping |
| NH8 | Uncertainty Gate | Gate, Escalation, HIGH/LOW |
| NH9 | Fixed Slots | Fixed Slot, Small/Large LLM |
| NH10 | Prefill, Safety/Accuracy | Mechanical Prefill, high_slots |
| NH11 | Shadow, real log | Shadow Mode, Sidecar, material_shortage |
| NH12-1 | Case 拡張 | material_shortage 事例 |
| NH12-2 | Compression | Mechanical Compression |

**注意:** `experiment_refs` は「その実験で使われた/議論された」ことを示す。`SUPPORTED` はその回の評価であり、本番 `adopt` ではない。

---

## 5. 今後追加すべき用語

- **Rejected Method / Selection Reason / Reuse** — Selector 出力の詳細フィールド（rules.json には存在、独立エントリ未作成）
- **Change Request** — State 実験用語（NH2）
- **Baseline / Condition / Ablation** — 実験設計語彙
- **Snippet / dumps / Collect / Execution Path** — search_web 診断の細分化
- **Mechanical Validator** — Validator との明示分離
- **Uncertainty Gate** — Gate のサブタイプとして独立エントリ
- **N2 Gate** — EXP-008 固有ゲート

`build_glossary.py` の `TERMS` リストに追加し、再生成すれば `glossary.json` に反映可能。

---

## 6. LLM に渡す場合の利用方法

### 推奨順序

1. **`llm/LLM_QUICK_REFERENCE.md`** — システムプロンプト先頭（~1KB）
2. **`llm/LLM_CONTEXT_GLOSSARY.md`** — Small/Large LLM の役割別に全文または該当セクション
3. **`glossary.json`** — ツール呼び出し・RAG・プログラム連携時

### 役割別

| LLM 役割 | 渡すもの |
|----------|----------|
| Small LLM（Observation） | QUICK_REFERENCE + Observation/DO NOT セクション |
| Large LLM（slot audit） | QUICK_REFERENCE + high_slots + Gate HIGH 定義 |
| 人間レビュー補助 | `human/GLOSSARY.md` 混同防止表 |

### 渡さない方がよいもの

- 実験の再解釈で昇格したような記述（本辞書は一次資料ベース）
- 本番 `selector.py` を変更する指示（experimental と明記）

---

## 7. 完了チェックリスト

- [x] `human/GLOSSARY.md`
- [x] `program/PROGRAM_GLOSSARY.md`
- [x] `llm/LLM_CONTEXT_GLOSSARY.md`
- [x] `llm/LLM_QUICK_REFERENCE.md`
- [x] `glossary.json`（40 terms）
- [x] 混同防止表（human + llm）
- [x] NH1–NH12 参照（glossary.json `experiment_refs` + human 表）
- [x] 確定 / experimental / 仮説 / UNKNOWN 区別
- [x] 未確定概念の UNKNOWN 明示
- [x] `GLOSSARY_REPORT.md`（本ファイル）

---

## 8. 制約遵守

- 本番 Agent / Tool / Manager / Selector / search_web / State 本体: **未変更**
- 既存実験 run: **未変更**
- 未実装機能を実装済みと記載: **なし**
- 存在しない JSON キーの invent: **なし**

---

## 9. メンテナンス

```bash
# 用語追加後
python knowledge_base/glossary/build_glossary.py
```

`TERMS` in `build_glossary.py` が単一の機械可読ソース。Markdown は人間/LLM 向けの展開版。
