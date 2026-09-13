# WEB検索効果レビューシート（再構成）

**これはレビュー資料の再構成であり、Agent実装の変更ではない。**

- heuristic / capability_route / Gate / Pipeline / Clarity / Stage3 / Stage4: **未変更**
- 既存 `web_effect_review_hits.*` / `hits_batch_results/`: **削除していない**
- 人間ラベルは空欄（レビュー結果は未作成）
- 「どちらを採用するか」項目は設けない（差分観測）

## 対象

- 件数: **25**（source: `web_effect_review_hits.json`）
- Webなし完成回答あり: **25**
- 検索結果あり (count>0): **25**
- Webあり完成回答あり: **25**
- 同一 `case_id` / `request` で without・search・with を対応付け

## 1ケースの見方

1. ユーザー要求（+ 質問の明確さ）
2. Webなし完成回答（+ 十分性）
3. Web検索結果 生データ（+ 有用性）
4. Webあり完成回答（+ 変化 / 活用）
5. 開発上のメモ

## 記入ファイル

| ファイル | 用途 |
|----------|------|
| `review_worksheet.xlsx` | **主推奨** Overview＋1ケース1シート、プルダウンあり |
| `review_worksheet.csv` | 表形式バックアップ |
| `COMPARE.md` | 読み比べカード |
| `review_dataset.json` | 機械可読（検索JSON生データ含む） |

## プルダウン

| 列 | 選択肢 |
|----|--------|
| question_clarity | ◎ 明確 / ○ ほぼ明確 / △ 曖昧 / × 意味が破綻している |
| web_without_answer_quality | ◎ 十分 / ○ 概ね十分 / △ 情報不足 / × 明確な問題あり |
| search_result_usefulness | ◎ 非常に有用 / ○ 有用 / △ 一部有用 / × 無関係・取得失敗 |
| web_effect | ◎ 明確に改善 / ○ 少し改善 / △ ほぼ変化なし / ▲ 悪化 / × 明確に悪化 |
| search_result_utilization | ◎ 十分活用 / ○ 一部活用 / △ ほぼ活用されていない / × 活用されていない / ― 判断不能 |

詳細意味は Excel の `Choices` シート。

## 再生成

```text
python analysis/build_web_effect_review_worksheet.py
```
