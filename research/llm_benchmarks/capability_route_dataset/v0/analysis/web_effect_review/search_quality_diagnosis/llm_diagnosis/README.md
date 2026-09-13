# llm_diagnosis

search_web 品質ボトルネックの LLM 独立分析（実装変更なし）。

- model: `qwen3:8b`

```text
python run_llm_diagnosis.py
```

出力:
- CASE_ANALYSIS.md — ケース別分析
- LLM_DIAGNOSIS.md — 全体分析
- llm_diagnosis.json / .csv
- HUMAN_DECISION_SHEET.md — 人間レビュー用

事前結論をプロンプトに含めない設計。
