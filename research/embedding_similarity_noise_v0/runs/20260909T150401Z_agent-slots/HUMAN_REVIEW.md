# Embedding similarity Japanese input noise v0

- run_id: `20260909T150401Z`
- embed_model: `qwen3-embedding:0.6b`
- backend: `None`
- device: `None`
- embedding_method: `None`
- gen_model: `qwen3:14b`
- with_gen: `False`
- Production / Grill 接続: なし
- 閾値正本化: なし
- SELECTED規則: なし

`gold_is_top` はこの候補集合で意図候補が1位だった観測。SELECTED規則ではない。

## 資源

- baseline: VRAM 3773 / 12288 MiB, RAM used 39862 / 65277 MB
- after_embed: VRAM 3765 / 12288 MiB, RAM used 39761 / 65277 MB

## Agent slot（Goal / Meaning / Focus / Target Role）

仮対応。Production スキーマではない。

- intended_slot_top: 15/30 (0.5)
- correct_object_top: 27/30 (0.9)
- confusion: {'same_object_other_slot:goal': 3, 'intended_slot': 15, 'same_object_other_slot:meaning': 9, 'other_object:board:meaning': 1, 'other_object:board:goal': 2}
- top_slot_type: {'goal': 5, 'meaning': 24, 'target_role': 1}
- failed: ['board_typo', 'board_asr', 'board_compound', 'runtime_colloquial', 'runtime_demonstrative', 'runtime_compound', 'research_typo', 'research_conversion', 'research_missing_char', 'research_particle', 'research_filler', 'research_restatement', 'research_asr', 'research_demonstrative', 'research_compound']

  - `board_typo` intended=`c_meaning_board` rank=2 top=`c_goal_board` same_object_other_slot:goal
  - `board_asr` intended=`c_meaning_board` rank=2 top=`c_goal_board` same_object_other_slot:goal
  - `board_compound` intended=`c_meaning_board` rank=2 top=`c_goal_board` same_object_other_slot:goal
  - `runtime_colloquial` intended=`c_role_runtime` rank=2 top=`c_meaning_runtime` same_object_other_slot:meaning
  - `runtime_demonstrative` intended=`c_role_runtime` rank=2 top=`c_meaning_runtime` same_object_other_slot:meaning
  - `runtime_compound` intended=`c_role_runtime` rank=3 top=`c_meaning_board` other_object:board:meaning
  - `research_typo` intended=`c_role_research` rank=5 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_conversion` intended=`c_role_research` rank=10 top=`c_goal_board` other_object:board:goal
  - `research_missing_char` intended=`c_role_research` rank=4 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_particle` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_filler` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_restatement` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_asr` intended=`c_role_research` rank=5 top=`c_goal_board` other_object:board:goal
  - `research_demonstrative` intended=`c_role_research` rank=2 top=`c_meaning_research` same_object_other_slot:meaning
  - `research_compound` intended=`c_role_research` rank=7 top=`c_meaning_research` same_object_other_slot:meaning

## ノイズ種別まとめ

- `clean`: gold_top 2/3 mean_rank=1.333 mean_gap=0.080024 mean_delta_vs_clean=None failed=['research_clean']
- `typo`: gold_top 1/3 mean_rank=2.667 mean_gap=0.032325 mean_delta_vs_clean=-0.110637 failed=['board_typo', 'research_typo']
- `conversion`: gold_top 2/3 mean_rank=4.0 mean_gap=0.042578 mean_delta_vs_clean=-0.100802 failed=['research_conversion']
- `missing_char`: gold_top 2/3 mean_rank=2.0 mean_gap=0.093086 mean_delta_vs_clean=-0.045333 failed=['research_missing_char']
- `particle_drop`: gold_top 2/3 mean_rank=1.333 mean_gap=0.079408 mean_delta_vs_clean=0.006285 failed=['research_particle']
- `colloquial`: gold_top 2/3 mean_rank=1.333 mean_gap=-0.012578 mean_delta_vs_clean=-0.08565 failed=['runtime_colloquial']
- `filler`: gold_top 2/3 mean_rank=1.333 mean_gap=0.094695 mean_delta_vs_clean=-0.06125 failed=['research_filler']
- `restatement`: gold_top 2/3 mean_rank=1.333 mean_gap=0.064461 mean_delta_vs_clean=-0.067133 failed=['research_restatement']
- `asr_like`: gold_top 1/3 mean_rank=2.667 mean_gap=0.025968 mean_delta_vs_clean=-0.101128 failed=['board_asr', 'research_asr']
- `demonstrative`: gold_top 1/3 mean_rank=1.667 mean_gap=-0.022481 mean_delta_vs_clean=-0.102532 failed=['runtime_demonstrative', 'research_demonstrative']
- `compound`: gold_top 0/3 mean_rank=4.0 mean_gap=-0.059309 mean_delta_vs_clean=-0.262824 failed=['board_compound', 'runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'particle_drop', 'colloquial', 'filler', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `board_typo` [typo] テとりすの盤面 gold_rank=2 gold_cos=0.6058 top=`c_goal_board` 0.624747 delta_vs_clean=-0.048532
- `board_asr` [asr_like] 手取り巣の盤面 gold_rank=2 gold_cos=0.602407 top=`c_goal_board` 0.631432 delta_vs_clean=-0.051925
- `board_compound` [compound] えっとテトリスの番面のやつ gold_rank=2 gold_cos=0.595035 top=`c_goal_board` 0.603893 delta_vs_clean=-0.059297
- `runtime_colloquial` [colloquial] 実際に動いてるほう gold_rank=2 gold_cos=0.557301 top=`c_meaning_runtime` 0.640264 delta_vs_clean=-0.259437
- `runtime_demonstrative` [demonstrative] 実際に使ってる方 gold_rank=2 gold_cos=0.528447 top=`c_meaning_runtime` 0.597457 delta_vs_clean=-0.288291
- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=3 gold_cos=0.463107 top=`c_meaning_board` 0.529294 delta_vs_clean=-0.353631
- `research_typo` [typo] けんきゅう用のもの gold_rank=5 gold_cos=0.49422 top=`c_meaning_research` 0.562899 delta_vs_clean=-0.225549
- `research_conversion` [conversion] 兼休用のもの gold_rank=10 gold_cos=0.460836 top=`c_goal_board` 0.532651 delta_vs_clean=-0.258933
- `research_missing_char` [missing_char] 究用のもの gold_rank=4 gold_cos=0.623813 top=`c_meaning_research` 0.63715 delta_vs_clean=-0.095956
- `research_particle` [particle_drop] 研究用もの gold_rank=2 gold_cos=0.711771 top=`c_meaning_research` 0.743193 delta_vs_clean=-0.007998
- `research_filler` [filler] まあ研究用のものかな gold_rank=2 gold_cos=0.583811 top=`c_meaning_research` 0.611788 delta_vs_clean=-0.135958
- `research_restatement` [restatement] 本番じゃなくて研究用のもの gold_rank=2 gold_cos=0.629912 top=`c_meaning_research` 0.660495 delta_vs_clean=-0.089857
- `research_asr` [asr_like] 兼急用のもの gold_rank=5 gold_cos=0.507719 top=`c_goal_board` 0.575285 delta_vs_clean=-0.21205
- `research_demonstrative` [demonstrative] 研究用のほう gold_rank=2 gold_cos=0.709471 top=`c_meaning_research` 0.722481 delta_vs_clean=-0.010298
- `research_compound` [compound] まあけんきゅう用のも gold_rank=7 gold_cos=0.344226 top=`c_meaning_research` 0.447107 delta_vs_clean=-0.375543

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_meaning_board` rank=1 cosine=0.654332 gold_is_top=`True` gap_vs_second=0.029171 delta_vs_clean=None

