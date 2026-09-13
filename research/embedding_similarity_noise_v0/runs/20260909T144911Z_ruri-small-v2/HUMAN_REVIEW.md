# Embedding similarity Japanese input noise v0

- run_id: `20260909T144911Z_ruri-small-v2`
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

- baseline: VRAM 3754 / 12288 MiB, RAM used 38811 / 65277 MB
- after_model_load: VRAM 3752 / 12288 MiB, RAM used 38881 / 65277 MB
- after_embed: VRAM 3752 / 12288 MiB, RAM used 38873 / 65277 MB

## ノイズ種別まとめ

- `clean`: gold_top 2/3 mean_rank=1.333 mean_gap=0.013582 mean_delta_vs_clean=None failed=['board_clean']
- `typo`: gold_top 0/3 mean_rank=3.333 mean_gap=-0.012349 mean_delta_vs_clean=-0.02405 failed=['board_typo', 'runtime_typo', 'research_typo']
- `conversion`: gold_top 2/3 mean_rank=1.667 mean_gap=0.002214 mean_delta_vs_clean=-0.023348 failed=['board_conversion']
- `missing_char`: gold_top 1/3 mean_rank=2.333 mean_gap=-0.003644 mean_delta_vs_clean=-0.021975 failed=['board_missing_char', 'runtime_missing_char']
- `particle_drop`: gold_top 3/3 mean_rank=1.0 mean_gap=0.013607 mean_delta_vs_clean=-0.001207 failed=[]
- `colloquial`: gold_top 2/3 mean_rank=2.0 mean_gap=0.002694 mean_delta_vs_clean=-0.002175 failed=['runtime_colloquial']
- `filler`: gold_top 3/3 mean_rank=1.0 mean_gap=0.015684 mean_delta_vs_clean=-0.004794 failed=[]
- `restatement`: gold_top 2/3 mean_rank=1.333 mean_gap=-0.001917 mean_delta_vs_clean=-0.011671 failed=['board_restatement']
- `asr_like`: gold_top 2/3 mean_rank=3.0 mean_gap=-0.000968 mean_delta_vs_clean=-0.021796 failed=['board_asr']
- `demonstrative`: gold_top 1/3 mean_rank=4.0 mean_gap=-0.006483 mean_delta_vs_clean=-0.019829 failed=['board_demonstrative', 'runtime_demonstrative']
- `compound`: gold_top 0/3 mean_rank=5.0 mean_gap=-0.028592 mean_delta_vs_clean=-0.038112 failed=['board_compound', 'runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'colloquial', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `board_typo` [typo] テとりすの盤面 gold_rank=4 gold_cos=0.73933 top=`c_prd` 0.752067 delta_vs_clean=-0.005295
- `board_conversion` [conversion] テトリスの番面 gold_rank=3 gold_cos=0.737392 top=`c_prd` 0.745463 delta_vs_clean=-0.007233
- `board_missing_char` [missing_char] テトリスの盤 gold_rank=3 gold_cos=0.737149 top=`c_score` 0.7499 delta_vs_clean=-0.007476
- `board_restatement` [restatement] いやスコアじゃなくてテトリスの盤面 gold_rank=2 gold_cos=0.765499 top=`c_score` 0.793852 delta_vs_clean=0.020874
- `board_asr` [asr_like] 手取り巣の盤面 gold_rank=7 gold_cos=0.726665 top=`c_score` 0.748456 delta_vs_clean=-0.01796
- `board_demonstrative` [demonstrative] そっちの盤面 gold_rank=2 gold_cos=0.757686 top=`c_prd` 0.759226 delta_vs_clean=0.013061
- `board_compound` [compound] えっとテトリスの番面のやつ gold_rank=3 gold_cos=0.754502 top=`c_theme` 0.759425 delta_vs_clean=0.009877
- `runtime_typo` [typo] 実交時に動いている実装 gold_rank=2 gold_cos=0.776069 top=`c_cpu` 0.77998 delta_vs_clean=-0.007813
- `runtime_missing_char` [missing_char] 実行時に動いている実 gold_rank=3 gold_cos=0.76452 top=`c_weather` 0.767814 delta_vs_clean=-0.019362
- `runtime_colloquial` [colloquial] 実際に動いてるほう gold_rank=4 gold_cos=0.755317 top=`c_prd` 0.77176 delta_vs_clean=-0.028565
- `runtime_demonstrative` [demonstrative] 実際に使ってる方 gold_rank=9 gold_cos=0.711629 top=`c_theme` 0.76009 delta_vs_clean=-0.072253
- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=7 gold_cos=0.722355 top=`c_board` 0.77586 delta_vs_clean=-0.061527
- `research_typo` [typo] けんきゅう用のもの gold_rank=4 gold_cos=0.759173 top=`c_score` 0.779573 delta_vs_clean=-0.059042
- `research_compound` [compound] まあけんきゅう用のも gold_rank=5 gold_cos=0.755529 top=`c_score` 0.782877 delta_vs_clean=-0.062686

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_board` rank=2 cosine=0.744625 gold_is_top=`False` gap_vs_second=-0.000466 delta_vs_clean=None

- r1 0.745091 `c_prd` PRDの書き方
- r2 0.744625 `c_board` game board state GOLD
- r3 0.743469 `c_score` ハイスコアの保存方法
- r4 0.742095 `c_theme` 画面の配色テーマ
- r5 0.73337 `c_cpu` CPU温度の取得方法
- r6 0.729174 `c_license` MIT license text for a Python package
- r7 0.728604 `c_weather` 今日の天気と降水確率
- r8 0.703749 `c_research` research experiment
- r9 0.698339 `c_runtime` runtime implementation

### board_typo [typo] テとりすの盤面

gold=`c_board` rank=4 cosine=0.73933 gold_is_top=`False` gap_vs_second=-0.012737 delta_vs_clean=-0.005295

- r1 0.752067 `c_prd` PRDの書き方
- r2 0.745804 `c_theme` 画面の配色テーマ
- r3 0.743573 `c_weather` 今日の天気と降水確率
- r4 0.73933 `c_board` game board state GOLD
- r5 0.730194 `c_score` ハイスコアの保存方法
- r6 0.725449 `c_license` MIT license text for a Python package
- r7 0.715209 `c_cpu` CPU温度の取得方法
- r8 0.708802 `c_research` research experiment
- r9 0.690738 `c_runtime` runtime implementation

### board_conversion [conversion] テトリスの番面

gold=`c_board` rank=3 cosine=0.737392 gold_is_top=`False` gap_vs_second=-0.008071 delta_vs_clean=-0.007233

- r1 0.745463 `c_prd` PRDの書き方
- r2 0.744012 `c_theme` 画面の配色テーマ
- r3 0.737392 `c_board` game board state GOLD
- r4 0.736827 `c_score` ハイスコアの保存方法
- r5 0.729982 `c_license` MIT license text for a Python package
- r6 0.723177 `c_weather` 今日の天気と降水確率
- r7 0.714512 `c_cpu` CPU温度の取得方法
- r8 0.708739 `c_research` research experiment
- r9 0.703128 `c_runtime` runtime implementation

### board_missing_char [missing_char] テトリスの盤

gold=`c_board` rank=3 cosine=0.737149 gold_is_top=`False` gap_vs_second=-0.012751 delta_vs_clean=-0.007476

- r1 0.7499 `c_score` ハイスコアの保存方法
- r2 0.743764 `c_prd` PRDの書き方
- r3 0.737149 `c_board` game board state GOLD
- r4 0.736386 `c_license` MIT license text for a Python package
- r5 0.729949 `c_weather` 今日の天気と降水確率
- r6 0.721136 `c_cpu` CPU温度の取得方法
- r7 0.7199 `c_theme` 画面の配色テーマ
- r8 0.716391 `c_runtime` runtime implementation
- r9 0.70427 `c_research` research experiment

### board_particle [particle_drop] テトリス盤面

gold=`c_board` rank=1 cosine=0.759038 gold_is_top=`True` gap_vs_second=0.001727 delta_vs_clean=0.014413

- r1 0.759038 `c_board` game board state GOLD
- r2 0.757311 `c_score` ハイスコアの保存方法
- r3 0.746883 `c_cpu` CPU温度の取得方法
- r4 0.745619 `c_prd` PRDの書き方
- r5 0.744491 `c_theme` 画面の配色テーマ
- r6 0.734413 `c_license` MIT license text for a Python package
- r7 0.73181 `c_weather` 今日の天気と降水確率
- r8 0.709068 `c_research` research experiment
- r9 0.703996 `c_runtime` runtime implementation

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_board` rank=1 cosine=0.772289 gold_is_top=`True` gap_vs_second=0.001869 delta_vs_clean=0.027664

- r1 0.772289 `c_board` game board state GOLD
- r2 0.77042 `c_score` ハイスコアの保存方法
- r3 0.767891 `c_prd` PRDの書き方
- r4 0.758258 `c_theme` 画面の配色テーマ
- r5 0.756455 `c_license` MIT license text for a Python package
- r6 0.752777 `c_cpu` CPU温度の取得方法
- r7 0.740682 `c_weather` 今日の天気と降水確率
- r8 0.727231 `c_runtime` runtime implementation
- r9 0.720684 `c_research` research experiment

### board_filler [filler] えっとテトリスの盤面

gold=`c_board` rank=1 cosine=0.763376 gold_is_top=`True` gap_vs_second=0.002312 delta_vs_clean=0.018751

- r1 0.763376 `c_board` game board state GOLD
- r2 0.761064 `c_theme` 画面の配色テーマ
- r3 0.759241 `c_score` ハイスコアの保存方法
- r4 0.755473 `c_prd` PRDの書き方
- r5 0.741462 `c_license` MIT license text for a Python package
- r6 0.738064 `c_cpu` CPU温度の取得方法
- r7 0.737209 `c_weather` 今日の天気と降水確率
- r8 0.709297 `c_runtime` runtime implementation
- r9 0.709038 `c_research` research experiment

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_board` rank=2 cosine=0.765499 gold_is_top=`False` gap_vs_second=-0.028353 delta_vs_clean=0.020874

- r1 0.793852 `c_score` ハイスコアの保存方法
- r2 0.765499 `c_board` game board state GOLD
- r3 0.758862 `c_prd` PRDの書き方
- r4 0.750948 `c_theme` 画面の配色テーマ
- r5 0.747522 `c_cpu` CPU温度の取得方法
- r6 0.734105 `c_license` MIT license text for a Python package
- r7 0.724715 `c_weather` 今日の天気と降水確率
- r8 0.714567 `c_runtime` runtime implementation
- r9 0.714454 `c_research` research experiment

### board_asr [asr_like] 手取り巣の盤面

gold=`c_board` rank=7 cosine=0.726665 gold_is_top=`False` gap_vs_second=-0.021791 delta_vs_clean=-0.01796

- r1 0.748456 `c_score` ハイスコアの保存方法
- r2 0.743245 `c_prd` PRDの書き方
- r3 0.739081 `c_weather` 今日の天気と降水確率
- r4 0.738564 `c_cpu` CPU温度の取得方法
- r5 0.736367 `c_theme` 画面の配色テーマ
- r6 0.727903 `c_license` MIT license text for a Python package
- r7 0.726665 `c_board` game board state GOLD
- r8 0.708652 `c_research` research experiment
- r9 0.695612 `c_runtime` runtime implementation

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_board` rank=2 cosine=0.757686 gold_is_top=`False` gap_vs_second=-0.00154 delta_vs_clean=0.013061

- r1 0.759226 `c_prd` PRDの書き方
- r2 0.757686 `c_board` game board state GOLD
- r3 0.753532 `c_score` ハイスコアの保存方法
- r4 0.753285 `c_weather` 今日の天気と降水確率
- r5 0.751182 `c_theme` 画面の配色テーマ
- r6 0.734302 `c_license` MIT license text for a Python package
- r7 0.729087 `c_cpu` CPU温度の取得方法
- r8 0.712261 `c_research` research experiment
- r9 0.707348 `c_runtime` runtime implementation

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_board` rank=3 cosine=0.754502 gold_is_top=`False` gap_vs_second=-0.004923 delta_vs_clean=0.009877

- r1 0.759425 `c_theme` 画面の配色テーマ
- r2 0.757338 `c_prd` PRDの書き方
- r3 0.754502 `c_board` game board state GOLD
- r4 0.751408 `c_score` ハイスコアの保存方法
- r5 0.748141 `c_license` MIT license text for a Python package
- r6 0.728879 `c_weather` 今日の天気と降水確率
- r7 0.720073 `c_cpu` CPU温度の取得方法
- r8 0.717064 `c_runtime` runtime implementation
- r9 0.712307 `c_research` research experiment

### runtime_clean [clean] 実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.783882 gold_is_top=`True` gap_vs_second=0.005752 delta_vs_clean=None

- r1 0.783882 `c_runtime` runtime implementation GOLD
- r2 0.77813 `c_cpu` CPU温度の取得方法
- r3 0.761522 `c_prd` PRDの書き方
- r4 0.753126 `c_board` game board state
- r5 0.752651 `c_theme` 画面の配色テーマ
- r6 0.75228 `c_score` ハイスコアの保存方法
- r7 0.747785 `c_license` MIT license text for a Python package
- r8 0.741768 `c_weather` 今日の天気と降水確率
- r9 0.740815 `c_research` research experiment

### runtime_typo [typo] 実交時に動いている実装

gold=`c_runtime` rank=2 cosine=0.776069 gold_is_top=`False` gap_vs_second=-0.003911 delta_vs_clean=-0.007813

- r1 0.77998 `c_cpu` CPU温度の取得方法
- r2 0.776069 `c_runtime` runtime implementation GOLD
- r3 0.757509 `c_prd` PRDの書き方
- r4 0.756013 `c_weather` 今日の天気と降水確率
- r5 0.75299 `c_board` game board state
- r6 0.750667 `c_score` ハイスコアの保存方法
- r7 0.750183 `c_license` MIT license text for a Python package
- r8 0.746451 `c_theme` 画面の配色テーマ
- r9 0.734905 `c_research` research experiment

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_runtime` rank=1 cosine=0.785105 gold_is_top=`True` gap_vs_second=0.009944 delta_vs_clean=0.001223

- r1 0.785105 `c_runtime` runtime implementation GOLD
- r2 0.775161 `c_cpu` CPU温度の取得方法
- r3 0.77252 `c_score` ハイスコアの保存方法
- r4 0.757701 `c_prd` PRDの書き方
- r5 0.749851 `c_weather` 今日の天気と降水確率
- r6 0.749729 `c_board` game board state
- r7 0.744146 `c_license` MIT license text for a Python package
- r8 0.74177 `c_theme` 画面の配色テーマ
- r9 0.732099 `c_research` research experiment

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_runtime` rank=3 cosine=0.76452 gold_is_top=`False` gap_vs_second=-0.003294 delta_vs_clean=-0.019362

- r1 0.767814 `c_weather` 今日の天気と降水確率
- r2 0.764773 `c_prd` PRDの書き方
- r3 0.76452 `c_runtime` runtime implementation GOLD
- r4 0.757994 `c_cpu` CPU温度の取得方法
- r5 0.754733 `c_score` ハイスコアの保存方法
- r6 0.749245 `c_license` MIT license text for a Python package
- r7 0.745563 `c_theme` 画面の配色テーマ
- r8 0.737121 `c_research` research experiment
- r9 0.731255 `c_board` game board state

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_runtime` rank=1 cosine=0.783432 gold_is_top=`True` gap_vs_second=0.008238 delta_vs_clean=-0.00045

- r1 0.783432 `c_runtime` runtime implementation GOLD
- r2 0.775194 `c_cpu` CPU温度の取得方法
- r3 0.756863 `c_prd` PRDの書き方
- r4 0.754781 `c_board` game board state
- r5 0.751461 `c_theme` 画面の配色テーマ
- r6 0.751426 `c_score` ハイスコアの保存方法
- r7 0.746366 `c_license` MIT license text for a Python package
- r8 0.741868 `c_weather` 今日の天気と降水確率
- r9 0.739132 `c_research` research experiment

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_runtime` rank=4 cosine=0.755317 gold_is_top=`False` gap_vs_second=-0.016443 delta_vs_clean=-0.028565

- r1 0.77176 `c_prd` PRDの書き方
- r2 0.761933 `c_cpu` CPU温度の取得方法
- r3 0.75593 `c_score` ハイスコアの保存方法
- r4 0.755317 `c_runtime` runtime implementation GOLD
- r5 0.754768 `c_weather` 今日の天気と降水確率
- r6 0.753002 `c_theme` 画面の配色テーマ
- r7 0.751148 `c_board` game board state
- r8 0.738289 `c_research` research experiment
- r9 0.728669 `c_license` MIT license text for a Python package

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_runtime` rank=1 cosine=0.780555 gold_is_top=`True` gap_vs_second=0.011789 delta_vs_clean=-0.003327

- r1 0.780555 `c_runtime` runtime implementation GOLD
- r2 0.768766 `c_cpu` CPU温度の取得方法
- r3 0.761285 `c_prd` PRDの書き方
- r4 0.754946 `c_theme` 画面の配色テーマ
- r5 0.75227 `c_score` ハイスコアの保存方法
- r6 0.747692 `c_board` game board state
- r7 0.740425 `c_license` MIT license text for a Python package
- r8 0.734653 `c_weather` 今日の天気と降水確率
- r9 0.733875 `c_research` research experiment

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.758067 gold_is_top=`True` gap_vs_second=0.003882 delta_vs_clean=-0.025815

- r1 0.758067 `c_runtime` runtime implementation GOLD
- r2 0.754185 `c_prd` PRDの書き方
- r3 0.752233 `c_cpu` CPU温度の取得方法
- r4 0.748558 `c_license` MIT license text for a Python package
- r5 0.739038 `c_theme` 画面の配色テーマ
- r6 0.736943 `c_board` game board state
- r7 0.734649 `c_research` research experiment
- r8 0.730582 `c_score` ハイスコアの保存方法
- r9 0.725302 `c_weather` 今日の天気と降水確率

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_runtime` rank=1 cosine=0.800219 gold_is_top=`True` gap_vs_second=0.01685 delta_vs_clean=0.016337

- r1 0.800219 `c_runtime` runtime implementation GOLD
- r2 0.783369 `c_cpu` CPU温度の取得方法
- r3 0.776889 `c_score` ハイスコアの保存方法
- r4 0.766868 `c_prd` PRDの書き方
- r5 0.756575 `c_board` game board state
- r6 0.754497 `c_weather` 今日の天気と降水確率
- r7 0.75219 `c_license` MIT license text for a Python package
- r8 0.748843 `c_theme` 画面の配色テーマ
- r9 0.736261 `c_research` research experiment

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_runtime` rank=9 cosine=0.711629 gold_is_top=`False` gap_vs_second=-0.048461 delta_vs_clean=-0.072253

- r1 0.76009 `c_theme` 画面の配色テーマ
- r2 0.753452 `c_prd` PRDの書き方
- r3 0.752695 `c_weather` 今日の天気と降水確率
- r4 0.751747 `c_score` ハイスコアの保存方法
- r5 0.743116 `c_board` game board state
- r6 0.741073 `c_cpu` CPU温度の取得方法
- r7 0.734611 `c_license` MIT license text for a Python package
- r8 0.722906 `c_research` research experiment
- r9 0.711629 `c_runtime` runtime implementation GOLD

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_runtime` rank=7 cosine=0.722355 gold_is_top=`False` gap_vs_second=-0.053505 delta_vs_clean=-0.061527

- r1 0.77586 `c_board` game board state
- r2 0.76965 `c_theme` 画面の配色テーマ
- r3 0.762417 `c_score` ハイスコアの保存方法
- r4 0.744927 `c_prd` PRDの書き方
- r5 0.74158 `c_cpu` CPU温度の取得方法
- r6 0.73701 `c_license` MIT license text for a Python package
- r7 0.722355 `c_runtime` runtime implementation GOLD
- r8 0.717687 `c_weather` 今日の天気と降水確率
- r9 0.699172 `c_research` research experiment

### research_clean [clean] 研究用のもの

gold=`c_research` rank=1 cosine=0.818215 gold_is_top=`True` gap_vs_second=0.035459 delta_vs_clean=None

- r1 0.818215 `c_research` research experiment GOLD
- r2 0.782756 `c_prd` PRDの書き方
- r3 0.775069 `c_license` MIT license text for a Python package
- r4 0.771916 `c_score` ハイスコアの保存方法
- r5 0.763466 `c_cpu` CPU温度の取得方法
- r6 0.759159 `c_theme` 画面の配色テーマ
- r7 0.747542 `c_board` game board state
- r8 0.745072 `c_weather` 今日の天気と降水確率
- r9 0.733368 `c_runtime` runtime implementation

### research_typo [typo] けんきゅう用のもの

gold=`c_research` rank=4 cosine=0.759173 gold_is_top=`False` gap_vs_second=-0.0204 delta_vs_clean=-0.059042

- r1 0.779573 `c_score` ハイスコアの保存方法
- r2 0.766358 `c_prd` PRDの書き方
- r3 0.762446 `c_cpu` CPU温度の取得方法
- r4 0.759173 `c_research` research experiment GOLD
- r5 0.751528 `c_license` MIT license text for a Python package
- r6 0.745633 `c_board` game board state
- r7 0.729887 `c_weather` 今日の天気と降水確率
- r8 0.729839 `c_theme` 画面の配色テーマ
- r9 0.716557 `c_runtime` runtime implementation

### research_conversion [conversion] 兼休用のもの

gold=`c_research` rank=1 cosine=0.75418 gold_is_top=`True` gap_vs_second=0.00477 delta_vs_clean=-0.064035

- r1 0.75418 `c_research` research experiment GOLD
- r2 0.74941 `c_score` ハイスコアの保存方法
- r3 0.748095 `c_prd` PRDの書き方
- r4 0.747079 `c_weather` 今日の天気と降水確率
- r5 0.742069 `c_license` MIT license text for a Python package
- r6 0.741867 `c_theme` 画面の配色テーマ
- r7 0.733752 `c_board` game board state
- r8 0.73374 `c_runtime` runtime implementation
- r9 0.733474 `c_cpu` CPU温度の取得方法

### research_missing_char [missing_char] 究用のもの

gold=`c_research` rank=1 cosine=0.779128 gold_is_top=`True` gap_vs_second=0.005114 delta_vs_clean=-0.039087

- r1 0.779128 `c_research` research experiment GOLD
- r2 0.774014 `c_score` ハイスコアの保存方法
- r3 0.768378 `c_prd` PRDの書き方
- r4 0.759646 `c_theme` 画面の配色テーマ
- r5 0.758804 `c_license` MIT license text for a Python package
- r6 0.752127 `c_cpu` CPU温度の取得方法
- r7 0.729919 `c_weather` 今日の天気と降水確率
- r8 0.729406 `c_board` game board state
- r9 0.716436 `c_runtime` runtime implementation

### research_particle [particle_drop] 研究用もの

gold=`c_research` rank=1 cosine=0.800631 gold_is_top=`True` gap_vs_second=0.030856 delta_vs_clean=-0.017584

- r1 0.800631 `c_research` research experiment GOLD
- r2 0.769775 `c_license` MIT license text for a Python package
- r3 0.767621 `c_prd` PRDの書き方
- r4 0.75394 `c_theme` 画面の配色テーマ
- r5 0.753759 `c_score` ハイスコアの保存方法
- r6 0.749827 `c_cpu` CPU温度の取得方法
- r7 0.737152 `c_board` game board state
- r8 0.729438 `c_weather` 今日の天気と降水確率
- r9 0.715394 `c_runtime` runtime implementation

### research_colloquial [colloquial] 研究用のやつ

gold=`c_research` rank=1 cosine=0.812592 gold_is_top=`True` gap_vs_second=0.022657 delta_vs_clean=-0.005623

- r1 0.812592 `c_research` research experiment GOLD
- r2 0.789935 `c_prd` PRDの書き方
- r3 0.786431 `c_license` MIT license text for a Python package
- r4 0.778955 `c_score` ハイスコアの保存方法
- r5 0.762527 `c_cpu` CPU温度の取得方法
- r6 0.754032 `c_theme` 画面の配色テーマ
- r7 0.751403 `c_board` game board state
- r8 0.743251 `c_weather` 今日の天気と降水確率
- r9 0.740088 `c_runtime` runtime implementation

### research_filler [filler] まあ研究用のものかな

gold=`c_research` rank=1 cosine=0.788408 gold_is_top=`True` gap_vs_second=0.032952 delta_vs_clean=-0.029807

- r1 0.788408 `c_research` research experiment GOLD
- r2 0.755456 `c_score` ハイスコアの保存方法
- r3 0.751284 `c_license` MIT license text for a Python package
- r4 0.750124 `c_prd` PRDの書き方
- r5 0.741279 `c_theme` 画面の配色テーマ
- r6 0.741052 `c_cpu` CPU温度の取得方法
- r7 0.732499 `c_weather` 今日の天気と降水確率
- r8 0.723839 `c_board` game board state
- r9 0.720826 `c_runtime` runtime implementation

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_research` rank=1 cosine=0.788144 gold_is_top=`True` gap_vs_second=0.01872 delta_vs_clean=-0.030071

- r1 0.788144 `c_research` research experiment GOLD
- r2 0.769424 `c_prd` PRDの書き方
- r3 0.756815 `c_score` ハイスコアの保存方法
- r4 0.74986 `c_license` MIT license text for a Python package
- r5 0.739586 `c_theme` 画面の配色テーマ
- r6 0.731107 `c_cpu` CPU温度の取得方法
- r7 0.730723 `c_board` game board state
- r8 0.7293 `c_weather` 今日の天気と降水確率
- r9 0.727744 `c_runtime` runtime implementation

### research_asr [asr_like] 兼急用のもの

gold=`c_research` rank=1 cosine=0.75445 gold_is_top=`True` gap_vs_second=0.002037 delta_vs_clean=-0.063765

- r1 0.75445 `c_research` research experiment GOLD
- r2 0.752413 `c_score` ハイスコアの保存方法
- r3 0.746505 `c_prd` PRDの書き方
- r4 0.742101 `c_weather` 今日の天気と降水確率
- r5 0.73983 `c_theme` 画面の配色テーマ
- r6 0.736415 `c_runtime` runtime implementation
- r7 0.73501 `c_license` MIT license text for a Python package
- r8 0.728672 `c_board` game board state
- r9 0.72431 `c_cpu` CPU温度の取得方法

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_research` rank=1 cosine=0.81792 gold_is_top=`True` gap_vs_second=0.030551 delta_vs_clean=-0.000295

- r1 0.81792 `c_research` research experiment GOLD
- r2 0.787369 `c_prd` PRDの書き方
- r3 0.773576 `c_license` MIT license text for a Python package
- r4 0.765993 `c_score` ハイスコアの保存方法
- r5 0.758557 `c_cpu` CPU温度の取得方法
- r6 0.747491 `c_board` game board state
- r7 0.743308 `c_theme` 画面の配色テーマ
- r8 0.73393 `c_runtime` runtime implementation
- r9 0.733137 `c_weather` 今日の天気と降水確率

### research_compound [compound] まあけんきゅう用のも

gold=`c_research` rank=5 cosine=0.755529 gold_is_top=`False` gap_vs_second=-0.027348 delta_vs_clean=-0.062686

- r1 0.782877 `c_score` ハイスコアの保存方法
- r2 0.766907 `c_cpu` CPU温度の取得方法
- r3 0.766732 `c_prd` PRDの書き方
- r4 0.762388 `c_license` MIT license text for a Python package
- r5 0.755529 `c_research` research experiment GOLD
- r6 0.753143 `c_board` game board state
- r7 0.745071 `c_theme` 画面の配色テーマ
- r8 0.738102 `c_runtime` runtime implementation
- r9 0.737781 `c_weather` 今日の天気と降水確率
