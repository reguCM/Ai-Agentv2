# Embedding similarity Japanese input noise v0

- run_id: `20260909T150425Z_llm-jp-3-150m_agent-slots`
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

- baseline: VRAM 3765 / 12288 MiB, RAM used 39640 / 65277 MB
- after_model_load: VRAM 3765 / 12288 MiB, RAM used 40144 / 65277 MB
- after_embed: VRAM 3765 / 12288 MiB, RAM used 39955 / 65277 MB

## Agent slot（Goal / Meaning / Focus / Target Role）

仮対応。Production スキーマではない。

- intended_slot_top: 0/30 (0.0)
- correct_object_top: 13/30 (0.4333)
- confusion: {'same_object_other_slot:goal': 13, 'other_object:board:goal': 14, 'other_object:research:goal': 3}
- top_slot_type: {'goal': 30}
- failed: ['board_typo', 'board_conversion', 'board_missing_char', 'board_particle', 'board_colloquial', 'board_filler', 'board_restatement', 'board_asr', 'board_demonstrative', 'board_compound', 'runtime_typo', 'runtime_conversion', 'runtime_missing_char', 'runtime_particle', 'runtime_colloquial', 'runtime_filler', 'runtime_restatement', 'runtime_asr', 'runtime_demonstrative', 'runtime_compound', 'research_typo', 'research_conversion', 'research_missing_char', 'research_particle', 'research_colloquial', 'research_filler', 'research_restatement', 'research_asr', 'research_demonstrative', 'research_compound']

  - `board_typo` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_conversion` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_missing_char` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_particle` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_colloquial` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_filler` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_restatement` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_asr` intended=`c_meaning_board` rank=6 top=`c_goal_board` same_object_other_slot:goal
  - `board_demonstrative` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `board_compound` intended=`c_meaning_board` rank=5 top=`c_goal_board` same_object_other_slot:goal
  - `runtime_typo` intended=`c_meaning_runtime` rank=3 top=`c_goal_board` other_object:board:goal
  - `runtime_conversion` intended=`c_meaning_runtime` rank=3 top=`c_goal_board` other_object:board:goal
  - `runtime_missing_char` intended=`c_meaning_runtime` rank=4 top=`c_goal_research` other_object:research:goal
  - `runtime_particle` intended=`c_meaning_runtime` rank=5 top=`c_goal_research` other_object:research:goal
  - `runtime_colloquial` intended=`c_role_runtime` rank=10 top=`c_goal_board` other_object:board:goal
  - `runtime_filler` intended=`c_meaning_runtime` rank=5 top=`c_goal_board` other_object:board:goal
  - `runtime_restatement` intended=`c_meaning_runtime` rank=4 top=`c_goal_research` other_object:research:goal
  - `runtime_asr` intended=`c_meaning_runtime` rank=3 top=`c_goal_board` other_object:board:goal
  - `runtime_demonstrative` intended=`c_role_runtime` rank=10 top=`c_goal_board` other_object:board:goal
  - `runtime_compound` intended=`c_role_runtime` rank=9 top=`c_goal_board` other_object:board:goal
  - `research_typo` intended=`c_role_research` rank=7 top=`c_goal_board` other_object:board:goal
  - `research_conversion` intended=`c_role_research` rank=6 top=`c_goal_board` other_object:board:goal
  - `research_missing_char` intended=`c_role_research` rank=6 top=`c_goal_board` other_object:board:goal
  - `research_particle` intended=`c_role_research` rank=2 top=`c_goal_research` same_object_other_slot:goal
  - `research_colloquial` intended=`c_role_research` rank=4 top=`c_goal_research` same_object_other_slot:goal
  - `research_filler` intended=`c_role_research` rank=8 top=`c_goal_board` other_object:board:goal
  - `research_restatement` intended=`c_role_research` rank=8 top=`c_goal_board` other_object:board:goal
  - `research_asr` intended=`c_role_research` rank=6 top=`c_goal_board` other_object:board:goal
  - `research_demonstrative` intended=`c_role_research` rank=3 top=`c_goal_research` same_object_other_slot:goal
  - `research_compound` intended=`c_role_research` rank=8 top=`c_goal_board` other_object:board:goal

## ノイズ種別まとめ

- `clean`: gold_top 0/3 mean_rank=3.667 mean_gap=-0.098481 mean_delta_vs_clean=None failed=['board_clean', 'runtime_clean', 'research_clean']
- `typo`: gold_top 0/3 mean_rank=5.0 mean_gap=-0.156731 mean_delta_vs_clean=-0.169549 failed=['board_typo', 'runtime_typo', 'research_typo']
- `conversion`: gold_top 0/3 mean_rank=4.667 mean_gap=-0.121568 mean_delta_vs_clean=-0.122372 failed=['board_conversion', 'runtime_conversion', 'research_conversion']
- `missing_char`: gold_top 0/3 mean_rank=5.0 mean_gap=-0.099068 mean_delta_vs_clean=-0.030884 failed=['board_missing_char', 'runtime_missing_char', 'research_missing_char']
- `particle_drop`: gold_top 0/3 mean_rank=4.0 mean_gap=-0.127452 mean_delta_vs_clean=-0.076276 failed=['board_particle', 'runtime_particle', 'research_particle']
- `colloquial`: gold_top 0/3 mean_rank=6.333 mean_gap=-0.199488 mean_delta_vs_clean=-0.130369 failed=['board_colloquial', 'runtime_colloquial', 'research_colloquial']
- `filler`: gold_top 0/3 mean_rank=6.0 mean_gap=-0.178807 mean_delta_vs_clean=-0.126749 failed=['board_filler', 'runtime_filler', 'research_filler']
- `restatement`: gold_top 0/3 mean_rank=5.667 mean_gap=-0.17322 mean_delta_vs_clean=-0.103326 failed=['board_restatement', 'runtime_restatement', 'research_restatement']
- `asr_like`: gold_top 0/3 mean_rank=5.0 mean_gap=-0.166633 mean_delta_vs_clean=-0.144948 failed=['board_asr', 'runtime_asr', 'research_asr']
- `demonstrative`: gold_top 0/3 mean_rank=6.0 mean_gap=-0.228257 mean_delta_vs_clean=-0.131737 failed=['board_demonstrative', 'runtime_demonstrative', 'research_demonstrative']
- `compound`: gold_top 0/3 mean_rank=7.333 mean_gap=-0.256789 mean_delta_vs_clean=-0.26137 failed=['board_compound', 'runtime_compound', 'research_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'particle_drop', 'colloquial', 'filler', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `board_typo` [typo] テとりすの盤面 gold_rank=5 gold_cos=0.393237 top=`c_goal_board` 0.611825 delta_vs_clean=-0.10918
- `board_conversion` [conversion] テトリスの番面 gold_rank=5 gold_cos=0.466682 top=`c_goal_board` 0.549788 delta_vs_clean=-0.035735
- `board_missing_char` [missing_char] テトリスの盤 gold_rank=5 gold_cos=0.500688 top=`c_goal_board` 0.592991 delta_vs_clean=-0.001729
- `board_particle` [particle_drop] テトリス盤面 gold_rank=5 gold_cos=0.435773 top=`c_goal_board` 0.520909 delta_vs_clean=-0.066644
- `board_colloquial` [colloquial] テトリスの盤面のやつ gold_rank=5 gold_cos=0.473785 top=`c_goal_board` 0.60362 delta_vs_clean=-0.028632
- `board_filler` [filler] えっとテトリスの盤面 gold_rank=5 gold_cos=0.541061 top=`c_goal_board` 0.67253 delta_vs_clean=0.038644
- `board_restatement` [restatement] いやスコアじゃなくてテトリスの盤面 gold_rank=5 gold_cos=0.533587 top=`c_goal_board` 0.699109 delta_vs_clean=0.03117
- `board_asr` [asr_like] 手取り巣の盤面 gold_rank=6 gold_cos=0.367045 top=`c_goal_board` 0.623786 delta_vs_clean=-0.135372
- `board_demonstrative` [demonstrative] そっちの盤面 gold_rank=5 gold_cos=0.506281 top=`c_goal_board` 0.700888 delta_vs_clean=0.003864
- `board_compound` [compound] えっとテトリスの番面のやつ gold_rank=5 gold_cos=0.495498 top=`c_goal_board` 0.618784 delta_vs_clean=-0.006919
- `runtime_typo` [typo] 実交時に動いている実装 gold_rank=3 gold_cos=0.661383 top=`c_goal_board` 0.702084 delta_vs_clean=-0.073628
- `runtime_conversion` [conversion] 実効時に動いている実装 gold_rank=3 gold_cos=0.648833 top=`c_goal_board` 0.717752 delta_vs_clean=-0.086178
- `runtime_missing_char` [missing_char] 実行時に動いている実 gold_rank=4 gold_cos=0.715381 top=`c_goal_research` 0.754273 delta_vs_clean=-0.01963
- `runtime_particle` [particle_drop] 実行時動いている実装 gold_rank=5 gold_cos=0.588174 top=`c_goal_research` 0.749584 delta_vs_clean=-0.146837
- `runtime_colloquial` [colloquial] 実際に動いてるほう gold_rank=10 gold_cos=0.369146 top=`c_goal_board` 0.658387 delta_vs_clean=-0.365865
- `runtime_filler` [filler] あのー実行時に動いている実装なんですけど gold_rank=5 gold_cos=0.565688 top=`c_goal_board` 0.686776 delta_vs_clean=-0.169323
- `runtime_restatement` [restatement] 実験用じゃなくて実行時に動いている実装 gold_rank=4 gold_cos=0.602267 top=`c_goal_research` 0.686569 delta_vs_clean=-0.132744
- `runtime_asr` [asr_like] 実効時に動いてる実装 gold_rank=3 gold_cos=0.644541 top=`c_goal_board` 0.714229 delta_vs_clean=-0.09047
- `runtime_demonstrative` [demonstrative] 実際に使ってる方 gold_rank=10 gold_cos=0.378713 top=`c_goal_board` 0.683135 delta_vs_clean=-0.356298
- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=9 gold_cos=0.306943 top=`c_goal_board` 0.628202 delta_vs_clean=-0.428068
- `research_typo` [typo] けんきゅう用のもの gold_rank=7 gold_cos=0.32745 top=`c_goal_board` 0.538354 delta_vs_clean=-0.325839
- `research_conversion` [conversion] 兼休用のもの gold_rank=6 gold_cos=0.408086 top=`c_goal_board` 0.620764 delta_vs_clean=-0.245203
- `research_missing_char` [missing_char] 究用のもの gold_rank=6 gold_cos=0.581996 top=`c_goal_board` 0.748005 delta_vs_clean=-0.071293
- `research_particle` [particle_drop] 研究用もの gold_rank=2 gold_cos=0.637943 top=`c_goal_research` 0.773752 delta_vs_clean=-0.015346
- `research_colloquial` [colloquial] 研究用のやつ gold_rank=4 gold_cos=0.656679 top=`c_goal_research` 0.836068 delta_vs_clean=0.00339
- `research_filler` [filler] まあ研究用のものかな gold_rank=8 gold_cos=0.40372 top=`c_goal_board` 0.687585 delta_vs_clean=-0.249569
- `research_restatement` [restatement] 本番じゃなくて研究用のもの gold_rank=8 gold_cos=0.444886 top=`c_goal_board` 0.714723 delta_vs_clean=-0.208403
- `research_asr` [asr_like] 兼急用のもの gold_rank=6 gold_cos=0.444288 top=`c_goal_board` 0.617758 delta_vs_clean=-0.209001
- `research_demonstrative` [demonstrative] 研究用のほう gold_rank=3 gold_cos=0.610511 top=`c_goal_research` 0.796253 delta_vs_clean=-0.042778
- `research_compound` [compound] まあけんきゅう用のも gold_rank=8 gold_cos=0.304167 top=`c_goal_board` 0.629988 delta_vs_clean=-0.349122

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_meaning_board` rank=4 cosine=0.502417 gold_is_top=`False` gap_vs_second=-0.105063 delta_vs_clean=None

