# Embedding similarity Japanese input noise v0

- run_id: `20260909T150421Z_ruri-small-v2_agent-slots`
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

- baseline: VRAM 3766 / 12288 MiB, RAM used 39524 / 65277 MB
- after_model_load: VRAM 3765 / 12288 MiB, RAM used 39642 / 65277 MB
- after_embed: VRAM 3765 / 12288 MiB, RAM used 39798 / 65277 MB

## Agent slot（Goal / Meaning / Focus / Target Role）

仮対応。Production スキーマではない。

- intended_slot_top: 15/30 (0.5)
- correct_object_top: 26/30 (0.8667)
- confusion: {'intended_slot': 15, 'same_object_other_slot:focus': 2, 'same_object_other_slot:meaning': 9, 'other_object:board:meaning': 3, 'unrelated:goal': 1}
- top_slot_type: {'meaning': 27, 'focus': 2, 'goal': 1}
- failed: ['board_conversion', 'board_compound', 'runtime_colloquial', 'runtime_demonstrative', 'runtime_compound', 'research_typo', 'research_conversion', 'research_missing_char', 'research_particle', 'research_colloquial', 'research_filler', 'research_restatement', 'research_asr', 'research_demonstrative', 'research_compound']

  - `board_conversion` intended=`c_meaning_board` rank=2 top=`c_focus_board` same_object_other_slot:focus
  - `board_compound` intended=`c_meaning_board` rank=2 top=`c_focus_board` same_object_other_slot:focus
  - `runtime_colloquial` intended=`c_role_runtime` rank=3 top=`c_meaning_runtime` same_object_other_slot:meaning
  - `runtime_demonstrative` intended=`c_role_runtime` rank=7 top=`c_meaning_runtime` same_object_other_slot:meaning
  - `runtime_compound` intended=`c_role_runtime` rank=5 top=`c_meaning_board` other_object:board:meaning
  - `research_typo` intended=`c_role_research` rank=9 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_conversion` intended=`c_role_research` rank=16 top=`c_goal_weather` unrelated:goal
  - `research_missing_char` intended=`c_role_research` rank=7 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_particle` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_colloquial` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_filler` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_restatement` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_asr` intended=`c_role_research` rank=17 top=`c_meaning_board` other_object:board:meaning
  - `research_demonstrative` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_compound` intended=`c_role_research` rank=9 top=`c_meaning_board` other_object:board:meaning

## ノイズ種別まとめ

- `clean`: gold_top 2/3 mean_rank=1.333 mean_gap=0.023509 mean_delta_vs_clean=None failed=['research_clean']
- `typo`: gold_top 2/3 mean_rank=3.667 mean_gap=0.015454 mean_delta_vs_clean=-0.052534 failed=['research_typo']
- `conversion`: gold_top 1/3 mean_rank=6.333 mean_gap=0.000908 mean_delta_vs_clean=-0.077768 failed=['board_conversion', 'research_conversion']
- `missing_char`: gold_top 2/3 mean_rank=3.0 mean_gap=-0.004575 mean_delta_vs_clean=-0.070336 failed=['research_missing_char']
- `particle_drop`: gold_top 2/3 mean_rank=1.333 mean_gap=0.019425 mean_delta_vs_clean=-0.012276 failed=['research_particle']
- `colloquial`: gold_top 1/3 mean_rank=2.0 mean_gap=-0.004891 mean_delta_vs_clean=-0.047007 failed=['runtime_colloquial', 'research_colloquial']
- `filler`: gold_top 2/3 mean_rank=1.333 mean_gap=0.026678 mean_delta_vs_clean=-0.016424 failed=['research_filler']
- `restatement`: gold_top 2/3 mean_rank=1.333 mean_gap=0.028909 mean_delta_vs_clean=-0.023198 failed=['research_restatement']
- `asr_like`: gold_top 2/3 mean_rank=6.333 mean_gap=0.006816 mean_delta_vs_clean=-0.070174 failed=['research_asr']
- `demonstrative`: gold_top 1/3 mean_rank=3.333 mean_gap=-0.001414 mean_delta_vs_clean=-0.067203 failed=['runtime_demonstrative', 'research_demonstrative']
- `compound`: gold_top 0/3 mean_rank=5.333 mean_gap=-0.034135 mean_delta_vs_clean=-0.111509 failed=['board_compound', 'runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'particle_drop', 'colloquial', 'filler', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `board_conversion` [conversion] テトリスの番面 gold_rank=2 gold_cos=0.778851 top=`c_focus_board` 0.788217 delta_vs_clean=-0.050966
- `board_compound` [compound] えっとテトリスの番面のやつ gold_rank=2 gold_cos=0.778627 top=`c_focus_board` 0.78045 delta_vs_clean=-0.05119
- `runtime_colloquial` [colloquial] 実際に動いてるほう gold_rank=3 gold_cos=0.789992 top=`c_meaning_runtime` 0.799929 delta_vs_clean=-0.148106
- `runtime_demonstrative` [demonstrative] 実際に使ってる方 gold_rank=7 gold_cos=0.745372 top=`c_meaning_runtime` 0.758691 delta_vs_clean=-0.192726
- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=5 gold_cos=0.748242 top=`c_meaning_board` 0.817381 delta_vs_clean=-0.189856
- `research_typo` [typo] けんきゅう用のもの gold_rank=9 gold_cos=0.76296 top=`c_meaning_research` 0.785986 delta_vs_clean=-0.092596
- `research_conversion` [conversion] 兼休用のもの gold_rank=16 gold_cos=0.723932 top=`c_goal_weather` 0.775884 delta_vs_clean=-0.131624
- `research_missing_char` [missing_char] 究用のもの gold_rank=7 gold_cos=0.772263 top=`c_meaning_research` 0.812881 delta_vs_clean=-0.083293
- `research_particle` [particle_drop] 研究用もの gold_rank=2 gold_cos=0.816399 top=`c_meaning_research` 0.858397 delta_vs_clean=-0.039157
- `research_colloquial` [colloquial] 研究用のやつ gold_rank=2 gold_cos=0.851099 top=`c_meaning_research` 0.872838 delta_vs_clean=-0.004457
- `research_filler` [filler] まあ研究用のものかな gold_rank=2 gold_cos=0.827722 top=`c_meaning_research` 0.85087 delta_vs_clean=-0.027834
- `research_restatement` [restatement] 本番じゃなくて研究用のもの gold_rank=2 gold_cos=0.832665 top=`c_meaning_research` 0.846283 delta_vs_clean=-0.022891
- `research_asr` [asr_like] 兼急用のもの gold_rank=17 gold_cos=0.724851 top=`c_meaning_board` 0.775099 delta_vs_clean=-0.130705
- `research_demonstrative` [demonstrative] 研究用のほう gold_rank=2 gold_cos=0.844788 top=`c_meaning_research` 0.873658 delta_vs_clean=-0.010768
- `research_compound` [compound] まあけんきゅう用のも gold_rank=9 gold_cos=0.762074 top=`c_meaning_board` 0.793518 delta_vs_clean=-0.093482

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_meaning_board` rank=1 cosine=0.829817 gold_is_top=`True` gap_vs_second=0.018396 delta_vs_clean=None

