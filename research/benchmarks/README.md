# research/benchmarks — Agent 開発・観測ベンチ

AI-Agent リポジトリ直下に置かれていた `_phase*` / `_kss*` / `_debug*` 等の **研究・ベンチマーク用スクリプト** を集約したディレクトリ。

本番 Agent（`agent.py`）の能力実績ではない。診断フレームワーク（`diagnostic_framework/`）の NH 実験とも別系統。

## 構成

| ディレクトリ | 内容 |
|-------------|------|
| `phases/phase1/` 〜 `phase5/` | Phase 1〜5 のベンチランナーと summary/log |
| `kss/` | Knowledge Source Scoring 系ベンチ（KSS-1, 11, 13〜15） |
| `observe/` | knowledge source 観測ベンチ |
| `debug/` | 一時デバッグ・結果ダンプ用スクリプト |
| `verify/` | Agent 検証（CURSOR_VALIDATION） |
| `smoke/` | スモークテスト |

## パス規約

- `common_paths.py` の `REPO_ROOT` がリポジトリルート
- ベンチ成果物（`*_summary.json`, `*.log`）は各 phase ディレクトリ内に置く
- `research/llm_benchmarks/` への出力先は従来どおり `REPO_ROOT` 基準

## 実行例

```bash
# リポジトリルートから
python research/benchmarks/phases/phase1/_phase1_run_benchmarks.py
python research/benchmarks/kss/_kss11_measurement_bench.py
```

## 関連ドキュメント

- `docs/kss*.md` — KSS 設計メモ
- `docs/diagnostic_framework/` — 診断フレームワーク仮完成記録（NH 系）
- `research/llm_benchmarks/` — LLM ベンチ本体・結果 JSON