- r1 0.60748 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.545703 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.502549 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.502417 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r5 0.499137 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r6 0.423957 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.362773 `c_role_board` Target Role: 盤面の観測データ
- r8 0.333686 `c_role_research` Target Role: 研究用の実験経路
- r9 0.332468 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.278216 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.130067 `c_meaning_research` Meaning: 研究用の実験
- r12 -0.00065 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.14902 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.264188 `c_focus_license` Focus path: LICENSE
- r15 -0.271912 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.29364 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.327507 `c_focus_research` Focus path: research/experiment_harness.py

### board_typo [typo] テとりすの盤面

gold=`c_meaning_board` rank=5 cosine=0.393237 gold_is_top=`False` gap_vs_second=-0.218588 delta_vs_clean=-0.10918

- r1 0.611825 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.543225 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.50043 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.474182 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.393237 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.357822 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.344056 `c_role_board` Target Role: 盤面の観測データ
- r8 0.298745 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r9 0.28847 `c_role_research` Target Role: 研究用の実験経路
- r10 0.221201 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.095182 `c_meaning_research` Meaning: 研究用の実験
- r12 -0.031833 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.185063 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.308766 `c_focus_board` Focus path: tetris/board_state.py
- r15 -0.313355 `c_focus_license` Focus path: LICENSE
- r16 -0.33412 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.346263 `c_focus_research` Focus path: research/experiment_harness.py

