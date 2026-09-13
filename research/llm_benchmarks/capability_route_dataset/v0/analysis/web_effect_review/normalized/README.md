# 検索結果 人間レビュー用正規化

検索結果そのものの自動評価ではなく、**人間が読める表示**への正規化のみ。

- 原データ (`web_effect_review_hits.json`) は変更しない
- `empty`（内容なし）と「無関係」を分離
- 英語原文は残し、必要なら日本語要約を補助表示
- 有用性・Web効果・採用の自動入力はしない
- heuristic / Gate / Pipeline / Stage3/4 非接続

主比較: `answer_without_web` → 検索結果カード → `answer_with_web`

## ファイル

| ファイル | 内容 |
|----------|------|
| `review_cards.md` | 人間向けカード |
| `review_dataset.json` | 正規化データ |
| `review_worksheet.csv` | 日本語列の記入用 |
| `SUMMARY.md` | 件数サマリ |

## 再生成

```text
python normalize_and_build.py --all
python normalize_and_build.py --sample10
python normalize_and_build.py --test
```