- r1 0.654332 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.625161 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.609825 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.534041 `c_role_board` Target Role: 盤面の観測データ
- r5 0.518836 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.507755 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.507705 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r8 0.49529 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r9 0.491851 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.480244 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.46371 `c_focus_license` Focus path: LICENSE
- r12 0.44909 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r13 0.439699 `c_role_research` Target Role: 研究用の実験経路
- r14 0.433489 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.425573 `c_meaning_research` Meaning: 研究用の実験
- r16 0.393111 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.374305 `c_focus_research` Focus path: research/experiment_harness.py

### board_typo [typo] テとりすの盤面

gold=`c_meaning_board` rank=2 cosine=0.6058 gold_is_top=`False` gap_vs_second=-0.018947 delta_vs_clean=-0.048532

- r1 0.624747 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.6058 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r3 0.530632 `c_role_runtime` Target Role: 実行時の本番経路
- r4 0.528331 `c_role_board` Target Role: 盤面の観測データ
- r5 0.501301 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r6 0.498858 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.497599 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.496278 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.485228 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.481808 `c_focus_board` Focus path: tetris/board_state.py
- r11 0.477871 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.474161 `c_focus_license` Focus path: LICENSE
- r13 0.459521 `c_role_research` Target Role: 研究用の実験経路
- r14 0.451288 `c_meaning_research` Meaning: 研究用の実験
- r15 0.443433 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.378913 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.358229 `c_focus_research` Focus path: research/experiment_harness.py

### board_conversion [conversion] テトリスの番面

gold=`c_meaning_board` rank=1 cosine=0.624236 gold_is_top=`True` gap_vs_second=0.010505 delta_vs_clean=-0.030096

