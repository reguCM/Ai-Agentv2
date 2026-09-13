# EXPERIMENT_SUMMARY — 横断的な重要知見

NH1〜NH14 および EXP 系から得られた、設計判断に直結する知見の整理。数値の一次ソースは各 run の `EXPERIMENT_REPORT.md` を参照。

---

## 重要な知見（10 項目）

### 1. LLM 単体の能力だけでは診断品質は決まらない

モデル名やサイズだけでなく、`num_ctx`、コード添付、route 分解、証拠境界が結果を支配する（EXP-002〜003, INTEGRATION_REPORT F002）。

### 2. Context、コード、Evidence、Workflow 分解が重要

- 十分な `num_ctx`（32768）とコード全文添付が前提（EXP-003）
- route 分解で stdout/LLM 接続は改善（EXP-006）
- collect/rank 分離で段階混同を抑制（EXP-007）

### 3. Observation と Fingerprint を分離すると安定する

NH7 で obs→機械 mapping が LLM 直出し指紋より優位。NH9 で LLM は slot 抽出のみに限定（fp 83% vs 43%）。

### 4. 機械的な安全制約は LLM より安定する

NH1 Strong Support、NH3 SUPPORTED。FA/unsafe_accept は制約追加で低下。LLM 判断に安全を委ねない。

### 5. UNKNOWN を許容することが安全性に重要

ログなし runtime 原因の断定禁止（N3 仮説）、Gate UNKNOWN→External Help（NH14）。過信より UNKNOWN の方が安全。

### 6. 大型 LLM は常時利用より、不確実時のエスカレーション候補として有望

EXP-010 条件付き支持。NH8 で large 2 vs 10、missed=0。常時大型は非推奨。

### 7. Glossary は LLM の推論能力を大幅に改善するものではなかった

NH13: terminology 混同 0 だが主因は Mixed/Reasoning。Observation slot 微増のみ。H-NH13-1 UNSUPPORTED。

### 8. Glossary は主として人間向け資料として価値がある

Human Glossary で Observation/Fingerprint/Gate 等の混同を防ぐ。LLM 常時投入は非推奨（NH13 Full で unsafe=2）。

### 9. 自動修正は今回の研究範囲では実装しない

全実験で `auto_fix = NOT_ALLOWED`。EXP-010、NH8〜NH14 でも一貫。

### 10. 最終的に Cursor / 人間へ判断を委譲する境界を作る方向が有望

NH11〜NH14 で HUMAN_REVIEW / EXTERNAL_HELP を失敗ではなく制御可能な出口として設計。NH14 でパッケージ生成まで成立。

---

## 手法別クイックリファレンス

| 手法 | 効果 | 限界 |
|------|------|------|
| 証拠4分類 | OBSERVED 捏造抑制 | 原因過信は残る |
| N2 経路存在 | 経路外偽原因排除 | 経路上誤因果は通過 |
| route 分解 | 表示/LLM 分離 | caller 誤認残存 |
| ルール Selector | sim 10/10 | 実ログで 8/10（NH9） |
| Mechanical Prefill | H ケース修正 | sim 限定検証 |
| Mechanical Compression | shortage 29→0 | coverage 完全ではない |
| Relevant Glossary | token 効率 | 診断品質は No Glossary と同等 |

---

## モデル・ハーネス

```text
結果 ≈ モデル × num_ctx × パック設計 × 証拠ラベル × ゲート × 設問設計
```

- Qwen `qwen3:8b` が NH5〜NH13 の主要小型モデル
- DeepSeek 全面置換は不支持（EXP-009）
- 大型は `qwen3:14b` または Composer（EXP-010）— 一般化は未検証

---

## 関連文書

- [DECISION_LOG.md](./DECISION_LOG.md) — 採用判断
- [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) — 限界
- FW/knowledge_base/FINDINGS.md — 詳細知見 ID 付き
