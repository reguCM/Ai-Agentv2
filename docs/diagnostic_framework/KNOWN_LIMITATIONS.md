# KNOWN_LIMITATIONS — 現時点の限界

「未検証」と「実験で不支持／失敗」を区別する。

---

## カバレッジ・データ

| 限界 | 種別 | 詳細 |
|------|------|------|
| 実ログ Observation coverage が完全ではない | 未検証の一般化 | NH14 mean_observation_coverage 0.6174 |
| State 専用の実ログケースが不足 | データ不足 | NH14 CASES.md に明記 |
| search_web 以外の Tool 診断 | 未検証 | EXP 系は search_web 中心 |
| NH12 拡張 30 件で required slot missing が全件 | 既知の課題 | Compression（NH12-2）で shortage は解消 |

---

## 本番統合

| 限界 | 種別 | 詳細 |
|------|------|------|
| 本番 Shadow 接続は限定的 | 未実装 | NH11〜NH14 は Shadow のみ |
| 本番 Selector / Validator への組み込みなし | 未実装 | FW/selector は実験用 |
| production mutations = 0 は実験設計による | 意図的制約 | 本番変更は行っていない |

---

## LLM・Selector

| 限界 | 種別 | 詳細 |
|------|------|------|
| LLM 自律 Selector は未検証 | 未検証 | H-SEL。ルール Selector のみ |
| LLM 指紋品質が不安定 | 部分的支持の限界 | NH6 avg acc 45% |
| 実ログで Selector 8/10 | 未検証の一般化 | NH9 C 条件 |
| Glossary による推論改善なし | 実験結果 | NH13 UNSUPPORTED（推論改善） |
| 存在と原因の混同（経路上誤因果） | 未解決 | EXP-007/008, OPEN_PROBLEMS |
| N3（ログなし runtime 断定禁止） | 未検証 | 仮説のみ |

---

## エスカレーション・External Help

| 限界 | 種別 | 詳細 |
|------|------|------|
| 大型 LLM エスカレーションの実運用検証不足 | 未検証 | sim/shadow 中心 |
| External Help はパッケージ生成まで | 未実装 | NH14 |
| 人間が Help Package を実際に使った評価なし | 未検証 | — |
| Cursor への自動送信なし | 未実装 | 凍結方針 |
| 有料 API 連携なし | 未実装 | — |

---

## 安全・修正

| 限界 | 種別 | 詳細 |
|------|------|------|
| auto_fix 未実装 | 意図的に不支持 | NOT_ALLOWED |
| self-repair 未実装 | 意図的に不支持 | — |
| REOPEN 例外の本番頻度未評価 | 未検証 | NH2 条件 D |

---

## Fingerprint・圧縮

| 限界 | 種別 | 詳細 |
|------|------|------|
| Fingerprint 自動生成には依然として限界 | 部分的支持 | 機械 mapping は sim で良好、LLM 直出しは弱い |
| Mechanical Compression の情報損失 | 未検証 | NH12-2 は shortage 解消。精度への長期影響は未評価 |
| Morph/Synonym 正規化は FR 増リスク | 実験結果 | NH4 PARTIALLY_SUPPORTED |

---

## モデル・ハーネス

| 限界 | 種別 | 詳細 |
|------|------|------|
| DeepSeek 全面置換は不支持 | 実験結果 | EXP-009 |
| 大型 LLM 改善の一般化 | 未検証 | EXP-010 は単一問題セット |
| ctx / プロンプト長超過 | 既知の失敗モード | EXP-002, EXP-009 |

---

## 関連

- [FUTURE_WORK.md](./FUTURE_WORK.md)
- FW/knowledge_base/OPEN_PROBLEMS.md