### board_conversion [conversion] テトリスの番面

gold=`c_meaning_board` rank=5 cosine=0.466682 gold_is_top=`False` gap_vs_second=-0.083106 delta_vs_clean=-0.035735

- r1 0.549788 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.533991 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.479566 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.470654 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.466682 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.412988 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.326323 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r8 0.298934 `c_role_research` Target Role: 研究用の実験経路
- r9 0.291992 `c_role_board` Target Role: 盤面の観測データ
- r10 0.251605 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.129099 `c_meaning_research` Meaning: 研究用の実験
- r12 -0.025109 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.15287 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.267985 `c_focus_license` Focus path: LICENSE
- r15 -0.269508 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.303875 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.317685 `c_focus_research` Focus path: research/experiment_harness.py

### board_missing_char [missing_char] テトリスの盤

gold=`c_meaning_board` rank=5 cosine=0.500688 gold_is_top=`False` gap_vs_second=-0.092303 delta_vs_clean=-0.001729

- r1 0.592991 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.558827 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.51314 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.506271 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.500688 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.437628 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.369049 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r8 0.34163 `c_role_research` Target Role: 研究用の実験経路
- r9 0.338099 `c_role_board` Target Role: 盤面の観測データ
- r10 0.290054 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.171918 `c_meaning_research` Meaning: 研究用の実験
- r12 0.006223 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.129129 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.234287 `c_focus_license` Focus path: LICENSE
- r15 -0.246437 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.27606 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.298115 `c_focus_research` Focus path: research/experiment_harness.py

