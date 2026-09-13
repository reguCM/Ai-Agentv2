# INDEX — 診断フレームワーク全体索引

「この仕組みについて最初から知りたい」場合の入口。

## 推奨ルート

```text
INDEX.md（本ファイル）
  ↓
CURRENT_STATUS.md
  ↓
ARCHITECTURE.md
  ↓
HISTORY.md
  ↓
必要な NH 実験の EXPERIMENT_REPORT（FW/runs/ 内）
```

## 現在の状態

| 文書 | 説明 |
|------|------|
| [CURRENT_STATUS.md](./CURRENT_STATUS.md) | 目的・パイプライン・できること・できないこと |
| [PROJECT_FREEZE.md](./PROJECT_FREEZE.md) | 仮完成版の定義と凍結方針 |
| [FREEZE_REPORT.md](./FREEZE_REPORT.md) | 2026-08-28 凍結作業の報告 |

## 主要 Knowledge Base（機械・実験用）

パス基準: `FW/knowledge_base/`（[README 参照](./README.md#フレームワーク実体の場所)）

| ファイル | 内容 |
|----------|------|
| HYPOTHESIS_STATUS.md | 全仮説の支持／反証／未検証 |
| INTEGRATION_REPORT.md | EXP 系（NH 以前）の人間向け総括 |
| EXPERIMENT_INDEX.md | EXP-001〜010 時系列 |
| FINDINGS.md | 比較的信頼できる知見 |
| METHOD_EFFECTIVENESS.md | 手法別効果 |
| method_catalog.json | 診断手法カタログ |
| glossary/ | Human / Program / LLM 用語辞書 |

## NH1〜NH14 実験

| NH | Run パス（`FW/runs/` 配下） | 概要 |
|----|----------------------------|------|
| NH1 | `20260826_183500/nh1_state_transition_constraints/` | State 遷移の機械制約 |
| NH2 | `20260826_190000/nh2_state_transition_generalization/` | Goal/Claim/Hypothesis への一般化 |
| NH3 | `20260826_191500/nh3_state_safety_boundary/` | Evidence 検証・sidecar |
| NH4 | `20260826_201500/nh4_state_safety_boundary/` | timestamp・正規化限界 |
| NH5 | `20260827_134500/nh5_selector_selection_experiment/` | ルール Selector |
| NH6 | `20260827_140500/nh6_fingerprint_selector_experiment/` | LLM 指紋生成 |
| NH7 | `20260827_143100/nh7_observation_to_fingerprint/` | Observation→機械 FP |
| NH8 | `20260827_145000/nh8_uncertainty_gated_escalation/` | 不確実性 Gate |
| NH9 | `20260827_151000/nh9_fixed_observation_escalation/` | Fixed slot・大型限定 |
| NH10 | `20260827_163000/nh10_mechanical_prefill_gate/` | Mechanical Prefill |
| NH11 | `20260827_195500/nh11_real_shadow/` | 実ログ Shadow（19件） |
| NH12 | `20260828_110500/nh12_real_shadow_expansion/` | Shadow 拡張（+30件） |
| NH12-2 | `20260828_114000/nh12_2_observation_compression/` | 機械圧縮 |
| NH13 | `20260828_123600/nh13_glossary_context_experiment/` | Glossary Context |
| NH13-7 | `20260828_131500/nh13_7_mechanical_glossary_selection/` | 機械 Glossary 選択 |
| NH14 | `20260828_134500/nh14_real_log_shadow_external_help/` | External Help パッケージ |

詳細: [HISTORY.md](./HISTORY.md)

## 実験 run（全タイムスタンプ）

`FW/runs/` に 37 タイムスタンプディレクトリ（20260824〜20260828）。NH 以前の EXP 系も含む。

## Selector（実験用）

`FW/selector/experiments/` 配下:

| ディレクトリ | 対応 NH |
|-------------|---------|
| nh5/ | NH5 |
| nh6/ | NH6 |
| nh7/ | NH7 |
| nh8/ | NH8 |
| nh9/ | NH9 |
| nh10/ | NH10 |
| nh11/ | NH11 |
| nh12/ | NH12 |
| nh12_2/ | NH12-2 |
| nh13/ | NH13 |
| nh13_7/ | NH13-7 |
| nh14/ | NH14 |

本番 Selector とは別物。Shadow 評価・シミュレーション用。

## Glossary

`FW/knowledge_base/glossary/`

| 層 | パス |
|----|------|
| Human | `glossary/human/GLOSSARY.md` |
| Program | `glossary/program/PROGRAM_GLOSSARY.md` |
| LLM | `glossary/llm/LLM_CONTEXT_GLOSSARY.md` |
| 機械 | `glossary/glossary.json` |

方針: [GLOSSARY_POLICY.md](./GLOSSARY_POLICY.md)

## 主要設計文書（本ディレクトリ）

| 文書 | 内容 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 概念アーキテクチャ |
| [EXPERIMENT_SUMMARY.md](./EXPERIMENT_SUMMARY.md) | 横断知見 |
| [DECISION_LOG.md](./DECISION_LOG.md) | 意思決定ログ |
| [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) | 限界 |
| [FUTURE_WORK.md](./FUTURE_WORK.md) | 再開候補 |

## ランナー（FW 直下）

| スクリプト | NH |
|-----------|-----|
| run_nh3_state_safety_experiment.py | NH3 |
| run_nh4_state_safety_experiment.py | NH4 |
| run_nh5_selector_selection_experiment.py | NH5 |
| run_nh6〜run_nh14_* | NH6〜NH14 |

凍結中は再実行しない。

## 今後の候補

[FUTURE_WORK.md](./FUTURE_WORK.md) — 必要性発生時のみ検討。

## AI-Agent 直下の研究ベンチ（移動済み）

2026-08-28 より、直下にあった `_phase*` / `_kss*` / `_debug*` 等は **`research/benchmarks/`** へ移動済み。

| 種別 | パス |
|------|------|
| Phase 1〜5 ベンチ | `research/benchmarks/phases/phase*/` |
| KSS ベンチ | `research/benchmarks/kss/` |
| デバッグ・検証 | `research/benchmarks/debug/`, `verify/` |

診断フレームワーク（NH 系）は `diagnostic_framework/` 配下のまま。役割が異なる。

[MOVE_CANDIDATES.md](./MOVE_CANDIDATES.md) — 移動記録  
[research/benchmarks/README.md](../../research/benchmarks/README.md) — ベンチ一覧
