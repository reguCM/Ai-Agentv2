# Embedding similarity Japanese input noise v0

- run_id: `20260909T143156Z`
- embed_model: `qwen3-embedding:0.6b`
- gen_model: `qwen3:14b`
- with_gen: `False`
- Production / Grill 接続: なし
- 閾値正本化: なし
- SELECTED規則: なし

`gold_is_top` はこの候補集合で意図候補が1位だった観測。SELECTED規則ではない。

## 資源

- baseline: VRAM 11795 / 12288 MiB, RAM used 40875 / 65277 MB
- after_embed: VRAM 11901 / 12288 MiB, RAM used 42054 / 65277 MB

## ノイズ種別まとめ

- `clean`: gold_top 3/3 mean_rank=1.0 mean_gap=0.170173 mean_delta_vs_clean=None failed=[]
- `typo`: gold_top 1/3 mean_rank=3.667 mean_gap=-0.006186 mean_delta_vs_clean=-0.174963 failed=['board_typo', 'research_typo']
- `conversion`: gold_top 2/3 mean_rank=2.667 mean_gap=0.004734 mean_delta_vs_clean=-0.143419 failed=['research_conversion']
- `missing_char`: gold_top 2/3 mean_rank=2.0 mean_gap=0.071906 mean_delta_vs_clean=-0.107414 failed=['research_missing_char']
- `particle_drop`: gold_top 3/3 mean_rank=1.0 mean_gap=0.167384 mean_delta_vs_clean=-0.005614 failed=[]
- `colloquial`: gold_top 2/3 mean_rank=1.333 mean_gap=0.093692 mean_delta_vs_clean=-0.080133 failed=['runtime_colloquial']
- `filler`: gold_top 3/3 mean_rank=1.0 mean_gap=0.095655 mean_delta_vs_clean=-0.131327 failed=[]
- `restatement`: gold_top 2/3 mean_rank=1.333 mean_gap=0.054404 mean_delta_vs_clean=-0.109999 failed=['board_restatement']
- `asr_like`: gold_top 1/3 mean_rank=4.667 mean_gap=-0.025922 mean_delta_vs_clean=-0.164375 failed=['board_asr', 'research_asr']
- `demonstrative`: gold_top 2/3 mean_rank=2.333 mean_gap=0.074812 mean_delta_vs_clean=-0.111708 failed=['board_demonstrative']
- `compound`: gold_top 0/3 mean_rank=3.667 mean_gap=-0.025974 mean_delta_vs_clean=-0.271858 failed=['board_compound', 'runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'colloquial', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `board_typo` [typo] テとりすの盤面 gold_rank=5 gold_cos=0.484704 top=`c_score` 0.550325 delta_vs_clean=-0.136306
- `board_restatement` [restatement] いやスコアじゃなくてテトリスの盤面 gold_rank=2 gold_cos=0.496874 top=`c_theme` 0.498443 delta_vs_clean=-0.124136
- `board_asr` [asr_like] 手取り巣の盤面 gold_rank=7 gold_cos=0.472401 top=`c_prd` 0.595016 delta_vs_clean=-0.148609
- `board_demonstrative` [demonstrative] そっちの盤面 gold_rank=5 gold_cos=0.507244 top=`c_theme` 0.541727 delta_vs_clean=-0.113766
- `board_compound` [compound] えっとテトリスの番面のやつ gold_rank=3 gold_cos=0.497421 top=`c_theme` 0.51927 delta_vs_clean=-0.123589
- `runtime_colloquial` [colloquial] 実際に動いてるほう gold_rank=2 gold_cos=0.49952 top=`c_theme` 0.506929 delta_vs_clean=-0.219124
- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=3 gold_cos=0.452868 top=`c_board` 0.47193 delta_vs_clean=-0.265776
- `research_typo` [typo] けんきゅう用のもの gold_rank=5 gold_cos=0.465206 top=`c_score` 0.542761 delta_vs_clean=-0.291518
- `research_conversion` [conversion] 兼休用のもの gold_rank=6 gold_cos=0.418174 top=`c_score` 0.572932 delta_vs_clean=-0.33855
- `research_missing_char` [missing_char] 究用のもの gold_rank=4 gold_cos=0.582145 top=`c_prd` 0.59479 delta_vs_clean=-0.174579
- `research_asr` [asr_like] 兼急用のもの gold_rank=6 gold_cos=0.467036 top=`c_prd` 0.564459 delta_vs_clean=-0.289688
- `research_compound` [compound] まあけんきゅう用のも gold_rank=5 gold_cos=0.330514 top=`c_theme` 0.367524 delta_vs_clean=-0.42621

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_board` rank=1 cosine=0.62101 gold_is_top=`True` gap_vs_second=0.085249 delta_vs_clean=None

- r1 0.62101 `c_board` game board state GOLD
- r2 0.535761 `c_score` ハイスコアの保存方法
- r3 0.532625 `c_theme` 画面の配色テーマ
- r4 0.520031 `c_prd` PRDの書き方
- r5 0.510193 `c_weather` 今日の天気と降水確率
- r6 0.505042 `c_runtime` runtime implementation
- r7 0.501499 `c_cpu` CPU温度の取得方法
- r8 0.468611 `c_research` research experiment
- r9 0.373873 `c_license` MIT license text for a Python package

### board_typo [typo] テとりすの盤面

gold=`c_board` rank=5 cosine=0.484704 gold_is_top=`False` gap_vs_second=-0.065621 delta_vs_clean=-0.136306

- r1 0.550325 `c_score` ハイスコアの保存方法
- r2 0.536502 `c_theme` 画面の配色テーマ
- r3 0.536027 `c_prd` PRDの書き方
- r4 0.507733 `c_weather` 今日の天気と降水確率
- r5 0.484704 `c_board` game board state GOLD
- r6 0.479427 `c_runtime` runtime implementation
- r7 0.477314 `c_cpu` CPU温度の取得方法
- r8 0.475775 `c_research` research experiment
- r9 0.365487 `c_license` MIT license text for a Python package

### board_conversion [conversion] テトリスの番面

gold=`c_board` rank=1 cosine=0.572495 gold_is_top=`True` gap_vs_second=0.029443 delta_vs_clean=-0.048515

- r1 0.572495 `c_board` game board state GOLD
- r2 0.543052 `c_score` ハイスコアの保存方法
- r3 0.533032 `c_theme` 画面の配色テーマ
- r4 0.506666 `c_cpu` CPU温度の取得方法
- r5 0.504798 `c_prd` PRDの書き方
- r6 0.502473 `c_runtime` runtime implementation
- r7 0.49132 `c_weather` 今日の天気と降水確率
- r8 0.455976 `c_research` research experiment
- r9 0.36603 `c_license` MIT license text for a Python package

### board_missing_char [missing_char] テトリスの盤

gold=`c_board` rank=1 cosine=0.608816 gold_is_top=`True` gap_vs_second=0.058359 delta_vs_clean=-0.012194

- r1 0.608816 `c_board` game board state GOLD
- r2 0.550457 `c_score` ハイスコアの保存方法
- r3 0.524079 `c_prd` PRDの書き方
- r4 0.509711 `c_weather` 今日の天気と降水確率
- r5 0.506455 `c_theme` 画面の配色テーマ
- r6 0.502639 `c_cpu` CPU温度の取得方法
- r7 0.499067 `c_runtime` runtime implementation
- r8 0.463648 `c_research` research experiment
- r9 0.378972 `c_license` MIT license text for a Python package

### board_particle [particle_drop] テトリス盤面

gold=`c_board` rank=1 cosine=0.614833 gold_is_top=`True` gap_vs_second=0.080356 delta_vs_clean=-0.006177

- r1 0.614833 `c_board` game board state GOLD
- r2 0.534477 `c_theme` 画面の配色テーマ
- r3 0.504608 `c_prd` PRDの書き方
- r4 0.503255 `c_score` ハイスコアの保存方法
- r5 0.497141 `c_weather` 今日の天気と降水確率
- r6 0.484453 `c_runtime` runtime implementation
- r7 0.484244 `c_cpu` CPU温度の取得方法
- r8 0.456984 `c_research` research experiment
- r9 0.36671 `c_license` MIT license text for a Python package

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_board` rank=1 cosine=0.602916 gold_is_top=`True` gap_vs_second=0.070123 delta_vs_clean=-0.018094

- r1 0.602916 `c_board` game board state GOLD
- r2 0.532793 `c_theme` 画面の配色テーマ
- r3 0.525569 `c_score` ハイスコアの保存方法
- r4 0.513868 `c_prd` PRDの書き方
- r5 0.498407 `c_runtime` runtime implementation
- r6 0.493612 `c_cpu` CPU温度の取得方法
- r7 0.492357 `c_weather` 今日の天気と降水確率
- r8 0.466084 `c_research` research experiment
- r9 0.364074 `c_license` MIT license text for a Python package

### board_filler [filler] えっとテトリスの盤面

gold=`c_board` rank=1 cosine=0.585966 gold_is_top=`True` gap_vs_second=0.053414 delta_vs_clean=-0.035044

- r1 0.585966 `c_board` game board state GOLD
- r2 0.532552 `c_theme` 画面の配色テーマ
- r3 0.523982 `c_score` ハイスコアの保存方法
- r4 0.522898 `c_prd` PRDの書き方
- r5 0.509769 `c_weather` 今日の天気と降水確率
- r6 0.500119 `c_runtime` runtime implementation
- r7 0.488095 `c_cpu` CPU温度の取得方法
- r8 0.479212 `c_research` research experiment
- r9 0.375408 `c_license` MIT license text for a Python package

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_board` rank=2 cosine=0.496874 gold_is_top=`False` gap_vs_second=-0.001569 delta_vs_clean=-0.124136

- r1 0.498443 `c_theme` 画面の配色テーマ
- r2 0.496874 `c_board` game board state GOLD
- r3 0.470815 `c_score` ハイスコアの保存方法
- r4 0.442529 `c_prd` PRDの書き方
- r5 0.409923 `c_runtime` runtime implementation
- r6 0.399216 `c_cpu` CPU温度の取得方法
- r7 0.397791 `c_weather` 今日の天気と降水確率
- r8 0.368036 `c_research` research experiment
- r9 0.310106 `c_license` MIT license text for a Python package

### board_asr [asr_like] 手取り巣の盤面

gold=`c_board` rank=7 cosine=0.472401 gold_is_top=`False` gap_vs_second=-0.122615 delta_vs_clean=-0.148609

- r1 0.595016 `c_prd` PRDの書き方
- r2 0.577524 `c_score` ハイスコアの保存方法
- r3 0.56709 `c_theme` 画面の配色テーマ
- r4 0.533819 `c_runtime` runtime implementation
- r5 0.521053 `c_research` research experiment
- r6 0.49879 `c_weather` 今日の天気と降水確率
- r7 0.472401 `c_board` game board state GOLD
- r8 0.458087 `c_cpu` CPU温度の取得方法
- r9 0.349772 `c_license` MIT license text for a Python package

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_board` rank=5 cosine=0.507244 gold_is_top=`False` gap_vs_second=-0.034483 delta_vs_clean=-0.113766

- r1 0.541727 `c_theme` 画面の配色テーマ
- r2 0.536779 `c_score` ハイスコアの保存方法
- r3 0.532829 `c_prd` PRDの書き方
- r4 0.510958 `c_weather` 今日の天気と降水確率
- r5 0.507244 `c_board` game board state GOLD
- r6 0.460798 `c_runtime` runtime implementation
- r7 0.449624 `c_research` research experiment
- r8 0.436475 `c_cpu` CPU温度の取得方法
- r9 0.34322 `c_license` MIT license text for a Python package

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_board` rank=3 cosine=0.497421 gold_is_top=`False` gap_vs_second=-0.021849 delta_vs_clean=-0.123589

- r1 0.51927 `c_theme` 画面の配色テーマ
- r2 0.508784 `c_score` ハイスコアの保存方法
- r3 0.497421 `c_board` game board state GOLD
- r4 0.486321 `c_prd` PRDの書き方
- r5 0.468485 `c_cpu` CPU温度の取得方法
- r6 0.465888 `c_runtime` runtime implementation
- r7 0.460343 `c_weather` 今日の天気と降水確率
- r8 0.446953 `c_research` research experiment
- r9 0.350474 `c_license` MIT license text for a Python package

### runtime_clean [clean] 実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.718644 gold_is_top=`True` gap_vs_second=0.217778 delta_vs_clean=None

- r1 0.718644 `c_runtime` runtime implementation GOLD
- r2 0.500866 `c_research` research experiment
- r3 0.478329 `c_cpu` CPU温度の取得方法
- r4 0.472516 `c_score` ハイスコアの保存方法
- r5 0.456681 `c_prd` PRDの書き方
- r6 0.437623 `c_theme` 画面の配色テーマ
- r7 0.431851 `c_board` game board state
- r8 0.414541 `c_weather` 今日の天気と降水確率
- r9 0.282617 `c_license` MIT license text for a Python package

### runtime_typo [typo] 実交時に動いている実装

gold=`c_runtime` rank=1 cosine=0.621579 gold_is_top=`True` gap_vs_second=0.124618 delta_vs_clean=-0.097065

- r1 0.621579 `c_runtime` runtime implementation GOLD
- r2 0.496961 `c_score` ハイスコアの保存方法
- r3 0.475209 `c_prd` PRDの書き方
- r4 0.470346 `c_research` research experiment
- r5 0.451415 `c_theme` 画面の配色テーマ
- r6 0.443258 `c_board` game board state
- r7 0.439691 `c_weather` 今日の天気と降水確率
- r8 0.436543 `c_cpu` CPU温度の取得方法
- r9 0.28848 `c_license` MIT license text for a Python package

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_runtime` rank=1 cosine=0.675451 gold_is_top=`True` gap_vs_second=0.139517 delta_vs_clean=-0.043193

- r1 0.675451 `c_runtime` runtime implementation GOLD
- r2 0.535934 `c_prd` PRDの書き方
- r3 0.534937 `c_research` research experiment
- r4 0.503427 `c_score` ハイスコアの保存方法
- r5 0.473641 `c_cpu` CPU温度の取得方法
- r6 0.459989 `c_theme` 画面の配色テーマ
- r7 0.456501 `c_weather` 今日の天気と降水確率
- r8 0.42941 `c_board` game board state
- r9 0.302729 `c_license` MIT license text for a Python package

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_runtime` rank=1 cosine=0.583174 gold_is_top=`True` gap_vs_second=0.170005 delta_vs_clean=-0.13547

- r1 0.583174 `c_runtime` runtime implementation GOLD
- r2 0.413169 `c_research` research experiment
- r3 0.385274 `c_cpu` CPU温度の取得方法
- r4 0.384717 `c_theme` 画面の配色テーマ
- r5 0.379301 `c_weather` 今日の天気と降水確率
- r6 0.366076 `c_prd` PRDの書き方
- r7 0.361381 `c_board` game board state
- r8 0.345773 `c_score` ハイスコアの保存方法
- r9 0.209294 `c_license` MIT license text for a Python package

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_runtime` rank=1 cosine=0.702058 gold_is_top=`True` gap_vs_second=0.185286 delta_vs_clean=-0.016586

- r1 0.702058 `c_runtime` runtime implementation GOLD
- r2 0.516772 `c_research` research experiment
- r3 0.47482 `c_prd` PRDの書き方
- r4 0.468863 `c_score` ハイスコアの保存方法
- r5 0.465018 `c_cpu` CPU温度の取得方法
- r6 0.464041 `c_board` game board state
- r7 0.455392 `c_theme` 画面の配色テーマ
- r8 0.451744 `c_weather` 今日の天気と降水確率
- r9 0.300418 `c_license` MIT license text for a Python package

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_runtime` rank=2 cosine=0.49952 gold_is_top=`False` gap_vs_second=-0.007409 delta_vs_clean=-0.219124

- r1 0.506929 `c_theme` 画面の配色テーマ
- r2 0.49952 `c_runtime` runtime implementation GOLD
- r3 0.478544 `c_weather` 今日の天気と降水確率
- r4 0.44552 `c_research` research experiment
- r5 0.437941 `c_board` game board state
- r6 0.416717 `c_prd` PRDの書き方
- r7 0.416054 `c_score` ハイスコアの保存方法
- r8 0.403408 `c_cpu` CPU温度の取得方法
- r9 0.246694 `c_license` MIT license text for a Python package

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_runtime` rank=1 cosine=0.503653 gold_is_top=`True` gap_vs_second=0.140915 delta_vs_clean=-0.214991

- r1 0.503653 `c_runtime` runtime implementation GOLD
- r2 0.362738 `c_research` research experiment
- r3 0.346551 `c_prd` PRDの書き方
- r4 0.341314 `c_theme` 画面の配色テーマ
- r5 0.337382 `c_score` ハイスコアの保存方法
- r6 0.316329 `c_weather` 今日の天気と降水確率
- r7 0.303263 `c_cpu` CPU温度の取得方法
- r8 0.293591 `c_board` game board state
- r9 0.170058 `c_license` MIT license text for a Python package

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.664481 gold_is_top=`True` gap_vs_second=0.066973 delta_vs_clean=-0.054163

- r1 0.664481 `c_runtime` runtime implementation GOLD
- r2 0.597508 `c_research` research experiment
- r3 0.475628 `c_score` ハイスコアの保存方法
- r4 0.456346 `c_prd` PRDの書き方
- r5 0.442339 `c_theme` 画面の配色テーマ
- r6 0.43776 `c_cpu` CPU温度の取得方法
- r7 0.410695 `c_board` game board state
- r8 0.400471 `c_weather` 今日の天気と降水確率
- r9 0.280571 `c_license` MIT license text for a Python package

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_runtime` rank=1 cosine=0.663816 gold_is_top=`True` gap_vs_second=0.142271 delta_vs_clean=-0.054828

- r1 0.663816 `c_runtime` runtime implementation GOLD
- r2 0.521545 `c_research` research experiment
- r3 0.517107 `c_prd` PRDの書き方
- r4 0.488738 `c_score` ハイスコアの保存方法
- r5 0.46451 `c_cpu` CPU温度の取得方法
- r6 0.445967 `c_theme` 画面の配色テーマ
- r7 0.44579 `c_weather` 今日の天気と降水確率
- r8 0.427404 `c_board` game board state
- r9 0.293446 `c_license` MIT license text for a Python package

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_runtime` rank=1 cosine=0.502482 gold_is_top=`True` gap_vs_second=0.024991 delta_vs_clean=-0.216162

- r1 0.502482 `c_runtime` runtime implementation GOLD
- r2 0.477491 `c_weather` 今日の天気と降水確率
- r3 0.470886 `c_research` research experiment
- r4 0.466673 `c_prd` PRDの書き方
- r5 0.461033 `c_score` ハイスコアの保存方法
- r6 0.455266 `c_theme` 画面の配色テーマ
- r7 0.453784 `c_board` game board state
- r8 0.441104 `c_cpu` CPU温度の取得方法
- r9 0.291027 `c_license` MIT license text for a Python package

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_runtime` rank=3 cosine=0.452868 gold_is_top=`False` gap_vs_second=-0.019062 delta_vs_clean=-0.265776

- r1 0.47193 `c_board` game board state
- r2 0.467429 `c_score` ハイスコアの保存方法
- r3 0.452868 `c_runtime` runtime implementation GOLD
- r4 0.448066 `c_theme` 画面の配色テーマ
- r5 0.417568 `c_cpu` CPU温度の取得方法
- r6 0.395065 `c_research` research experiment
- r7 0.383604 `c_prd` PRDの書き方
- r8 0.374837 `c_weather` 今日の天気と降水確率
- r9 0.247088 `c_license` MIT license text for a Python package

### research_clean [clean] 研究用のもの

gold=`c_research` rank=1 cosine=0.756724 gold_is_top=`True` gap_vs_second=0.207492 delta_vs_clean=None

- r1 0.756724 `c_research` research experiment GOLD
- r2 0.549232 `c_prd` PRDの書き方
- r3 0.523563 `c_runtime` runtime implementation
- r4 0.497804 `c_score` ハイスコアの保存方法
- r5 0.48177 `c_theme` 画面の配色テーマ
- r6 0.454538 `c_cpu` CPU温度の取得方法
- r7 0.418587 `c_weather` 今日の天気と降水確率
- r8 0.384425 `c_board` game board state
- r9 0.322165 `c_license` MIT license text for a Python package

### research_typo [typo] けんきゅう用のもの

gold=`c_research` rank=5 cosine=0.465206 gold_is_top=`False` gap_vs_second=-0.077555 delta_vs_clean=-0.291518

- r1 0.542761 `c_score` ハイスコアの保存方法
- r2 0.508311 `c_prd` PRDの書き方
- r3 0.504555 `c_theme` 画面の配色テーマ
- r4 0.491396 `c_weather` 今日の天気と降水確率
- r5 0.465206 `c_research` research experiment GOLD
- r6 0.440565 `c_runtime` runtime implementation
- r7 0.430509 `c_cpu` CPU温度の取得方法
- r8 0.412703 `c_board` game board state
- r9 0.358441 `c_license` MIT license text for a Python package

### research_conversion [conversion] 兼休用のもの

gold=`c_research` rank=6 cosine=0.418174 gold_is_top=`False` gap_vs_second=-0.154758 delta_vs_clean=-0.33855

- r1 0.572932 `c_score` ハイスコアの保存方法
- r2 0.4941 `c_prd` PRDの書き方
- r3 0.49401 `c_theme` 画面の配色テーマ
- r4 0.461948 `c_runtime` runtime implementation
- r5 0.444739 `c_board` game board state
- r6 0.418174 `c_research` research experiment GOLD
- r7 0.413845 `c_weather` 今日の天気と降水確率
- r8 0.410217 `c_cpu` CPU温度の取得方法
- r9 0.348057 `c_license` MIT license text for a Python package

### research_missing_char [missing_char] 究用のもの

gold=`c_research` rank=4 cosine=0.582145 gold_is_top=`False` gap_vs_second=-0.012645 delta_vs_clean=-0.174579

- r1 0.59479 `c_prd` PRDの書き方
- r2 0.58909 `c_runtime` runtime implementation
- r3 0.585705 `c_score` ハイスコアの保存方法
- r4 0.582145 `c_research` research experiment GOLD
- r5 0.529831 `c_theme` 画面の配色テーマ
- r6 0.521363 `c_weather` 今日の天気と降水確率
- r7 0.517767 `c_cpu` CPU温度の取得方法
- r8 0.461536 `c_board` game board state
- r9 0.402398 `c_license` MIT license text for a Python package

### research_particle [particle_drop] 研究用もの

gold=`c_research` rank=1 cosine=0.762645 gold_is_top=`True` gap_vs_second=0.23651 delta_vs_clean=0.005921

- r1 0.762645 `c_research` research experiment GOLD
- r2 0.526135 `c_prd` PRDの書き方
- r3 0.525741 `c_runtime` runtime implementation
- r4 0.493965 `c_theme` 画面の配色テーマ
- r5 0.491212 `c_score` ハイスコアの保存方法
- r6 0.461981 `c_cpu` CPU温度の取得方法
- r7 0.420646 `c_weather` 今日の天気と降水確率
- r8 0.395228 `c_board` game board state
- r9 0.316213 `c_license` MIT license text for a Python package

### research_colloquial [colloquial] 研究用のやつ

gold=`c_research` rank=1 cosine=0.753542 gold_is_top=`True` gap_vs_second=0.218363 delta_vs_clean=-0.003182

- r1 0.753542 `c_research` research experiment GOLD
- r2 0.535179 `c_prd` PRDの書き方
- r3 0.511112 `c_runtime` runtime implementation
- r4 0.482334 `c_score` ハイスコアの保存方法
- r5 0.476996 `c_theme` 画面の配色テーマ
- r6 0.445291 `c_cpu` CPU温度の取得方法
- r7 0.401705 `c_weather` 今日の天気と降水確率
- r8 0.363352 `c_board` game board state
- r9 0.325305 `c_license` MIT license text for a Python package

### research_filler [filler] まあ研究用のものかな

gold=`c_research` rank=1 cosine=0.612778 gold_is_top=`True` gap_vs_second=0.092637 delta_vs_clean=-0.143946

- r1 0.612778 `c_research` research experiment GOLD
- r2 0.520141 `c_prd` PRDの書き方
- r3 0.466732 `c_runtime` runtime implementation
- r4 0.46266 `c_theme` 画面の配色テーマ
- r5 0.460644 `c_score` ハイスコアの保存方法
- r6 0.444814 `c_cpu` CPU温度の取得方法
- r7 0.41604 `c_weather` 今日の天気と降水確率
- r8 0.357532 `c_board` game board state
- r9 0.330571 `c_license` MIT license text for a Python package

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_research` rank=1 cosine=0.605026 gold_is_top=`True` gap_vs_second=0.097807 delta_vs_clean=-0.151698

- r1 0.605026 `c_research` research experiment GOLD
- r2 0.507219 `c_prd` PRDの書き方
- r3 0.484921 `c_score` ハイスコアの保存方法
- r4 0.484842 `c_theme` 画面の配色テーマ
- r5 0.461952 `c_runtime` runtime implementation
- r6 0.403723 `c_cpu` CPU温度の取得方法
- r7 0.403304 `c_weather` 今日の天気と降水確率
- r8 0.367093 `c_board` game board state
- r9 0.309539 `c_license` MIT license text for a Python package

### research_asr [asr_like] 兼急用のもの

gold=`c_research` rank=6 cosine=0.467036 gold_is_top=`False` gap_vs_second=-0.097423 delta_vs_clean=-0.289688

- r1 0.564459 `c_prd` PRDの書き方
- r2 0.539634 `c_score` ハイスコアの保存方法
- r3 0.508736 `c_runtime` runtime implementation
- r4 0.506197 `c_weather` 今日の天気と降水確率
- r5 0.49427 `c_theme` 画面の配色テーマ
- r6 0.467036 `c_research` research experiment GOLD
- r7 0.432699 `c_cpu` CPU温度の取得方法
- r8 0.404768 `c_board` game board state
- r9 0.352104 `c_license` MIT license text for a Python package

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_research` rank=1 cosine=0.751529 gold_is_top=`True` gap_vs_second=0.233928 delta_vs_clean=-0.005195

- r1 0.751529 `c_research` research experiment GOLD
- r2 0.517601 `c_prd` PRDの書き方
- r3 0.511737 `c_runtime` runtime implementation
- r4 0.466487 `c_theme` 画面の配色テーマ
- r5 0.462298 `c_score` ハイスコアの保存方法
- r6 0.442389 `c_cpu` CPU温度の取得方法
- r7 0.396849 `c_weather` 今日の天気と降水確率
- r8 0.365689 `c_board` game board state
- r9 0.286772 `c_license` MIT license text for a Python package

### research_compound [compound] まあけんきゅう用のも

gold=`c_research` rank=5 cosine=0.330514 gold_is_top=`False` gap_vs_second=-0.03701 delta_vs_clean=-0.42621

- r1 0.367524 `c_theme` 画面の配色テーマ
- r2 0.358047 `c_prd` PRDの書き方
- r3 0.353555 `c_weather` 今日の天気と降水確率
- r4 0.346111 `c_score` ハイスコアの保存方法
- r5 0.330514 `c_research` research experiment GOLD
- r6 0.319802 `c_board` game board state
- r7 0.309236 `c_cpu` CPU温度の取得方法
- r8 0.27763 `c_runtime` runtime implementation
- r9 0.239437 `c_license` MIT license text for a Python package