### board_particle [particle_drop] テトリス盤面

gold=`c_meaning_board` rank=5 cosine=0.435773 gold_is_top=`False` gap_vs_second=-0.085136 delta_vs_clean=-0.066644

- r1 0.520909 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.485704 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.457896 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.437835 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.435773 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.433605 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.416258 `c_role_board` Target Role: 盤面の観測データ
- r8 0.365009 `c_role_research` Target Role: 研究用の実験経路
- r9 0.291226 `c_role_runtime` Target Role: 実行時の本番経路
- r10 0.210672 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r11 0.070286 `c_meaning_research` Meaning: 研究用の実験
- r12 0.05092 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.044029 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.162359 `c_focus_license` Focus path: LICENSE
- r15 -0.174198 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.211822 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.239642 `c_focus_research` Focus path: research/experiment_harness.py

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_meaning_board` rank=5 cosine=0.473785 gold_is_top=`False` gap_vs_second=-0.129835 delta_vs_clean=-0.028632

- r1 0.60362 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.525744 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.484702 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.482337 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.473785 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.392745 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.352926 `c_role_board` Target Role: 盤面の観測データ
- r8 0.313031 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r9 0.306896 `c_role_research` Target Role: 研究用の実験経路
- r10 0.250568 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.098915 `c_meaning_research` Meaning: 研究用の実験
- r12 -0.032691 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.194902 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.315662 `c_focus_board` Focus path: tetris/board_state.py
- r15 -0.318851 `c_focus_license` Focus path: LICENSE
- r16 -0.332057 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.374306 `c_focus_research` Focus path: research/experiment_harness.py

### board_filler [filler] えっとテトリスの盤面

gold=`c_meaning_board` rank=5 cosine=0.541061 gold_is_top=`False` gap_vs_second=-0.131469 delta_vs_clean=0.038644

- r1 0.67253 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.617189 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.581158 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.566142 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.541061 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.482148 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.467661 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.342758 `c_role_research` Target Role: 研究用の実験経路
- r9 0.337773 `c_role_board` Target Role: 盤面の観測データ
- r10 0.320334 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.265832 `c_meaning_research` Meaning: 研究用の実験
- r12 0.068944 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.101744 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.197492 `c_focus_board` Focus path: tetris/board_state.py
- r15 -0.21469 `c_focus_license` Focus path: LICENSE
- r16 -0.222685 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.242448 `c_focus_research` Focus path: research/experiment_harness.py

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_meaning_board` rank=5 cosine=0.533587 gold_is_top=`False` gap_vs_second=-0.165522 delta_vs_clean=0.03117

- r1 0.699109 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.602242 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r3 0.600747 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.595695 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.533587 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.480837 `c_meaning_score` Meaning: ハイスコアの保存方法
- r7 0.439479 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r8 0.350232 `c_role_board` Target Role: 盤面の観測データ
- r9 0.346487 `c_role_research` Target Role: 研究用の実験経路
- r10 0.325661 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.219164 `c_meaning_research` Meaning: 研究用の実験
- r12 0.045192 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.10908 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.236735 `c_focus_board` Focus path: tetris/board_state.py
- r15 -0.240979 `c_focus_license` Focus path: LICENSE
- r16 -0.255525 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.279509 `c_focus_research` Focus path: research/experiment_harness.py

### board_asr [asr_like] 手取り巣の盤面

gold=`c_meaning_board` rank=6 cosine=0.367045 gold_is_top=`False` gap_vs_second=-0.256741 delta_vs_clean=-0.135372

- r1 0.623786 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.49647 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.477708 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.437401 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.436309 `c_role_board` Target Role: 盤面の観測データ
- r6 0.367045 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r7 0.350299 `c_role_research` Target Role: 研究用の実験経路
- r8 0.297096 `c_meaning_score` Meaning: ハイスコアの保存方法
- r9 0.296706 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.263006 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.108794 `c_meaning_research` Meaning: 研究用の実験
- r12 0.038263 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.124673 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.260191 `c_focus_license` Focus path: LICENSE
- r15 -0.282139 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.305576 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.30714 `c_focus_research` Focus path: research/experiment_harness.py

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_meaning_board` rank=5 cosine=0.506281 gold_is_top=`False` gap_vs_second=-0.194607 delta_vs_clean=0.003864

- r1 0.700888 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.59952 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.566778 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.53997 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.506281 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.458892 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.423326 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.357921 `c_role_board` Target Role: 盤面の観測データ
- r9 0.323226 `c_role_research` Target Role: 研究用の実験経路
- r10 0.282514 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.233689 `c_meaning_research` Meaning: 研究用の実験
- r12 0.046398 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.14017 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.243663 `c_focus_license` Focus path: LICENSE
- r15 -0.260354 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.285001 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.294745 `c_focus_runtime` Focus path: src/runtime/implementation.py

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_meaning_board` rank=5 cosine=0.495498 gold_is_top=`False` gap_vs_second=-0.123286 delta_vs_clean=-0.006919