- r1 0.829817 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.811421 `c_role_board` Target Role: 盤面の観測データ
- r3 0.783497 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.783276 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r5 0.745638 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.735941 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.735244 `c_focus_license` Focus path: LICENSE
- r8 0.732075 `c_role_research` Target Role: 研究用の実験経路
- r9 0.730355 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.730268 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.729299 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.72872 `c_goal_research` Goal: 研究用コードを読んで要約する
- r13 0.724794 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r14 0.722713 `c_meaning_research` Meaning: 研究用の実験
- r15 0.71921 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r16 0.714825 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r17 0.71032 `c_role_followup` Target Role: followup_investigation の追加調査

### board_typo [typo] テとりすの盤面

gold=`c_meaning_board` rank=1 cosine=0.812725 gold_is_top=`True` gap_vs_second=0.006147 delta_vs_clean=-0.017092

- r1 0.812725 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.806578 `c_role_board` Target Role: 盤面の観測データ
- r3 0.791576 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.781138 `c_focus_board` Focus path: tetris/board_state.py
- r5 0.741309 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.74014 `c_focus_license` Focus path: LICENSE
- r7 0.736134 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.735633 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.726382 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.721669 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r11 0.719624 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.719097 `c_role_research` Target Role: 研究用の実験経路
- r13 0.719015 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r14 0.716558 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.711952 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.710563 `c_meaning_research` Meaning: 研究用の実験
- r17 0.703283 `c_role_followup` Target Role: followup_investigation の追加調査

### board_conversion [conversion] テトリスの番面

gold=`c_meaning_board` rank=2 cosine=0.778851 gold_is_top=`False` gap_vs_second=-0.009366 delta_vs_clean=-0.050966

- r1 0.788217 `c_focus_board` Focus path: tetris/board_state.py
- r2 0.778851 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r3 0.767443 `c_role_board` Target Role: 盤面の観測データ
- r4 0.754344 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r5 0.751236 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.748708 `c_focus_license` Focus path: LICENSE
- r7 0.747542 `c_role_runtime` Target Role: 実行時の本番経路
- r8 0.739787 `c_role_research` Target Role: 研究用の実験経路
- r9 0.732748 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.730514 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.729079 `c_meaning_research` Meaning: 研究用の実験
- r12 0.72661 `c_meaning_score` Meaning: ハイスコアの保存方法
- r13 0.725012 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r14 0.71819 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.715546 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r16 0.713938 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.711692 `c_meaning_runtime` Meaning: 実行時に動いている実装

