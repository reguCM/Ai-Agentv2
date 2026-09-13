# knowledge_base — LLM自己診断実験の統合知識

本ディレクトリは、`search_web` 品質診断まわりの **既存実験成果の読み取り・整理・統合のみ** を目的とする。

- 新規実験は行っていない
- 既存実験結果は上書き・改変していない
- 本番 `search_web` / Agent / ranking 等は変更していない

## ファイル一覧

| ファイル | 内容 |
|----------|------|
| [EXPERIMENT_INDEX.md](./EXPERIMENT_INDEX.md) | 実験の時系列索引 |
| [FINDINGS.md](./FINDINGS.md) | 比較的信頼できる知見（事実と解釈を分離） |
| [HYPOTHESIS_STATUS.md](./HYPOTHESIS_STATUS.md) | 仮説の支持／反証／未検証 |
| [METHOD_EFFECTIVENESS.md](./METHOD_EFFECTIVENESS.md) | 手法別の効きどころと限界 |
| [MODEL_COMPARISON.md](./MODEL_COMPARISON.md) | モデル性能と入力設計の分離 |
| [DIAGNOSTIC_WORKFLOW.md](./DIAGNOSTIC_WORKFLOW.md) | 暫定診断手順（仮案） |
| [SELF_DIAGNOSIS_SELECTOR.md](./SELF_DIAGNOSIS_SELECTOR.md) | 状況別の診断方法選択知識 |
| [OPEN_PROBLEMS.md](./OPEN_PROBLEMS.md) | 未解決問題 |
| [experiment_data.json](./experiment_data.json) | 機械参照用の構造化索引 |
| [method_catalog.json](./method_catalog.json) | 診断手法カタログ（実験から登録） |
| [INTEGRATION_REPORT.md](./INTEGRATION_REPORT.md) | 人間向け総括 |
| [glossary/](./glossary/) | 用語・概念辞書（human / program / llm / glossary.json） |
| [../selector/](../selector/) | 暫定ルールベース Selector（既存問題の再利用評価） |

## 現時点の暫定アーキテクチャ

以下は実験結果から導いた **暫定案** であり、**確定設計ではない**。

```text
機械的観測
   ↓
証拠境界（FACT / OBSERVED / INFERENCE / UNKNOWN）
   ↓
必要な局所解析（route 分解・collect/rank 分離など）
   ↓
小型LLM（局所コード・ログ列挙）
   ↓
構造化された候補
   ↓
安全ゲート（N2 経路存在・N3 観測必須 など）
   ↓
大型LLM（全体統合・偽原因棄却・優先順位）
   ↓
追加調査
   ↓
人間承認
   ↓
修正提案（未承認では実行しない）
   ↓
テスト
   ↓
再診断
```

根拠の要約は `INTEGRATION_REPORT.md` と `METHOD_EFFECTIVENESS.md` を参照。