- r1 0.618784 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.584535 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.542846 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.51651 `c_goal_research` Goal: 研究用コードを読んで要約する
- r5 0.495498 `c_meaning_board` Meaning: ゲームの盤面状態 GOLD
- r6 0.443135 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.434998 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.296842 `c_role_research` Target Role: 研究用の実験経路
- r9 0.284421 `c_role_board` Target Role: 盤面の観測データ
- r10 0.277332 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.226656 `c_meaning_research` Meaning: 研究用の実験
- r12 0.024904 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.137146 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.228433 `c_focus_board` Focus path: tetris/board_state.py
- r15 -0.251466 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r16 -0.2552 `c_focus_license` Focus path: LICENSE
- r17 -0.270738 `c_focus_research` Focus path: research/experiment_harness.py

### runtime_clean [clean] 実行時に動いている実装

gold=`c_meaning_runtime` rank=4 cosine=0.735011 gold_is_top=`False` gap_vs_second=-0.049879 delta_vs_clean=None

- r1 0.78489 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.784163 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r3 0.772086 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.735011 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r5 0.657049 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.623669 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.615653 `c_role_research` Target Role: 研究用の実験経路
- r8 0.56975 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.54182 `c_role_board` Target Role: 盤面の観測データ
- r10 0.497636 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.472142 `c_meaning_research` Meaning: 研究用の実験
- r12 0.293275 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.160474 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.001068 `c_focus_license` Focus path: LICENSE
- r15 -0.030435 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.050241 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.063749 `c_focus_research` Focus path: research/experiment_harness.py

### runtime_typo [typo] 実交時に動いている実装

gold=`c_meaning_runtime` rank=3 cosine=0.661383 gold_is_top=`False` gap_vs_second=-0.040701 delta_vs_clean=-0.073628

- r1 0.702084 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.69575 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.661383 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r4 0.641825 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.579387 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.486249 `c_role_research` Target Role: 研究用の実験経路
- r7 0.481425 `c_meaning_board` Meaning: ゲームの盤面状態
- r8 0.457889 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.418154 `c_meaning_research` Meaning: 研究用の実験
- r10 0.417259 `c_role_board` Target Role: 盤面の観測データ
- r11 0.384493 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.158561 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.013745 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.113671 `c_focus_license` Focus path: LICENSE
- r15 -0.147351 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.166153 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.189415 `c_focus_runtime` Focus path: src/runtime/implementation.py

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_meaning_runtime` rank=3 cosine=0.648833 gold_is_top=`False` gap_vs_second=-0.068919 delta_vs_clean=-0.086178

- r1 0.717752 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.687701 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.648833 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r4 0.640035 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.589604 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.484112 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.470816 `c_role_research` Target Role: 研究用の実験経路
- r8 0.442257 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.417194 `c_role_board` Target Role: 盤面の観測データ
- r10 0.405822 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.398827 `c_meaning_research` Meaning: 研究用の実験
- r12 0.150307 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.013658 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.142474 `c_focus_license` Focus path: LICENSE
- r15 -0.162638 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.18747 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.210019 `c_focus_runtime` Focus path: src/runtime/implementation.py

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_meaning_runtime` rank=4 cosine=0.715381 gold_is_top=`False` gap_vs_second=-0.038892 delta_vs_clean=-0.01963

- r1 0.754273 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.748085 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.746092 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.715381 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r5 0.652043 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.58315 `c_role_runtime` Target Role: 実行時の本番経路
- r7 0.580856 `c_role_research` Target Role: 研究用の実験経路
- r8 0.542378 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.503352 `c_role_board` Target Role: 盤面の観測データ
- r10 0.474194 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.462302 `c_meaning_research` Meaning: 研究用の実験
- r12 0.260326 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.128363 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.018654 `c_focus_license` Focus path: LICENSE
- r15 -0.049012 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.078328 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.082013 `c_focus_runtime` Focus path: src/runtime/implementation.py

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_meaning_runtime` rank=5 cosine=0.588174 gold_is_top=`False` gap_vs_second=-0.16141 delta_vs_clean=-0.146837

- r1 0.749584 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.733088 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.725033 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.598535 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.588174 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r6 0.574536 `c_role_research` Target Role: 研究用の実験経路
- r7 0.557415 `c_role_runtime` Target Role: 実行時の本番経路
- r8 0.525464 `c_role_board` Target Role: 盤面の観測データ
- r9 0.489216 `c_meaning_board` Meaning: ゲームの盤面状態
- r10 0.423376 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.358746 `c_meaning_research` Meaning: 研究用の実験
- r12 0.238007 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.118953 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.047541 `c_focus_license` Focus path: LICENSE
- r15 -0.099205 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.111495 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.116356 `c_focus_research` Focus path: research/experiment_harness.py

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_role_runtime` rank=10 cosine=0.369146 gold_is_top=`False` gap_vs_second=-0.289241 delta_vs_clean=-0.365865