### board_missing_char [missing_char] テトリスの盤

gold=`c_meaning_board` rank=1 cosine=0.797767 gold_is_top=`True` gap_vs_second=0.003841 delta_vs_clean=-0.03205

- r1 0.797767 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.793926 `c_role_board` Target Role: 盤面の観測データ
- r3 0.778354 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.760596 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r5 0.742472 `c_role_runtime` Target Role: 実行時の本番経路
- r6 0.739392 `c_role_research` Target Role: 研究用の実験経路
- r7 0.738542 `c_focus_license` Focus path: LICENSE
- r8 0.737773 `c_focus_research` Focus path: research/experiment_harness.py
- r9 0.733237 `c_meaning_score` Meaning: ハイスコアの保存方法
- r10 0.732707 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r11 0.73049 `c_goal_research` Goal: 研究用コードを読んで要約する
- r12 0.724738 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.720458 `c_meaning_research` Meaning: 研究用の実験
- r14 0.717023 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r15 0.710787 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.709955 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r17 0.70964 `c_goal_runtime` Goal: 実行時コードを読んで要約する

### board_particle [particle_drop] テトリス盤面

gold=`c_meaning_board` rank=1 cosine=0.83621 gold_is_top=`True` gap_vs_second=0.012364 delta_vs_clean=0.006393

- r1 0.83621 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.823846 `c_role_board` Target Role: 盤面の観測データ
- r3 0.79127 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.788382 `c_focus_board` Focus path: tetris/board_state.py
- r5 0.750545 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.748343 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.742977 `c_focus_license` Focus path: LICENSE
- r8 0.74047 `c_role_research` Target Role: 研究用の実験経路
- r9 0.739225 `c_meaning_score` Meaning: ハイスコアの保存方法
- r10 0.736956 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.736874 `c_goal_weather` Goal: 今日の天気を調べる
- r12 0.734829 `c_goal_research` Goal: 研究用コードを読んで要約する
- r13 0.731009 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r14 0.729288 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.723075 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r16 0.721456 `c_meaning_research` Meaning: 研究用の実験
- r17 0.717951 `c_role_followup` Target Role: followup_investigation の追加調査

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_meaning_board` rank=1 cosine=0.841359 gold_is_top=`True` gap_vs_second=0.017002 delta_vs_clean=0.011542

- r1 0.841359 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.824357 `c_role_board` Target Role: 盤面の観測データ
- r3 0.794788 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.7855 `c_focus_board` Focus path: tetris/board_state.py
- r5 0.760288 `c_role_runtime` Target Role: 実行時の本番経路
- r6 0.755615 `c_role_research` Target Role: 研究用の実験経路
- r7 0.75425 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.751656 `c_focus_license` Focus path: LICENSE
- r9 0.751009 `c_focus_research` Focus path: research/experiment_harness.py
- r10 0.750737 `c_goal_research` Goal: 研究用コードを読んで要約する
- r11 0.746375 `c_goal_weather` Goal: 今日の天気を調べる
- r12 0.74551 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.744646 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r14 0.743289 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r15 0.742485 `c_meaning_research` Meaning: 研究用の実験
- r16 0.737362 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r17 0.727929 `c_role_followup` Target Role: followup_investigation の追加調査

### board_filler [filler] えっとテトリスの盤面

gold=`c_meaning_board` rank=1 cosine=0.831914 gold_is_top=`True` gap_vs_second=0.024073 delta_vs_clean=0.002097

- r1 0.831914 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.807841 `c_role_board` Target Role: 盤面の観測データ
- r3 0.790468 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.789554 `c_focus_board` Focus path: tetris/board_state.py
- r5 0.750197 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.745605 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.744166 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.744023 `c_focus_license` Focus path: LICENSE
- r9 0.739343 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.739265 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.736244 `c_role_research` Target Role: 研究用の実験経路
- r12 0.734093 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r13 0.732466 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.728257 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.728198 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r16 0.72522 `c_meaning_research` Meaning: 研究用の実験
- r17 0.719563 `c_role_followup` Target Role: followup_investigation の追加調査

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_meaning_board` rank=1 cosine=0.828648 gold_is_top=`True` gap_vs_second=0.025054 delta_vs_clean=-0.001169

