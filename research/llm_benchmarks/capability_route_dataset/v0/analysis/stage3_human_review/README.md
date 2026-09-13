# v0 Stage 3 Human Review Dataset

**実装変更なし**（Agent / heuristic / Gate / Pipeline 未改変）。

## 成果物

| ファイル | 内容 |
|----------|------|
| `HUMAN_REVIEW.md` | 人間向け一覧・トピック集計・言い換え・追加提案 |
| `human_review_dataset.json` | 完全データ（行＋集計＋軸草案） |
| `human_review_dataset.csv` | 表形式（Excel向け） |
| `stage3_axis_draft.json` | C/D/F/G/E 分類軸草案のみ |

## 列（レビュー用）

```text
case_id
→ human_web_need          # 人間スキャフォールド（自動正解ではない）
→ heuristic_judgment      # judged_appropriate
→ llm_called_search_web
→ search_primary_outcome  # 検索経路（判断正誤ではない）
→ answer_surface_proxy    # Stage2表面
→ classification_candidates  # 草案タグ
→ classification_reason
→ misjudgment_final = null
```

## C/D/F/G/E ファミリ

- **C** 判断層と実行層のずれ（underflag / overflag）
- **D** 検索経路（error / hits / empty / blocked）— **判断誤りと分離**
- **F** route / related（uncertain飽和、continue≠達成、new_tool衝突）
- **G** Tool能力・行動（既存Tool経路、gapなのに検索、など）
- **E** 根拠・回答表面（不足／hits未検証）

## 注意

- n=50 では一般化しない
- heuristic 修正はまだしない
- Stage3 自動ラベル実装・Stage4 改善には進まない（人間が軸を確定するまで）