- r1 0.658387 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.62746 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.627022 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r4 0.604373 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.574622 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r6 0.459979 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.40956 `c_meaning_research` Meaning: 研究用の実験
- r8 0.403351 `c_meaning_score` Meaning: ハイスコアの保存方法
- r9 0.402029 `c_role_research` Target Role: 研究用の実験経路
- r10 0.369146 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r11 0.332056 `c_role_board` Target Role: 盤面の観測データ
- r12 0.120936 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.022013 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.118955 `c_focus_license` Focus path: LICENSE
- r15 -0.143535 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.153469 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.204927 `c_focus_runtime` Focus path: src/runtime/implementation.py

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_meaning_runtime` rank=5 cosine=0.565688 gold_is_top=`False` gap_vs_second=-0.121088 delta_vs_clean=-0.169323

- r1 0.686776 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.650955 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r3 0.648059 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.615828 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.565688 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r6 0.473018 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.435606 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.403078 `c_role_research` Target Role: 研究用の実験経路
- r9 0.395678 `c_role_runtime` Target Role: 実行時の本番経路
- r10 0.345188 `c_role_board` Target Role: 盤面の観測データ
- r11 0.306388 `c_meaning_research` Meaning: 研究用の実験
- r12 0.075233 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.062313 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.190393 `c_focus_license` Focus path: LICENSE
- r15 -0.202387 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.22307 `c_focus_runtime` Focus path: src/runtime/implementation.py
- r17 -0.228466 `c_focus_research` Focus path: research/experiment_harness.py

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_meaning_runtime` rank=4 cosine=0.602267 gold_is_top=`False` gap_vs_second=-0.084302 delta_vs_clean=-0.132744

- r1 0.686569 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.651259 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.618732 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.602267 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r5 0.545371 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.515396 `c_role_research` Target Role: 研究用の実験経路
- r7 0.452573 `c_meaning_board` Meaning: ゲームの盤面状態
- r8 0.429471 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.413525 `c_role_board` Target Role: 盤面の観測データ
- r10 0.404203 `c_meaning_research` Meaning: 研究用の実験
- r11 0.382218 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.151389 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.019853 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.173437 `c_focus_license` Focus path: LICENSE
- r15 -0.174228 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.202815 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.229995 `c_focus_runtime` Focus path: src/runtime/implementation.py

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_meaning_runtime` rank=3 cosine=0.644541 gold_is_top=`False` gap_vs_second=-0.069688 delta_vs_clean=-0.09047

- r1 0.714229 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.674695 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.644541 `c_meaning_runtime` Meaning: 実行時に動いている実装 GOLD
- r4 0.635117 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.590666 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.486667 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.455102 `c_role_research` Target Role: 研究用の実験経路
- r8 0.430485 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.407451 `c_meaning_score` Meaning: ハイスコアの保存方法
- r10 0.403541 `c_role_board` Target Role: 盤面の観測データ
- r11 0.390003 `c_meaning_research` Meaning: 研究用の実験
- r12 0.138804 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.024361 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.151378 `c_focus_license` Focus path: LICENSE
- r15 -0.166039 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.191088 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.21196 `c_focus_runtime` Focus path: src/runtime/implementation.py

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_role_runtime` rank=10 cosine=0.378713 gold_is_top=`False` gap_vs_second=-0.304422 delta_vs_clean=-0.356298

