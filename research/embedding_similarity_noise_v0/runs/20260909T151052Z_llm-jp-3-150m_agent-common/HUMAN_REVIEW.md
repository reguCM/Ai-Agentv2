# Embedding similarity Japanese input noise v0

- run_id: `20260909T151052Z_llm-jp-3-150m_agent-common`
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

- baseline: VRAM 3766 / 12288 MiB, RAM used 39024 / 65277 MB
- after_model_load: VRAM 3766 / 12288 MiB, RAM used 39485 / 65277 MB
- after_embed: VRAM 3766 / 12288 MiB, RAM used 39492 / 65277 MB

## Agent slot（Goal / Meaning / Focus / Target Role）

仮対応。Production スキーマではない。

- intended_slot_top: 0/30 (0.0)
- correct_object_top: 12/30 (0.4)
- confusion: {'other_object:web:goal': 18, 'same_object_other_slot:goal': 12}
- top_slot_type: {'goal': 30}
- failed: ['read_typo', 'read_conversion', 'read_missing_char', 'read_particle', 'read_colloquial', 'read_filler', 'read_restatement', 'read_asr', 'read_demonstrative', 'read_compound', 'search_typo', 'search_conversion', 'search_missing_char', 'search_particle', 'search_colloquial', 'search_filler', 'search_restatement', 'search_asr', 'search_demonstrative', 'search_compound', 'web_typo', 'web_conversion', 'web_missing_char', 'web_particle', 'web_colloquial', 'web_filler', 'web_restatement', 'web_asr', 'web_demonstrative', 'web_compound']

  - `read_typo` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `read_conversion` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `read_missing_char` intended=`c_meaning_read` rank=8 top=`c_goal_web` other_object:web:goal
  - `read_particle` intended=`c_meaning_read` rank=8 top=`c_goal_web` other_object:web:goal
  - `read_colloquial` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `read_filler` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `read_restatement` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `read_asr` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `read_demonstrative` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `read_compound` intended=`c_meaning_read` rank=7 top=`c_goal_web` other_object:web:goal
  - `search_typo` intended=`c_meaning_search` rank=3 top=`c_goal_web` other_object:web:goal
  - `search_conversion` intended=`c_meaning_search` rank=4 top=`c_goal_web` other_object:web:goal
  - `search_missing_char` intended=`c_meaning_search` rank=4 top=`c_goal_search` same_object_other_slot:goal
  - `search_particle` intended=`c_meaning_search` rank=4 top=`c_goal_search` same_object_other_slot:goal
  - `search_colloquial` intended=`c_role_search` rank=13 top=`c_goal_web` other_object:web:goal
  - `search_filler` intended=`c_meaning_search` rank=5 top=`c_goal_web` other_object:web:goal
  - `search_restatement` intended=`c_meaning_search` rank=2 top=`c_goal_web` other_object:web:goal
  - `search_asr` intended=`c_meaning_search` rank=3 top=`c_goal_web` other_object:web:goal
  - `search_demonstrative` intended=`c_role_search` rank=13 top=`c_goal_web` other_object:web:goal
  - `search_compound` intended=`c_role_search` rank=13 top=`c_goal_web` other_object:web:goal
  - `web_typo` intended=`c_meaning_web` rank=6 top=`c_goal_web` same_object_other_slot:goal
  - `web_conversion` intended=`c_meaning_web` rank=6 top=`c_goal_web` same_object_other_slot:goal
  - `web_missing_char` intended=`c_meaning_web` rank=5 top=`c_goal_web` same_object_other_slot:goal
  - `web_particle` intended=`c_meaning_web` rank=5 top=`c_goal_web` same_object_other_slot:goal
  - `web_colloquial` intended=`c_role_web` rank=10 top=`c_goal_web` same_object_other_slot:goal
  - `web_filler` intended=`c_meaning_web` rank=5 top=`c_goal_web` same_object_other_slot:goal
  - `web_restatement` intended=`c_meaning_web` rank=5 top=`c_goal_web` same_object_other_slot:goal
  - `web_asr` intended=`c_meaning_web` rank=6 top=`c_goal_web` same_object_other_slot:goal
  - `web_demonstrative` intended=`c_role_web` rank=9 top=`c_goal_web` same_object_other_slot:goal
  - `web_compound` intended=`c_role_web` rank=11 top=`c_goal_web` same_object_other_slot:goal

## ノイズ種別まとめ