- r1 0.624236 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.613731 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.570109 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.525631 `c_role_board` Target Role: 盤面の観測データ
- r5 0.519632 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r6 0.510258 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.500966 `c_goal_weather` Goal: 今日の天気を調べる
- r8 0.491926 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r9 0.491685 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.488037 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.462169 `c_focus_license` Focus path: LICENSE
- r12 0.448638 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r13 0.445242 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.436528 `c_role_research` Target Role: 研究用の実験経路
- r15 0.425374 `c_meaning_research` Meaning: 研究用の実験
- r16 0.383442 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.35668 `c_focus_research` Focus path: research/experiment_harness.py

### board_missing_char [missing_char] テトリスの盤

gold=`c_meaning_board` rank=1 cosine=0.626323 gold_is_top=`True` gap_vs_second=0.021425 delta_vs_clean=-0.028009

- r1 0.626323 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.604898 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.597287 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.514493 `c_role_board` Target Role: 盤面の観測データ
- r5 0.513459 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.505931 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r7 0.496503 `c_role_runtime` Target Role: 実行時の本番経路
- r8 0.486505 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r9 0.484821 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.4846 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.460325 `c_focus_license` Focus path: LICENSE
- r12 0.432841 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r13 0.430059 `c_role_research` Target Role: 研究用の実験経路
- r14 0.423788 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.415923 `c_meaning_research` Meaning: 研究用の実験
- r16 0.387264 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.368162 `c_focus_research` Focus path: research/experiment_harness.py

### board_particle [particle_drop] テトリス盤面

gold=`c_meaning_board` rank=1 cosine=0.649382 gold_is_top=`True` gap_vs_second=0.026947 delta_vs_clean=-0.00495

- r1 0.649382 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.622435 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.612591 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.539041 `c_role_board` Target Role: 盤面の観測データ
- r5 0.50779 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.496524 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.486633 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r8 0.47365 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r9 0.472167 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.460057 `c_focus_license` Focus path: LICENSE
- r11 0.452336 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.436608 `c_role_research` Target Role: 研究用の実験経路
- r13 0.430721 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r14 0.426003 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.415213 `c_meaning_research` Meaning: 研究用の実験
- r16 0.382636 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.371773 `c_focus_research` Focus path: research/experiment_harness.py

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_meaning_board` rank=1 cosine=0.659778 gold_is_top=`True` gap_vs_second=0.039709 delta_vs_clean=0.005446

- r1 0.659778 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.620069 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.598596 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.534744 `c_role_board` Target Role: 盤面の観測データ
- r5 0.504767 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.502514 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.500859 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r8 0.487838 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r9 0.484628 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.46788 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.456298 `c_focus_license` Focus path: LICENSE
- r12 0.456136 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r13 0.43875 `c_role_research` Target Role: 研究用の実験経路
- r14 0.430491 `c_meaning_research` Meaning: 研究用の実験
- r15 0.426734 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.392031 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.375478 `c_focus_research` Focus path: research/experiment_harness.py

### board_filler [filler] えっとテトリスの盤面

gold=`c_meaning_board` rank=1 cosine=0.653773 gold_is_top=`True` gap_vs_second=0.003405 delta_vs_clean=-0.000559

- r1 0.653773 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.650368 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.596895 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.532622 `c_role_board` Target Role: 盤面の観測データ
- r5 0.513446 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r6 0.510151 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.503418 `c_role_runtime` Target Role: 実行時の本番経路
- r8 0.501728 `c_goal_research` Goal: 研究用コードを読んで要約する
- r9 0.497409 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.483282 `c_focus_license` Focus path: LICENSE
- r11 0.48187 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.471419 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r13 0.442116 `c_role_research` Target Role: 研究用の実験経路
- r14 0.441961 `c_meaning_research` Meaning: 研究用の実験
- r15 0.428009 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.388739 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.38122 `c_focus_research` Focus path: research/experiment_harness.py

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_meaning_board` rank=1 cosine=0.595868 gold_is_top=`True` gap_vs_second=0.041715 delta_vs_clean=-0.058464

- r1 0.595868 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.554153 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.537954 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.511664 `c_role_board` Target Role: 盤面の観測データ
- r5 0.485078 `c_meaning_score` Meaning: ハイスコアの保存方法
- r6 0.451862 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.445298 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.429514 `c_focus_license` Focus path: LICENSE
- r9 0.425975 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.417179 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.416656 `c_role_research` Target Role: 研究用の実験経路
- r12 0.414088 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r13 0.394064 `c_meaning_research` Meaning: 研究用の実験
- r14 0.391199 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.382738 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.338553 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.331943 `c_focus_research` Focus path: research/experiment_harness.py

### board_asr [asr_like] 手取り巣の盤面

gold=`c_meaning_board` rank=2 cosine=0.602407 gold_is_top=`False` gap_vs_second=-0.029025 delta_vs_clean=-0.051925