- r1 0.683135 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.655323 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.642284 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.607387 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.584265 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r6 0.465248 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.437287 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.410155 `c_role_research` Target Role: 研究用の実験経路
- r9 0.393204 `c_meaning_research` Meaning: 研究用の実験
- r10 0.378713 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r11 0.340703 `c_role_board` Target Role: 盤面の観測データ
- r12 0.125871 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.01554 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.122344 `c_focus_license` Focus path: LICENSE
- r15 -0.144209 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.154265 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.202249 `c_focus_runtime` Focus path: src/runtime/implementation.py

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_role_runtime` rank=9 cosine=0.306943 gold_is_top=`False` gap_vs_second=-0.321259 delta_vs_clean=-0.428068

- r1 0.628202 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.575725 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.571608 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.53983 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.480273 `c_meaning_board` Meaning: ゲームの盤面状態
- r6 0.477275 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.418816 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.330677 `c_role_research` Target Role: 研究用の実験経路
- r9 0.306943 `c_role_runtime` Target Role: 実行時の本番経路 GOLD
- r10 0.27409 `c_role_board` Target Role: 盤面の観測データ
- r11 0.270316 `c_meaning_research` Meaning: 研究用の実験
- r12 -0.008645 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.130862 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.236678 `c_focus_license` Focus path: LICENSE
- r15 -0.24447 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.266504 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.282404 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_clean [clean] 研究用のもの

gold=`c_role_research` rank=3 cosine=0.653289 gold_is_top=`False` gap_vs_second=-0.1405 delta_vs_clean=None

- r1 0.793789 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.653601 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.653289 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r4 0.589375 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.538861 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.533206 `c_role_board` Target Role: 盤面の観測データ
- r7 0.492176 `c_meaning_research` Meaning: 研究用の実験
- r8 0.487285 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r9 0.479259 `c_role_runtime` Target Role: 実行時の本番経路
- r10 0.441273 `c_meaning_board` Meaning: ゲームの盤面状態
- r11 0.393512 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.298327 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.17252 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.041514 `c_focus_license` Focus path: LICENSE
- r15 -0.022507 `c_focus_research` Focus path: research/experiment_harness.py
- r16 -0.040202 `c_focus_board` Focus path: tetris/board_state.py
- r17 -0.097107 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_typo [typo] けんきゅう用のもの

gold=`c_role_research` rank=7 cosine=0.32745 gold_is_top=`False` gap_vs_second=-0.210904 delta_vs_clean=-0.325839

- r1 0.538354 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.491581 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.476615 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.399929 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.345729 `c_role_board` Target Role: 盤面の観測データ
- r6 0.344397 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.32745 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r8 0.296017 `c_meaning_score` Meaning: ハイスコアの保存方法
- r9 0.290559 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.229152 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.151322 `c_meaning_research` Meaning: 研究用の実験
- r12 0.066747 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.058649 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.172291 `c_focus_license` Focus path: LICENSE
- r15 -0.184254 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.190975 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.218498 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_conversion [conversion] 兼休用のもの

gold=`c_role_research` rank=6 cosine=0.408086 gold_is_top=`False` gap_vs_second=-0.212678 delta_vs_clean=-0.245203

- r1 0.620764 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.5966 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.529576 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.507426 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.409988 `c_role_board` Target Role: 盤面の観測データ
- r6 0.408086 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r7 0.388554 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.379253 `c_meaning_board` Meaning: ゲームの盤面状態
- r9 0.364395 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.32535 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.211707 `c_meaning_research` Meaning: 研究用の実験
- r12 0.120863 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.000902 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.113542 `c_focus_license` Focus path: LICENSE
- r15 -0.162306 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.179126 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.216321 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_missing_char [missing_char] 究用のもの

gold=`c_role_research` rank=6 cosine=0.581996 gold_is_top=`False` gap_vs_second=-0.166009 delta_vs_clean=-0.071293

- r1 0.748005 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.741646 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.62443 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.59287 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.584656 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r6 0.581996 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r7 0.551404 `c_role_board` Target Role: 盤面の観測データ
- r8 0.480527 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.477894 `c_meaning_board` Meaning: ゲームの盤面状態
- r10 0.46375 `c_meaning_research` Meaning: 研究用の実験
- r11 0.4187 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.289447 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.155293 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.034047 `c_focus_license` Focus path: LICENSE
- r15 -0.025388 `c_focus_research` Focus path: research/experiment_harness.py
- r16 -0.026518 `c_focus_board` Focus path: tetris/board_state.py
- r17 -0.101497 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_particle [particle_drop] 研究用もの

gold=`c_role_research` rank=2 cosine=0.637943 gold_is_top=`False` gap_vs_second=-0.135809 delta_vs_clean=-0.015346

- r1 0.773752 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.637943 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r3 0.636302 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r4 0.567952 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.534095 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.516279 `c_role_board` Target Role: 盤面の観測データ
- r7 0.469321 `c_meaning_research` Meaning: 研究用の実験
- r8 0.462566 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.462498 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r10 0.423889 `c_meaning_board` Meaning: ゲームの盤面状態
- r11 0.385397 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.267071 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.148209 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.017367 `c_focus_license` Focus path: LICENSE
- r15 -0.046317 `c_focus_research` Focus path: research/experiment_harness.py
- r16 -0.062235 `c_focus_board` Focus path: tetris/board_state.py
- r17 -0.113325 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_colloquial [colloquial] 研究用のやつ

gold=`c_role_research` rank=4 cosine=0.656679 gold_is_top=`False` gap_vs_second=-0.179389 delta_vs_clean=0.00339

- r1 0.836068 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.738957 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.671612 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.656679 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r5 0.64945 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.56426 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.538254 `c_role_board` Target Role: 盤面の観測データ
- r8 0.51065 `c_meaning_research` Meaning: 研究用の実験
- r9 0.506496 `c_role_runtime` Target Role: 実行時の本番経路
- r10 0.504015 `c_meaning_board` Meaning: ゲームの盤面状態
- r11 0.462025 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.263804 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.128249 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.012605 `c_focus_license` Focus path: LICENSE
- r15 -0.074953 `c_focus_research` Focus path: research/experiment_harness.py
- r16 -0.077862 `c_focus_board` Focus path: tetris/board_state.py
- r17 -0.127809 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_filler [filler] まあ研究用のものかな

gold=`c_role_research` rank=8 cosine=0.40372 gold_is_top=`False` gap_vs_second=-0.283865 delta_vs_clean=-0.249569

- r1 0.687585 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.68031 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.606848 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.60294 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.52611 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r6 0.460862 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.421406 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.40372 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r9 0.358231 `c_meaning_research` Meaning: 研究用の実験
- r10 0.339352 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.317282 `c_role_board` Target Role: 盤面の観測データ
- r12 0.079926 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.080884 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.194641 `c_focus_license` Focus path: LICENSE
- r15 -0.210988 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.223001 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.256455 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_role_research` rank=8 cosine=0.444886 gold_is_top=`False` gap_vs_second=-0.269837 delta_vs_clean=-0.208403