- r1 0.828648 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.803594 `c_role_board` Target Role: 盤面の観測データ
- r3 0.799173 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.782952 `c_focus_board` Focus path: tetris/board_state.py
- r5 0.7765 `c_meaning_score` Meaning: ハイスコアの保存方法
- r6 0.76124 `c_goal_research` Goal: 研究用コードを読んで要約する
- r7 0.75909 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.756353 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.75373 `c_focus_license` Focus path: LICENSE
- r10 0.748326 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.745104 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r12 0.742634 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.741345 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r14 0.739664 `c_role_research` Target Role: 研究用の実験経路
- r15 0.726136 `c_meaning_research` Meaning: 研究用の実験
- r16 0.723276 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.722976 `c_meaning_runtime` Meaning: 実行時に動いている実装

### board_asr [asr_like] 手取り巣の盤面

gold=`c_meaning_board` rank=1 cosine=0.794806 gold_is_top=`True` gap_vs_second=0.003634 delta_vs_clean=-0.035011

- r1 0.794806 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.791172 `c_role_board` Target Role: 盤面の観測データ
- r3 0.781649 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.781563 `c_focus_board` Focus path: tetris/board_state.py
- r5 0.773934 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.762492 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.747678 `c_focus_license` Focus path: LICENSE
- r8 0.745296 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r9 0.744912 `c_role_research` Target Role: 研究用の実験経路
- r10 0.743341 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r11 0.73957 `c_goal_research` Goal: 研究用コードを読んで要約する
- r12 0.735662 `c_meaning_score` Meaning: ハイスコアの保存方法
- r13 0.73295 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r14 0.7312 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.730969 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.729218 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.720474 `c_meaning_research` Meaning: 研究用の実験

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_meaning_board` rank=1 cosine=0.831702 gold_is_top=`True` gap_vs_second=0.037947 delta_vs_clean=0.001885

- r1 0.831702 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.793755 `c_role_board` Target Role: 盤面の観測データ
- r3 0.789984 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.776813 `c_focus_board` Focus path: tetris/board_state.py
- r5 0.763631 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.753729 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.750486 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.750203 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.749692 `c_focus_license` Focus path: LICENSE
- r10 0.738952 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r11 0.7355 `c_goal_research` Goal: 研究用コードを読んで要約する
- r12 0.734639 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.733029 `c_meaning_research` Meaning: 研究用の実験
- r14 0.732136 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.729008 `c_role_research` Target Role: 研究用の実験経路
- r16 0.727786 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r17 0.718135 `c_role_followup` Target Role: followup_investigation の追加調査

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_meaning_board` rank=2 cosine=0.778627 gold_is_top=`False` gap_vs_second=-0.001823 delta_vs_clean=-0.05119

- r1 0.78045 `c_focus_board` Focus path: tetris/board_state.py
- r2 0.778627 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r3 0.764182 `c_role_board` Target Role: 盤面の観測データ
- r4 0.752887 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r5 0.751727 `c_role_runtime` Target Role: 実行時の本番経路
- r6 0.750127 `c_focus_license` Focus path: LICENSE
- r7 0.748346 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.747237 `c_role_research` Target Role: 研究用の実験経路
- r9 0.741217 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.737283 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.73728 `c_goal_weather` Goal: 今日の天気を調べる
- r12 0.735637 `c_meaning_research` Meaning: 研究用の実験
- r13 0.731178 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r14 0.72427 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r15 0.721281 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.720864 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r17 0.717633 `c_meaning_cpu` Meaning: CPU温度の取得方法

### runtime_clean [clean] 実行時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.938098 gold_is_top=`True` gap_vs_second=0.08753 delta_vs_clean=None

- r1 0.938098 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.850568 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r3 0.844181 `c_role_runtime` Target Role: 実行時の本番経路
- r4 0.824568 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.81375 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.809575 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.794578 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.788433 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.779764 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.773495 `c_meaning_research` Meaning: 研究用の実験
- r11 0.773213 `c_role_research` Target Role: 研究用の実験経路
- r12 0.768993 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r13 0.768468 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.766823 `c_role_board` Target Role: 盤面の観測データ
- r15 0.766131 `c_meaning_score` Meaning: ハイスコアの保存方法
- r16 0.759725 `c_focus_license` Focus path: LICENSE
- r17 0.752204 `c_role_followup` Target Role: followup_investigation の追加調査

### runtime_typo [typo] 実交時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.890184 gold_is_top=`True` gap_vs_second=0.063241 delta_vs_clean=-0.047914

- r1 0.890184 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.826943 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.810135 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.808693 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.801428 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.795314 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.793192 `c_meaning_board` Meaning: ゲームの盤面状態
- r8 0.790288 `c_role_board` Target Role: 盤面の観測データ
- r9 0.77733 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.775876 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.77459 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r12 0.774002 `c_role_research` Target Role: 研究用の実験経路
- r13 0.768276 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.763693 `c_meaning_research` Meaning: 研究用の実験
- r15 0.763293 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.761208 `c_focus_license` Focus path: LICENSE
- r17 0.755783 `c_meaning_score` Meaning: ハイスコアの保存方法

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.887384 gold_is_top=`True` gap_vs_second=0.064043 delta_vs_clean=-0.050714