- r1 0.631432 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.602407 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r3 0.580947 `c_role_runtime` Target Role: 実行時の本番経路
- r4 0.568403 `c_role_board` Target Role: 盤面の観測データ
- r5 0.519572 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r6 0.517344 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.515919 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.514138 `c_role_research` Target Role: 研究用の実験経路
- r9 0.513288 `c_focus_license` Focus path: LICENSE
- r10 0.508095 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.48866 `c_role_followup` Target Role: followup_investigation の追加調査
- r12 0.487932 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.478354 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.473501 `c_meaning_research` Meaning: 研究用の実験
- r15 0.451107 `c_focus_board` Focus path: tetris/board_state.py
- r16 0.440431 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.420844 `c_focus_research` Focus path: research/experiment_harness.py

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_meaning_board` rank=1 cosine=0.645326 gold_is_top=`True` gap_vs_second=0.014578 delta_vs_clean=-0.009006

- r1 0.645326 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r2 0.630748 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.547127 `c_role_board` Target Role: 盤面の観測データ
- r4 0.528442 `c_role_runtime` Target Role: 実行時の本番経路
- r5 0.525549 `c_focus_license` Focus path: LICENSE
- r6 0.491792 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.489401 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r8 0.487004 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.485003 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.47615 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r11 0.474693 `c_focus_board` Focus path: tetris/board_state.py
- r12 0.458756 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.45323 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.449424 `c_role_research` Target Role: 研究用の実験経路
- r15 0.447488 `c_meaning_research` Meaning: 研究用の実験
- r16 0.406082 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.372517 `c_focus_research` Focus path: research/experiment_harness.py

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_meaning_board` rank=2 cosine=0.595035 gold_is_top=`False` gap_vs_second=-0.008858 delta_vs_clean=-0.059297

- r1 0.603893 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.595035 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r3 0.516197 `c_focus_board` Focus path: tetris/board_state.py
- r4 0.513145 `c_role_board` Target Role: 盤面の観測データ
- r5 0.492645 `c_role_runtime` Target Role: 実行時の本番経路
- r6 0.484953 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r7 0.479881 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r8 0.471462 `c_goal_research` Goal: 研究用コードを読んで要約する
- r9 0.463998 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.462815 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.45689 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r12 0.447596 `c_focus_license` Focus path: LICENSE
- r13 0.429068 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.428202 `c_role_research` Target Role: 研究用の実験経路
- r15 0.426396 `c_meaning_research` Meaning: 研究用の実験
- r16 0.361235 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.343465 `c_focus_research` Focus path: research/experiment_harness.py

### runtime_clean [clean] 実行時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.816738 gold_is_top=`True` gap_vs_second=0.22616 delta_vs_clean=None

- r1 0.816738 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.590578 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.585334 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.551355 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.515757 `c_role_research` Target Role: 研究用の実験経路
- r6 0.496042 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r7 0.494344 `c_role_board` Target Role: 盤面の観測データ
- r8 0.480738 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r9 0.480522 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.463814 `c_meaning_research` Meaning: 研究用の実験
- r11 0.452202 `c_meaning_board` Meaning: ゲームの盤面状態
- r12 0.44576 `c_role_followup` Target Role: followup_investigation の追加調査
- r13 0.425051 `c_focus_research` Focus path: research/experiment_harness.py
- r14 0.420527 `c_focus_license` Focus path: LICENSE
- r15 0.418266 `c_meaning_score` Meaning: ハイスコアの保存方法
- r16 0.410184 `c_goal_weather` Goal: 今日の天気を調べる
- r17 0.388923 `c_focus_board` Focus path: tetris/board_state.py

### runtime_typo [typo] 実交時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.758907 gold_is_top=`True` gap_vs_second=0.1846 delta_vs_clean=-0.057831

- r1 0.758907 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.574307 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.528582 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.513404 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.499417 `c_role_board` Target Role: 盤面の観測データ
- r6 0.489059 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r7 0.4865 `c_role_research` Target Role: 研究用の実験経路
- r8 0.471405 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.468355 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.462879 `c_role_followup` Target Role: followup_investigation の追加調査
- r11 0.451176 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.43173 `c_meaning_score` Meaning: ハイスコアの保存方法
- r13 0.431567 `c_focus_license` Focus path: LICENSE
- r14 0.42907 `c_meaning_research` Meaning: 研究用の実験
- r15 0.423405 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.389931 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.371554 `c_focus_board` Focus path: tetris/board_state.py

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.803362 gold_is_top=`True` gap_vs_second=0.189043 delta_vs_clean=-0.013376

