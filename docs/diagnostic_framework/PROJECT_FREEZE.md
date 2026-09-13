# PROJECT_FREEZE — 仮完成版の定義

**凍結日:** 2026-08-28  
**対象:** AI-Agent 診断フレームワーク（NH1〜NH14 および関連 KB・Selector・Glossary）

---

## 宣言

NH1〜NH14 までの実験により、ローカル LLM を中心とした診断補助システムについて、以下の暫定構造を得た:

- Observation
- Mechanical Fingerprint
- Validator
- Gate
- Selector
- UNKNOWN
- 必要時の External Help

ただし、これは **完成品ではなく「仮完成版」** である。

---

## 凍結の意味

| 含む | 含まない |
|------|----------|
| 現状の記録・索引の固定 | 研究の永久終了 |
| 新規 NH 実験の停止 | 本番 AI-Agent 開発の停止 |
| 過去 run の改変禁止 | KB の将来更新禁止（experimental 追記は需要時） |
| 本番コード無変更の維持 | External Help の将来実装禁止 |

---

## 今後の方針

1. **AI-Agent 本体の開発を優先する**
2. 次のいずれかが **具体的に発生した時** のみ、必要範囲で実験・改良を再開する:
   - 実際にローカル LLM へ任せたい問題が発生した
   - 現在の仕組みでは困る
   - 新しい用途が必要になった
3. 再開時は [FUTURE_WORK.md](./FUTURE_WORK.md) の A〜D フレームワークに従う

---

## 現時点の実装対象外（明示）

以下は凍結期間中、**実装対象外** とする（将来の再評価は可能）:

- 自動修正（auto_fix）
- 自己修復（self-repair）
- 有料 API 連携
- Cursor 自動連携（External Help の自動送信）
- 本番 Agent / Tool / Manager / Selector / search_web への無断統合
- 過去実験 run の再実行・上書き

---

## 成果物の所在

| 種別 | 場所 |
|------|------|
| 人間向け仮完成記録 | `docs/diagnostic_framework/`（本ディレクトリ） |
| 実験一次記録 | `FW/runs/` |
| 機械・実験 KB | `FW/knowledge_base/` |
| 実験用コード | `FW/selector/`, `FW/run_nh*.py` |

---

## 区切りの根拠

- NH14 で実ログ 12 件、LLM 0 回の end-to-end Shadow + External Help パッケージ生成まで到達
- 判定: **PARTIALLY_READY**（安全引き渡しは成立、因果確定は委譲）
- これ以上の研究は、本番開発からの **具体的フィードバック** なしには優先度が低いと判断

---

## 関連

- [FREEZE_REPORT.md](./FREEZE_REPORT.md) — 本作業の実施内容
- [CURRENT_STATUS.md](./CURRENT_STATUS.md) — 現状サマリー
