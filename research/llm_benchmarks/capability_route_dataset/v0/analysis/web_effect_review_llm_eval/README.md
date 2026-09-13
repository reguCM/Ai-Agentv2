# Web検索結果・LLM評価一致度パイロット

目的: 人間レビューと同等の判断を別LLMが再現できるか測る（**実装変更なし**）。

- 対象: `pilot_11_cases.json` の11件
- 入力: `web_effect_review/normalized/review_dataset.json`
- CSVをLLMに直接渡さず `evaluation_cards.md` 形式で評価
- 人間未入力時は agreement 空欄

## 実行

```text
python run_llm_eval_pilot.py
python run_llm_eval_pilot.py --dry-run
```

## 出力

| ファイル | 内容 |
|----------|------|
| evaluation_cards.md | 評価カード |
| llm_evaluation.json / .csv | LLM評価 |
| human_vs_llm.csv | 人間比較 |
| REPORT.md | 集計 |
