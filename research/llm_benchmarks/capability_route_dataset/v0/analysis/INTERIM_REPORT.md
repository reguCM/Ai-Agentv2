# v0 データセット — 途中報告（収集実行中）

**日付:** 2026-08-22  
**方針:** 観測のみ。heuristic未変更。Stage3ラベルなし。Gate/Pipeline非接続。

## 1. Web検索基礎スモーク（単体）

対象: `general_web_search`（Agent経由ではない）

| クエリ | hits | 観察 |
|--------|------:|------|
| Python programming language | 3 | 英語一般語は結果が出ることがある |
| 今日の天気 東京 | 0 | 時事・天気系日本語は空になりやすい |
| zxqwv-nonexistent-... | 0 | 存在しない話題は空/error |

→ **Web判断成功 ≠ 検索hits成功**。データセットでも分離して記録する。

詳細: `analysis/web_search_foundation_smoke.json`

## 2. ケース設計（50件）

場所: `cases.json`

| category | 件数 |
|----------|-----:|
| web_needed_clear | 6 |
| web_unneeded_clear | 6 |
| web_needed_ambiguous | 5 |
| web_word_but_unneeded | 5 |
| web_needed_no_web_words | 5 |
| search_hard | 5 |
| existing_tool_ok | 5 |
| tool_gap_candidate | 5 |
| composite_multi_tool | 3 |
| paraphrase | 5 |

- 要求文に「Web検索して」等の誘導を入れない（旧パイロットケースから改善）
- 言い換え: `para_osaka_weather` / `para_rtx3060`
- 正解ラベルなし（observe_goal は人間用メモのみ）

## 3. 収集実行

```text
run_collection.py --cases .../v0/cases.json --out .../v0/results/run_v0_50
```

- collection trust（Gate off しない）
- Clarity skip は収集時のみ
- 結果は上書きせず `results/run_v0_50/` に保存

完了後:

```text
python .../v0/summarize_run.py .../v0/results/run_v0_50
```

で `human_summary.json` を生成し、本報告を更新する。

## 4. 現時点で禁止していること

- capability_route の実行接続 / Pipeline自動起動 / Gate迂回
- heuristic 修正 / Stage3自動ラベル / Stage4 LLM改善

## 5. 次の人間判断ポイント（50件完了後）

1. 判断と実行のズレ表（judged × called）
2. 言い換えグループ内の判断変化
3. 追加が必要なカテゴリ
4. 100件へ増やすか / Stage3分類軸の検討を始めるか
