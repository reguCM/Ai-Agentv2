# pre_web 人間レビュー

**Agentの正解ではない。** 既存ログ・実装・heuristic・Stage4は変更しない。

## あなたがやること（これだけ）

1. [CHOICES.md](CHOICES.md) で選択肢の意味を確認する
2. [COMPARE.md](COMPARE.md) または [cards/](cards/) を **要求→Webなし→検索結果→最終回答** の順で読む
3. [記入シート.csv](記入シート.csv)（または review_worksheet.csv）の右端4列だけ埋める

| 列名 | 内容 |
|------|------|
| **Web必要性** | この要求に Web は要ったか |
| **Web効果** | Webなし回答と比べて最終回答はどう変わったか |
| **事実性への効果** | 事実の正しさはどう変わったか |
| **理由** | 上記を選んだ短い根拠 |

**quadrant（4象限）は人間が書かない。** 記入後に次で自動生成する:

```text
python analysis/build_pre_web_human_review.py --apply-quadrants --worksheet 記入シート.csv
```

## 4象限（自動生成）

| | Webで改善 | 改善しない/悪化 |
|---|-----------|----------------|
| Web必須・有益（必須/有用） | ◎ 理想的な検索 | △ 検索品質の問題 |
| Web任意・不要寄り（任意/不要） | ○ 検索の追加価値 | ○/△ 無駄な検索 |

「不要なのに検索した＝悪い」と決めない。○ を積極的に探す。

- 総数: 50 / Web実行あり: 30
- 優先確認（rank≤2）: 13

## 優先ケース

| case | category | Web実行 | outcome | フラグ |
|------|----------|---------|---------|--------|
| D01 | web_word_but_unneeded | はい | error | 不要寄りなのに検索した（重点） / 以前ヒントno_webなのに検索 / 追加価値がないか要確認 |
| C01 | web_needed_ambiguous | はい | error | 任意・曖昧だが検索あり |
| C02 | web_needed_ambiguous | はい | hits | 任意・曖昧だが検索あり / hitsあり・検索結果を精読 |
| C03 | web_needed_ambiguous | はい | error | 任意・曖昧だが検索あり |
| C04 | web_needed_ambiguous | はい | error | 任意・曖昧だが検索あり |
| C05 | web_needed_ambiguous | はい | error | 任意・曖昧だが検索あり |
| E04 | web_needed_no_web_words | はい | error | 任意・曖昧だが検索あり |
| G08 | tool_gap_candidate | はい | error | 任意・曖昧だが検索あり |
| H01 | composite_multi_tool | はい | error | 任意・曖昧だが検索あり |
| H02 | composite_multi_tool | はい | error | 任意・曖昧だが検索あり |
| P01a | paraphrase | はい | hits | hitsあり・検索結果を精読 |
| P01b | paraphrase | はい | hits | hitsあり・検索結果を精読 |
| P02a | paraphrase | はい | error | 任意・曖昧だが検索あり |

## ファイル

| ファイル | 用途 |
|----------|------|
| `CHOICES.md` | 選択肢の意味 |
| `記入シート.csv` | 記入用（右端4列）※推奨 |
| `review_worksheet.csv` | 同上（ロック時は記入シート.csvを使用） |
| `COMPARE.md` | 全件比較カード |
| `cards/A01.md` など | 1ケース1ファイル |
| `review_dataset.json` | 機械可読 |
| `review_with_quadrants.csv` | 記入後の象限付き（`--apply-quadrants`） |
