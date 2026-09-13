# SEARCH_PATH_TRACE_REPORT

- 生成: `2026-08-24T05:29:15.285814+00:00`
- 実装変更: **なし**（調査ハーネスのみ）
- 追跡ケース数: 10
- return_limit 既定: 5

## 問題の分離（要約）

| 種類 | 今回の観測 |
|------|-----------|
| 件数問題 | API生は中央値程度10件。returnは最大5件。真に1件returnは 1件 |
| 内容問題 | return件数>0でも内容あり=[0, 1, 0, 3, 0, 1, 0, 0, 5, 0]。空snippetが多い |
| 関連性問題 | A06等（Python 3.13→Python 3.0）で観測 |
| 選別問題 | unique後→ranking/limitで削減されたケース: 5件（上限5） |
| 受け渡し問題 | live return件数≠LLM受領 のコード上削減: 0件（Agentはraw全件） |
| 利用問題 | snippet空のみのケースは『利用』と扱わない。内容ありでも利用薄い例あり |

## 「検索結果1」の正体

人間向け表示の「検索結果 1」は**リスト番号**であり、件数=1を意味しない。
例: B05は表示で1,2,3と続き、return=3件。
本当に return=1 だった追跡ケース: ['A06']

## ケース表（再取得）

| case | query | API生 | hit化 | unique | ranking後 | return | LLM受領 | 内容あり |
|------|-------|------:|-----:|-------:|---------:|-------:|--------:|---------:|
| B05 | `Python tuple` | 3 | 3 | 3 | 3 | 3 | 3 | 0 |
| C02 | `Ollama` | 18 | 15 | 14 | 3 | 3 | 3 | 1 |
| C03 | `GeForce RTX 3060` | 5 | 5 | 5 | 5 | 5 | 5 | 0 |
| A04 | `NVIDIA` | 21 | 15 | 14 | 5 | 5 | 5 | 3 |
| A06 | `Python 3.13` | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| C04 | `large language model` | 10 | 7 | 6 | 2 | 2 | 2 | 1 |
| P02a | `GeForce RTX 3060` | 5 | 5 | 5 | 5 | 5 | 5 | 0 |
| E02 | `ChatGPT Plus` | 2 | 2 | 2 | 2 | 2 | 2 | 0 |
| WB02 | `Docker (software)` | 14 | 7 | 6 | 5 | 5 | 5 | 5 |
| A03 | `OpenAI` | 10 | 10 | 10 | 5 | 5 | 5 | 0 |

## Q1〜Q10 回答

### Q1 検索APIは実際に何件返しているか？
- 3backend合計の生件数（今回再取得）: min=1, max=21, median≈10
- DDG Instant Answer は Abstract+Related のみ（汎用SERPの10件ではない）
- Wikipedia OpenSearch は最大 fetch_limit=5 タイトル

### Q2 「人間向け1件」はどの段階で1件になったのか？
- **多くは1件になっていない。** 表示ラベル『検索結果 1』の誤解。
- 真に1件return: ['A06']
- 1件化の主因候補は API候補が少ない＋unique後に少数、ではなく内容空のまま複数残る方が多い

### Q3 rankingで1件になっているのか？
- ranking/limit は最大5件に切る。1件強制ではない。
- unique→rankingで減ったケース数: 5
- **『多数→rankingで1件』が主因ではない**（観測上）
- 追加事実: `rank_hits_for_query` は **score>0 の hit だけを優先返却**する。  
  例: C02 は unique後14件だが ranking後**3件**（return_limit=5未満）。  
  → limitだけでなく「クエリ語が title/snippet に無い候補の除外」でも減る。
- それでも主問題は件数より **残った候補の snippet 空**。

### Q4 ranking後は複数なのにLLMへ1件だけか？
- **いいえ（コード根拠）。** Agentは `json.dumps(result)` で hits 全件を渡す。
- live return件数とLLM受領件数の不一致: 0
- ハーネス保存時に backend フィールドは落ちるが件数は保持