- r1 0.714723 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.700434 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.624274 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r4 0.6129 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.497169 `c_meaning_board` Meaning: ゲームの盤面状態
- r6 0.489476 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.469242 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.444886 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r9 0.386722 `c_role_board` Target Role: 盤面の観測データ
- r10 0.385286 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.336326 `c_meaning_research` Meaning: 研究用の実験
- r12 0.138754 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.00796 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.125534 `c_focus_license` Focus path: LICENSE
- r15 -0.156592 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.161396 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.205203 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_asr [asr_like] 兼急用のもの

gold=`c_role_research` rank=6 cosine=0.444288 gold_is_top=`False` gap_vs_second=-0.17347 delta_vs_clean=-0.209001

- r1 0.617758 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.584161 `c_goal_research` Goal: 研究用コードを読んで要約する
- r3 0.524809 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.508151 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.467512 `c_role_board` Target Role: 盤面の観測データ
- r6 0.444288 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r7 0.378585 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r8 0.36939 `c_role_runtime` Target Role: 実行時の本番経路
- r9 0.352245 `c_meaning_board` Meaning: ゲームの盤面状態
- r10 0.326013 `c_meaning_score` Meaning: ハイスコアの保存方法
- r11 0.188791 `c_meaning_research` Meaning: 研究用の実験
- r12 0.136275 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.036365 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.106606 `c_focus_license` Focus path: LICENSE
- r15 -0.127141 `c_focus_board` Focus path: tetris/board_state.py
- r16 -0.157621 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.180639 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_role_research` rank=3 cosine=0.610511 gold_is_top=`False` gap_vs_second=-0.185742 delta_vs_clean=-0.042778

- r1 0.796253 `c_goal_research` Goal: 研究用コードを読んで要約する
- r2 0.684576 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r3 0.610511 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r4 0.609056 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.569753 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.537605 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r7 0.509333 `c_meaning_research` Meaning: 研究用の実験
- r8 0.476255 `c_role_board` Target Role: 盤面の観測データ
- r9 0.46041 `c_meaning_board` Meaning: ゲームの盤面状態
- r10 0.455997 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.408122 `c_meaning_score` Meaning: ハイスコアの保存方法
- r12 0.243944 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.102492 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.022939 `c_focus_license` Focus path: LICENSE
- r15 -0.07828 `c_focus_research` Focus path: research/experiment_harness.py
- r16 -0.097628 `c_focus_board` Focus path: tetris/board_state.py
- r17 -0.151263 `c_focus_runtime` Focus path: src/runtime/implementation.py

### research_compound [compound] まあけんきゅう用のも

gold=`c_role_research` rank=8 cosine=0.304167 gold_is_top=`False` gap_vs_second=-0.325821 delta_vs_clean=-0.349122

- r1 0.629988 `c_goal_board` Goal: 盤面の内容を読んで要約する
- r2 0.590108 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.554549 `c_goal_research` Goal: 研究用コードを読んで要約する
- r4 0.516341 `c_goal_runtime` Goal: 実行時コードを読んで要約する
- r5 0.441989 `c_meaning_runtime` Meaning: 実行時に動いている実装
- r6 0.415032 `c_meaning_board` Meaning: ゲームの盤面状態
- r7 0.381457 `c_meaning_score` Meaning: ハイスコアの保存方法
- r8 0.304167 `c_role_research` Target Role: 研究用の実験経路 GOLD
- r9 0.280375 `c_role_board` Target Role: 盤面の観測データ
- r10 0.254377 `c_role_runtime` Target Role: 実行時の本番経路
- r11 0.235776 `c_meaning_research` Meaning: 研究用の実験
- r12 0.005316 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.150382 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 -0.247835 `c_focus_board` Focus path: tetris/board_state.py
- r15 -0.250631 `c_focus_license` Focus path: LICENSE
- r16 -0.27279 `c_focus_research` Focus path: research/experiment_harness.py
- r17 -0.292567 `c_focus_runtime` Focus path: src/runtime/implementation.py