- r1 0.887384 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.823341 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.813321 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.810432 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.799406 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.791883 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.791547 `c_meaning_board` Meaning: ゲームの盤面状態
- r8 0.791035 `c_role_board` Target Role: 盤面の観測データ
- r9 0.78268 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.777338 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.776975 `c_focus_license` Focus path: LICENSE
- r12 0.776585 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.773798 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r14 0.769516 `c_role_research` Target Role: 研究用の実験経路
- r15 0.763398 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.762546 `c_meaning_research` Meaning: 研究用の実験
- r17 0.762297 `c_goal_weather` Goal: 今日の天気を調べる

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_meaning_runtime` rank=1 cosine=0.842433 gold_is_top=`True` gap_vs_second=0.023053 delta_vs_clean=-0.095665

- r1 0.842433 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.81938 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.816913 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.797267 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.785423 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.78525 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.784994 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.781575 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.780512 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.778727 `c_focus_license` Focus path: LICENSE
- r11 0.77347 `c_meaning_research` Meaning: 研究用の実験
- r12 0.769881 `c_role_research` Target Role: 研究用の実験経路
- r13 0.767826 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r14 0.76446 `c_role_board` Target Role: 盤面の観測データ
- r15 0.75822 `c_meaning_score` Meaning: ハイスコアの保存方法
- r16 0.757902 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.731468 `c_role_followup` Target Role: followup_investigation の追加調査

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.934035 gold_is_top=`True` gap_vs_second=0.087909 delta_vs_clean=-0.004063

- r1 0.934035 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.846126 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r3 0.838923 `c_role_runtime` Target Role: 実行時の本番経路
- r4 0.823062 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.813024 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.808183 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.788872 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.788536 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.777107 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.769925 `c_meaning_research` Meaning: 研究用の実験
- r11 0.767942 `c_role_research` Target Role: 研究用の実験経路
- r12 0.766227 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.764272 `c_role_board` Target Role: 盤面の観測データ
- r14 0.763947 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r15 0.76369 `c_meaning_score` Meaning: ハイスコアの保存方法
- r16 0.760906 `c_focus_license` Focus path: LICENSE
- r17 0.750041 `c_role_followup` Target Role: followup_investigation の追加調査

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_role_runtime` rank=3 cosine=0.789992 gold_is_top=`False` gap_vs_second=-0.009937 delta_vs_clean=-0.148106

- r1 0.799929 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r2 0.794695 `c_meaning_board` Meaning: ゲームの盤面状態
- r3 0.789992 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r4 0.77382 `c_focus_research` Focus path: research/experiment_harness.py
- r5 0.7717 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.771672 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r7 0.76788 `c_goal_weather` Goal: 今日の天気を調べる
- r8 0.767825 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r9 0.765111 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r10 0.764709 `c_role_board` Target Role: 盤面の観測データ
- r11 0.762049 `c_goal_research` Goal: 研究用コードを読んで要約する
- r12 0.759795 `c_focus_license` Focus path: LICENSE
- r13 0.759108 `c_meaning_research` Meaning: 研究用の実験
- r14 0.758948 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r15 0.753664 `c_role_research` Target Role: 研究用の実験経路
- r16 0.747851 `c_meaning_score` Meaning: ハイスコアの保存方法
- r17 0.72577 `c_role_followup` Target Role: followup_investigation の追加調査

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_meaning_runtime` rank=1 cosine=0.914563 gold_is_top=`True` gap_vs_second=0.07911 delta_vs_clean=-0.023535

- r1 0.914563 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.835453 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r3 0.835397 `c_role_runtime` Target Role: 実行時の本番経路
- r4 0.814499 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.800507 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.798091 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.783013 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.779336 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.769387 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.767032 `c_role_research` Target Role: 研究用の実験経路
- r11 0.76365 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.762585 `c_meaning_research` Meaning: 研究用の実験
- r13 0.757609 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r14 0.755927 `c_focus_license` Focus path: LICENSE
- r15 0.754028 `c_role_board` Target Role: 盤面の観測データ
- r16 0.753197 `c_goal_weather` Goal: 今日の天気を調べる
- r17 0.747486 `c_role_followup` Target Role: followup_investigation の追加調査

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.892564 gold_is_top=`True` gap_vs_second=0.075291 delta_vs_clean=-0.045534

- r1 0.892564 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.817273 `c_meaning_research` Meaning: 研究用の実験
- r3 0.807178 `c_role_runtime` Target Role: 実行時の本番経路
- r4 0.806107 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.794459 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.794421 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r7 0.792059 `c_role_research` Target Role: 研究用の実験経路
- r8 0.789645 `c_goal_research` Goal: 研究用コードを読んで要約する
- r9 0.788679 `c_focus_board` Focus path: tetris/board_state.py
- r10 0.770419 `c_meaning_board` Meaning: ゲームの盤面状態
- r11 0.758236 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.749109 `c_role_board` Target Role: 盤面の観測データ
- r13 0.747426 `c_focus_license` Focus path: LICENSE
- r14 0.74483 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.742812 `c_meaning_score` Meaning: ハイスコアの保存方法
- r16 0.740759 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r17 0.737982 `c_role_followup` Target Role: followup_investigation の追加調査

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_meaning_runtime` rank=1 cosine=0.893291 gold_is_top=`True` gap_vs_second=0.067061 delta_vs_clean=-0.044807