### Q5 LLMに渡った結果は内容ありなのか？
- ケース別 内容あり件数: {'B05': 0, 'C02': 1, 'C03': 0, 'A04': 3, 'A06': 0, 'C04': 1, 'P02a': 0, 'E02': 0, 'WB02': 5, 'A03': 0}
- 複数件returnでも内容あり0のケースが存在（件数≠有用性）

### Q6 内容なし結果をLLMが参考にしているか？
- title/urlのみは『検索結果を利用』と扱わない（規則）
- 機械マーカー判定（stored）:
  - B05: 判断不能
  - C02: 明確に検索結果を利用
  - C03: 判断不能
  - A04: 検索結果を利用した可能性が高い
  - A06: 判断不能
  - C04: 検索結果を利用した形跡が薄い
  - P02a: 判断不能
  - E02: 判断不能
  - WB02: 検索結果を利用した可能性が高い
  - A03: 判断不能

### Q7 日本語検索だけ特に弱いのか？

- python_tuple_en: api=3 return=3 content=0 (ja_snip=0, en_snip=0)
- python_tuple_ja: api=0 return=0 content=0 (ja_snip=0, en_snip=0)
- python_tuple_ja_long: api=0 return=0 content=0 (ja_snip=0, en_snip=0)
- rtx_en: api=5 return=5 content=0 (ja_snip=0, en_snip=0)
- rtx_ja: api=1 return=1 content=0 (ja_snip=0, en_snip=0)
- 日本語クエリでも OpenSearch はタイトルを返すことがあるが、**description空は日英共通**。『日本語だから件数0』ではなく『OpenSearch descriptionが空』が共通。

### Q8 どのbackendが主な原因か？
- 今回10ケース再取得の backend 集計:

| backend | 結果数 | snippetあり | snippetなし | error |
|---------|------:|----------:|----------:|------:|
| duckduckgo | 39 | 39 | 0 | 0 |
| wikipedia-ja | 15 | **0** | **15** | 1 |
| wikipedia-en | 35 | **0** | **35** | 0 |

- Wikipedia OpenSearch の description は**今回の再取得では日英ともほぼ空**（内容なし hit の主供給源）。
- DDG は Text を snippet にも入れるため「snippetあり」と数えやすいが、Abstract が無く Related だけのことも多く、**有用な独立本文とは限らない**。
- **単一backend全面故障というより、情報源の性質（Instant Answer / OpenSearch短文）が主因候補。**
- 日本語クエリ比較では件数0もあり得るが、英語でも snippet空は共通。

### Q9 主因の場所はどこか？
優先順位（今回の観測）:
1. **snippet取得（APIが返す短文が空）＋ページ本文未取得** … 内容問題
2. **検索APIの種類（Instant Answer / OpenSearch）** … 情報源が薄い
3. ranking/limit … 件数上限5。1件化の主因ではない
4. LLM受け渡し … 削減していない
5. LLM利用 … 内容がある場合のみ評価対象；空snippetでは判断不能

### Q10 最初に直すべき箇所（提案のみ・未実装）
1. ページ本文/Wikipedia extracts 等の**本文取得段階の追加可否を検証**
2. snippet空 hit の扱い（LLMへ『有用hit』として渡さない等）の設計検討
3. Instant Answer以外の検索ソース要否の検証
4. ranking変更は『有用snippetが下位に落ちている』証拠が出てから

## 確認済み / 疑い / 未確認

### 確認済み
- return_limit=5。rankingは1件強制ではない
- titleのみでもhit化される
- Agent handoffはhits件数を削らない
- 人間表示『検索結果1』は番号表示

### 強く疑われる
- OpenSearch description空が内容なしの主因
- 本文未取得設計

### 未確認
- 本番Agentのtool_call query分布（今回は既存ログqueryを再実行）
- 瞬間的429の再現頻度（実行時刻依存）
