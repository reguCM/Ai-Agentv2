# DECISION_LOG — 意思決定ログ

**凍結日:** 2026-08-28  
「採用しない」は永続禁止ではなく、**現時点の優先順位** を示す。必要性発生時に再評価する。

---

## 採用候補（experimental / adoption candidate）

実験で支持され、今後の AI-Agent 開発で参照価値が高いもの。

| 決定 | 根拠 |
|------|------|
| Mechanical State Transition Constraint | NH1 Strong Support, NH2 Supported |
| History-based validation | NH1〜NH2 |
| Evidence validation（実在・content） | NH3 SUPPORTED |
| timestamp / freshness 確認 | NH4 SUPPORTED |
| Mechanical Prefill | NH10 SUPPORTED in sim |
| Mechanical Fingerprint（obs→map） | NH7, NH9 SUPPORTED in sim |
| uncertainty Gate | NH8 SUPPORTED in sim |
| UNKNOWN の明示的許容 | NH5, NH8, NH14 |
| Safety-first validation | NH1〜NH14 で unsafe_accept=0 維持 |
| Observation / Fingerprint 分離 | NH7, NH9 |
| 証拠4分類（FACT/OBSERVED/INFERENCE/UNKNOWN） | EXP-007 |
| route 分解（状況依存） | EXP-006 |
| N2 経路外フィルタ（原因強度には使わない） | EXP-008 |
| Mechanical Compression | NH12-2 SUPPORTED |
| ルール Selector（Shadow） | NH5 SUPPORTED in sim |
| HUMAN_REVIEW を失敗扱いしない | NH11 SUPPORTED in shadow |

---

## 条件付き（状況・追加検証が必要）

| 決定 | 条件 | 根拠 |
|------|------|------|
| Large LLM escalation | 不確実 slot / Gate HIGH のみ | NH8, EXP-010 |
| External Help Package | 自力確定不可時のみ。自動送信はしない | NH14 PARTIAL_READY |
| Relevant Glossary | 必要時のみ機械選択。常時投入しない | NH13-7 PARTIAL, NH13 D 条件 |
| 小型 LLM 局所解析 | 構造化後の候補生成まで | EXP-003, INTEGRATION_REPORT |
| sidecar 最小セット | test + runtime + evidence_content | NH4 SUPPORTED |
| Update Request + Manager | FA 削減。常時二次レビューは不支持 | H-REQ-1, H-REV-1 |

---

## 現時点では採用しない

| 決定 | 理由 | 再評価トリガー |
|------|------|---------------|
| Full Glossary 常時投入 | unsafe 増、token 非効率 | 特定 slot で明確な改善が実測された場合 |
| LLM による完全自律 Selector | 未検証、再現性不明 | ローカル LLM に任せたい選択タスクが具体化 |
| Morph/Synonym による積極的正規化 | NH4 PARTIALLY_SUPPORTED、FR 増リスク | 正規化が必要なケースが本番で頻発 |
| DeepSeek 全面置換 | EXP-009 不支持 | モデル・ctx 条件が変わった場合 |
| 常時大型 LLM | 効率・コスト。NH8 で削減可能 | 品質要件が小型では絶対に足りないと判明 |
| 自動修正（auto_fix） | 全実験 NOT_ALLOWED | 承認・テスト・ロールバック体制が整備後 |
| 自己修復（self-repair） | 研究範囲外 | 同上 |
| 有料 API への依存 | 未実装、方針外 | 明示的なビジネス要件 |
| Cursor 自動連携 | NH14 はパッケージまで | External Help の実利用評価後 |
| 仕様書のみでの実装帰属解決 | EXP-005 | 仕様と実装の乖離が問題化した場合 |
| N2 YES を強い原因とみなす | EXP-008 限界 | — |
| フル経路物語の常時投入 | 過信増（EXP-008 条件 C） | — |

---

## 未決定（保留）

| 項目 | 状態 |
|------|------|
| N1（1 接続ずつ Yes/No） | 未検証・採用候補仮説 |
| N3（ログなし runtime 断定禁止） | 未検証・採用候補仮説 |
| 小型→大型二段正式パイプライン | H-2STAGE 未検証 |
| 本番 Shadow 常時接続 | 未実装 |
| KB experimental → confirmed 昇格 | 凍結中は行わない |

---

## 関連

- [CURRENT_STATUS.md](./CURRENT_STATUS.md) — 成熟度
- FW/knowledge_base/HYPOTHESIS_STATUS.md — 仮説単位の判定原文