- r1 0.893291 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.82623 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.818207 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.817934 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.802563 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.792626 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.791851 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.790209 `c_role_board` Target Role: 盤面の観測データ
- r9 0.78481 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.784225 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.780224 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.778477 `c_focus_license` Focus path: LICENSE
- r13 0.772642 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r14 0.772435 `c_role_research` Target Role: 研究用の実験経路
- r15 0.767427 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.766153 `c_goal_weather` Goal: 今日の天気を調べる
- r17 0.765322 `c_meaning_research` Meaning: 研究用の実験

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_role_runtime` rank=7 cosine=0.745372 gold_is_top=`False` gap_vs_second=-0.013319 delta_vs_clean=-0.192726

- r1 0.758691 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r2 0.755647 `c_meaning_board` Meaning: ゲームの盤面状態
- r3 0.754962 `c_focus_license` Focus path: LICENSE
- r4 0.752842 `c_meaning_research` Meaning: 研究用の実験
- r5 0.747665 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.747247 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.745372 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r8 0.737367 `c_role_board` Target Role: 盤面の観測データ
- r9 0.735003 `c_meaning_score` Meaning: ハイスコアの保存方法
- r10 0.734767 `c_goal_research` Goal: 研究用コードを読んで要約する
- r11 0.734542 `c_focus_board` Focus path: tetris/board_state.py
- r12 0.733281 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r13 0.732723 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r14 0.732306 `c_role_research` Target Role: 研究用の実験経路
- r15 0.730417 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r16 0.72906 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.70123 `c_role_followup` Target Role: followup_investigation の追加調査

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_role_runtime` rank=5 cosine=0.748242 gold_is_top=`False` gap_vs_second=-0.069139 delta_vs_clean=-0.189856

- r1 0.817381 `c_meaning_board` Meaning: ゲームの盤面状態
- r2 0.757998 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r3 0.757288 `c_focus_license` Focus path: LICENSE
- r4 0.754804 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r5 0.748242 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r6 0.741372 `c_focus_board` Focus path: tetris/board_state.py
- r7 0.740687 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r8 0.740258 `c_meaning_score` Meaning: ハイスコアの保存方法
- r9 0.739639 `c_focus_research` Focus path: research/experiment_harness.py
- r10 0.739006 `c_goal_research` Goal: 研究用コードを読んで要約する
- r11 0.737744 `c_role_board` Target Role: 盤面の観測データ
- r12 0.737485 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r13 0.735537 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.725222 `c_meaning_research` Meaning: 研究用の実験
- r15 0.724706 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.713297 `c_role_research` Target Role: 研究用の実験経路
- r17 0.686068 `c_role_followup` Target Role: followup_investigation の追加調査

### research_clean [clean] 研究用のもの

gold=`c_role_research` rank=2 cosine=0.855556 gold_is_top=`False` gap_vs_second=-0.035399 delta_vs_clean=None

- r1 0.890955 `c_meaning_research` Meaning: 研究用の実験
- r2 0.855556 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.840161 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.805105 `c_focus_research` Focus path: research/experiment_harness.py
- r5 0.803136 `c_role_board` Target Role: 盤面の観測データ
- r6 0.784404 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.784015 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.778654 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.778646 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r10 0.776351 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.772615 `c_role_followup` Target Role: followup_investigation の追加調査
- r12 0.772363 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r13 0.770334 `c_role_runtime` Target Role: 実行時の本番経路
- r14 0.765325 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r15 0.762848 `c_focus_license` Focus path: LICENSE
- r16 0.753071 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.750556 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_typo [typo] けんきゅう用のもの

gold=`c_role_research` rank=9 cosine=0.76296 gold_is_top=`False` gap_vs_second=-0.023026 delta_vs_clean=-0.092596

