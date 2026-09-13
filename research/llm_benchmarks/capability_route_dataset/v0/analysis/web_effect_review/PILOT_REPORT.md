# パイロット確認報告（10件）

生成日時の成果物: 同ディレクトリの `web_effect_review.csv` / `.json` / `COMPARE.md`

## 結論（定義適合）

**主比較対象は定義どおり「完成回答同士」になっている。**

| 項目 | 結果 |
|------|------|
| `answer_without_web` | 10/10 非空。`search_web` 未実行・検索結果未投入・ローカルTool未使用で生成した**ユーザー向け完成回答** |
| `answer_with_web` | 10/10 非空。同一 `request` で `search_web` 実行 → hits（今回は0）をLLMに渡したうえで生成した**ユーザー向け完成回答** |
| 同一 request / 同一モデル | はい（`get_llm_profile()`） |
| 既存 `pre_web_answer_candidate` の再利用 | **なし**（別ハーネスで再生成） |
| L系（ローカルTool本質） | パイロットから除外 |
| 人間ラベル自動付与 | **なし**（空欄） |
| heuristic / Gate / Pipeline 変更 | **なし** |

したがって、古い `pre_web_human_review` の「候補 vs 本番最終」比較ではなく、

> WEBなし完成回答 ↔ WEBあり完成回答

の横並び比較が可能。

## 生成パイプライン（実装）

```text
without_web:
  request → LLM(SYSTEM_SHARED, toolsなし) → answer_without_web

with_web:
  request → LLM(query提案) → search_web(query) → hits JSON をLLMへ
         → LLM(SYSTEM_SHARED+WEBルール) → answer_with_web
```

- ローカルTool（cpu/gpu/files）は呼ばない
- `agent.py` 本番ループは起動しない（比較ハーネス専用）
- 既存 `run_v0_50_preweb/` / `pre_web_human_review/` は削除していない

## パイロット10件

| id | band | 選定理由 |
|----|------|----------|
| A01 | W0 | 時事ニュース |
| A02 | W0 | 為替の現在値 |
| A05 | W0 | 天気予報 |
| A06 | W0 | 版固有の外部情報 |
| B05 | W1 | 一般知識（不要寄りでも検索効果を見る） |
| C02 | W1 | 知識/WEB両方可 |
| C03 | W1 | 「今」の扱い |
| E02 | W0 | 製品プラン |
| E05 | W0 | 時事イベント |
| P01a | W0 | 天気（言い換え） |

除外例: B01–B04/B06/D*/G*/H* などローカルToolが本質のL系。

## 重要な観測（検索経路）

今回の10件は **すべて `search_web` が `hit_count=0` / error=`検索結果がありません`**。

そのため `answer_with_web` は「検索成功後の改善」ではなく、

- 検索を試み、結果が空だったあとに返した完成回答

になっている。

これは失敗ではなく、比較上こう読める。

- without: 知識だけで具体的に書いた（時事では幻覚リスクあり）
- with: 空hitsを踏まえ「確認できなかった」系に寄ることが多い

→ `web_effect` が「※検索結果が回答に実質影響なし」や「×悪化」（情報量減）になりやすいパイロットになる。
→ **検索がヒットする環境での再パイロット**が次の確認ポイント（ただし50件一括はまだしない）。

## 人間レビューの使い方

1. `COMPARE.md` で without / with を読む（検索JSONは補助）
2. `web_effect_review.csv` の空欄を埋める  
   `web_need` / `web_effect` / `factual_effect` / `overall_effect` / `reason` / `reviewer_note`
3. heuristic 判断・LLMがsearchを呼んだか・hit/error を**正解ラベルにしない**

## 次にやること / やらないこと

- **やる**: この10件のCSV体裁・比較単位が意図どおりか人間が確認
- **まだやらない**: 残り40件の一括再生成、heuristic変更、Stage3/4、自動ラベル

確認OKかつ検索が実際に hits を返す状態で、W0/W1 を拡張する。
