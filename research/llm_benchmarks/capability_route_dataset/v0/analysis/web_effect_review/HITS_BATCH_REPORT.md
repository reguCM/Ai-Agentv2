# hits取得バッチ報告（25件）

## 結論

比較単位は維持したまま、**検索 hits>0 の完成回答ペアを25件**追加した。

| 条件 | 結果 |
|------|------|
| `answer_without_web` / `answer_with_web` 両方非空 | 25/25 |
| `web_hit_count` > 0 | 25/25 |
| ローカルTool | 未使用 |
| 同一 request・同一モデル条件 | はい |
| 自動ラベル / heuristic / Gate 変更 | なし |
| 旧パイロット（hits=0） | 削除せず残置 |

## 人間レビュー主対象

| ファイル | 内容 |
|----------|------|
| `web_effect_review_hits.csv` | 完成回答横並び＋空欄ラベル |
| `COMPARE_web_effect_review_hits.md` | request → without → search補助 → with |
| `CHOICES.md` | 選択肢定義 |

## 採用ID（25）

B05, C02, C03, P02a, P02b, A06, E02, A03, A04, C04, C05, E05, E04, WB01–WB12

## スキップ

- **E03**（東京都ごみ分別）: 複数クエリでも hits=0（429含む）→ レビュー集合から除外

## 生成上の工夫（ハーネスのみ）

- `seed_queries` で百科事典向き英語クエリを優先
- hits が取れるまでクエリを複数試行（`search_web` 本体・heuristic は未変更）
- `--require-hits` で hits=0 をレビュー集合に入れない

## 注意

- 本バッチは「検索が実際に返る」ケース中心のため、時事ニュース／予報の比率は低い
- 評価対象は依然として **完成回答同士**（検索JSONは補助）