- r1 0.785986 `c_meaning_research` Meaning: 研究用の実験
- r2 0.784629 `c_meaning_board` Meaning: ゲームの盤面状態
- r3 0.78162 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.778524 `c_role_board` Target Role: 盤面の観測データ
- r5 0.776714 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r6 0.769774 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.76902 `c_goal_weather` Goal: 今日の天気を調べる
- r8 0.766223 `c_focus_license` Focus path: LICENSE
- r9 0.76296 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r10 0.756778 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.756195 `c_focus_research` Focus path: research/experiment_harness.py
- r12 0.751008 `c_role_runtime` Target Role: 実行時の本番経路
- r13 0.748731 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r14 0.736686 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.736142 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.731504 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.729509 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_conversion [conversion] 兼休用のもの

gold=`c_role_research` rank=16 cosine=0.723932 gold_is_top=`False` gap_vs_second=-0.051952 delta_vs_clean=-0.131624

- r1 0.775884 `c_goal_weather` Goal: 今日の天気を調べる
- r2 0.771561 `c_focus_license` Focus path: LICENSE
- r3 0.76341 `c_meaning_board` Meaning: ゲームの盤面状態
- r4 0.759486 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r5 0.75287 `c_focus_board` Focus path: tetris/board_state.py
- r6 0.751925 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.7509 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.749681 `c_goal_research` Goal: 研究用コードを読んで要約する
- r9 0.747654 `c_role_board` Target Role: 盤面の観測データ
- r10 0.746475 `c_meaning_research` Meaning: 研究用の実験
- r11 0.745339 `c_role_runtime` Target Role: 実行時の本番経路
- r12 0.744408 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r13 0.743966 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r14 0.741511 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.735198 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.723932 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r17 0.718289 `c_role_followup` Target Role: followup_investigation の追加調査

### research_missing_char [missing_char] 究用のもの

gold=`c_role_research` rank=7 cosine=0.772263 gold_is_top=`False` gap_vs_second=-0.040618 delta_vs_clean=-0.083293

- r1 0.812881 `c_meaning_research` Meaning: 研究用の実験
- r2 0.788734 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.781876 `c_meaning_score` Meaning: ハイスコアの保存方法
- r4 0.777288 `c_meaning_board` Meaning: ゲームの盤面状態
- r5 0.775698 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r6 0.773689 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.772263 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r8 0.767864 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.762201 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.755312 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r11 0.750012 `c_role_board` Target Role: 盤面の観測データ
- r12 0.748737 `c_focus_license` Focus path: LICENSE
- r13 0.745905 `c_focus_board` Focus path: tetris/board_state.py
- r14 0.740302 `c_role_runtime` Target Role: 実行時の本番経路
- r15 0.73934 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r16 0.722558 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.721323 `c_role_followup` Target Role: followup_investigation の追加調査

### research_particle [particle_drop] 研究用もの

gold=`c_role_research` rank=2 cosine=0.816399 gold_is_top=`False` gap_vs_second=-0.041998 delta_vs_clean=-0.039157

- r1 0.858397 `c_meaning_research` Meaning: 研究用の実験
- r2 0.816399 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.806435 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.786129 `c_focus_research` Focus path: research/experiment_harness.py
- r5 0.773958 `c_role_board` Target Role: 盤面の観測データ
- r6 0.770796 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.769849 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.763893 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.760426 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.759517 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.756619 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r12 0.753302 `c_focus_license` Focus path: LICENSE
- r13 0.752909 `c_role_runtime` Target Role: 実行時の本番経路
- r14 0.745929 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r15 0.745244 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.739871 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.733918 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_colloquial [colloquial] 研究用のやつ

gold=`c_role_research` rank=2 cosine=0.851099 gold_is_top=`False` gap_vs_second=-0.021739 delta_vs_clean=-0.004457

- r1 0.872838 `c_meaning_research` Meaning: 研究用の実験
- r2 0.851099 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.840454 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.795383 `c_role_board` Target Role: 盤面の観測データ
- r5 0.790629 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.78065 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.77818 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r8 0.776947 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.774378 `c_role_runtime` Target Role: 実行時の本番経路
- r10 0.773435 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.770171 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.769416 `c_role_followup` Target Role: followup_investigation の追加調査
- r13 0.769252 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r14 0.761124 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.754234 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r16 0.751563 `c_focus_license` Focus path: LICENSE
- r17 0.747383 `c_focus_board` Focus path: tetris/board_state.py

### research_filler [filler] まあ研究用のものかな

gold=`c_role_research` rank=2 cosine=0.827722 gold_is_top=`False` gap_vs_second=-0.023148 delta_vs_clean=-0.027834

