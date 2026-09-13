# Embedding similarity Japanese input noise v0

- run_id: `20260909T144951Z_llm-jp-3-150m`
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

- baseline: VRAM 3755 / 12288 MiB, RAM used 39476 / 65277 MB
- after_model_load: VRAM 3754 / 12288 MiB, RAM used 39904 / 65277 MB
- after_embed: VRAM 3754 / 12288 MiB, RAM used 39931 / 65277 MB

## ノイズ種別まとめ

- `clean`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.754022 mean_delta_vs_clean=None failed=['board_clean', 'runtime_clean', 'research_clean']
- `typo`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.788196 mean_delta_vs_clean=-0.113354 failed=['board_typo', 'runtime_typo', 'research_typo']
- `conversion`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.809691 mean_delta_vs_clean=-0.087733 failed=['board_conversion', 'runtime_conversion', 'research_conversion']
- `missing_char`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.70655 mean_delta_vs_clean=0.015192 failed=['board_missing_char', 'runtime_missing_char', 'research_missing_char']
- `particle_drop`: gold_top 0/3 mean_rank=7.0 mean_gap=-0.802708 mean_delta_vs_clean=-0.033197 failed=['board_particle', 'runtime_particle', 'research_particle']
- `colloquial`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.782618 mean_delta_vs_clean=-0.049617 failed=['board_colloquial', 'runtime_colloquial', 'research_colloquial']
- `filler`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.778518 mean_delta_vs_clean=-0.072635 failed=['board_filler', 'runtime_filler', 'research_filler']
- `restatement`: gold_top 0/3 mean_rank=7.0 mean_gap=-0.793713 mean_delta_vs_clean=-0.07723 failed=['board_restatement', 'runtime_restatement', 'research_restatement']
- `asr_like`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.782706 mean_delta_vs_clean=-0.095488 failed=['board_asr', 'runtime_asr', 'research_asr']
- `demonstrative`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.706347 mean_delta_vs_clean=-0.021104 failed=['board_demonstrative', 'runtime_demonstrative', 'research_demonstrative']
- `compound`: gold_top 0/3 mean_rank=6.667 mean_gap=-0.814669 mean_delta_vs_clean=-0.111213 failed=['board_compound', 'runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'particle_drop', 'colloquial', 'filler', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `board_typo` [typo] テとりすの盤面 gold_rank=8 gold_cos=-0.32196 top=`c_score` 0.741992 delta_vs_clean=-0.053536
- `board_conversion` [conversion] テトリスの番面 gold_rank=8 gold_cos=-0.244644 top=`c_score` 0.778992 delta_vs_clean=0.02378
- `board_missing_char` [missing_char] テトリスの盤 gold_rank=8 gold_cos=-0.233699 top=`c_score` 0.785565 delta_vs_clean=0.034725
- `board_particle` [particle_drop] テトリス盤面 gold_rank=9 gold_cos=-0.232101 top=`c_score` 0.804691 delta_vs_clean=0.036323
- `board_colloquial` [colloquial] テトリスの盤面のやつ gold_rank=8 gold_cos=-0.314371 top=`c_score` 0.793445 delta_vs_clean=-0.045947
- `board_filler` [filler] えっとテトリスの盤面 gold_rank=8 gold_cos=-0.158063 top=`c_score` 0.709855 delta_vs_clean=0.110361
- `board_restatement` [restatement] いやスコアじゃなくてテトリスの盤面 gold_rank=8 gold_cos=-0.201757 top=`c_score` 0.77416 delta_vs_clean=0.066667
- `board_asr` [asr_like] 手取り巣の盤面 gold_rank=8 gold_cos=-0.269089 top=`c_theme` 0.698123 delta_vs_clean=-0.000665
- `board_demonstrative` [demonstrative] そっちの盤面 gold_rank=8 gold_cos=-0.205779 top=`c_score` 0.684882 delta_vs_clean=0.062645
- `board_compound` [compound] えっとテトリスの番面のやつ gold_rank=8 gold_cos=-0.181434 top=`c_score` 0.694159 delta_vs_clean=0.08699
- `runtime_typo` [typo] 実交時に動いている実装 gold_rank=6 gold_cos=0.000223 top=`c_theme` 0.590405 delta_vs_clean=-0.094404
- `runtime_conversion` [conversion] 実効時に動いている実装 gold_rank=6 gold_cos=-0.023439 top=`c_theme` 0.592028 delta_vs_clean=-0.118066
- `runtime_missing_char` [missing_char] 実行時に動いている実 gold_rank=6 gold_cos=0.076104 top=`c_theme` 0.650253 delta_vs_clean=-0.018523
- `runtime_particle` [particle_drop] 実行時動いている実装 gold_rank=6 gold_cos=-0.006412 top=`c_theme` 0.73139 delta_vs_clean=-0.101039
- `runtime_colloquial` [colloquial] 実際に動いてるほう gold_rank=6 gold_cos=0.023368 top=`c_weather` 0.587865 delta_vs_clean=-0.071259
- `runtime_filler` [filler] あのー実行時に動いている実装なんですけど gold_rank=6 gold_cos=-0.087273 top=`c_score` 0.673913 delta_vs_clean=-0.1819
- `runtime_restatement` [restatement] 実験用じゃなくて実行時に動いている実装 gold_rank=6 gold_cos=-0.07053 top=`c_score` 0.592347 delta_vs_clean=-0.165157
- `runtime_asr` [asr_like] 実効時に動いてる実装 gold_rank=6 gold_cos=-0.026064 top=`c_score` 0.592042 delta_vs_clean=-0.120691
- `runtime_demonstrative` [demonstrative] 実際に使ってる方 gold_rank=6 gold_cos=-4.4e-05 top=`c_weather` 0.618561 delta_vs_clean=-0.094671
- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=6 gold_cos=-0.116305 top=`c_score` 0.666091 delta_vs_clean=-0.210932
- `research_typo` [typo] けんきゅう用のもの gold_rank=6 gold_cos=-0.128566 top=`c_theme` 0.581888 delta_vs_clean=-0.192121
- `research_conversion` [conversion] 兼休用のもの gold_rank=6 gold_cos=-0.105358 top=`c_theme` 0.684611 delta_vs_clean=-0.168913
- `research_missing_char` [missing_char] 究用のもの gold_rank=6 gold_cos=0.092928 top=`c_theme` 0.619166 delta_vs_clean=0.029373
- `research_particle` [particle_drop] 研究用もの gold_rank=6 gold_cos=0.028679 top=`c_theme` 0.662208 delta_vs_clean=-0.034876
- `research_colloquial` [colloquial] 研究用のやつ gold_rank=6 gold_cos=0.031909 top=`c_theme` 0.707449 delta_vs_clean=-0.031646
- `research_filler` [filler] まあ研究用のものかな gold_rank=6 gold_cos=-0.08281 top=`c_score` 0.623639 delta_vs_clean=-0.146365
- `research_restatement` [restatement] 本番じゃなくて研究用のもの gold_rank=7 gold_cos=-0.069645 top=`c_score` 0.672699 delta_vs_clean=-0.1332
- `research_asr` [asr_like] 兼急用のもの gold_rank=6 gold_cos=-0.101554 top=`c_theme` 0.661246 delta_vs_clean=-0.165109
- `research_demonstrative` [demonstrative] 研究用のほう gold_rank=6 gold_cos=0.032268 top=`c_theme` 0.642043 delta_vs_clean=-0.031287
- `research_compound` [compound] まあけんきゅう用のも gold_rank=6 gold_cos=-0.146143 top=`c_weather` 0.639874 delta_vs_clean=-0.209698

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_board` rank=8 cosine=-0.268424 gold_is_top=`False` gap_vs_second=-1.069075 delta_vs_clean=None

- r1 0.800651 `c_score` ハイスコアの保存方法
- r2 0.719029 `c_theme` 画面の配色テーマ
- r3 0.603474 `c_weather` 今日の天気と降水確率
- r4 0.367776 `c_cpu` CPU温度の取得方法
- r5 0.317524 `c_prd` PRDの書き方
- r6 -0.232938 `c_runtime` runtime implementation
- r7 -0.249858 `c_research` research experiment
- r8 -0.268424 `c_board` game board state GOLD
- r9 -0.333529 `c_license` MIT license text for a Python package

### board_typo [typo] テとりすの盤面

gold=`c_board` rank=8 cosine=-0.32196 gold_is_top=`False` gap_vs_second=-1.063952 delta_vs_clean=-0.053536

- r1 0.741992 `c_score` ハイスコアの保存方法
- r2 0.710782 `c_theme` 画面の配色テーマ
- r3 0.655575 `c_weather` 今日の天気と降水確率
- r4 0.35945 `c_cpu` CPU温度の取得方法
- r5 0.320157 `c_prd` PRDの書き方
- r6 -0.267414 `c_research` research experiment
- r7 -0.271013 `c_runtime` runtime implementation
- r8 -0.32196 `c_board` game board state GOLD
- r9 -0.368478 `c_license` MIT license text for a Python package

### board_conversion [conversion] テトリスの番面

gold=`c_board` rank=8 cosine=-0.244644 gold_is_top=`False` gap_vs_second=-1.023636 delta_vs_clean=0.02378

- r1 0.778992 `c_score` ハイスコアの保存方法
- r2 0.658553 `c_theme` 画面の配色テーマ
- r3 0.586898 `c_weather` 今日の天気と降水確率
- r4 0.314182 `c_cpu` CPU温度の取得方法
- r5 0.289244 `c_prd` PRDの書き方
- r6 -0.214712 `c_runtime` runtime implementation
- r7 -0.225392 `c_research` research experiment
- r8 -0.244644 `c_board` game board state GOLD
- r9 -0.31105 `c_license` MIT license text for a Python package

### board_missing_char [missing_char] テトリスの盤

gold=`c_board` rank=8 cosine=-0.233699 gold_is_top=`False` gap_vs_second=-1.019264 delta_vs_clean=0.034725

- r1 0.785565 `c_score` ハイスコアの保存方法
- r2 0.669677 `c_theme` 画面の配色テーマ
- r3 0.594256 `c_weather` 今日の天気と降水確率
- r4 0.350621 `c_cpu` CPU温度の取得方法
- r5 0.337749 `c_prd` PRDの書き方
- r6 -0.189192 `c_runtime` runtime implementation
- r7 -0.207521 `c_research` research experiment
- r8 -0.233699 `c_board` game board state GOLD
- r9 -0.303359 `c_license` MIT license text for a Python package

### board_particle [particle_drop] テトリス盤面

gold=`c_board` rank=9 cosine=-0.232101 gold_is_top=`False` gap_vs_second=-1.036792 delta_vs_clean=0.036323

- r1 0.804691 `c_score` ハイスコアの保存方法
- r2 0.720366 `c_theme` 画面の配色テーマ
- r3 0.523983 `c_weather` 今日の天気と降水確率
- r4 0.405955 `c_cpu` CPU温度の取得方法
- r5 0.335203 `c_prd` PRDの書き方
- r6 -0.205571 `c_runtime` runtime implementation
- r7 -0.223614 `c_research` research experiment
- r8 -0.227691 `c_license` MIT license text for a Python package
- r9 -0.232101 `c_board` game board state GOLD

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_board` rank=8 cosine=-0.314371 gold_is_top=`False` gap_vs_second=-1.107816 delta_vs_clean=-0.045947

- r1 0.793445 `c_score` ハイスコアの保存方法
- r2 0.726657 `c_theme` 画面の配色テーマ
- r3 0.61021 `c_weather` 今日の天気と降水確率
- r4 0.353554 `c_cpu` CPU温度の取得方法
- r5 0.274395 `c_prd` PRDの書き方
- r6 -0.280614 `c_runtime` runtime implementation
- r7 -0.293373 `c_research` research experiment
- r8 -0.314371 `c_board` game board state GOLD
- r9 -0.379052 `c_license` MIT license text for a Python package

### board_filler [filler] えっとテトリスの盤面

gold=`c_board` rank=8 cosine=-0.158063 gold_is_top=`False` gap_vs_second=-0.867918 delta_vs_clean=0.110361

- r1 0.709855 `c_score` ハイスコアの保存方法
- r2 0.647795 `c_theme` 画面の配色テーマ
- r3 0.618539 `c_weather` 今日の天気と降水確率
- r4 0.358683 `c_cpu` CPU温度の取得方法
- r5 0.35719 `c_prd` PRDの書き方
- r6 -0.107216 `c_runtime` runtime implementation
- r7 -0.126887 `c_research` research experiment
- r8 -0.158063 `c_board` game board state GOLD
- r9 -0.270927 `c_license` MIT license text for a Python package

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_board` rank=8 cosine=-0.201757 gold_is_top=`False` gap_vs_second=-0.975917 delta_vs_clean=0.066667

- r1 0.77416 `c_score` ハイスコアの保存方法
- r2 0.666637 `c_theme` 画面の配色テーマ
- r3 0.601029 `c_weather` 今日の天気と降水確率
- r4 0.388559 `c_cpu` CPU温度の取得方法
- r5 0.379792 `c_prd` PRDの書き方
- r6 -0.157184 `c_runtime` runtime implementation
- r7 -0.181478 `c_research` research experiment
- r8 -0.201757 `c_board` game board state GOLD
- r9 -0.301759 `c_license` MIT license text for a Python package

### board_asr [asr_like] 手取り巣の盤面

gold=`c_board` rank=8 cosine=-0.269089 gold_is_top=`False` gap_vs_second=-0.967212 delta_vs_clean=-0.000665

- r1 0.698123 `c_theme` 画面の配色テーマ
- r2 0.660603 `c_score` ハイスコアの保存方法
- r3 0.629918 `c_weather` 今日の天気と降水確率
- r4 0.45087 `c_cpu` CPU温度の取得方法
- r5 0.344126 `c_prd` PRDの書き方
- r6 -0.231643 `c_research` research experiment
- r7 -0.254316 `c_runtime` runtime implementation
- r8 -0.269089 `c_board` game board state GOLD
- r9 -0.347666 `c_license` MIT license text for a Python package

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_board` rank=8 cosine=-0.205779 gold_is_top=`False` gap_vs_second=-0.890661 delta_vs_clean=0.062645

- r1 0.684882 `c_score` ハイスコアの保存方法
- r2 0.671389 `c_theme` 画面の配色テーマ
- r3 0.655809 `c_weather` 今日の天気と降水確率
- r4 0.380147 `c_prd` PRDの書き方
- r5 0.369786 `c_cpu` CPU温度の取得方法
- r6 -0.153039 `c_research` research experiment
- r7 -0.15517 `c_runtime` runtime implementation
- r8 -0.205779 `c_board` game board state GOLD
- r9 -0.317213 `c_license` MIT license text for a Python package

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_board` rank=8 cosine=-0.181434 gold_is_top=`False` gap_vs_second=-0.875593 delta_vs_clean=0.08699

- r1 0.694159 `c_score` ハイスコアの保存方法
- r2 0.621848 `c_theme` 画面の配色テーマ
- r3 0.604319 `c_weather` 今日の天気と降水確率
- r4 0.310217 `c_cpu` CPU温度の取得方法
- r5 0.298603 `c_prd` PRDの書き方
- r6 -0.139014 `c_runtime` runtime implementation
- r7 -0.152988 `c_research` research experiment
- r8 -0.181434 `c_board` game board state GOLD
- r9 -0.291297 `c_license` MIT license text for a Python package

### runtime_clean [clean] 実行時に動いている実装

gold=`c_runtime` rank=6 cosine=0.094627 gold_is_top=`False` gap_vs_second=-0.590017 delta_vs_clean=None

- r1 0.684644 `c_theme` 画面の配色テーマ
- r2 0.644916 `c_score` ハイスコアの保存方法
- r3 0.616962 `c_cpu` CPU温度の取得方法
- r4 0.613895 `c_prd` PRDの書き方
- r5 0.569297 `c_weather` 今日の天気と降水確率
- r6 0.094627 `c_runtime` runtime implementation GOLD
- r7 0.02712 `c_research` research experiment
- r8 -0.039618 `c_board` game board state
- r9 -0.068574 `c_license` MIT license text for a Python package

### runtime_typo [typo] 実交時に動いている実装

gold=`c_runtime` rank=6 cosine=0.000223 gold_is_top=`False` gap_vs_second=-0.590182 delta_vs_clean=-0.094404

- r1 0.590405 `c_theme` 画面の配色テーマ
- r2 0.578276 `c_weather` 今日の天気と降水確率
- r3 0.556451 `c_score` ハイスコアの保存方法
- r4 0.501838 `c_prd` PRDの書き方
- r5 0.484854 `c_cpu` CPU温度の取得方法
- r6 0.000223 `c_runtime` runtime implementation GOLD
- r7 -0.035299 `c_research` research experiment
- r8 -0.11546 `c_board` game board state
- r9 -0.17802 `c_license` MIT license text for a Python package

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_runtime` rank=6 cosine=-0.023439 gold_is_top=`False` gap_vs_second=-0.615467 delta_vs_clean=-0.118066

- r1 0.592028 `c_theme` 画面の配色テーマ
- r2 0.590858 `c_score` ハイスコアの保存方法
- r3 0.58941 `c_weather` 今日の天気と降水確率
- r4 0.488124 `c_prd` PRDの書き方
- r5 0.478045 `c_cpu` CPU温度の取得方法
- r6 -0.023439 `c_runtime` runtime implementation GOLD
- r7 -0.056417 `c_research` research experiment
- r8 -0.133652 `c_board` game board state
- r9 -0.211539 `c_license` MIT license text for a Python package

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_runtime` rank=6 cosine=0.076104 gold_is_top=`False` gap_vs_second=-0.574149 delta_vs_clean=-0.018523

- r1 0.650253 `c_theme` 画面の配色テーマ
- r2 0.622921 `c_score` ハイスコアの保存方法
- r3 0.59124 `c_prd` PRDの書き方
- r4 0.583659 `c_weather` 今日の天気と降水確率
- r5 0.579266 `c_cpu` CPU温度の取得方法
- r6 0.076104 `c_runtime` runtime implementation GOLD
- r7 0.020343 `c_research` research experiment
- r8 -0.048558 `c_board` game board state
- r9 -0.089065 `c_license` MIT license text for a Python package

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_runtime` rank=6 cosine=-0.006412 gold_is_top=`False` gap_vs_second=-0.737802 delta_vs_clean=-0.101039

- r1 0.73139 `c_theme` 画面の配色テーマ
- r2 0.655057 `c_score` ハイスコアの保存方法
- r3 0.626321 `c_cpu` CPU温度の取得方法
- r4 0.586774 `c_weather` 今日の天気と降水確率
- r5 0.585745 `c_prd` PRDの書き方
- r6 -0.006412 `c_runtime` runtime implementation GOLD
- r7 -0.060883 `c_research` research experiment
- r8 -0.123601 `c_board` game board state
- r9 -0.126611 `c_license` MIT license text for a Python package

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_runtime` rank=6 cosine=0.023368 gold_is_top=`False` gap_vs_second=-0.564497 delta_vs_clean=-0.071259

- r1 0.587865 `c_weather` 今日の天気と降水確率
- r2 0.534975 `c_score` ハイスコアの保存方法
- r3 0.498067 `c_theme` 画面の配色テーマ
- r4 0.470056 `c_prd` PRDの書き方
- r5 0.382577 `c_cpu` CPU温度の取得方法
- r6 0.023368 `c_runtime` runtime implementation GOLD
- r7 0.005365 `c_research` research experiment
- r8 -0.075934 `c_board` game board state
- r9 -0.188349 `c_license` MIT license text for a Python package

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_runtime` rank=6 cosine=-0.087273 gold_is_top=`False` gap_vs_second=-0.761186 delta_vs_clean=-0.1819

- r1 0.673913 `c_score` ハイスコアの保存方法
- r2 0.628175 `c_theme` 画面の配色テーマ
- r3 0.623124 `c_weather` 今日の天気と降水確率
- r4 0.435056 `c_prd` PRDの書き方
- r5 0.406389 `c_cpu` CPU温度の取得方法
- r6 -0.087273 `c_runtime` runtime implementation GOLD
- r7 -0.117112 `c_research` research experiment
- r8 -0.182174 `c_board` game board state
- r9 -0.24102 `c_license` MIT license text for a Python package

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_runtime` rank=6 cosine=-0.07053 gold_is_top=`False` gap_vs_second=-0.662877 delta_vs_clean=-0.165157

- r1 0.592347 `c_score` ハイスコアの保存方法
- r2 0.583484 `c_theme` 画面の配色テーマ
- r3 0.545764 `c_weather` 今日の天気と降水確率
- r4 0.495961 `c_cpu` CPU温度の取得方法
- r5 0.461667 `c_prd` PRDの書き方
- r6 -0.07053 `c_runtime` runtime implementation GOLD
- r7 -0.072506 `c_research` research experiment
- r8 -0.171691 `c_board` game board state
- r9 -0.210358 `c_license` MIT license text for a Python package

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_runtime` rank=6 cosine=-0.026064 gold_is_top=`False` gap_vs_second=-0.618106 delta_vs_clean=-0.120691

- r1 0.592042 `c_score` ハイスコアの保存方法
- r2 0.591191 `c_weather` 今日の天気と降水確率
- r3 0.582524 `c_theme` 画面の配色テーマ
- r4 0.474274 `c_prd` PRDの書き方
- r5 0.459389 `c_cpu` CPU温度の取得方法
- r6 -0.026064 `c_runtime` runtime implementation GOLD
- r7 -0.058921 `c_research` research experiment
- r8 -0.133335 `c_board` game board state
- r9 -0.218247 `c_license` MIT license text for a Python package

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_runtime` rank=6 cosine=-4.4e-05 gold_is_top=`False` gap_vs_second=-0.618605 delta_vs_clean=-0.094671

- r1 0.618561 `c_weather` 今日の天気と降水確率
- r2 0.593035 `c_score` ハイスコアの保存方法
- r3 0.546195 `c_theme` 画面の配色テーマ
- r4 0.483339 `c_prd` PRDの書き方
- r5 0.395829 `c_cpu` CPU温度の取得方法
- r6 -4.4e-05 `c_runtime` runtime implementation GOLD
- r7 -0.006679 `c_research` research experiment
- r8 -0.08596 `c_board` game board state
- r9 -0.196069 `c_license` MIT license text for a Python package

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_runtime` rank=6 cosine=-0.116305 gold_is_top=`False` gap_vs_second=-0.782396 delta_vs_clean=-0.210932

- r1 0.666091 `c_score` ハイスコアの保存方法
- r2 0.605427 `c_weather` 今日の天気と降水確率
- r3 0.548601 `c_theme` 画面の配色テーマ
- r4 0.363388 `c_prd` PRDの書き方
- r5 0.296102 `c_cpu` CPU温度の取得方法
- r6 -0.116305 `c_runtime` runtime implementation GOLD
- r7 -0.136579 `c_research` research experiment
- r8 -0.183551 `c_board` game board state
- r9 -0.28496 `c_license` MIT license text for a Python package

### research_clean [clean] 研究用のもの

gold=`c_research` rank=6 cosine=0.063555 gold_is_top=`False` gap_vs_second=-0.602973 delta_vs_clean=None

- r1 0.666528 `c_theme` 画面の配色テーマ
- r2 0.625677 `c_cpu` CPU温度の取得方法
- r3 0.609269 `c_prd` PRDの書き方
- r4 0.545182 `c_score` ハイスコアの保存方法
- r5 0.500975 `c_weather` 今日の天気と降水確率
- r6 0.063555 `c_research` research experiment GOLD
- r7 0.024921 `c_runtime` runtime implementation
- r8 -0.014717 `c_license` MIT license text for a Python package
- r9 -0.070495 `c_board` game board state

### research_typo [typo] けんきゅう用のもの

gold=`c_research` rank=6 cosine=-0.128566 gold_is_top=`False` gap_vs_second=-0.710454 delta_vs_clean=-0.192121

- r1 0.581888 `c_theme` 画面の配色テーマ
- r2 0.578924 `c_weather` 今日の天気と降水確率
- r3 0.560055 `c_score` ハイスコアの保存方法
- r4 0.375143 `c_cpu` CPU温度の取得方法
- r5 0.342836 `c_prd` PRDの書き方
- r6 -0.128566 `c_research` research experiment GOLD
- r7 -0.155225 `c_runtime` runtime implementation
- r8 -0.187882 `c_board` game board state
- r9 -0.229528 `c_license` MIT license text for a Python package

### research_conversion [conversion] 兼休用のもの

gold=`c_research` rank=6 cosine=-0.105358 gold_is_top=`False` gap_vs_second=-0.789969 delta_vs_clean=-0.168913

- r1 0.684611 `c_theme` 画面の配色テーマ
- r2 0.652805 `c_score` ハイスコアの保存方法
- r3 0.604002 `c_weather` 今日の天気と降水確率
- r4 0.486572 `c_prd` PRDの書き方
- r5 0.484445 `c_cpu` CPU温度の取得方法
- r6 -0.105358 `c_research` research experiment GOLD
- r7 -0.118024 `c_runtime` runtime implementation
- r8 -0.169824 `c_board` game board state
- r9 -0.184476 `c_license` MIT license text for a Python package

### research_missing_char [missing_char] 究用のもの

gold=`c_research` rank=6 cosine=0.092928 gold_is_top=`False` gap_vs_second=-0.526238 delta_vs_clean=0.029373

- r1 0.619166 `c_theme` 画面の配色テーマ
- r2 0.603686 `c_prd` PRDの書き方
- r3 0.584904 `c_cpu` CPU温度の取得方法
- r4 0.560919 `c_weather` 今日の天気と降水確率
- r5 0.522316 `c_score` ハイスコアの保存方法
- r6 0.092928 `c_research` research experiment GOLD
- r7 0.077717 `c_runtime` runtime implementation
- r8 -0.009878 `c_board` game board state
- r9 -0.057361 `c_license` MIT license text for a Python package

### research_particle [particle_drop] 研究用もの

gold=`c_research` rank=6 cosine=0.028679 gold_is_top=`False` gap_vs_second=-0.633529 delta_vs_clean=-0.034876

- r1 0.662208 `c_theme` 画面の配色テーマ
- r2 0.600416 `c_cpu` CPU温度の取得方法
- r3 0.586555 `c_prd` PRDの書き方
- r4 0.552192 `c_score` ハイスコアの保存方法
- r5 0.504577 `c_weather` 今日の天気と降水確率
- r6 0.028679 `c_research` research experiment GOLD
- r7 -0.007437 `c_runtime` runtime implementation
- r8 -0.038391 `c_license` MIT license text for a Python package
- r9 -0.101018 `c_board` game board state

### research_colloquial [colloquial] 研究用のやつ

gold=`c_research` rank=6 cosine=0.031909 gold_is_top=`False` gap_vs_second=-0.67554 delta_vs_clean=-0.031646

- r1 0.707449 `c_theme` 画面の配色テーマ
- r2 0.639012 `c_score` ハイスコアの保存方法
- r3 0.615565 `c_prd` PRDの書き方
- r4 0.606518 `c_cpu` CPU温度の取得方法
- r5 0.593343 `c_weather` 今日の天気と降水確率
- r6 0.031909 `c_research` research experiment GOLD
- r7 0.00806 `c_runtime` runtime implementation
- r8 -0.066657 `c_license` MIT license text for a Python package
- r9 -0.093249 `c_board` game board state

### research_filler [filler] まあ研究用のものかな

gold=`c_research` rank=6 cosine=-0.08281 gold_is_top=`False` gap_vs_second=-0.706449 delta_vs_clean=-0.146365

- r1 0.623639 `c_score` ハイスコアの保存方法
- r2 0.607732 `c_weather` 今日の天気と降水確率
- r3 0.581686 `c_theme` 画面の配色テーマ
- r4 0.426077 `c_prd` PRDの書き方
- r5 0.393983 `c_cpu` CPU温度の取得方法
- r6 -0.08281 `c_research` research experiment GOLD
- r7 -0.091116 `c_runtime` runtime implementation
- r8 -0.171619 `c_board` game board state
- r9 -0.234389 `c_license` MIT license text for a Python package

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_research` rank=7 cosine=-0.069645 gold_is_top=`False` gap_vs_second=-0.742344 delta_vs_clean=-0.1332

- r1 0.672699 `c_score` ハイスコアの保存方法
- r2 0.665192 `c_theme` 画面の配色テーマ
- r3 0.612673 `c_weather` 今日の天気と降水確率
- r4 0.515749 `c_prd` PRDの書き方
- r5 0.468863 `c_cpu` CPU温度の取得方法
- r6 -0.06701 `c_runtime` runtime implementation
- r7 -0.069645 `c_research` research experiment GOLD
- r8 -0.136303 `c_board` game board state
- r9 -0.187439 `c_license` MIT license text for a Python package

### research_asr [asr_like] 兼急用のもの

gold=`c_research` rank=6 cosine=-0.101554 gold_is_top=`False` gap_vs_second=-0.7628 delta_vs_clean=-0.165109

- r1 0.661246 `c_theme` 画面の配色テーマ
- r2 0.61373 `c_score` ハイスコアの保存方法
- r3 0.602246 `c_weather` 今日の天気と降水確率
- r4 0.525359 `c_cpu` CPU温度の取得方法
- r5 0.476022 `c_prd` PRDの書き方
- r6 -0.101554 `c_research` research experiment GOLD
- r7 -0.109277 `c_runtime` runtime implementation
- r8 -0.1593 `c_board` game board state
- r9 -0.195206 `c_license` MIT license text for a Python package

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_research` rank=6 cosine=0.032268 gold_is_top=`False` gap_vs_second=-0.609775 delta_vs_clean=-0.031287

- r1 0.642043 `c_theme` 画面の配色テーマ
- r2 0.583547 `c_prd` PRDの書き方
- r3 0.573203 `c_cpu` CPU温度の取得方法
- r4 0.568541 `c_score` ハイスコアの保存方法
- r5 0.532142 `c_weather` 今日の天気と降水確率
- r6 0.032268 `c_research` research experiment GOLD
- r7 0.001406 `c_runtime` runtime implementation
- r8 -0.079982 `c_license` MIT license text for a Python package
- r9 -0.086826 `c_board` game board state

### research_compound [compound] まあけんきゅう用のも

gold=`c_research` rank=6 cosine=-0.146143 gold_is_top=`False` gap_vs_second=-0.786017 delta_vs_clean=-0.209698

- r1 0.639874 `c_weather` 今日の天気と降水確率
- r2 0.625305 `c_score` ハイスコアの保存方法
- r3 0.553343 `c_theme` 画面の配色テーマ
- r4 0.343059 `c_prd` PRDの書き方
- r5 0.313017 `c_cpu` CPU温度の取得方法
- r6 -0.146143 `c_research` research experiment GOLD
- r7 -0.147243 `c_runtime` runtime implementation
- r8 -0.212206 `c_board` game board state
- r9 -0.29469 `c_license` MIT license text for a Python package