- r1 0.803362 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.614319 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.584681 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.53837 `c_role_research` Target Role: 研究用の実験経路
- r5 0.528617 `c_role_board` Target Role: 盤面の観測データ
- r6 0.52526 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r7 0.522039 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r8 0.519344 `c_goal_research` Goal: 研究用コードを読んで要約する
- r9 0.506721 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.501344 `c_meaning_research` Meaning: 研究用の実験
- r11 0.48861 `c_role_followup` Target Role: followup_investigation の追加調査
- r12 0.486134 `c_meaning_board` Meaning: ゲームの盤面状態
- r13 0.468279 `c_meaning_score` Meaning: ハイスコアの保存方法
- r14 0.461118 `c_focus_license` Focus path: LICENSE
- r15 0.444947 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.436911 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.395611 `c_focus_board` Focus path: tetris/board_state.py

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_meaning_runtime` rank=1 cosine=0.804705 gold_is_top=`True` gap_vs_second=0.27117 delta_vs_clean=-0.012033

- r1 0.804705 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.533535 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.500406 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.453697 `c_role_research` Target Role: 研究用の実験経路
- r5 0.435641 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r6 0.414893 `c_meaning_research` Meaning: 研究用の実験
- r7 0.412838 `c_role_board` Target Role: 盤面の観測データ
- r8 0.407062 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.396737 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.395651 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r11 0.392866 `c_goal_research` Goal: 研究用コードを読んで要約する
- r12 0.36319 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.352947 `c_focus_license` Focus path: LICENSE
- r14 0.351154 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.344915 `c_focus_research` Focus path: research/experiment_harness.py
- r16 0.327842 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.308376 `c_meaning_score` Meaning: ハイスコアの保存方法

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.84854 gold_is_top=`True` gap_vs_second=0.242698 delta_vs_clean=0.031802

- r1 0.84854 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.605842 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.573715 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.542075 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.523841 `c_role_research` Target Role: 研究用の実験経路
- r6 0.504057 `c_role_board` Target Role: 盤面の観測データ
- r7 0.486784 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r8 0.485612 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r9 0.479136 `c_meaning_board` Meaning: ゲームの盤面状態
- r10 0.478745 `c_meaning_research` Meaning: 研究用の実験
- r11 0.478342 `c_goal_research` Goal: 研究用コードを読んで要約する
- r12 0.473565 `c_role_followup` Target Role: followup_investigation の追加調査
- r13 0.446722 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.446081 `c_focus_license` Focus path: LICENSE
- r15 0.423548 `c_meaning_score` Meaning: ハイスコアの保存方法
- r16 0.422634 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.404836 `c_focus_board` Focus path: tetris/board_state.py

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_role_runtime` rank=2 cosine=0.557301 gold_is_top=`False` gap_vs_second=-0.082963 delta_vs_clean=-0.259437

- r1 0.640264 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r2 0.557301 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r3 0.489815 `c_meaning_board` Meaning: ゲームの盤面状態
- r4 0.477885 `c_role_board` Target Role: 盤面の観測データ
- r5 0.472622 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.472089 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r7 0.469503 `c_role_research` Target Role: 研究用の実験経路
- r8 0.447468 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.444211 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r10 0.428147 `c_goal_research` Goal: 研究用コードを読んで要約する
- r11 0.421372 `c_focus_license` Focus path: LICENSE
- r12 0.418941 `c_meaning_research` Meaning: 研究用の実験
- r13 0.418285 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.394002 `c_meaning_score` Meaning: ハイスコアの保存方法
- r15 0.380364 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r16 0.380097 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.341398 `c_focus_research` Focus path: research/experiment_harness.py

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_meaning_runtime` rank=1 cosine=0.769504 gold_is_top=`True` gap_vs_second=0.308656 delta_vs_clean=-0.047234

- r1 0.769504 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.460848 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.423316 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.390178 `c_role_research` Target Role: 研究用の実験経路
- r5 0.384358 `c_meaning_research` Meaning: 研究用の実験
- r6 0.384146 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r7 0.375209 `c_meaning_board` Meaning: ゲームの盤面状態
- r8 0.359353 `c_role_board` Target Role: 盤面の観測データ
- r9 0.340067 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.339366 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r11 0.337866 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.324229 `c_meaning_score` Meaning: ハイスコアの保存方法
- r13 0.323831 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.306922 `c_focus_license` Focus path: LICENSE
- r15 0.305061 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.272574 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.247759 `c_focus_board` Focus path: tetris/board_state.py

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_meaning_runtime` rank=1 cosine=0.76366 gold_is_top=`True` gap_vs_second=0.18225 delta_vs_clean=-0.053078

