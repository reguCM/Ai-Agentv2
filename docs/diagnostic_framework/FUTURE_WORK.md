# FUTURE_WORK — 再開候補（今すぐ実施しない）

凍結中は **タスクとして着手しない**。具体的な必要性が発生した時点で、該当セクションのみ検討する。

---

## 優先フレームワーク

```text
A. ローカル LLM に任せたい仕事が出た
   → 既存 Selector/Validator で適用可能か検討

B. ローカル LLM では難しい仕事が出た
   → Large LLM / Cursor 委譲を検討

C. 人間の確認が必要なケースが出た
   → External Help Package の実用性を検討

D. 作成手順そのものに問題が出た
   → 新しい実験（NH15+）を設計
```

---

## A — ローカル LLM 適用の検討

**トリガー例:**

- 本番 Agent で特定 Tool の診断をローカル LLM に任せたい
- State 更新前の機械検証を本番フローに入れたい

**参照:**

- NH1〜NH4（Validator）
- NH5（Selector ルール）
- NH12-2（Compression）
- [DECISION_LOG.md](./DECISION_LOG.md) 採用候補

**やらないこと（デフォルト）:** いきなり本番 auto_fix

---

## B — エスカレーションの検討

**トリガー例:**

- Gate HIGH が頻発し小型では品質が足りない
- 因果確定が必要だが Shadow では不十分

**参照:**

- NH8〜NH10（Gate + Prefill）
- EXP-010（大型 LLM）
- H-2STAGE（二段パイプライン未検証）

---

## C — External Help の実用化

**トリガー例:**

- Cursor / 人間が Help Package を実際に使う運用が始まる
- UNKNOWN ケースの引き渡し品質に不満

**参照:**

- NH14 run + `external_help_requests/`
- EXTERNAL_HELP_SCHEMA.md（run 内）

**検討項目:** パッケージ形式の改善、自動送信の要否（現状は不要と判断）

---

## D — 新規実験

**トリガー例:**

- Observation coverage がボトルネックと判明
- 新 Tool 種別で Fingerprint が機能しない
- Glossary Relevant 選択が特定領域でのみ有効と判明

**設計原則:**

- 過去 run を上書きしない
- LLM 呼び出しは必要最小限
- Safety ゲート（unsafe_accept=0）を維持
- 結果は experimental 追記のみ（KB 確定昇格しない）

---

## 保留中の仮説（必要性発生時）

| ID | 内容 |
|----|------|
| H-N1 | 1 接続ずつ Yes/No |
| H-N3 | ログなし runtime 原因の断定禁止 |
| H-N2b | 偽原因シードで N2 再現率 |
| H-2STAGE | 小型局所 + 大型統合 |
| H-SEL | LLM 自律 Selector |

---

## 関連

- [PROJECT_FREEZE.md](./PROJECT_FREEZE.md)
- [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md)