- r1 0.85087 `c_meaning_research` Meaning: 研究用の実験
- r2 0.827722 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.810875 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.789245 `c_focus_research` Focus path: research/experiment_harness.py
- r5 0.767745 `c_role_board` Target Role: 盤面の観測データ
- r6 0.757584 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.757266 `c_role_followup` Target Role: followup_investigation の追加調査
- r8 0.754661 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.751367 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.749491 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r11 0.747263 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r12 0.747084 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r13 0.747004 `c_role_runtime` Target Role: 実行時の本番経路
- r14 0.746832 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r15 0.740691 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r16 0.736269 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.735478 `c_focus_license` Focus path: LICENSE

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_role_research` rank=2 cosine=0.832665 gold_is_top=`False` gap_vs_second=-0.013618 delta_vs_clean=-0.022891

- r1 0.846283 `c_meaning_research` Meaning: 研究用の実験
- r2 0.832665 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.818547 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.80246 `c_role_runtime` Target Role: 実行時の本番経路
- r5 0.782545 `c_focus_research` Focus path: research/experiment_harness.py
- r6 0.767558 `c_role_board` Target Role: 盤面の観測データ
- r7 0.765811 `c_meaning_board` Meaning: ゲームの盤面状態
- r8 0.763019 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r9 0.757789 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r10 0.757712 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r11 0.756191 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r12 0.75565 `c_focus_board` Focus path: tetris/board_state.py
- r13 0.754046 `c_meaning_score` Meaning: ハイスコアの保存方法
- r14 0.749804 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.74614 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.744891 `c_focus_license` Focus path: LICENSE
- r17 0.73715 `c_meaning_cpu` Meaning: CPU温度の取得方法

### research_asr [asr_like] 兼急用のもの

gold=`c_role_research` rank=17 cosine=0.724851 gold_is_top=`False` gap_vs_second=-0.050248 delta_vs_clean=-0.130705

- r1 0.775099 `c_meaning_board` Meaning: ゲームの盤面状態
- r2 0.765843 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.763195 `c_focus_license` Focus path: LICENSE
- r4 0.761152 `c_meaning_score` Meaning: ハイスコアの保存方法
- r5 0.758769 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r6 0.758173 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.755652 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.745417 `c_meaning_research` Meaning: 研究用の実験
- r9 0.74473 `c_focus_board` Focus path: tetris/board_state.py
- r10 0.744365 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r11 0.743521 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r12 0.743125 `c_goal_research` Goal: 研究用コードを読んで要約する
- r13 0.742661 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r14 0.736675 `c_role_board` Target Role: 盤面の観測データ
- r15 0.734169 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.733333 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.724851 `c_role_research` Target Role: 研究用の実験経路 GOLD

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_role_research` rank=2 cosine=0.844788 gold_is_top=`False` gap_vs_second=-0.02887 delta_vs_clean=-0.010768

- r1 0.873658 `c_meaning_research` Meaning: 研究用の実験
- r2 0.844788 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.820981 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.811262 `c_focus_research` Focus path: research/experiment_harness.py
- r5 0.778721 `c_meaning_score` Meaning: ハイスコアの保存方法
- r6 0.778411 `c_role_board` Target Role: 盤面の観測データ
- r7 0.77447 `c_role_runtime` Target Role: 実行時の本番経路
- r8 0.774198 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.772115 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.768671 `c_role_followup` Target Role: followup_investigation の追加調査
- r11 0.764081 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r12 0.76187 `c_focus_board` Focus path: tetris/board_state.py
- r13 0.759857 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r14 0.757821 `c_focus_license` Focus path: LICENSE
- r15 0.757082 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.754465 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.752715 `c_goal_runtime` Goal: 実行時コードを読んで要約する

### research_compound [compound] まあけんきゅう用のも

gold=`c_role_research` rank=9 cosine=0.762074 gold_is_top=`False` gap_vs_second=-0.031444 delta_vs_clean=-0.093482

- r1 0.793518 `c_meaning_board` Meaning: ゲームの盤面状態
- r2 0.788534 `c_meaning_research` Meaning: 研究用の実験
- r3 0.784888 `c_meaning_score` Meaning: ハイスコアの保存方法
- r4 0.78055 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r5 0.778858 `c_goal_research` Goal: 研究用コードを読んで要約する
- r6 0.774616 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.766346 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r8 0.764319 `c_focus_research` Focus path: research/experiment_harness.py
- r9 0.762074 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r10 0.761469 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r11 0.759818 `c_focus_license` Focus path: LICENSE
- r12 0.757981 `c_role_runtime` Target Role: 実行時の本番経路
- r13 0.757168 `c_role_board` Target Role: 盤面の観測データ
- r14 0.751413 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r15 0.743569 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.740785 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.734853 `c_focus_board` Focus path: tetris/board_state.py