- r1 0.76366 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.58141 `c_role_research` Target Role: 研究用の実験経路
- r3 0.570567 `c_meaning_research` Meaning: 研究用の実験
- r4 0.562117 `c_role_runtime` Target Role: 実行時の本番経路
- r5 0.534187 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r6 0.517841 `c_focus_research` Focus path: research/experiment_harness.py
- r7 0.511482 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r8 0.502935 `c_role_board` Target Role: 盤面の観測データ
- r9 0.469383 `c_role_followup` Target Role: followup_investigation の追加調査
- r10 0.468367 `c_goal_research` Goal: 研究用コードを読んで要約する
- r11 0.468124 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.441094 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r13 0.440954 `c_meaning_board` Meaning: ゲームの盤面状態
- r14 0.417206 `c_focus_license` Focus path: LICENSE
- r15 0.408146 `c_meaning_score` Meaning: ハイスコアの保存方法
- r16 0.392787 `c_goal_weather` Goal: 今日の天気を調べる
- r17 0.379445 `c_focus_board` Focus path: tetris/board_state.py

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_meaning_runtime` rank=1 cosine=0.777329 gold_is_top=`True` gap_vs_second=0.174495 delta_vs_clean=-0.039409

- r1 0.777329 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r2 0.602834 `c_role_runtime` Target Role: 実行時の本番経路
- r3 0.568462 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.525912 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r5 0.519619 `c_role_research` Target Role: 研究用の実験経路
- r6 0.514968 `c_role_board` Target Role: 盤面の観測データ
- r7 0.511176 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r8 0.497529 `c_goal_research` Goal: 研究用コードを読んで要約する
- r9 0.489947 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.481223 `c_meaning_board` Meaning: ゲームの盤面状態
- r11 0.475564 `c_meaning_research` Meaning: 研究用の実験
- r12 0.471218 `c_role_followup` Target Role: followup_investigation の追加調査
- r13 0.450485 `c_focus_license` Focus path: LICENSE
- r14 0.443969 `c_meaning_score` Meaning: ハイスコアの保存方法
- r15 0.437828 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.429327 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.394191 `c_focus_board` Focus path: tetris/board_state.py

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_role_runtime` rank=2 cosine=0.528447 gold_is_top=`False` gap_vs_second=-0.06901 delta_vs_clean=-0.288291