- `clean`: gold_top 0/3 mean_rank=5.333 mean_gap=-0.265234 mean_delta_vs_clean=None failed=['read_clean', 'search_clean', 'web_clean']
- `typo`: gold_top 0/3 mean_rank=5.333 mean_gap=-0.294231 mean_delta_vs_clean=-0.168701 failed=['read_typo', 'search_typo', 'web_typo']
- `conversion`: gold_top 0/3 mean_rank=5.667 mean_gap=-0.254204 mean_delta_vs_clean=-0.045471 failed=['read_conversion', 'search_conversion', 'web_conversion']
- `missing_char`: gold_top 0/3 mean_rank=5.667 mean_gap=-0.230881 mean_delta_vs_clean=-0.007542 failed=['read_missing_char', 'search_missing_char', 'web_missing_char']
- `particle_drop`: gold_top 0/3 mean_rank=5.667 mean_gap=-0.266107 mean_delta_vs_clean=-0.008841 failed=['read_particle', 'search_particle', 'web_particle']
- `colloquial`: gold_top 0/3 mean_rank=10.0 mean_gap=-0.61793 mean_delta_vs_clean=-0.418523 failed=['read_colloquial', 'search_colloquial', 'web_colloquial']
- `filler`: gold_top 0/3 mean_rank=5.667 mean_gap=-0.320842 mean_delta_vs_clean=-0.075843 failed=['read_filler', 'search_filler', 'web_filler']
- `restatement`: gold_top 0/3 mean_rank=4.667 mean_gap=-0.291745 mean_delta_vs_clean=-0.060571 failed=['read_restatement', 'search_restatement', 'web_restatement']
- `asr_like`: gold_top 0/3 mean_rank=5.333 mean_gap=-0.284166 mean_delta_vs_clean=-0.151538 failed=['read_asr', 'search_asr', 'web_asr']
- `demonstrative`: gold_top 0/3 mean_rank=9.667 mean_gap=-0.55525 mean_delta_vs_clean=-0.344537 failed=['read_demonstrative', 'search_demonstrative', 'web_demonstrative']
- `compound`: gold_top 0/3 mean_rank=10.333 mean_gap=-0.66604 mean_delta_vs_clean=-0.419296 failed=['read_compound', 'search_compound', 'web_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'particle_drop', 'colloquial', 'filler', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `read_typo` [typo] このふぁいるを読んで gold_rank=7 gold_cos=0.342494 top=`c_goal_web` 0.750364 delta_vs_clean=-0.156649
- `read_conversion` [conversion] このファイルを呼んで gold_rank=7 gold_cos=0.47289 top=`c_goal_web` 0.793637 delta_vs_clean=-0.026253
- `read_missing_char` [missing_char] このファイルを読 gold_rank=8 gold_cos=0.507307 top=`c_goal_web` 0.793254 delta_vs_clean=0.008164
- `read_particle` [particle_drop] このファイル読んで gold_rank=8 gold_cos=0.489011 top=`c_goal_web` 0.826594 delta_vs_clean=-0.010132
- `read_colloquial` [colloquial] このファイルのやつ読んで gold_rank=7 gold_cos=0.442203 top=`c_goal_web` 0.810807 delta_vs_clean=-0.05694
- `read_filler` [filler] えっとこのファイルを読んで gold_rank=7 gold_cos=0.439227 top=`c_goal_web` 0.813855 delta_vs_clean=-0.059916
- `read_restatement` [restatement] いや検索じゃなくてこのファイルを読んで gold_rank=7 gold_cos=0.432938 top=`c_goal_web` 0.80023 delta_vs_clean=-0.066205
- `read_asr` [asr_like] このファいるを呼んで gold_rank=7 gold_cos=0.336097 top=`c_goal_web` 0.771968 delta_vs_clean=-0.163046
- `read_demonstrative` [demonstrative] そっちのファイル gold_rank=7 gold_cos=0.443519 top=`c_goal_web` 0.771687 delta_vs_clean=-0.055624
- `read_compound` [compound] えっとこのファイルを呼んでくれるやつ gold_rank=7 gold_cos=0.404475 top=`c_goal_web` 0.795649 delta_vs_clean=-0.094668
- `search_typo` [typo] りぽじとりの中を検索して gold_rank=3 gold_cos=0.489155 top=`c_goal_web` 0.573435 delta_vs_clean=-0.240679
- `search_conversion` [conversion] リポジトリの中を件作して gold_rank=4 gold_cos=0.691098 top=`c_goal_web` 0.787903 delta_vs_clean=-0.038736
- `search_missing_char` [missing_char] リポジトリの中を検 gold_rank=4 gold_cos=0.68406 top=`c_goal_search` 0.777909 delta_vs_clean=-0.045774
- `search_particle` [particle_drop] リポジトリ中を検索して gold_rank=4 gold_cos=0.716791 top=`c_goal_search` 0.872321 delta_vs_clean=-0.013043
- `search_colloquial` [colloquial] 中を探してるほう gold_rank=13 gold_cos=-0.077495 top=`c_goal_web` 0.692376 delta_vs_clean=-0.807329
- `search_filler` [filler] あのーリポジトリの中を検索してなんですけど gold_rank=5 gold_cos=0.583436 top=`c_goal_web` 0.754019 delta_vs_clean=-0.146398
- `search_restatement` [restatement] ネットじゃなくてリポジトリの中を検索して gold_rank=2 gold_cos=0.632063 top=`c_goal_web` 0.776815 delta_vs_clean=-0.097771
- `search_asr` [asr_like] リポジ鳥の中を件作して gold_rank=3 gold_cos=0.482824 top=`c_goal_web` 0.575287 delta_vs_clean=-0.24701
- `search_demonstrative` [demonstrative] ローカルのほう gold_rank=13 gold_cos=0.037699 top=`c_goal_web` 0.773414 delta_vs_clean=-0.692135
- `search_compound` [compound] あの実際フォルダで探してるほう gold_rank=13 gold_cos=0.005708 top=`c_goal_web` 0.81153 delta_vs_clean=-0.724126
- `web_typo` [typo] ねっとで調べて gold_rank=6 gold_cos=0.37098 top=`c_goal_web` 0.761524 delta_vs_clean=-0.108776
- `web_conversion` [conversion] 熱っとで調べて gold_rank=6 gold_cos=0.408331 top=`c_goal_web` 0.753391 delta_vs_clean=-0.071425
- `web_missing_char` [missing_char] ネットで調 gold_rank=5 gold_cos=0.49474 top=`c_goal_web` 0.807586 delta_vs_clean=0.014984
- `web_particle` [particle_drop] ネット調べて gold_rank=5 gold_cos=0.476409 top=`c_goal_web` 0.781616 delta_vs_clean=-0.003347
- `web_colloquial` [colloquial] ネットのやつ gold_rank=10 gold_cos=0.088456 top=`c_goal_web` 0.803772 delta_vs_clean=-0.3913
- `web_filler` [filler] まあネットで調べてかな gold_rank=5 gold_cos=0.45854 top=`c_goal_web` 0.875856 delta_vs_clean=-0.021216
- `web_restatement` [restatement] ローカルじゃなくてネットで調べて gold_rank=5 gold_cos=0.46202 top=`c_goal_web` 0.825211 delta_vs_clean=-0.017736
- `web_asr` [asr_like] 熱斗で調べて gold_rank=6 gold_cos=0.435199 top=`c_goal_web` 0.759363 delta_vs_clean=-0.044557
- `web_demonstrative` [demonstrative] ネットのほう gold_rank=9 gold_cos=0.193904 top=`c_goal_web` 0.795772 delta_vs_clean=-0.285852
- `web_compound` [compound] まあねっとで調べるのも gold_rank=11 gold_cos=0.040662 top=`c_goal_web` 0.841785 delta_vs_clean=-0.439094

## 各クエリ

### read_clean [clean] このファイルを読んで

gold=`c_meaning_read` rank=7 cosine=0.499143 gold_is_top=`False` gap_vs_second=-0.314204 delta_vs_clean=None

- r1 0.813347 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.752437 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.684557 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.656702 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.64678 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.606474 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.499143 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.491986 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.223631 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.223094 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.220865 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.19269 `c_role_web` Target Role: search_web のネット検索
- r13 0.173614 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.101307 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.015443 `c_focus_license` Focus path: LICENSE
- r16 -0.019214 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.065215 `c_focus_search` Focus path: search_files query in workspace

### read_typo [typo] このふぁいるを読んで

gold=`c_meaning_read` rank=7 cosine=0.342494 gold_is_top=`False` gap_vs_second=-0.40787 delta_vs_clean=-0.156649

- r1 0.750364 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.618952 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.528106 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.516661 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.424786 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.402014 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.342494 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.266388 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.004172 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 -0.019599 `c_focus_web` Focus: search_web の検索クエリ
- r11 -0.0407 `c_role_read` Target Role: read_file のワークスペース読取
- r12 -0.054686 `c_role_web` Target Role: search_web のネット検索
- r13 -0.087267 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.139318 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.22297 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.227365 `c_focus_license` Focus path: LICENSE
- r17 -0.266334 `c_focus_search` Focus path: search_files query in workspace

### read_conversion [conversion] このファイルを呼んで

gold=`c_meaning_read` rank=7 cosine=0.47289 gold_is_top=`False` gap_vs_second=-0.320747 delta_vs_clean=-0.026253

- r1 0.793637 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.719146 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.653639 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.645383 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.617167 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.56312 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.47289 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.447215 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.206301 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.197966 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.176904 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.163296 `c_role_web` Target Role: search_web のネット検索
- r13 0.144628 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.069907 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.067306 `c_focus_license` Focus path: LICENSE
- r16 -0.070736 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.121953 `c_focus_search` Focus path: search_files query in workspace

### read_missing_char [missing_char] このファイルを読

gold=`c_meaning_read` rank=8 cosine=0.507307 gold_is_top=`False` gap_vs_second=-0.285947 delta_vs_clean=0.008164

- r1 0.793254 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.751796 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.662325 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.65363 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r5 0.649724 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r6 0.60812 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.50793 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.507307 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r9 0.291939 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.258574 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.248108 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.231749 `c_role_web` Target Role: search_web のネット検索
- r13 0.216773 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.149416 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.021408 `c_focus_license` Focus path: LICENSE
- r16 0.014312 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.030421 `c_focus_search` Focus path: search_files query in workspace

### read_particle [particle_drop] このファイル読んで

gold=`c_meaning_read` rank=8 cosine=0.489011 gold_is_top=`False` gap_vs_second=-0.337583 delta_vs_clean=-0.010132

- r1 0.826594 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.724087 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.693344 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.635187 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.611338 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.596293 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.497385 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.489011 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r9 0.225799 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.201712 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.196421 `c_role_read` Target Role: read_file のワークスペース読取
- r12 0.167653 `c_role_web` Target Role: search_web のネット検索
- r13 0.142635 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.09482 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.004748 `c_focus_license` Focus path: LICENSE
- r16 -0.026143 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.069155 `c_focus_search` Focus path: search_files query in workspace

### read_colloquial [colloquial] このファイルのやつ読んで

gold=`c_meaning_read` rank=7 cosine=0.442203 gold_is_top=`False` gap_vs_second=-0.368604 delta_vs_clean=-0.05694

- r1 0.810807 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.708535 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.65231 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.601439 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.598213 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.54405 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.442203 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.433198 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.185489 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.174584 `c_role_read` Target Role: read_file のワークスペース読取
- r11 0.161543 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.13023 `c_role_web` Target Role: search_web のネット検索
- r13 0.112393 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.036317 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.089562 `c_focus_license` Focus path: LICENSE
- r16 -0.090487 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.129387 `c_focus_search` Focus path: search_files query in workspace

### read_filler [filler] えっとこのファイルを読んで

gold=`c_meaning_read` rank=7 cosine=0.439227 gold_is_top=`False` gap_vs_second=-0.374628 delta_vs_clean=-0.059916

- r1 0.813855 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.697001 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.682679 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.612693 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.60541 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.549967 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.439227 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.429295 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.169463 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.165985 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.158564 `c_role_read` Target Role: read_file のワークスペース読取
- r12 0.125696 `c_role_web` Target Role: search_web のネット検索
- r13 0.108475 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.026085 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.082873 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.098831 `c_focus_license` Focus path: LICENSE
- r17 -0.114672 `c_focus_search` Focus path: search_files query in workspace

### read_restatement [restatement] いや検索じゃなくてこのファイルを読んで

gold=`c_meaning_read` rank=7 cosine=0.432938 gold_is_top=`False` gap_vs_second=-0.367292 delta_vs_clean=-0.066205

- r1 0.80023 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.678978 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.662093 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.621633 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.612174 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.53675 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.432938 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.382655 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.193026 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.14679 `c_role_read` Target Role: read_file のワークスペース読取
- r11 0.142869 `c_role_web` Target Role: search_web のネット検索
- r12 0.136455 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.116033 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.003536 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.119354 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.142749 `c_focus_license` Focus path: LICENSE
- r17 -0.145013 `c_focus_search` Focus path: search_files query in workspace

### read_asr [asr_like] このファいるを呼んで

gold=`c_meaning_read` rank=7 cosine=0.336097 gold_is_top=`False` gap_vs_second=-0.435871 delta_vs_clean=-0.163046

- r1 0.771968 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.606811 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.555087 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.526696 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.454694 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.429416 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.336097 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.283834 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.009458 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 -0.005769 `c_role_read` Target Role: read_file のワークスペース読取
- r11 -0.009044 `c_focus_web` Focus: search_web の検索クエリ
- r12 -0.031539 `c_role_web` Target Role: search_web のネット検索
- r13 -0.065695 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.122321 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.242723 `c_focus_license` Focus path: LICENSE
- r16 -0.249555 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.285351 `c_focus_search` Focus path: search_files query in workspace

### read_demonstrative [demonstrative] そっちのファイル

gold=`c_meaning_read` rank=7 cosine=0.443519 gold_is_top=`False` gap_vs_second=-0.328168 delta_vs_clean=-0.055624

- r1 0.771687 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.654524 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.618042 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.591494 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.531452 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.493615 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.443519 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.383091 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.133364 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.106131 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.080452 `c_role_read` Target Role: read_file のワークスペース読取
- r12 0.068195 `c_role_web` Target Role: search_web のネット検索
- r13 0.041636 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.044931 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.157875 `c_focus_license` Focus path: LICENSE
- r16 -0.16668 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.190621 `c_focus_search` Focus path: search_files query in workspace

### read_compound [compound] えっとこのファイルを呼んでくれるやつ

gold=`c_meaning_read` rank=7 cosine=0.404475 gold_is_top=`False` gap_vs_second=-0.391174 delta_vs_clean=-0.094668

- r1 0.795649 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.65816 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.640438 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.590936 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.570359 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.505263 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.404475 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.385649 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.135566 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.131165 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.126554 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.098304 `c_role_web` Target Role: search_web のネット検索
- r13 0.07987 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.009247 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.134133 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.157858 `c_focus_license` Focus path: LICENSE
- r17 -0.165839 `c_focus_search` Focus path: search_files query in workspace

### search_clean [clean] リポジトリの中を検索して

gold=`c_meaning_search` rank=4 cosine=0.729834 gold_is_top=`False` gap_vs_second=-0.108819 delta_vs_clean=None

- r1 0.838653 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.803357 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.760103 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.729834 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.686815 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.655007 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.551079 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.537258 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.404949 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.400013 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.368617 `c_role_search` Target Role: search_files のワークスペース検索
- r12 0.360802 `c_role_web` Target Role: search_web のネット検索
- r13 0.333274 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.221248 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.09736 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.059609 `c_focus_license` Focus path: LICENSE
- r17 0.056536 `c_focus_search` Focus path: search_files query in workspace

### search_typo [typo] りぽじとりの中を検索して

gold=`c_meaning_search` rank=3 cosine=0.489155 gold_is_top=`False` gap_vs_second=-0.08428 delta_vs_clean=-0.240679

- r1 0.573435 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.540645 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.489155 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r4 0.409327 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.345323 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r6 0.332902 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.280339 `c_meaning_web` Meaning: ウェブを検索する
- r8 0.159623 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 -0.023669 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 -0.037074 `c_focus_web` Focus: search_web の検索クエリ
- r11 -0.048164 `c_role_web` Target Role: search_web のネット検索
- r12 -0.051259 `c_role_read` Target Role: read_file のワークスペース読取
- r13 -0.075863 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.1728 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.265412 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.278913 `c_focus_license` Focus path: LICENSE
- r17 -0.295285 `c_focus_search` Focus path: search_files query in workspace

### search_conversion [conversion] リポジトリの中を件作して

gold=`c_meaning_search` rank=4 cosine=0.691098 gold_is_top=`False` gap_vs_second=-0.096805 delta_vs_clean=-0.038736

- r1 0.787903 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.769177 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.766238 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r4 0.691098 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.673172 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.60264 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.506272 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.485289 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.317727 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.297183 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.267429 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.26476 `c_role_web` Target Role: search_web のネット検索
- r13 0.263859 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.142887 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.015749 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.017311 `c_focus_license` Focus path: LICENSE
- r17 -0.026017 `c_focus_search` Focus path: search_files query in workspace

### search_missing_char [missing_char] リポジトリの中を検

gold=`c_meaning_search` rank=4 cosine=0.68406 gold_is_top=`False` gap_vs_second=-0.093849 delta_vs_clean=-0.045774

- r1 0.777909 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.770706 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.751375 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.68406 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.673491 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.623283 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.522531 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.517378 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r9 0.380956 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.354041 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.331001 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.328272 `c_role_search` Target Role: search_files のワークスペース検索
- r13 0.323356 `c_role_web` Target Role: search_web のネット検索
- r14 0.213563 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.091852 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.072074 `c_focus_license` Focus path: LICENSE
- r17 0.05073 `c_focus_search` Focus path: search_files query in workspace

### search_particle [particle_drop] リポジトリ中を検索して

gold=`c_meaning_search` rank=4 cosine=0.716791 gold_is_top=`False` gap_vs_second=-0.15553 delta_vs_clean=-0.013043

- r1 0.872321 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.816504 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.735081 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.716791 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.671631 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.667524 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.54202 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.536741 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r9 0.456448 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.439615 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.417226 `c_role_search` Target Role: search_files のワークスペース検索
- r12 0.405907 `c_role_web` Target Role: search_web のネット検索
- r13 0.365502 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.268947 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.130203 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.088486 `c_focus_search` Focus path: search_files query in workspace
- r17 0.08699 `c_focus_license` Focus path: LICENSE

### search_colloquial [colloquial] 中を探してるほう

gold=`c_role_search` rank=13 cosine=-0.077495 gold_is_top=`False` gap_vs_second=-0.769871 delta_vs_clean=-0.807329

- r1 0.692376 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.561261 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.489896 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.488833 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.390807 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.365104 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.320028 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.248178 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.034918 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 -0.022858 `c_focus_web` Focus: search_web の検索クエリ
- r11 -0.023557 `c_role_read` Target Role: read_file のワークスペース読取
- r12 -0.045652 `c_role_web` Target Role: search_web のネット検索
- r13 -0.077495 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r14 -0.134845 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.236079 `c_focus_license` Focus path: LICENSE
- r16 -0.247973 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.262534 `c_focus_search` Focus path: search_files query in workspace

### search_filler [filler] あのーリポジトリの中を検索してなんですけど

gold=`c_meaning_search` rank=5 cosine=0.583436 gold_is_top=`False` gap_vs_second=-0.170583 delta_vs_clean=-0.146398

- r1 0.754019 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.627006 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.622493 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.602414 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r5 0.583436 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r6 0.478952 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.385902 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.328487 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.134244 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.112663 `c_role_read` Target Role: read_file のワークスペース読取
- r11 0.095695 `c_role_web` Target Role: search_web のネット検索
- r12 0.077989 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.07792 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.051023 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.143871 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.185073 `c_focus_search` Focus path: search_files query in workspace
- r17 -0.188862 `c_focus_license` Focus path: LICENSE

### search_restatement [restatement] ネットじゃなくてリポジトリの中を検索して

gold=`c_meaning_search` rank=2 cosine=0.632063 gold_is_top=`False` gap_vs_second=-0.144752 delta_vs_clean=-0.097771

- r1 0.776815 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.632063 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r3 0.625938 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.619353 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.611163 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.516481 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.443012 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.347633 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.180186 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.155822 `c_role_web` Target Role: search_web のネット検索
- r11 0.132153 `c_role_read` Target Role: read_file のワークスペース読取
- r12 0.112962 `c_role_search` Target Role: search_files のワークスペース検索
- r13 0.101658 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 -0.022046 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.121099 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.157163 `c_focus_search` Focus path: search_files query in workspace
- r17 -0.165335 `c_focus_license` Focus path: LICENSE

### search_asr [asr_like] リポジ鳥の中を件作して

gold=`c_meaning_search` rank=3 cosine=0.482824 gold_is_top=`False` gap_vs_second=-0.092463 delta_vs_clean=-0.24701

- r1 0.575287 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.528319 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.482824 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r4 0.43279 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.375464 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.308578 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r7 0.286219 `c_meaning_web` Meaning: ウェブを検索する
- r8 0.135902 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 -0.039904 `c_role_read` Target Role: read_file のワークスペース読取
- r10 -0.04537 `c_role_web` Target Role: search_web のネット検索
- r11 -0.049153 `c_focus_web` Focus: search_web の検索クエリ
- r12 -0.055909 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 -0.070554 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.19035 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.30614 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.332035 `c_focus_license` Focus path: LICENSE
- r17 -0.352065 `c_focus_search` Focus path: search_files query in workspace

### search_demonstrative [demonstrative] ローカルのほう

gold=`c_role_search` rank=13 cosine=0.037699 gold_is_top=`False` gap_vs_second=-0.735715 delta_vs_clean=-0.692135

- r1 0.773414 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.649587 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.586688 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.585146 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.502198 `c_meaning_web` Meaning: ウェブを検索する
- r6 0.493313 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.429568 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.388668 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.151941 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.109902 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.080284 `c_role_web` Target Role: search_web のネット検索
- r12 0.075744 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.037699 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r14 -0.002982 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.065546 `c_focus_license` Focus path: LICENSE
- r16 -0.101127 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.140719 `c_focus_search` Focus path: search_files query in workspace

### search_compound [compound] あの実際フォルダで探してるほう

gold=`c_role_search` rank=13 cosine=0.005708 gold_is_top=`False` gap_vs_second=-0.805822 delta_vs_clean=-0.724126

- r1 0.81153 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.62146 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.602046 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.538988 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.535389 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.460313 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.342368 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.328624 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.071878 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.061207 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.054489 `c_role_read` Target Role: read_file のワークスペース読取
- r12 0.033147 `c_role_web` Target Role: search_web のネット検索
- r13 0.005708 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r14 -0.075268 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.185834 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 -0.197108 `c_focus_license` Focus path: LICENSE
- r17 -0.220909 `c_focus_search` Focus path: search_files query in workspace

### web_clean [clean] ネットで調べて

gold=`c_meaning_web` rank=5 cosine=0.479756 gold_is_top=`False` gap_vs_second=-0.37268 delta_vs_clean=None

- r1 0.852436 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.636219 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.558347 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.541699 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.479756 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r6 0.458954 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.393103 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.316402 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.092107 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.076214 `c_role_web` Target Role: search_web のネット検索
- r11 0.061568 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.012849 `c_role_read` Target Role: read_file のワークスペース読取
- r13 -0.004163 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.067219 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.175969 `c_focus_license` Focus path: LICENSE
- r16 -0.186184 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.198867 `c_focus_search` Focus path: search_files query in workspace

### web_typo [typo] ねっとで調べて

gold=`c_meaning_web` rank=6 cosine=0.37098 gold_is_top=`False` gap_vs_second=-0.390544 delta_vs_clean=-0.108776

- r1 0.761524 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.592486 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.497017 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.467336 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.390636 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.37098 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r7 0.293272 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.235487 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.016389 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 -0.023574 `c_focus_web` Focus: search_web の検索クエリ
- r11 -0.058938 `c_role_read` Target Role: read_file のワークスペース読取
- r12 -0.062794 `c_role_web` Target Role: search_web のネット検索
- r13 -0.101353 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.155279 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.240377 `c_focus_license` Focus path: LICENSE
- r16 -0.246034 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.261311 `c_focus_search` Focus path: search_files query in workspace

### web_conversion [conversion] 熱っとで調べて

gold=`c_meaning_web` rank=6 cosine=0.408331 gold_is_top=`False` gap_vs_second=-0.34506 delta_vs_clean=-0.071425

- r1 0.753391 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.58019 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.537608 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.4967 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.423656 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.408331 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r7 0.312225 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.277623 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.082485 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.010571 `c_focus_web` Focus: search_web の検索クエリ
- r11 -0.005992 `c_role_read` Target Role: read_file のワークスペース読取
- r12 -0.028621 `c_role_web` Target Role: search_web のネット検索
- r13 -0.065659 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.114799 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.226132 `c_focus_license` Focus path: LICENSE
- r16 -0.246989 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.26223 `c_focus_search` Focus path: search_files query in workspace

### web_missing_char [missing_char] ネットで調

gold=`c_meaning_web` rank=5 cosine=0.49474 gold_is_top=`False` gap_vs_second=-0.312846 delta_vs_clean=0.014984

- r1 0.807586 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.644761 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.592544 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.555448 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.49474 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r6 0.473362 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.426458 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.336947 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.127657 `c_role_web` Target Role: search_web のネット検索
- r10 0.123087 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.099742 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.068085 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.04789 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.009193 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.121992 `c_focus_license` Focus path: LICENSE
- r16 -0.138583 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.160354 `c_focus_search` Focus path: search_files query in workspace

### web_particle [particle_drop] ネット調べて

gold=`c_meaning_web` rank=5 cosine=0.476409 gold_is_top=`False` gap_vs_second=-0.305207 delta_vs_clean=-0.003347

- r1 0.781616 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.652224 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.585777 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.528624 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.476409 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r6 0.457058 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r7 0.444508 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r8 0.324791 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.140953 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.132031 `c_role_web` Target Role: search_web のネット検索
- r11 0.097052 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.052447 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.047872 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.02455 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.128424 `c_focus_license` Focus path: LICENSE
- r16 -0.141976 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.16406 `c_focus_search` Focus path: search_files query in workspace

### web_colloquial [colloquial] ネットのやつ

gold=`c_role_web` rank=10 cosine=0.088456 gold_is_top=`False` gap_vs_second=-0.715316 delta_vs_clean=-0.3913

- r1 0.803772 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.618809 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.556707 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.524725 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.483245 `c_meaning_web` Meaning: ウェブを検索する
- r6 0.451159 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.394609 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.306981 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.092256 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.088456 `c_role_web` Target Role: search_web のネット検索 GOLD
- r11 0.059567 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.01482 `c_role_read` Target Role: read_file のワークスペース読取
- r13 -0.00279 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.071124 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.178866 `c_focus_license` Focus path: LICENSE
- r16 -0.190813 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.214227 `c_focus_search` Focus path: search_files query in workspace

### web_filler [filler] まあネットで調べてかな

gold=`c_meaning_web` rank=5 cosine=0.45854 gold_is_top=`False` gap_vs_second=-0.417316 delta_vs_clean=-0.021216

- r1 0.875856 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.594634 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.543095 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.48567 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.45854 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r6 0.450696 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.300608 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.297288 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r9 0.04793 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.0409 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.002473 `c_role_web` Target Role: search_web のネット検索
- r12 -0.021095 `c_role_read` Target Role: read_file のワークスペース読取
- r13 -0.062272 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.100725 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.197187 `c_focus_license` Focus path: LICENSE
- r16 -0.203829 `c_focus_search` Focus path: search_files query in workspace
- r17 -0.208643 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md

### web_restatement [restatement] ローカルじゃなくてネットで調べて

gold=`c_meaning_web` rank=5 cosine=0.46202 gold_is_top=`False` gap_vs_second=-0.363191 delta_vs_clean=-0.017736

- r1 0.825211 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.605205 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.54335 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.537117 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.46202 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r6 0.46065 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.35954 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.291459 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.048601 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.029326 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.017741 `c_role_web` Target Role: search_web のネット検索
- r12 -0.021333 `c_role_read` Target Role: read_file のワークスペース読取
- r13 -0.046557 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.115718 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.194029 `c_focus_license` Focus path: LICENSE
- r16 -0.205472 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.234512 `c_focus_search` Focus path: search_files query in workspace

### web_asr [asr_like] 熱斗で調べて

gold=`c_meaning_web` rank=6 cosine=0.435199 gold_is_top=`False` gap_vs_second=-0.324164 delta_vs_clean=-0.044557

- r1 0.759363 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.623803 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.569301 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.53456 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.449922 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.435199 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r7 0.361433 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.284767 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.080436 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.04098 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.01859 `c_role_web` Target Role: search_web のネット検索
- r12 0.017617 `c_role_read` Target Role: read_file のワークスペース読取
- r13 -0.03485 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.07612 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.192022 `c_focus_license` Focus path: LICENSE
- r16 -0.207042 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.246945 `c_focus_search` Focus path: search_files query in workspace

### web_demonstrative [demonstrative] ネットのほう

gold=`c_role_web` rank=9 cosine=0.193904 gold_is_top=`False` gap_vs_second=-0.601868 delta_vs_clean=-0.285852

- r1 0.795772 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.661007 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.628133 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r4 0.60079 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.537575 `c_meaning_web` Meaning: ウェブを検索する
- r6 0.517331 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.491098 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.409608 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.193904 `c_role_web` Target Role: search_web のネット検索 GOLD
- r10 0.19388 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.184664 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.132182 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.109116 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.058095 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.04728 `c_focus_license` Focus path: LICENSE
- r16 -0.064899 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.097703 `c_focus_search` Focus path: search_files query in workspace

### web_compound [compound] まあねっとで調べるのも

gold=`c_role_web` rank=11 cosine=0.040662 gold_is_top=`False` gap_vs_second=-0.801123 delta_vs_clean=-0.439094

- r1 0.841785 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.665126 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.589451 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.553451 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.492879 `c_meaning_web` Meaning: ウェブを検索する
- r6 0.490816 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.383627 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.342238 `c_meaning_create` Meaning: 新しいファイルを作る
- r9 0.085432 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.081144 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.040662 `c_role_web` Target Role: search_web のネット検索 GOLD
- r12 0.028486 `c_role_read` Target Role: read_file のワークスペース読取
- r13 -0.014465 `c_role_search` Target Role: search_files のワークスペース検索
- r14 -0.060405 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 -0.153421 `c_focus_license` Focus path: LICENSE
- r16 -0.167658 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 -0.190271 `c_focus_search` Focus path: search_files query in workspace
