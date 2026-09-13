# 暫定 Diagnostic Method Selector

ルールベース＋知識ベース。機械学習型の分類器ではない。

- 本番 `search_web` / Agent / ranking は変更しない
- 既存実験 run は上書きしない
- LLM（Qwen / DeepSeek / 大型）は呼び出さない
- 同じ `problem_id` では `reuse_index.json` 経由で過去成果物を参照する

## 構成

| ファイル | 役割 |
|----------|------|
| `../knowledge_base/method_catalog.json` | 実験から登録した手法カタログ |
| `rules.json` | 特徴 → 手法の選択規則 |
| `reuse_index.json` | 問題IDごとの再利用成果物 |
| `problems/search_web_quality.json` | 既存 search_web 診断の問題指紋 |
| `expected_eval.json` | 知識ベースから作った評価期待 |
| `selector.py` | 選択エンジン |
| `run_selector.py` | 実行（新規 run ディレクトリへ出力） |

## 実行

```text
python diagnostic_framework/selector/run_selector.py
```

作業ディレクトリは `diagnostic_framework/selector` でも可。

## 出力

`diagnostic_framework/runs/<timestamp>/selector_eval/`

- `selector_result.json` — 選択・未選択・理由・信頼度・再利用パス
- `SELECTOR_EVAL.md` — 人間向け評価
- `selector_eval.json` — gold 照合

## 限界

- 問題特徴は人間（または上流の機械観測）が付ける。特徴抽出の自動化は未実装
- LLM が手法を自律選択できるかは未検証
- 選択結果が真因の正しさを保証しない
