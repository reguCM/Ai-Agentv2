# Embedding similarity Japanese input noise v0

- run_id: `20260909T145541Z_llm-jp-3-150m_ja-gold`
- embed_model: `llm-jp/llm-jp-3-150m`
- backend: `llm-jp-3-150m`
- device: `cpu`
- embedding_method: `mean_pool_last_hidden_state`
- gen_model: `None`
- with_gen: `False`
- Production / Grill 接続: なし
- 閾値正本化: なし
- SELECTED規則: なし

`gold_is_top` はこの候補集合で意図候補が1位だった観測。SELECTED規則ではない。

## 資源

- baseline: VRAM 3764 / 12288 MiB, RAM used 39906 / 65277 MB
- after_model_load: VRAM 3763 / 12288 MiB, RAM used 40369 / 65277 MB
- after_embed: VRAM 3763 / 12288 MiB, RAM used 40351 / 65277 MB

## ノイズ種別まとめ

- `clean`: gold_top 3/3 mean_rank=1.0 mean_gap=0.140687 mean_delta_vs_clean=None failed=[]
- `typo`: gold_top 2/3 mean_rank=2.333 mean_gap=0.019323 mean_delta_vs_clean=-0.163409 failed=['research_typo']
- `conversion`: gold_top 2/3 mean_rank=2.0 mean_gap=0.037235 mean_delta_vs_clean=-0.126366 failed=['research_conversion']
- `missing_char`: gold_top 3/3 mean_rank=1.0 mean_gap=0.077936 mean_delta_vs_clean=-0.05111 failed=[]
- `particle_drop`: gold_top 3/3 mean_rank=1.0 mean_gap=0.108058 mean_delta_vs_clean=-0.042509 failed=[]
- `colloquial`: gold_top 3/3 mean_rank=1.0 mean_gap=0.109647 mean_delta_vs_clean=-0.04075 failed=[]
- `filler`: gold_top 2/3 mean_rank=1.667 mean_gap=0.035518 mean_delta_vs_clean=-0.114696 failed=['research_filler']
- `restatement`: gold_top 2/3 mean_rank=1.667 mean_gap=0.021736 mean_delta_vs_clean=-0.1054 failed=['research_restatement']
- `asr_like`: gold_top 2/3 mean_rank=2.0 mean_gap=0.047367 mean_delta_vs_clean=-0.151626 failed=['research_asr']
- `demonstrative`: gold_top 3/3 mean_rank=1.0 mean_gap=0.116701 mean_delta_vs_clean=-0.065102 failed=[]
- `compound`: gold_top 1/3 mean_rank=2.333 mean_gap=-0.026904 mean_delta_vs_clean=-0.197732 failed=['runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'filler', 'restatement', 'asr_like', 'compound']

## 失敗ケース

- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=2 gold_cos=0.738341 top=`c_board` 0.789676 delta_vs_clean=-0.215818
- `research_typo` [typo] けんきゅう用のもの gold_rank=5 gold_cos=0.554709 top=`c_board` 0.688094 delta_vs_clean=-0.344615
- `research_conversion` [conversion] 兼休用のもの gold_rank=4 gold_cos=0.658339 top=`c_board` 0.723772 delta_vs_clean=-0.240985
- `research_filler` [filler] まあ研究用のものかな gold_rank=3 gold_cos=0.747341 top=`c_runtime` 0.797819 delta_vs_clean=-0.151983
- `research_restatement` [restatement] 本番じゃなくて研究用のもの gold_rank=3 gold_cos=0.748311 top=`c_board` 0.800593 delta_vs_clean=-0.151013
- `research_asr` [asr_like] 兼急用のもの gold_rank=4 gold_cos=0.653201 top=`c_board` 0.713404 delta_vs_clean=-0.246123
- `research_compound` [compound] まあけんきゅう用のも gold_rank=4 gold_cos=0.628834 top=`c_board` 0.760426 delta_vs_clean=-0.27049

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_board` rank=1 cosine=0.903262 gold_is_top=`True` gap_vs_second=0.102611 delta_vs_clean=None

- r1 0.903262 `c_board` ゲームの盤面状態 GOLD
- r2 0.800651 `c_score` ハイスコアの保存方法
- r3 0.719029 `c_theme` 画面の配色テーマ
- r4 0.640068 `c_runtime` 実行時の実装
- r5 0.603474 `c_weather` 今日の天気と降水確率
- r6 0.590837 `c_research` 研究用の実験
- r7 0.367776 `c_cpu` CPU温度の取得方法
- r8 0.317524 `c_prd` PRDの書き方
- r9 -0.333529 `c_license` MIT license text for a Python package

### board_typo [typo] テとりすの盤面

gold=`c_board` rank=1 cosine=0.840688 gold_is_top=`True` gap_vs_second=0.098696 delta_vs_clean=-0.062574

- r1 0.840688 `c_board` ゲームの盤面状態 GOLD
- r2 0.741992 `c_score` ハイスコアの保存方法
- r3 0.710782 `c_theme` 画面の配色テーマ
- r4 0.655575 `c_weather` 今日の天気と降水確率
- r5 0.622044 `c_runtime` 実行時の実装
- r6 0.597621 `c_research` 研究用の実験
- r7 0.35945 `c_cpu` CPU温度の取得方法
- r8 0.320157 `c_prd` PRDの書き方
- r9 -0.368478 `c_license` MIT license text for a Python package

### board_conversion [conversion] テトリスの番面

gold=`c_board` rank=1 cosine=0.851691 gold_is_top=`True` gap_vs_second=0.072699 delta_vs_clean=-0.051571

- r1 0.851691 `c_board` ゲームの盤面状態 GOLD
- r2 0.778992 `c_score` ハイスコアの保存方法
- r3 0.658553 `c_theme` 画面の配色テーマ
- r4 0.617236 `c_runtime` 実行時の実装
- r5 0.586898 `c_weather` 今日の天気と降水確率
- r6 0.560324 `c_research` 研究用の実験
- r7 0.314182 `c_cpu` CPU温度の取得方法
- r8 0.289244 `c_prd` PRDの書き方
- r9 -0.31105 `c_license` MIT license text for a Python package

### board_missing_char [missing_char] テトリスの盤

gold=`c_board` rank=1 cosine=0.871401 gold_is_top=`True` gap_vs_second=0.085836 delta_vs_clean=-0.031861

- r1 0.871401 `c_board` ゲームの盤面状態 GOLD
- r2 0.785565 `c_score` ハイスコアの保存方法
- r3 0.669677 `c_theme` 画面の配色テーマ
- r4 0.658486 `c_runtime` 実行時の実装
- r5 0.603311 `c_research` 研究用の実験
- r6 0.594256 `c_weather` 今日の天気と降水確率
- r7 0.350621 `c_cpu` CPU温度の取得方法
- r8 0.337749 `c_prd` PRDの書き方
- r9 -0.303359 `c_license` MIT license text for a Python package

### board_particle [particle_drop] テトリス盤面

gold=`c_board` rank=1 cosine=0.828045 gold_is_top=`True` gap_vs_second=0.023354 delta_vs_clean=-0.075217

- r1 0.828045 `c_board` ゲームの盤面状態 GOLD
- r2 0.804691 `c_score` ハイスコアの保存方法
- r3 0.720366 `c_theme` 画面の配色テーマ
- r4 0.523983 `c_weather` 今日の天気と降水確率
- r5 0.504352 `c_research` 研究用の実験
- r6 0.503729 `c_runtime` 実行時の実装
- r7 0.405955 `c_cpu` CPU温度の取得方法
- r8 0.335203 `c_prd` PRDの書き方
- r9 -0.227691 `c_license` MIT license text for a Python package

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_board` rank=1 cosine=0.902267 gold_is_top=`True` gap_vs_second=0.108822 delta_vs_clean=-0.000995

- r1 0.902267 `c_board` ゲームの盤面状態 GOLD
- r2 0.793445 `c_score` ハイスコアの保存方法
- r3 0.726657 `c_theme` 画面の配色テーマ
- r4 0.632273 `c_runtime` 実行時の実装
- r5 0.61021 `c_weather` 今日の天気と降水確率
- r6 0.583691 `c_research` 研究用の実験
- r7 0.353554 `c_cpu` CPU温度の取得方法
- r8 0.274395 `c_prd` PRDの書き方
- r9 -0.379052 `c_license` MIT license text for a Python package

### board_filler [filler] えっとテトリスの盤面

gold=`c_board` rank=1 cosine=0.830276 gold_is_top=`True` gap_vs_second=0.117624 delta_vs_clean=-0.072986

- r1 0.830276 `c_board` ゲームの盤面状態 GOLD
- r2 0.712652 `c_runtime` 実行時の実装
- r3 0.709855 `c_score` ハイスコアの保存方法
- r4 0.647795 `c_theme` 画面の配色テーマ
- r5 0.618989 `c_research` 研究用の実験
- r6 0.618539 `c_weather` 今日の天気と降水確率
- r7 0.358683 `c_cpu` CPU温度の取得方法
- r8 0.35719 `c_prd` PRDの書き方
- r9 -0.270927 `c_license` MIT license text for a Python package

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_board` rank=1 cosine=0.869459 gold_is_top=`True` gap_vs_second=0.095299 delta_vs_clean=-0.033803

- r1 0.869459 `c_board` ゲームの盤面状態 GOLD
- r2 0.77416 `c_score` ハイスコアの保存方法
- r3 0.727235 `c_runtime` 実行時の実装
- r4 0.666637 `c_theme` 画面の配色テーマ
- r5 0.635737 `c_research` 研究用の実験
- r6 0.601029 `c_weather` 今日の天気と降水確率
- r7 0.388559 `c_cpu` CPU温度の取得方法
- r8 0.379792 `c_prd` PRDの書き方
- r9 -0.301759 `c_license` MIT license text for a Python package

### board_asr [asr_like] 手取り巣の盤面

gold=`c_board` rank=1 cosine=0.789307 gold_is_top=`True` gap_vs_second=0.091184 delta_vs_clean=-0.113955

- r1 0.789307 `c_board` ゲームの盤面状態 GOLD
- r2 0.698123 `c_theme` 画面の配色テーマ
- r3 0.660603 `c_score` ハイスコアの保存方法
- r4 0.637141 `c_runtime` 実行時の実装
- r5 0.629918 `c_weather` 今日の天気と降水確率
- r6 0.613754 `c_research` 研究用の実験
- r7 0.45087 `c_cpu` CPU温度の取得方法
- r8 0.344126 `c_prd` PRDの書き方
- r9 -0.347666 `c_license` MIT license text for a Python package

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_board` rank=1 cosine=0.842153 gold_is_top=`True` gap_vs_second=0.112081 delta_vs_clean=-0.061109

- r1 0.842153 `c_board` ゲームの盤面状態 GOLD
- r2 0.730072 `c_runtime` 実行時の実装
- r3 0.684882 `c_score` ハイスコアの保存方法
- r4 0.671389 `c_theme` 画面の配色テーマ
- r5 0.655809 `c_weather` 今日の天気と降水確率
- r6 0.641793 `c_research` 研究用の実験
- r7 0.380147 `c_prd` PRDの書き方
- r8 0.369786 `c_cpu` CPU温度の取得方法
- r9 -0.317213 `c_license` MIT license text for a Python package

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_board` rank=1 cosine=0.796374 gold_is_top=`True` gap_vs_second=0.102215 delta_vs_clean=-0.106888

- r1 0.796374 `c_board` ゲームの盤面状態 GOLD
- r2 0.694159 `c_score` ハイスコアの保存方法
- r3 0.672776 `c_runtime` 実行時の実装
- r4 0.621848 `c_theme` 画面の配色テーマ
- r5 0.604319 `c_weather` 今日の天気と降水確率
- r6 0.581254 `c_research` 研究用の実験
- r7 0.310217 `c_cpu` CPU温度の取得方法
- r8 0.298603 `c_prd` PRDの書き方
- r9 -0.291297 `c_license` MIT license text for a Python package

### runtime_clean [clean] 実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.954159 gold_is_top=`True` gap_vs_second=0.145452 delta_vs_clean=None

- r1 0.954159 `c_runtime` 実行時の実装 GOLD
- r2 0.808707 `c_research` 研究用の実験
- r3 0.764836 `c_board` ゲームの盤面状態
- r4 0.684644 `c_theme` 画面の配色テーマ
- r5 0.644916 `c_score` ハイスコアの保存方法
- r6 0.616962 `c_cpu` CPU温度の取得方法
- r7 0.613895 `c_prd` PRDの書き方
- r8 0.569297 `c_weather` 今日の天気と降水確率
- r9 -0.068574 `c_license` MIT license text for a Python package

### runtime_typo [typo] 実交時に動いている実装

gold=`c_runtime` rank=1 cosine=0.87112 gold_is_top=`True` gap_vs_second=0.092659 delta_vs_clean=-0.083039

- r1 0.87112 `c_runtime` 実行時の実装 GOLD
- r2 0.778461 `c_research` 研究用の実験
- r3 0.709684 `c_board` ゲームの盤面状態
- r4 0.590405 `c_theme` 画面の配色テーマ
- r5 0.578276 `c_weather` 今日の天気と降水確率
- r6 0.556451 `c_score` ハイスコアの保存方法
- r7 0.501838 `c_prd` PRDの書き方
- r8 0.484854 `c_cpu` CPU温度の取得方法
- r9 -0.17802 `c_license` MIT license text for a Python package

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_runtime` rank=1 cosine=0.867617 gold_is_top=`True` gap_vs_second=0.104439 delta_vs_clean=-0.086542

- r1 0.867617 `c_runtime` 実行時の実装 GOLD
- r2 0.763178 `c_research` 研究用の実験
- r3 0.734661 `c_board` ゲームの盤面状態
- r4 0.592028 `c_theme` 画面の配色テーマ
- r5 0.590858 `c_score` ハイスコアの保存方法
- r6 0.58941 `c_weather` 今日の天気と降水確率
- r7 0.488124 `c_prd` PRDの書き方
- r8 0.478045 `c_cpu` CPU温度の取得方法
- r9 -0.211539 `c_license` MIT license text for a Python package

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_runtime` rank=1 cosine=0.933244 gold_is_top=`True` gap_vs_second=0.132164 delta_vs_clean=-0.020915

- r1 0.933244 `c_runtime` 実行時の実装 GOLD
- r2 0.80108 `c_research` 研究用の実験
- r3 0.743368 `c_board` ゲームの盤面状態
- r4 0.650253 `c_theme` 画面の配色テーマ
- r5 0.622921 `c_score` ハイスコアの保存方法
- r6 0.59124 `c_prd` PRDの書き方
- r7 0.583659 `c_weather` 今日の天気と降水確率
- r8 0.579266 `c_cpu` CPU温度の取得方法
- r9 -0.089065 `c_license` MIT license text for a Python package

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_runtime` rank=1 cosine=0.905686 gold_is_top=`True` gap_vs_second=0.113392 delta_vs_clean=-0.048473

- r1 0.905686 `c_runtime` 実行時の実装 GOLD
- r2 0.792294 `c_research` 研究用の実験
- r3 0.773983 `c_board` ゲームの盤面状態
- r4 0.73139 `c_theme` 画面の配色テーマ
- r5 0.655057 `c_score` ハイスコアの保存方法
- r6 0.626321 `c_cpu` CPU温度の取得方法
- r7 0.586774 `c_weather` 今日の天気と降水確率
- r8 0.585745 `c_prd` PRDの書き方
- r9 -0.126611 `c_license` MIT license text for a Python package

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_runtime` rank=1 cosine=0.795537 gold_is_top=`True` gap_vs_second=0.101611 delta_vs_clean=-0.158622

- r1 0.795537 `c_runtime` 実行時の実装 GOLD
- r2 0.693926 `c_research` 研究用の実験
- r3 0.662702 `c_board` ゲームの盤面状態
- r4 0.587865 `c_weather` 今日の天気と降水確率
- r5 0.534975 `c_score` ハイスコアの保存方法
- r6 0.498067 `c_theme` 画面の配色テーマ
- r7 0.470056 `c_prd` PRDの書き方
- r8 0.382577 `c_cpu` CPU温度の取得方法
- r9 -0.188349 `c_license` MIT license text for a Python package

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_runtime` rank=1 cosine=0.835041 gold_is_top=`True` gap_vs_second=0.039407 delta_vs_clean=-0.119118

- r1 0.835041 `c_runtime` 実行時の実装 GOLD
- r2 0.795634 `c_board` ゲームの盤面状態
- r3 0.703998 `c_research` 研究用の実験
- r4 0.673913 `c_score` ハイスコアの保存方法
- r5 0.628175 `c_theme` 画面の配色テーマ
- r6 0.623124 `c_weather` 今日の天気と降水確率
- r7 0.435056 `c_prd` PRDの書き方
- r8 0.406389 `c_cpu` CPU温度の取得方法
- r9 -0.24102 `c_license` MIT license text for a Python package

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.822775 gold_is_top=`True` gap_vs_second=0.02219 delta_vs_clean=-0.131384

- r1 0.822775 `c_runtime` 実行時の実装 GOLD
- r2 0.800585 `c_research` 研究用の実験
- r3 0.728289 `c_board` ゲームの盤面状態
- r4 0.592347 `c_score` ハイスコアの保存方法
- r5 0.583484 `c_theme` 画面の配色テーマ
- r6 0.545764 `c_weather` 今日の天気と降水確率
- r7 0.495961 `c_cpu` CPU温度の取得方法
- r8 0.461667 `c_prd` PRDの書き方
- r9 -0.210358 `c_license` MIT license text for a Python package

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_runtime` rank=1 cosine=0.859359 gold_is_top=`True` gap_vs_second=0.111121 delta_vs_clean=-0.0948

- r1 0.859359 `c_runtime` 実行時の実装 GOLD
- r2 0.748238 `c_research` 研究用の実験
- r3 0.737798 `c_board` ゲームの盤面状態
- r4 0.592042 `c_score` ハイスコアの保存方法
- r5 0.591191 `c_weather` 今日の天気と降水確率
- r6 0.582524 `c_theme` 画面の配色テーマ
- r7 0.474274 `c_prd` PRDの書き方
- r8 0.459389 `c_cpu` CPU温度の取得方法
- r9 -0.218247 `c_license` MIT license text for a Python package

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_runtime` rank=1 cosine=0.796791 gold_is_top=`True` gap_vs_second=0.098924 delta_vs_clean=-0.157368

- r1 0.796791 `c_runtime` 実行時の実装 GOLD
- r2 0.697867 `c_research` 研究用の実験
- r3 0.696794 `c_board` ゲームの盤面状態
- r4 0.618561 `c_weather` 今日の天気と降水確率
- r5 0.593035 `c_score` ハイスコアの保存方法
- r6 0.546195 `c_theme` 画面の配色テーマ
- r7 0.483339 `c_prd` PRDの書き方
- r8 0.395829 `c_cpu` CPU温度の取得方法
- r9 -0.196069 `c_license` MIT license text for a Python package

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_runtime` rank=2 cosine=0.738341 gold_is_top=`False` gap_vs_second=-0.051335 delta_vs_clean=-0.215818

- r1 0.789676 `c_board` ゲームの盤面状態
- r2 0.738341 `c_runtime` 実行時の実装 GOLD
- r3 0.666091 `c_score` ハイスコアの保存方法
- r4 0.642049 `c_research` 研究用の実験
- r5 0.605427 `c_weather` 今日の天気と降水確率
- r6 0.548601 `c_theme` 画面の配色テーマ
- r7 0.363388 `c_prd` PRDの書き方
- r8 0.296102 `c_cpu` CPU温度の取得方法
- r9 -0.28496 `c_license` MIT license text for a Python package

### research_clean [clean] 研究用のもの

gold=`c_research` rank=1 cosine=0.899324 gold_is_top=`True` gap_vs_second=0.173997 delta_vs_clean=None

- r1 0.899324 `c_research` 研究用の実験 GOLD
- r2 0.725327 `c_runtime` 実行時の実装
- r3 0.666528 `c_theme` 画面の配色テーマ
- r4 0.655617 `c_board` ゲームの盤面状態
- r5 0.625677 `c_cpu` CPU温度の取得方法
- r6 0.609269 `c_prd` PRDの書き方
- r7 0.545182 `c_score` ハイスコアの保存方法
- r8 0.500975 `c_weather` 今日の天気と降水確率
- r9 -0.014717 `c_license` MIT license text for a Python package

### research_typo [typo] けんきゅう用のもの

gold=`c_research` rank=5 cosine=0.554709 gold_is_top=`False` gap_vs_second=-0.133385 delta_vs_clean=-0.344615

- r1 0.688094 `c_board` ゲームの盤面状態
- r2 0.581888 `c_theme` 画面の配色テーマ
- r3 0.578924 `c_weather` 今日の天気と降水確率
- r4 0.560055 `c_score` ハイスコアの保存方法
- r5 0.554709 `c_research` 研究用の実験 GOLD
- r6 0.541289 `c_runtime` 実行時の実装
- r7 0.375143 `c_cpu` CPU温度の取得方法
- r8 0.342836 `c_prd` PRDの書き方
- r9 -0.229528 `c_license` MIT license text for a Python package

### research_conversion [conversion] 兼休用のもの

gold=`c_research` rank=4 cosine=0.658339 gold_is_top=`False` gap_vs_second=-0.065433 delta_vs_clean=-0.240985

- r1 0.723772 `c_board` ゲームの盤面状態
- r2 0.684611 `c_theme` 画面の配色テーマ
- r3 0.674213 `c_runtime` 実行時の実装
- r4 0.658339 `c_research` 研究用の実験 GOLD
- r5 0.652805 `c_score` ハイスコアの保存方法
- r6 0.604002 `c_weather` 今日の天気と降水確率
- r7 0.486572 `c_prd` PRDの書き方
- r8 0.484445 `c_cpu` CPU温度の取得方法
- r9 -0.184476 `c_license` MIT license text for a Python package

### research_missing_char [missing_char] 究用のもの

gold=`c_research` rank=1 cosine=0.798769 gold_is_top=`True` gap_vs_second=0.015809 delta_vs_clean=-0.100555

- r1 0.798769 `c_research` 研究用の実験 GOLD
- r2 0.78296 `c_runtime` 実行時の実装
- r3 0.668015 `c_board` ゲームの盤面状態
- r4 0.619166 `c_theme` 画面の配色テーマ
- r5 0.603686 `c_prd` PRDの書き方
- r6 0.584904 `c_cpu` CPU温度の取得方法
- r7 0.560919 `c_weather` 今日の天気と降水確率
- r8 0.522316 `c_score` ハイスコアの保存方法
- r9 -0.057361 `c_license` MIT license text for a Python package

### research_particle [particle_drop] 研究用もの

gold=`c_research` rank=1 cosine=0.895487 gold_is_top=`True` gap_vs_second=0.187427 delta_vs_clean=-0.003837

- r1 0.895487 `c_research` 研究用の実験 GOLD
- r2 0.70806 `c_runtime` 実行時の実装
- r3 0.662208 `c_theme` 画面の配色テーマ
- r4 0.661058 `c_board` ゲームの盤面状態
- r5 0.600416 `c_cpu` CPU温度の取得方法
- r6 0.586555 `c_prd` PRDの書き方
- r7 0.552192 `c_score` ハイスコアの保存方法
- r8 0.504577 `c_weather` 今日の天気と降水確率
- r9 -0.038391 `c_license` MIT license text for a Python package

### research_colloquial [colloquial] 研究用のやつ

gold=`c_research` rank=1 cosine=0.936692 gold_is_top=`True` gap_vs_second=0.118509 delta_vs_clean=0.037368

- r1 0.936692 `c_research` 研究用の実験 GOLD
- r2 0.818183 `c_runtime` 実行時の実装
- r3 0.754254 `c_board` ゲームの盤面状態
- r4 0.707449 `c_theme` 画面の配色テーマ
- r5 0.639012 `c_score` ハイスコアの保存方法
- r6 0.615565 `c_prd` PRDの書き方
- r7 0.606518 `c_cpu` CPU温度の取得方法
- r8 0.593343 `c_weather` 今日の天気と降水確率
- r9 -0.066657 `c_license` MIT license text for a Python package

### research_filler [filler] まあ研究用のものかな

gold=`c_research` rank=3 cosine=0.747341 gold_is_top=`False` gap_vs_second=-0.050478 delta_vs_clean=-0.151983

- r1 0.797819 `c_runtime` 実行時の実装
- r2 0.76622 `c_board` ゲームの盤面状態
- r3 0.747341 `c_research` 研究用の実験 GOLD
- r4 0.623639 `c_score` ハイスコアの保存方法
- r5 0.607732 `c_weather` 今日の天気と降水確率
- r6 0.581686 `c_theme` 画面の配色テーマ
- r7 0.426077 `c_prd` PRDの書き方
- r8 0.393983 `c_cpu` CPU温度の取得方法
- r9 -0.234389 `c_license` MIT license text for a Python package

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_research` rank=3 cosine=0.748311 gold_is_top=`False` gap_vs_second=-0.052282 delta_vs_clean=-0.151013

- r1 0.800593 `c_board` ゲームの盤面状態
- r2 0.790055 `c_runtime` 実行時の実装
- r3 0.748311 `c_research` 研究用の実験 GOLD
- r4 0.672699 `c_score` ハイスコアの保存方法
- r5 0.665192 `c_theme` 画面の配色テーマ
- r6 0.612673 `c_weather` 今日の天気と降水確率
- r7 0.515749 `c_prd` PRDの書き方
- r8 0.468863 `c_cpu` CPU温度の取得方法
- r9 -0.187439 `c_license` MIT license text for a Python package

### research_asr [asr_like] 兼急用のもの

gold=`c_research` rank=4 cosine=0.653201 gold_is_top=`False` gap_vs_second=-0.060203 delta_vs_clean=-0.246123

- r1 0.713404 `c_board` ゲームの盤面状態
- r2 0.688975 `c_runtime` 実行時の実装
- r3 0.661246 `c_theme` 画面の配色テーマ
- r4 0.653201 `c_research` 研究用の実験 GOLD
- r5 0.61373 `c_score` ハイスコアの保存方法
- r6 0.602246 `c_weather` 今日の天気と降水確率
- r7 0.525359 `c_cpu` CPU温度の取得方法
- r8 0.476022 `c_prd` PRDの書き方
- r9 -0.195206 `c_license` MIT license text for a Python package

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_research` rank=1 cosine=0.922496 gold_is_top=`True` gap_vs_second=0.139099 delta_vs_clean=0.023172

- r1 0.922496 `c_research` 研究用の実験 GOLD
- r2 0.783397 `c_runtime` 実行時の実装
- r3 0.685795 `c_board` ゲームの盤面状態
- r4 0.642043 `c_theme` 画面の配色テーマ
- r5 0.583547 `c_prd` PRDの書き方
- r6 0.573203 `c_cpu` CPU温度の取得方法
- r7 0.568541 `c_score` ハイスコアの保存方法
- r8 0.532142 `c_weather` 今日の天気と降水確率
- r9 -0.079982 `c_license` MIT license text for a Python package

### research_compound [compound] まあけんきゅう用のも

gold=`c_research` rank=4 cosine=0.628834 gold_is_top=`False` gap_vs_second=-0.131592 delta_vs_clean=-0.27049

- r1 0.760426 `c_board` ゲームの盤面状態
- r2 0.706448 `c_runtime` 実行時の実装
- r3 0.639874 `c_weather` 今日の天気と降水確率
- r4 0.628834 `c_research` 研究用の実験 GOLD
- r5 0.625305 `c_score` ハイスコアの保存方法
- r6 0.553343 `c_theme` 画面の配色テーマ
- r7 0.343059 `c_prd` PRDの書き方
- r8 0.313017 `c_cpu` CPU温度の取得方法
- r9 -0.29469 `c_license` MIT license text for a Python package