- r1 0.597457 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r2 0.528447 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r3 0.516796 `c_role_board` Target Role: 盤面の観測データ
- r4 0.501178 `c_role_research` Target Role: 研究用の実験経路
- r5 0.47433 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.461236 `c_role_followup` Target Role: followup_investigation の追加調査
- r7 0.457613 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r8 0.447285 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.43896 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r10 0.433299 `c_meaning_board` Meaning: ゲームの盤面状態
- r11 0.421746 `c_meaning_research` Meaning: 研究用の実験
- r12 0.417044 `c_goal_research` Goal: 研究用コードを読んで要約する
- r13 0.409553 `c_meaning_score` Meaning: ハイスコアの保存方法
- r14 0.396552 `c_focus_license` Focus path: LICENSE
- r15 0.370057 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r16 0.358115 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.339588 `c_focus_research` Focus path: research/experiment_harness.py

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_role_runtime` rank=3 cosine=0.463107 gold_is_top=`False` gap_vs_second=-0.066187 delta_vs_clean=-0.353631

- r1 0.529294 `c_meaning_board` Meaning: ゲームの盤面状態
- r2 0.521847 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r3 0.463107 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r4 0.423959 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r5 0.419176 `c_role_board` Target Role: 盤面の観測データ
- r6 0.41562 `c_role_research` Target Role: 研究用の実験経路
- r7 0.415593 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.411783 `c_meaning_research` Meaning: 研究用の実験
- r9 0.398048 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r10 0.394557 `c_goal_research` Goal: 研究用コードを読んで要約する
- r11 0.38872 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r12 0.366607 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.364075 `c_focus_license` Focus path: LICENSE
- r14 0.358483 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.353719 `c_focus_board` Focus path: tetris/board_state.py
- r16 0.342867 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.314198 `c_focus_research` Focus path: research/experiment_harness.py

### research_clean [clean] 研究用のもの

gold=`c_role_research` rank=2 cosine=0.719769 gold_is_top=`False` gap_vs_second=-0.01526 delta_vs_clean=None

- r1 0.735029 `c_meaning_research` Meaning: 研究用の実験
- r2 0.719769 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.632734 `c_role_followup` Target Role: followup_investigation の追加調査
- r4 0.607 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.592673 `c_role_board` Target Role: 盤面の観測データ
- r6 0.537707 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.528774 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r8 0.515986 `c_focus_research` Focus path: research/experiment_harness.py
- r9 0.507926 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r10 0.499423 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r11 0.497897 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.460516 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.450833 `c_meaning_board` Meaning: ゲームの盤面状態
- r14 0.438692 `c_meaning_score` Meaning: ハイスコアの保存方法
- r15 0.423439 `c_focus_license` Focus path: LICENSE
- r16 0.396062 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.344106 `c_focus_board` Focus path: tetris/board_state.py

### research_typo [typo] けんきゅう用のもの

gold=`c_role_research` rank=5 cosine=0.49422 gold_is_top=`False` gap_vs_second=-0.068679 delta_vs_clean=-0.225549

- r1 0.562899 `c_meaning_research` Meaning: 研究用の実験
- r2 0.544355 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.535939 `c_meaning_board` Meaning: ゲームの盤面状態
- r4 0.49466 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.49422 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r6 0.484015 `c_goal_research` Goal: 研究用コードを読んで要約する
- r7 0.482803 `c_role_board` Target Role: 盤面の観測データ
- r8 0.476902 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.472539 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.471364 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.468516 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.443939 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r13 0.441371 `c_focus_license` Focus path: LICENSE
- r14 0.427768 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.353228 `c_focus_board` Focus path: tetris/board_state.py
- r16 0.335463 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.309905 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_conversion [conversion] 兼休用のもの

gold=`c_role_research` rank=10 cosine=0.460836 gold_is_top=`False` gap_vs_second=-0.071815 delta_vs_clean=-0.258933

- r1 0.532651 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.51576 `c_meaning_score` Meaning: ハイスコアの保存方法
- r3 0.511241 `c_meaning_board` Meaning: ゲームの盤面状態
- r4 0.499386 `c_role_runtime` Target Role: 実行時の本番経路
- r5 0.487752 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r6 0.486429 `c_role_board` Target Role: 盤面の観測データ
- r7 0.477956 `c_goal_research` Goal: 研究用コードを読んで要約する
- r8 0.477049 `c_meaning_research` Meaning: 研究用の実験
- r9 0.473223 `c_role_followup` Target Role: followup_investigation の追加調査
- r10 0.460836 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r11 0.45063 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r12 0.446501 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.419599 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.416839 `c_focus_license` Focus path: LICENSE
- r15 0.357229 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r16 0.34891 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.340847 `c_focus_board` Focus path: tetris/board_state.py

### research_missing_char [missing_char] 究用のもの

gold=`c_role_research` rank=4 cosine=0.623813 gold_is_top=`False` gap_vs_second=-0.013337 delta_vs_clean=-0.095956

- r1 0.63715 `c_meaning_research` Meaning: 研究用の実験
- r2 0.634413 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.630088 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.623813 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r5 0.591289 `c_role_board` Target Role: 盤面の観測データ
- r6 0.588153 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r7 0.586639 `c_role_runtime` Target Role: 実行時の本番経路
- r8 0.57025 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.559284 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.548668 `c_meaning_board` Meaning: ゲームの盤面状態
- r11 0.547012 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r12 0.536377 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.520829 `c_meaning_score` Meaning: ハイスコアの保存方法
- r14 0.510784 `c_focus_license` Focus path: LICENSE
- r15 0.43296 `c_focus_research` Focus path: research/experiment_harness.py
- r16 0.426398 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.426226 `c_focus_board` Focus path: tetris/board_state.py

### research_particle [particle_drop] 研究用もの

gold=`c_role_research` rank=2 cosine=0.711771 gold_is_top=`False` gap_vs_second=-0.031422 delta_vs_clean=-0.007998

- r1 0.743193 `c_meaning_research` Meaning: 研究用の実験
- r2 0.711771 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.607869 `c_role_followup` Target Role: followup_investigation の追加調査
- r4 0.594535 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.585814 `c_role_board` Target Role: 盤面の観測データ
- r6 0.531037 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.523639 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.519319 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r9 0.511722 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.506255 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r11 0.494025 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r12 0.472241 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.46237 `c_meaning_board` Meaning: ゲームの盤面状態
- r14 0.428112 `c_meaning_score` Meaning: ハイスコアの保存方法
- r15 0.427169 `c_focus_license` Focus path: LICENSE
- r16 0.406845 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.354176 `c_focus_board` Focus path: tetris/board_state.py

### research_colloquial [colloquial] 研究用のやつ

gold=`c_role_research` rank=1 cosine=0.716809 gold_is_top=`True` gap_vs_second=0.005521 delta_vs_clean=-0.00296

- r1 0.716809 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r2 0.711288 `c_meaning_research` Meaning: 研究用の実験
- r3 0.621526 `c_role_followup` Target Role: followup_investigation の追加調査
- r4 0.591855 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.58551 `c_role_board` Target Role: 盤面の観測データ
- r6 0.541351 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.511652 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.506137 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r9 0.497532 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r10 0.479727 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.471507 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r12 0.457176 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.422347 `c_meaning_score` Meaning: ハイスコアの保存方法
- r14 0.421434 `c_meaning_board` Meaning: ゲームの盤面状態
- r15 0.414456 `c_focus_license` Focus path: LICENSE
- r16 0.390585 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.336584 `c_focus_board` Focus path: tetris/board_state.py

### research_filler [filler] まあ研究用のものかな

gold=`c_role_research` rank=2 cosine=0.583811 gold_is_top=`False` gap_vs_second=-0.027977 delta_vs_clean=-0.135958

- r1 0.611788 `c_meaning_research` Meaning: 研究用の実験
- r2 0.583811 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.54538 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.518025 `c_role_board` Target Role: 盤面の観測データ
- r5 0.514054 `c_role_followup` Target Role: followup_investigation の追加調査
- r6 0.486923 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r7 0.470314 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r8 0.461976 `c_focus_research` Focus path: research/experiment_harness.py
- r9 0.447697 `c_role_runtime` Target Role: 実行時の本番経路
- r10 0.4458 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r11 0.426491 `c_meaning_board` Meaning: ゲームの盤面状態
- r12 0.421941 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.417684 `c_meaning_score` Meaning: ハイスコアの保存方法
- r14 0.415813 `c_focus_license` Focus path: LICENSE
- r15 0.415114 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r16 0.32494 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.321429 `c_focus_board` Focus path: tetris/board_state.py

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_role_research` rank=2 cosine=0.629912 gold_is_top=`False` gap_vs_second=-0.030583 delta_vs_clean=-0.089857

