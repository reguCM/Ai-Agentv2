# 診断フレームワーク — 仮完成版記録

本ディレクトリは、AI-Agent 診断フレームワーク（NH1〜NH14 および関連実験）の **人間向け正式記録** である。

研究の終了宣言ではない。**一旦の凍結・仮完成** を文書化し、今後は AI-Agent 本体開発を優先する。

## フレームワーク実体の場所

リポジトリ内の実体パス（以下 **FW** と表記）:

```text
research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/search_quality_diagnosis/diagnostic_framework/
```

| 領域 | パス | 役割 |
|------|------|------|
| 実験一次記録 | `FW/runs/` | 各 NH の run ディレクトリ（改変禁止） |
| 機械・実験 KB | `FW/knowledge_base/` | 仮説状態・手法カタログ・用語辞書 |
| 実験用 Selector | `FW/selector/` | NH 別実験コード（本番 Selector ではない） |
| 人間向け記録 | `docs/diagnostic_framework/`（本ディレクトリ） | 全体像・意思決定・凍結宣言 |

## 読み方（推奨順）

1. [INDEX.md](./INDEX.md) — 全体索引
2. [CURRENT_STATUS.md](./CURRENT_STATUS.md) — 現状を一枚で把握
3. [ARCHITECTURE.md](./ARCHITECTURE.md) — 暫定アーキテクチャ
4. [HISTORY.md](./HISTORY.md) — NH1〜NH14 時系列
5. 必要に応じて [EXPERIMENT_SUMMARY.md](./EXPERIMENT_SUMMARY.md)、[DECISION_LOG.md](./DECISION_LOG.md)

## ドキュメント一覧

| ファイル | 内容 |
|----------|------|
| [INDEX.md](./INDEX.md) | 全体索引・入門ルート |
| [CURRENT_STATUS.md](./CURRENT_STATUS.md) | 現在の目的・能力・成熟度 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Observation〜External Help の概念整理 |
| [HISTORY.md](./HISTORY.md) | NH1〜NH14 実験履歴 |
| [EXPERIMENT_SUMMARY.md](./EXPERIMENT_SUMMARY.md) | 横断的な重要知見 |
| [DECISION_LOG.md](./DECISION_LOG.md) | 採用候補・条件付き・非採用の整理 |
| [GLOSSARY_POLICY.md](./GLOSSARY_POLICY.md) | 用語辞書の位置づけ |
| [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) | 現時点の限界 |
| [FUTURE_WORK.md](./FUTURE_WORK.md) | 必要性発生時の再開候補 |
| [PROJECT_FREEZE.md](./PROJECT_FREEZE.md) | 仮完成・凍結の定義 |
| [MOVE_CANDIDATES.md](./MOVE_CANDIDATES.md) | AI-Agent 直下ファイルの整理候補 |
| [FREEZE_REPORT.md](./FREEZE_REPORT.md) | 本作業の完了報告 |

## 関連（FW 内）

- [INTEGRATION_REPORT.md](../../research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/search_quality_diagnosis/diagnostic_framework/knowledge_base/INTEGRATION_REPORT.md) — EXP 系の統合（NH 以前）
- [HYPOTHESIS_STATUS.md](../../research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/search_quality_diagnosis/diagnostic_framework/knowledge_base/HYPOTHESIS_STATUS.md) — 仮説判定の機械参照元
- [EXPERIMENT_INDEX.md](../../research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/search_quality_diagnosis/diagnostic_framework/knowledge_base/EXPERIMENT_INDEX.md) — EXP-001〜010 索引

## 変更ポリシー（凍結中）

- 本番 Agent / Tool / Manager / Selector / `search_web` 本体は変更しない
- `FW/runs/` の過去実験結果は上書き・改変しない
- 新規 NH 実験は、具体的な利用需要が発生するまで開始しない
- `auto_fix` は NOT_ALLOWED のまま
