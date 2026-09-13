# Embedding similarity Japanese input noise v0

- run_id: `20260909T145538Z_ruri-small-v2_ja-gold`
- embed_model: `cl-nagoya/ruri-small-v2`
- backend: `ruri-small-v2`
- device: `cpu`
- embedding_method: `mean_pool_last_hidden_state_with_ruri_prefix`
- gen_model: `None`
- with_gen: `False`
- Production / Grill 接続: なし
- 閾値正本化: なし
- SELECTED規則: なし

`gold_is_top` はこの候補集合で意図候補が1位だった観測。SELECTED規則ではない。

## 資源

- baseline: VRAM 3765 / 12288 MiB, RAM used 39795 / 65277 MB
- after_model_load: VRAM 3764 / 12288 MiB, RAM used 39881 / 65277 MB
- after_embed: VRAM 3764 / 12288 MiB, RAM used 40064 / 65277 MB

## ノイズ種別まとめ

- `clean`: gold_top 3/3 mean_rank=1.0 mean_gap=0.115815 mean_delta_vs_clean=None failed=[]
- `typo`: gold_top 2/3 mean_rank=1.333 mean_gap=0.055103 mean_delta_vs_clean=-0.050748 failed=['research_typo']
- `conversion`: gold_top 2/3 mean_rank=1.333 mean_gap=0.036169 mean_delta_vs_clean=-0.081076 failed=['research_conversion']
- `missing_char`: gold_top 3/3 mean_rank=1.0 mean_gap=0.045326 mean_delta_vs_clean=-0.070279 failed=[]
- `particle_drop`: gold_top 3/3 mean_rank=1.0 mean_gap=0.107741 mean_delta_vs_clean=-0.010029 failed=[]
- `colloquial`: gold_top 2/3 mean_rank=1.333 mean_gap=0.051339 mean_delta_vs_clean=-0.047396 failed=['runtime_colloquial']
- `filler`: gold_top 3/3 mean_rank=1.0 mean_gap=0.104396 mean_delta_vs_clean=-0.011165 failed=[]
- `restatement`: gold_top 3/3 mean_rank=1.0 mean_gap=0.067693 mean_delta_vs_clean=-0.027059 failed=[]
- `asr_like`: gold_top 2/3 mean_rank=2.0 mean_gap=0.0391 mean_delta_vs_clean=-0.071372 failed=['research_asr']
- `demonstrative`: gold_top 2/3 mean_rank=1.667 mean_gap=0.052217 mean_delta_vs_clean=-0.063508 failed=['runtime_demonstrative']
- `compound`: gold_top 1/3 mean_rank=1.667 mean_gap=-0.01473 mean_delta_vs_clean=-0.104875 failed=['runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'colloquial', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `runtime_colloquial` [colloquial] 実際に動いてるほう gold_rank=2 gold_cos=0.784885 top=`c_board` 0.831482 delta_vs_clean=-0.142525
- `runtime_demonstrative` [demonstrative] 実際に使ってる方 gold_rank=3 gold_cos=0.766473 top=`c_research` 0.79472 delta_vs_clean=-0.160937
- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=2 gold_cos=0.770417 top=`c_board` 0.856142 delta_vs_clean=-0.156993
- `research_typo` [typo] けんきゅう用のもの gold_rank=2 gold_cos=0.797986 top=`c_board` 0.802349 delta_vs_clean=-0.0965
- `research_conversion` [conversion] 兼休用のもの gold_rank=2 gold_cos=0.762695 top=`c_board` 0.777738 delta_vs_clean=-0.131791
- `research_asr` [asr_like] 兼急用のもの gold_rank=4 gold_cos=0.750439 top=`c_board` 0.787205 delta_vs_clean=-0.144047
- `research_compound` [compound] まあけんきゅう用のも gold_rank=2 gold_cos=0.792163 top=`c_board` 0.802488 delta_vs_clean=-0.102323

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_board` rank=1 cosine=0.866594 gold_is_top=`True` gap_vs_second=0.121503 delta_vs_clean=None

- r1 0.866594 `c_board` ゲームの盤面状態 GOLD
- r2 0.745091 `c_prd` PRDの書き方
- r3 0.743469 `c_score` ハイスコアの保存方法
- r4 0.742095 `c_theme` 画面の配色テーマ
- r5 0.734301 `c_research` 研究用の実験
- r6 0.73337 `c_cpu` CPU温度の取得方法
- r7 0.729174 `c_license` MIT license text for a Python package
- r8 0.728604 `c_weather` 今日の天気と降水確率
- r9 0.725888 `c_runtime` 実行時の実装

### board_typo [typo] テとりすの盤面

gold=`c_board` rank=1 cosine=0.853697 gold_is_top=`True` gap_vs_second=0.10163 delta_vs_clean=-0.012897

- r1 0.853697 `c_board` ゲームの盤面状態 GOLD
- r2 0.752067 `c_prd` PRDの書き方
- r3 0.745804 `c_theme` 画面の配色テーマ
- r4 0.743573 `c_weather` 今日の天気と降水確率
- r5 0.730194 `c_score` ハイスコアの保存方法
- r6 0.728393 `c_research` 研究用の実験
- r7 0.727074 `c_runtime` 実行時の実装
- r8 0.725449 `c_license` MIT license text for a Python package
- r9 0.715209 `c_cpu` CPU温度の取得方法

### board_conversion [conversion] テトリスの番面

gold=`c_board` rank=1 cosine=0.807469 gold_is_top=`True` gap_vs_second=0.062006 delta_vs_clean=-0.059125

- r1 0.807469 `c_board` ゲームの盤面状態 GOLD
- r2 0.745463 `c_prd` PRDの書き方
- r3 0.744012 `c_theme` 画面の配色テーマ
- r4 0.736827 `c_score` ハイスコアの保存方法
- r5 0.735761 `c_research` 研究用の実験
- r6 0.729982 `c_license` MIT license text for a Python package
- r7 0.723177 `c_weather` 今日の天気と降水確率
- r8 0.722378 `c_runtime` 実行時の実装
- r9 0.714512 `c_cpu` CPU温度の取得方法

### board_missing_char [missing_char] テトリスの盤

gold=`c_board` rank=1 cosine=0.827421 gold_is_top=`True` gap_vs_second=0.077521 delta_vs_clean=-0.039173

- r1 0.827421 `c_board` ゲームの盤面状態 GOLD
- r2 0.7499 `c_score` ハイスコアの保存方法
- r3 0.743764 `c_prd` PRDの書き方
- r4 0.736386 `c_license` MIT license text for a Python package
- r5 0.732905 `c_research` 研究用の実験
- r6 0.729949 `c_weather` 今日の天気と降水確率
- r7 0.725233 `c_runtime` 実行時の実装
- r8 0.721136 `c_cpu` CPU温度の取得方法
- r9 0.7199 `c_theme` 画面の配色テーマ

### board_particle [particle_drop] テトリス盤面

gold=`c_board` rank=1 cosine=0.878269 gold_is_top=`True` gap_vs_second=0.120958 delta_vs_clean=0.011675

- r1 0.878269 `c_board` ゲームの盤面状態 GOLD
- r2 0.757311 `c_score` ハイスコアの保存方法
- r3 0.746883 `c_cpu` CPU温度の取得方法
- r4 0.745619 `c_prd` PRDの書き方
- r5 0.744491 `c_theme` 画面の配色テーマ
- r6 0.740376 `c_runtime` 実行時の実装
- r7 0.737923 `c_research` 研究用の実験
- r8 0.734413 `c_license` MIT license text for a Python package
- r9 0.73181 `c_weather` 今日の天気と降水確率

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_board` rank=1 cosine=0.880501 gold_is_top=`True` gap_vs_second=0.110081 delta_vs_clean=0.013907

- r1 0.880501 `c_board` ゲームの盤面状態 GOLD
- r2 0.77042 `c_score` ハイスコアの保存方法
- r3 0.767891 `c_prd` PRDの書き方
- r4 0.758258 `c_theme` 画面の配色テーマ
- r5 0.757579 `c_research` 研究用の実験
- r6 0.756455 `c_license` MIT license text for a Python package
- r7 0.756049 `c_runtime` 実行時の実装
- r8 0.752777 `c_cpu` CPU温度の取得方法
- r9 0.740682 `c_weather` 今日の天気と降水確率

### board_filler [filler] えっとテトリスの盤面

gold=`c_board` rank=1 cosine=0.870653 gold_is_top=`True` gap_vs_second=0.109589 delta_vs_clean=0.004059

- r1 0.870653 `c_board` ゲームの盤面状態 GOLD
- r2 0.761064 `c_theme` 画面の配色テーマ
- r3 0.759241 `c_score` ハイスコアの保存方法
- r4 0.755473 `c_prd` PRDの書き方
- r5 0.741462 `c_license` MIT license text for a Python package
- r6 0.73807 `c_research` 研究用の実験
- r7 0.738064 `c_cpu` CPU温度の取得方法
- r8 0.737209 `c_weather` 今日の天気と降水確率
- r9 0.733772 `c_runtime` 実行時の実装

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_board` rank=1 cosine=0.862806 gold_is_top=`True` gap_vs_second=0.068954 delta_vs_clean=-0.003788

- r1 0.862806 `c_board` ゲームの盤面状態 GOLD
- r2 0.793852 `c_score` ハイスコアの保存方法
- r3 0.758862 `c_prd` PRDの書き方
- r4 0.750948 `c_theme` 画面の配色テーマ
- r5 0.747522 `c_cpu` CPU温度の取得方法
- r6 0.739604 `c_research` 研究用の実験
- r7 0.734105 `c_license` MIT license text for a Python package
- r8 0.731771 `c_runtime` 実行時の実装
- r9 0.724715 `c_weather` 今日の天気と降水確率

### board_asr [asr_like] 手取り巣の盤面

gold=`c_board` rank=1 cosine=0.844847 gold_is_top=`True` gap_vs_second=0.089047 delta_vs_clean=-0.021747

- r1 0.844847 `c_board` ゲームの盤面状態 GOLD
- r2 0.7558 `c_runtime` 実行時の実装
- r3 0.748456 `c_score` ハイスコアの保存方法
- r4 0.743245 `c_prd` PRDの書き方
- r5 0.742684 `c_research` 研究用の実験
- r6 0.739081 `c_weather` 今日の天気と降水確率
- r7 0.738564 `c_cpu` CPU温度の取得方法
- r8 0.736367 `c_theme` 画面の配色テーマ
- r9 0.727903 `c_license` MIT license text for a Python package

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_board` rank=1 cosine=0.863332 gold_is_top=`True` gap_vs_second=0.104106 delta_vs_clean=-0.003262

- r1 0.863332 `c_board` ゲームの盤面状態 GOLD
- r2 0.759226 `c_prd` PRDの書き方
- r3 0.753532 `c_score` ハイスコアの保存方法
- r4 0.753285 `c_weather` 今日の天気と降水確率
- r5 0.751182 `c_theme` 画面の配色テーマ
- r6 0.741515 `c_research` 研究用の実験
- r7 0.740879 `c_runtime` 実行時の実装
- r8 0.734302 `c_license` MIT license text for a Python package
- r9 0.729087 `c_cpu` CPU温度の取得方法

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_board` rank=1 cosine=0.811284 gold_is_top=`True` gap_vs_second=0.051859 delta_vs_clean=-0.05531

- r1 0.811284 `c_board` ゲームの盤面状態 GOLD
- r2 0.759425 `c_theme` 画面の配色テーマ
- r3 0.757338 `c_prd` PRDの書き方
- r4 0.751408 `c_score` ハイスコアの保存方法
- r5 0.748681 `c_research` 研究用の実験
- r6 0.748141 `c_license` MIT license text for a Python package
- r7 0.732024 `c_runtime` 実行時の実装
- r8 0.728879 `c_weather` 今日の天気と降水確率
- r9 0.720073 `c_cpu` CPU温度の取得方法

### runtime_clean [clean] 実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.92741 gold_is_top=`True` gap_vs_second=0.123825 delta_vs_clean=None

- r1 0.92741 `c_runtime` 実行時の実装 GOLD
- r2 0.803585 `c_board` ゲームの盤面状態
- r3 0.77813 `c_cpu` CPU温度の取得方法
- r4 0.774526 `c_research` 研究用の実験
- r5 0.761522 `c_prd` PRDの書き方
- r6 0.752651 `c_theme` 画面の配色テーマ
- r7 0.75228 `c_score` ハイスコアの保存方法
- r8 0.747785 `c_license` MIT license text for a Python package
- r9 0.741768 `c_weather` 今日の天気と降水確率

### runtime_typo [typo] 実交時に動いている実装

gold=`c_runtime` rank=1 cosine=0.884563 gold_is_top=`True` gap_vs_second=0.068042 delta_vs_clean=-0.042847

- r1 0.884563 `c_runtime` 実行時の実装 GOLD
- r2 0.816521 `c_board` ゲームの盤面状態
- r3 0.77998 `c_cpu` CPU温度の取得方法
- r4 0.774737 `c_research` 研究用の実験
- r5 0.757509 `c_prd` PRDの書き方
- r6 0.756013 `c_weather` 今日の天気と降水確率
- r7 0.750667 `c_score` ハイスコアの保存方法
- r8 0.750183 `c_license` MIT license text for a Python package
- r9 0.746451 `c_theme` 画面の配色テーマ

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_runtime` rank=1 cosine=0.875098 gold_is_top=`True` gap_vs_second=0.061544 delta_vs_clean=-0.052312

- r1 0.875098 `c_runtime` 実行時の実装 GOLD
- r2 0.813554 `c_board` ゲームの盤面状態
- r3 0.775161 `c_cpu` CPU温度の取得方法
- r4 0.77252 `c_score` ハイスコアの保存方法
- r5 0.769033 `c_research` 研究用の実験
- r6 0.757701 `c_prd` PRDの書き方
- r7 0.749851 `c_weather` 今日の天気と降水確率
- r8 0.744146 `c_license` MIT license text for a Python package
- r9 0.74177 `c_theme` 画面の配色テーマ

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_runtime` rank=1 cosine=0.84025 gold_is_top=`True` gap_vs_second=0.028851 delta_vs_clean=-0.08716

- r1 0.84025 `c_runtime` 実行時の実装 GOLD
- r2 0.811399 `c_board` ゲームの盤面状態
- r3 0.785063 `c_research` 研究用の実験
- r4 0.767814 `c_weather` 今日の天気と降水確率
- r5 0.764773 `c_prd` PRDの書き方
- r6 0.757994 `c_cpu` CPU温度の取得方法
- r7 0.754733 `c_score` ハイスコアの保存方法
- r8 0.749245 `c_license` MIT license text for a Python package
- r9 0.745563 `c_theme` 画面の配色テーマ

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_runtime` rank=1 cosine=0.923504 gold_is_top=`True` gap_vs_second=0.118771 delta_vs_clean=-0.003906

- r1 0.923504 `c_runtime` 実行時の実装 GOLD
- r2 0.804733 `c_board` ゲームの盤面状態
- r3 0.775194 `c_cpu` CPU温度の取得方法
- r4 0.771773 `c_research` 研究用の実験
- r5 0.756863 `c_prd` PRDの書き方
- r6 0.751461 `c_theme` 画面の配色テーマ
- r7 0.751426 `c_score` ハイスコアの保存方法
- r8 0.746366 `c_license` MIT license text for a Python package
- r9 0.741868 `c_weather` 今日の天気と降水確率

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_runtime` rank=2 cosine=0.784885 gold_is_top=`False` gap_vs_second=-0.046597 delta_vs_clean=-0.142525

- r1 0.831482 `c_board` ゲームの盤面状態
- r2 0.784885 `c_runtime` 実行時の実装 GOLD
- r3 0.776074 `c_research` 研究用の実験
- r4 0.77176 `c_prd` PRDの書き方
- r5 0.761933 `c_cpu` CPU温度の取得方法
- r6 0.75593 `c_score` ハイスコアの保存方法
- r7 0.754768 `c_weather` 今日の天気と降水確率
- r8 0.753002 `c_theme` 画面の配色テーマ
- r9 0.728669 `c_license` MIT license text for a Python package

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_runtime` rank=1 cosine=0.90596 gold_is_top=`True` gap_vs_second=0.108578 delta_vs_clean=-0.02145

- r1 0.90596 `c_runtime` 実行時の実装 GOLD
- r2 0.797382 `c_board` ゲームの盤面状態
- r3 0.769605 `c_research` 研究用の実験
- r4 0.768766 `c_cpu` CPU温度の取得方法
- r5 0.761285 `c_prd` PRDの書き方
- r6 0.754946 `c_theme` 画面の配色テーマ
- r7 0.75227 `c_score` ハイスコアの保存方法
- r8 0.740425 `c_license` MIT license text for a Python package
- r9 0.734653 `c_weather` 今日の天気と降水確率

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.884078 gold_is_top=`True` gap_vs_second=0.058161 delta_vs_clean=-0.043332

- r1 0.884078 `c_runtime` 実行時の実装 GOLD
- r2 0.825917 `c_research` 研究用の実験
- r3 0.784314 `c_board` ゲームの盤面状態
- r4 0.754185 `c_prd` PRDの書き方
- r5 0.752233 `c_cpu` CPU温度の取得方法
- r6 0.748558 `c_license` MIT license text for a Python package
- r7 0.739038 `c_theme` 画面の配色テーマ
- r8 0.730582 `c_score` ハイスコアの保存方法
- r9 0.725302 `c_weather` 今日の天気と降水確率

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_runtime` rank=1 cosine=0.879087 gold_is_top=`True` gap_vs_second=0.06502 delta_vs_clean=-0.048323

- r1 0.879087 `c_runtime` 実行時の実装 GOLD
- r2 0.814067 `c_board` ゲームの盤面状態
- r3 0.783369 `c_cpu` CPU温度の取得方法
- r4 0.776889 `c_score` ハイスコアの保存方法
- r5 0.772827 `c_research` 研究用の実験
- r6 0.766868 `c_prd` PRDの書き方
- r7 0.754497 `c_weather` 今日の天気と降水確率
- r8 0.75219 `c_license` MIT license text for a Python package
- r9 0.748843 `c_theme` 画面の配色テーマ

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_runtime` rank=3 cosine=0.766473 gold_is_top=`False` gap_vs_second=-0.028247 delta_vs_clean=-0.160937

- r1 0.79472 `c_research` 研究用の実験
- r2 0.786568 `c_board` ゲームの盤面状態
- r3 0.766473 `c_runtime` 実行時の実装 GOLD
- r4 0.76009 `c_theme` 画面の配色テーマ
- r5 0.753452 `c_prd` PRDの書き方
- r6 0.752695 `c_weather` 今日の天気と降水確率
- r7 0.751747 `c_score` ハイスコアの保存方法
- r8 0.741073 `c_cpu` CPU温度の取得方法
- r9 0.734611 `c_license` MIT license text for a Python package

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_runtime` rank=2 cosine=0.770417 gold_is_top=`False` gap_vs_second=-0.085725 delta_vs_clean=-0.156993

- r1 0.856142 `c_board` ゲームの盤面状態
- r2 0.770417 `c_runtime` 実行時の実装 GOLD
- r3 0.76965 `c_theme` 画面の配色テーマ
- r4 0.762417 `c_score` ハイスコアの保存方法
- r5 0.749893 `c_research` 研究用の実験
- r6 0.744927 `c_prd` PRDの書き方
- r7 0.74158 `c_cpu` CPU温度の取得方法
- r8 0.73701 `c_license` MIT license text for a Python package
- r9 0.717687 `c_weather` 今日の天気と降水確率

### research_clean [clean] 研究用のもの

gold=`c_research` rank=1 cosine=0.894486 gold_is_top=`True` gap_vs_second=0.102118 delta_vs_clean=None

- r1 0.894486 `c_research` 研究用の実験 GOLD
- r2 0.792368 `c_board` ゲームの盤面状態
- r3 0.782756 `c_prd` PRDの書き方
- r4 0.775069 `c_license` MIT license text for a Python package
- r5 0.771916 `c_score` ハイスコアの保存方法
- r6 0.764654 `c_runtime` 実行時の実装
- r7 0.763466 `c_cpu` CPU温度の取得方法
- r8 0.759159 `c_theme` 画面の配色テーマ
- r9 0.745072 `c_weather` 今日の天気と降水確率

### research_typo [typo] けんきゅう用のもの

gold=`c_research` rank=2 cosine=0.797986 gold_is_top=`False` gap_vs_second=-0.004363 delta_vs_clean=-0.0965

- r1 0.802349 `c_board` ゲームの盤面状態
- r2 0.797986 `c_research` 研究用の実験 GOLD
- r3 0.779573 `c_score` ハイスコアの保存方法
- r4 0.766358 `c_prd` PRDの書き方
- r5 0.762446 `c_cpu` CPU温度の取得方法
- r6 0.751528 `c_license` MIT license text for a Python package
- r7 0.744441 `c_runtime` 実行時の実装
- r8 0.729887 `c_weather` 今日の天気と降水確率
- r9 0.729839 `c_theme` 画面の配色テーマ

### research_conversion [conversion] 兼休用のもの

gold=`c_research` rank=2 cosine=0.762695 gold_is_top=`False` gap_vs_second=-0.015043 delta_vs_clean=-0.131791

- r1 0.777738 `c_board` ゲームの盤面状態
- r2 0.762695 `c_research` 研究用の実験 GOLD
- r3 0.754997 `c_runtime` 実行時の実装
- r4 0.74941 `c_score` ハイスコアの保存方法
- r5 0.748095 `c_prd` PRDの書き方
- r6 0.747079 `c_weather` 今日の天気と降水確率
- r7 0.742069 `c_license` MIT license text for a Python package
- r8 0.741867 `c_theme` 画面の配色テーマ
- r9 0.733474 `c_cpu` CPU温度の取得方法

### research_missing_char [missing_char] 究用のもの

gold=`c_research` rank=1 cosine=0.809982 gold_is_top=`True` gap_vs_second=0.029605 delta_vs_clean=-0.084504

- r1 0.809982 `c_research` 研究用の実験 GOLD
- r2 0.780377 `c_board` ゲームの盤面状態
- r3 0.774014 `c_score` ハイスコアの保存方法
- r4 0.768378 `c_prd` PRDの書き方
- r5 0.759646 `c_theme` 画面の配色テーマ
- r6 0.758804 `c_license` MIT license text for a Python package
- r7 0.752127 `c_cpu` CPU温度の取得方法
- r8 0.743732 `c_runtime` 実行時の実装
- r9 0.729919 `c_weather` 今日の天気と降水確率

### research_particle [particle_drop] 研究用もの

gold=`c_research` rank=1 cosine=0.856631 gold_is_top=`True` gap_vs_second=0.083495 delta_vs_clean=-0.037855

- r1 0.856631 `c_research` 研究用の実験 GOLD
- r2 0.773136 `c_board` ゲームの盤面状態
- r3 0.769775 `c_license` MIT license text for a Python package
- r4 0.767621 `c_prd` PRDの書き方
- r5 0.759973 `c_runtime` 実行時の実装
- r6 0.75394 `c_theme` 画面の配色テーマ
- r7 0.753759 `c_score` ハイスコアの保存方法
- r8 0.749827 `c_cpu` CPU温度の取得方法
- r9 0.729438 `c_weather` 今日の天気と降水確率

### research_colloquial [colloquial] 研究用のやつ

gold=`c_research` rank=1 cosine=0.880915 gold_is_top=`True` gap_vs_second=0.090534 delta_vs_clean=-0.013571

- r1 0.880915 `c_research` 研究用の実験 GOLD
- r2 0.790381 `c_board` ゲームの盤面状態
- r3 0.789935 `c_prd` PRDの書き方
- r4 0.786431 `c_license` MIT license text for a Python package
- r5 0.778955 `c_score` ハイスコアの保存方法
- r6 0.765242 `c_runtime` 実行時の実装
- r7 0.762527 `c_cpu` CPU温度の取得方法
- r8 0.754032 `c_theme` 画面の配色テーマ
- r9 0.743251 `c_weather` 今日の天気と降水確率

### research_filler [filler] まあ研究用のものかな

gold=`c_research` rank=1 cosine=0.878382 gold_is_top=`True` gap_vs_second=0.095022 delta_vs_clean=-0.016104

- r1 0.878382 `c_research` 研究用の実験 GOLD
- r2 0.78336 `c_board` ゲームの盤面状態
- r3 0.755456 `c_score` ハイスコアの保存方法
- r4 0.751284 `c_license` MIT license text for a Python package
- r5 0.750364 `c_runtime` 実行時の実装
- r6 0.750124 `c_prd` PRDの書き方
- r7 0.741279 `c_theme` 画面の配色テーマ
- r8 0.741052 `c_cpu` CPU温度の取得方法
- r9 0.732499 `c_weather` 今日の天気と降水確率

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_research` rank=1 cosine=0.860429 gold_is_top=`True` gap_vs_second=0.075964 delta_vs_clean=-0.034057

- r1 0.860429 `c_research` 研究用の実験 GOLD
- r2 0.784465 `c_board` ゲームの盤面状態
- r3 0.769424 `c_prd` PRDの書き方
- r4 0.756815 `c_score` ハイスコアの保存方法
- r5 0.754015 `c_runtime` 実行時の実装
- r6 0.74986 `c_license` MIT license text for a Python package
- r7 0.739586 `c_theme` 画面の配色テーマ
- r8 0.731107 `c_cpu` CPU温度の取得方法
- r9 0.7293 `c_weather` 今日の天気と降水確率

### research_asr [asr_like] 兼急用のもの

gold=`c_research` rank=4 cosine=0.750439 gold_is_top=`False` gap_vs_second=-0.036766 delta_vs_clean=-0.144047

- r1 0.787205 `c_board` ゲームの盤面状態
- r2 0.752413 `c_score` ハイスコアの保存方法
- r3 0.75142 `c_runtime` 実行時の実装
- r4 0.750439 `c_research` 研究用の実験 GOLD
- r5 0.746505 `c_prd` PRDの書き方
- r6 0.742101 `c_weather` 今日の天気と降水確率
- r7 0.73983 `c_theme` 画面の配色テーマ
- r8 0.73501 `c_license` MIT license text for a Python package
- r9 0.72431 `c_cpu` CPU温度の取得方法

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_research` rank=1 cosine=0.868161 gold_is_top=`True` gap_vs_second=0.080792 delta_vs_clean=-0.026325

- r1 0.868161 `c_research` 研究用の実験 GOLD
- r2 0.787369 `c_prd` PRDの書き方
- r3 0.777492 `c_board` ゲームの盤面状態
- r4 0.773576 `c_license` MIT license text for a Python package
- r5 0.765993 `c_score` ハイスコアの保存方法
- r6 0.760737 `c_runtime` 実行時の実装
- r7 0.758557 `c_cpu` CPU温度の取得方法
- r8 0.743308 `c_theme` 画面の配色テーマ
- r9 0.733137 `c_weather` 今日の天気と降水確率

### research_compound [compound] まあけんきゅう用のも

gold=`c_research` rank=2 cosine=0.792163 gold_is_top=`False` gap_vs_second=-0.010325 delta_vs_clean=-0.102323

- r1 0.802488 `c_board` ゲームの盤面状態
- r2 0.792163 `c_research` 研究用の実験 GOLD
- r3 0.782877 `c_score` ハイスコアの保存方法
- r4 0.766907 `c_cpu` CPU温度の取得方法
- r5 0.766732 `c_prd` PRDの書き方
- r6 0.762388 `c_license` MIT license text for a Python package
- r7 0.758796 `c_runtime` 実行時の実装
- r8 0.745071 `c_theme` 画面の配色テーマ
- r9 0.737781 `c_weather` 今日の天気と降水確率