- r1 0.660495 `c_meaning_research` Meaning: 研究用の実験
- r2 0.629912 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.565835 `c_role_followup` Target Role: followup_investigation の追加調査
- r4 0.539686 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.534073 `c_role_board` Target Role: 盤面の観測データ
- r6 0.513939 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.4745 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r8 0.473057 `c_focus_research` Focus path: research/experiment_harness.py
- r9 0.460247 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.456122 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r11 0.454127 `c_meaning_board` Meaning: ゲームの盤面状態
- r12 0.439762 `c_meaning_score` Meaning: ハイスコアの保存方法
- r13 0.435289 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r14 0.417097 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.405059 `c_focus_license` Focus path: LICENSE
- r16 0.357794 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.326624 `c_focus_board` Focus path: tetris/board_state.py

### research_asr [asr_like] 兼急用のもの

gold=`c_role_research` rank=5 cosine=0.507719 gold_is_top=`False` gap_vs_second=-0.067566 delta_vs_clean=-0.21205

- r1 0.575285 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.541542 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.532162 `c_role_runtime` Target Role: 実行時の本番経路
- r4 0.522247 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.507719 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r6 0.499713 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.495914 `c_role_followup` Target Role: followup_investigation の追加調査
- r8 0.492385 `c_role_board` Target Role: 盤面の観測データ
- r9 0.487287 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.479159 `c_meaning_research` Meaning: 研究用の実験
- r11 0.467331 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.46529 `c_meaning_score` Meaning: ハイスコアの保存方法
- r13 0.454571 `c_meaning_board` Meaning: ゲームの盤面状態
- r14 0.417545 `c_focus_license` Focus path: LICENSE
- r15 0.360942 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r16 0.356756 `c_focus_board` Focus path: tetris/board_state.py
- r17 0.345886 `c_focus_research` Focus path: research/experiment_harness.py

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_role_research` rank=2 cosine=0.709471 gold_is_top=`False` gap_vs_second=-0.01301 delta_vs_clean=-0.010298

- r1 0.722481 `c_meaning_research` Meaning: 研究用の実験
- r2 0.709471 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.618043 `c_role_followup` Target Role: followup_investigation の追加調査
- r4 0.596727 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.573831 `c_role_board` Target Role: 盤面の観測データ
- r6 0.525216 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.520813 `c_focus_research` Focus path: research/experiment_harness.py
- r8 0.51377 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r9 0.494456 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r10 0.490804 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r11 0.474445 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.464713 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.427489 `c_meaning_board` Meaning: ゲームの盤面状態
- r14 0.419696 `c_meaning_score` Meaning: ハイスコアの保存方法
- r15 0.414856 `c_focus_license` Focus path: LICENSE
- r16 0.389337 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 0.338317 `c_focus_board` Focus path: tetris/board_state.py

### research_compound [compound] まあけんきゅう用のも

gold=`c_role_research` rank=7 cosine=0.344226 gold_is_top=`False` gap_vs_second=-0.102881 delta_vs_clean=-0.375543

- r1 0.447107 `c_meaning_research` Meaning: 研究用の実験
- r2 0.440321 `c_meaning_board` Meaning: ゲームの盤面状態
- r3 0.382153 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.364387 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r5 0.353882 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r6 0.344647 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.344226 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r8 0.342125 `c_meaning_score` Meaning: ハイスコアの保存方法
- r9 0.339167 `c_goal_research` Goal: 研究用コードを読んで要約する
- r10 0.338421 `c_role_board` Target Role: 盤面の観測データ
- r11 0.327971 `c_role_runtime` Target Role: 実行時の本番経路
- r12 0.31015 `c_role_followup` Target Role: followup_investigation の追加調査
- r13 0.306292 `c_focus_license` Focus path: LICENSE
- r14 0.291696 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r15 0.258839 `c_focus_board` Focus path: tetris/board_state.py
- r16 0.211961 `c_focus_research` Focus path: research/experiment_harness.py
- r17 0.202012 `c_focus_runtime` Focus path: src/runtime/implementation.py
