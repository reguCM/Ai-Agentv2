# v0 収集完了報告（50件目標・人間向け）

**status:** 観測フェーズ完了（判断ロジック未変更）  
**results:** `results/run_v0_50/`  
**summary JSON:** `analysis/human_summary_run_v0_50.json`

## 実施内容

1. Web検索単体スモーク（`analysis/web_search_foundation_smoke.json`）
2. 意図的ケース50件設計（`cases.json`）— 正解ラベルなし
3. PROJECT_AGENT 全件実行（Stage1/2ログ）
4. 人間向け集計（`summarize_run.py`）

禁止事項（接続・Gate迂回・heuristic改変・Stage3/4）は遵守。

## 収集結果サマリ（50件・H02再実行後）

全ケース Stage1/2 ログあり（H02は初回TypeError後に再実行して埋めた）。

### route（heuristic_v1・正解ではない）

| route | 件数 |
|-------|-----:|
| uncertain | 39 |
| agent_continue | 10 |
| needs_new_tool | 1 |

大半が `uncertain`（related一致が弱いとここに落ちる）。

### Web判断 × 実行（最重要のズレ表）

| | called | not_called |
|--|-------:|----------:|
| judged_yes | 3 | 5 |
| judged_no | **29** | 13 |

**最大パターン: 「Web不要と判断したが実際には search_web を呼んだ」（29件）。**  
`web_pattern` でも `web_not_judged_but_called` が最多。

judged_yes かつ called はわずか3件。検索 outcome は多くが `error`（基礎スモークと一致：時事系はhitsしにくい）。

### 言い換えグループ

- `para_osaka_weather` (P01a/b/c): いずれも judged_web=false / called=true / pattern同一
- `para_rtx3060` (P02a/b): 同上

このグループ内では表現差による大変化は見えていない（サンプル小）。

### Tool不足候補

`needs_new_tool` はごく少数（1件程度）。多くは uncertain。**正誤判定はしていない。**

### 検索成功傾向

- Stage2 pattern に `hits` 成功連鎖はほぼ無し
- `error` / 未呼び出し / judged_no+called が中心
- **判断観測には十分。検索品質改善（F-002）とは別問題として保持**

## 追加収集が必要そうな種別（提案）

1. judged_yes+called+hits が取れるクエリ（英語・安定トピック）を意図的に少数追加し、判断と検索成功を分離して見る
2. H02 再実行で composite ログを埋める
3. Web語なし（E）と Web語あり不要（D）のズレをカテゴリ別に切り出す表
4. 100件化は急がず、まず上記ズレの再現性確認

## 人間への判断依頼（次ステップ）

この時点で止めています。次はどれにしますか。

- A: 現状49〜50件で傾向メモを深掘り（Stage3分類軸の草案のみ、実装なし）
- B: 不足カテゴリを足して〜100件まで収集継続
- C: H02再実行＋英語hits系の小追加のみ
- D: まだ収集を続け、判断ロジックは触らない

**Stage3自動ラベル / Stage4 heuristic・LLM改善は、承認後まで開始しない。**
