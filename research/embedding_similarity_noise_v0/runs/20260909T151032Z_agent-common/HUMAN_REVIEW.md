# Embedding similarity Japanese input noise v0

- run_id: `20260909T151032Z`
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

- baseline: VRAM 3765 / 12288 MiB, RAM used 38796 / 65277 MB
- after_embed: VRAM 3765 / 12288 MiB, RAM used 38839 / 65277 MB

## Agent slot（Goal / Meaning / Focus / Target Role）

仮対応。Production スキーマではない。

- intended_slot_top: 1/30 (0.0333)
- correct_object_top: 27/30 (0.9)
- confusion: {'same_object_other_slot:goal': 17, 'same_object_other_slot:target_role': 9, 'other_object:web:goal': 2, 'unrelated:meaning': 1, 'intended_slot': 1}
- top_slot_type: {'goal': 19, 'target_role': 10, 'meaning': 1}
- failed: ['read_typo', 'read_conversion', 'read_missing_char', 'read_particle', 'read_colloquial', 'read_filler', 'read_restatement', 'read_asr', 'read_demonstrative', 'read_compound', 'search_typo', 'search_conversion', 'search_missing_char', 'search_particle', 'search_colloquial', 'search_filler', 'search_restatement', 'search_asr', 'search_demonstrative', 'search_compound', 'web_typo', 'web_conversion', 'web_missing_char', 'web_particle', 'web_filler', 'web_restatement', 'web_asr', 'web_demonstrative', 'web_compound']

  - `read_typo` intended=`c_meaning_read` rank=4 top=`c_goal_read` same_object_other_slot:goal
  - `read_conversion` intended=`c_meaning_read` rank=4 top=`c_role_read` same_object_other_slot:target_role
  - `read_missing_char` intended=`c_meaning_read` rank=3 top=`c_role_read` same_object_other_slot:target_role
  - `read_particle` intended=`c_meaning_read` rank=3 top=`c_role_read` same_object_other_slot:target_role
  - `read_colloquial` intended=`c_meaning_read` rank=2 top=`c_role_read` same_object_other_slot:target_role
  - `read_filler` intended=`c_meaning_read` rank=3 top=`c_role_read` same_object_other_slot:target_role
  - `read_restatement` intended=`c_meaning_read` rank=4 top=`c_role_read` same_object_other_slot:target_role
  - `read_asr` intended=`c_meaning_read` rank=8 top=`c_goal_web` other_object:web:goal
  - `read_demonstrative` intended=`c_meaning_read` rank=4 top=`c_meaning_create` unrelated:meaning
  - `read_compound` intended=`c_meaning_read` rank=3 top=`c_role_read` same_object_other_slot:target_role
  - `search_typo` intended=`c_meaning_search` rank=4 top=`c_goal_search` same_object_other_slot:goal
  - `search_conversion` intended=`c_meaning_search` rank=4 top=`c_goal_search` same_object_other_slot:goal
  - `search_missing_char` intended=`c_meaning_search` rank=3 top=`c_goal_search` same_object_other_slot:goal
  - `search_particle` intended=`c_meaning_search` rank=3 top=`c_goal_search` same_object_other_slot:goal
  - `search_colloquial` intended=`c_role_search` rank=7 top=`c_goal_search` same_object_other_slot:goal
  - `search_filler` intended=`c_meaning_search` rank=2 top=`c_goal_search` same_object_other_slot:goal
  - `search_restatement` intended=`c_meaning_search` rank=6 top=`c_goal_search` same_object_other_slot:goal
  - `search_asr` intended=`c_meaning_search` rank=14 top=`c_goal_search` same_object_other_slot:goal
  - `search_demonstrative` intended=`c_role_search` rank=10 top=`c_goal_web` other_object:web:goal
  - `search_compound` intended=`c_role_search` rank=2 top=`c_goal_search` same_object_other_slot:goal
  - `web_typo` intended=`c_meaning_web` rank=4 top=`c_goal_web` same_object_other_slot:goal
  - `web_conversion` intended=`c_meaning_web` rank=7 top=`c_goal_web` same_object_other_slot:goal
  - `web_missing_char` intended=`c_meaning_web` rank=4 top=`c_role_web` same_object_other_slot:target_role
  - `web_particle` intended=`c_meaning_web` rank=4 top=`c_goal_web` same_object_other_slot:goal
  - `web_filler` intended=`c_meaning_web` rank=3 top=`c_goal_web` same_object_other_slot:goal
  - `web_restatement` intended=`c_meaning_web` rank=3 top=`c_role_web` same_object_other_slot:target_role
  - `web_asr` intended=`c_meaning_web` rank=8 top=`c_goal_web` same_object_other_slot:goal
  - `web_demonstrative` intended=`c_role_web` rank=2 top=`c_goal_web` same_object_other_slot:goal
  - `web_compound` intended=`c_role_web` rank=2 top=`c_goal_web` same_object_other_slot:goal

## ノイズ種別まとめ

- `clean`: gold_top 0/3 mean_rank=3.0 mean_gap=-0.121102 mean_delta_vs_clean=None failed=['read_clean', 'search_clean', 'web_clean']
- `typo`: gold_top 0/3 mean_rank=4.0 mean_gap=-0.08265 mean_delta_vs_clean=-0.078724 failed=['read_typo', 'search_typo', 'web_typo']
- `conversion`: gold_top 0/3 mean_rank=5.0 mean_gap=-0.14799 mean_delta_vs_clean=-0.084788 failed=['read_conversion', 'search_conversion', 'web_conversion']
- `missing_char`: gold_top 0/3 mean_rank=3.333 mean_gap=-0.151531 mean_delta_vs_clean=-0.054592 failed=['read_missing_char', 'search_missing_char', 'web_missing_char']
- `particle_drop`: gold_top 0/3 mean_rank=3.333 mean_gap=-0.142733 mean_delta_vs_clean=0.02158 failed=['read_particle', 'search_particle', 'web_particle']
- `colloquial`: gold_top 1/3 mean_rank=3.333 mean_gap=-0.030265 mean_delta_vs_clean=-0.021072 failed=['read_colloquial', 'search_colloquial']
- `filler`: gold_top 0/3 mean_rank=2.667 mean_gap=-0.093082 mean_delta_vs_clean=-0.057459 failed=['read_filler', 'search_filler', 'web_filler']
- `restatement`: gold_top 0/3 mean_rank=4.333 mean_gap=-0.137765 mean_delta_vs_clean=-0.054667 failed=['read_restatement', 'search_restatement', 'web_restatement']
- `asr_like`: gold_top 0/3 mean_rank=10.0 mean_gap=-0.106631 mean_delta_vs_clean=-0.187571 failed=['read_asr', 'search_asr', 'web_asr']
- `demonstrative`: gold_top 0/3 mean_rank=5.333 mean_gap=-0.032552 mean_delta_vs_clean=-0.093631 failed=['read_demonstrative', 'search_demonstrative', 'web_demonstrative']
- `compound`: gold_top 0/3 mean_rank=2.333 mean_gap=-0.054399 mean_delta_vs_clean=-0.077934 failed=['read_compound', 'search_compound', 'web_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'particle_drop', 'colloquial', 'filler', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `read_typo` [typo] このふぁいるを読んで gold_rank=4 gold_cos=0.475819 top=`c_goal_read` 0.489736 delta_vs_clean=-0.178923
- `read_conversion` [conversion] このファイルを呼んで gold_rank=4 gold_cos=0.527209 top=`c_role_read` 0.643107 delta_vs_clean=-0.127533
- `read_missing_char` [missing_char] このファイルを読 gold_rank=3 gold_cos=0.595825 top=`c_role_read` 0.766114 delta_vs_clean=-0.058917
- `read_particle` [particle_drop] このファイル読んで gold_rank=3 gold_cos=0.660302 top=`c_role_read` 0.727371 delta_vs_clean=0.00556
- `read_colloquial` [colloquial] このファイルのやつ読んで gold_rank=2 gold_cos=0.645948 top=`c_role_read` 0.658064 delta_vs_clean=-0.008794
- `read_filler` [filler] えっとこのファイルを読んで gold_rank=3 gold_cos=0.638956 top=`c_role_read` 0.70016 delta_vs_clean=-0.015786
- `read_restatement` [restatement] いや検索じゃなくてこのファイルを読んで gold_rank=4 gold_cos=0.602467 top=`c_role_read` 0.696243 delta_vs_clean=-0.052275
- `read_asr` [asr_like] このファいるを呼んで gold_rank=8 gold_cos=0.456696 top=`c_goal_web` 0.527308 delta_vs_clean=-0.198046
- `read_demonstrative` [demonstrative] そっちのファイル gold_rank=4 gold_cos=0.577613 top=`c_meaning_create` 0.586699 delta_vs_clean=-0.077129
- `read_compound` [compound] えっとこのファイルを呼んでくれるやつ gold_rank=3 gold_cos=0.568044 top=`c_role_read` 0.633829 delta_vs_clean=-0.086698
- `search_typo` [typo] りぽじとりの中を検索して gold_rank=4 gold_cos=0.605154 top=`c_goal_search` 0.689009 delta_vs_clean=-0.060513
- `search_conversion` [conversion] リポジトリの中を件作して gold_rank=4 gold_cos=0.553699 top=`c_goal_search` 0.72178 delta_vs_clean=-0.111968
- `search_missing_char` [missing_char] リポジトリの中を検 gold_rank=3 gold_cos=0.611144 top=`c_goal_search` 0.820509 delta_vs_clean=-0.054523
- `search_particle` [particle_drop] リポジトリ中を検索して gold_rank=3 gold_cos=0.650712 top=`c_goal_search` 0.886619 delta_vs_clean=-0.014955
- `search_colloquial` [colloquial] 中を探してるほう gold_rank=7 gold_cos=0.569166 top=`c_goal_search` 0.662075 delta_vs_clean=-0.096501
- `search_filler` [filler] あのーリポジトリの中を検索してなんですけど gold_rank=2 gold_cos=0.538794 top=`c_goal_search` 0.686939 delta_vs_clean=-0.126873
- `search_restatement` [restatement] ネットじゃなくてリポジトリの中を検索して gold_rank=6 gold_cos=0.604234 top=`c_goal_search` 0.850277 delta_vs_clean=-0.061433
- `search_asr` [asr_like] リポジ鳥の中を件作して gold_rank=14 gold_cos=0.411548 top=`c_goal_search` 0.547456 delta_vs_clean=-0.254119
- `search_demonstrative` [demonstrative] ローカルのほう gold_rank=10 gold_cos=0.429509 top=`c_goal_web` 0.513989 delta_vs_clean=-0.236158
- `search_compound` [compound] あの実際フォルダで探してるほう gold_rank=2 gold_cos=0.566125 top=`c_goal_search` 0.613312 delta_vs_clean=-0.099542
- `web_typo` [typo] ねっとで調べて gold_rank=4 gold_cos=0.578747 top=`c_goal_web` 0.728926 delta_vs_clean=0.003264
- `web_conversion` [conversion] 熱っとで調べて gold_rank=7 gold_cos=0.560621 top=`c_goal_web` 0.720613 delta_vs_clean=-0.014862
- `web_missing_char` [missing_char] ネットで調 gold_rank=4 gold_cos=0.525148 top=`c_role_web` 0.600086 delta_vs_clean=-0.050335
- `web_particle` [particle_drop] ネット調べて gold_rank=4 gold_cos=0.649619 top=`c_goal_web` 0.774841 delta_vs_clean=0.074136
- `web_filler` [filler] まあネットで調べてかな gold_rank=3 gold_cos=0.545766 top=`c_goal_web` 0.615662 delta_vs_clean=-0.029717
- `web_restatement` [restatement] ローカルじゃなくてネットで調べて gold_rank=3 gold_cos=0.52519 top=`c_role_web` 0.598667 delta_vs_clean=-0.050293
- `web_asr` [asr_like] 熱斗で調べて gold_rank=8 gold_cos=0.464936 top=`c_goal_web` 0.57831 delta_vs_clean=-0.110547
- `web_demonstrative` [demonstrative] ネットのほう gold_rank=2 gold_cos=0.607877 top=`c_goal_web` 0.611967 delta_vs_clean=0.032394
- `web_compound` [compound] まあねっとで調べるのも gold_rank=2 gold_cos=0.527921 top=`c_goal_web` 0.578145 delta_vs_clean=-0.047562

## 各クエリ

### read_clean [clean] このファイルを読んで

gold=`c_meaning_read` rank=3 cosine=0.654742 gold_is_top=`False` gap_vs_second=-0.079336 delta_vs_clean=None

- r1 0.734078 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.673879 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.654742 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.593372 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.544073 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.542144 `c_focus_license` Focus path: LICENSE
- r7 0.533786 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.506239 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r9 0.493116 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.489816 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.488347 `c_goal_weather` Goal: 今日の天気を調べる
- r12 0.450068 `c_role_web` Target Role: search_web のネット検索
- r13 0.448917 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r14 0.430662 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.429518 `c_focus_search` Focus path: search_files query in workspace
- r16 0.417292 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.416425 `c_meaning_web` Meaning: ウェブを検索する

### read_typo [typo] このふぁいるを読んで

gold=`c_meaning_read` rank=4 cosine=0.475819 gold_is_top=`False` gap_vs_second=-0.013917 delta_vs_clean=-0.178923

- r1 0.489736 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r2 0.489686 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.489503 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.475819 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r5 0.449995 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.42841 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r7 0.407593 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r8 0.401512 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.400445 `c_meaning_create` Meaning: 新しいファイルを作る
- r10 0.384563 `c_focus_license` Focus path: LICENSE
- r11 0.377459 `c_role_web` Target Role: search_web のネット検索
- r12 0.369098 `c_focus_web` Focus: search_web の検索クエリ
- r13 0.359947 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.356754 `c_meaning_web` Meaning: ウェブを検索する
- r15 0.354212 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.351068 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r17 0.261549 `c_focus_search` Focus path: search_files query in workspace

### read_conversion [conversion] このファイルを呼んで

gold=`c_meaning_read` rank=4 cosine=0.527209 gold_is_top=`False` gap_vs_second=-0.115898 delta_vs_clean=-0.127533

- r1 0.643107 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.558331 `c_meaning_create` Meaning: 新しいファイルを作る
- r3 0.555015 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.527209 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r5 0.500375 `c_role_search` Target Role: search_files のワークスペース検索
- r6 0.457647 `c_goal_web` Goal: ネットで調べて要点を返す
- r7 0.453474 `c_focus_license` Focus path: LICENSE
- r8 0.448867 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.43792 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r10 0.424675 `c_role_web` Target Role: search_web のネット検索
- r11 0.41853 `c_goal_weather` Goal: 今日の天気を調べる
- r12 0.412246 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r13 0.412086 `c_focus_web` Focus: search_web の検索クエリ
- r14 0.395975 `c_focus_search` Focus path: search_files query in workspace
- r15 0.386803 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.386104 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r17 0.375607 `c_meaning_web` Meaning: ウェブを検索する

### read_missing_char [missing_char] このファイルを読

gold=`c_meaning_read` rank=3 cosine=0.595825 gold_is_top=`False` gap_vs_second=-0.170289 delta_vs_clean=-0.058917

- r1 0.766114 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.64598 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.595825 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.542094 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.49339 `c_role_search` Target Role: search_files のワークスペース検索
- r6 0.481568 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r7 0.468888 `c_goal_web` Goal: ネットで調べて要点を返す
- r8 0.468348 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r9 0.466872 `c_focus_license` Focus path: LICENSE
- r10 0.429452 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.407075 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r12 0.406986 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r13 0.398136 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.38882 `c_role_web` Target Role: search_web のネット検索
- r15 0.387523 `c_focus_search` Focus path: search_files query in workspace
- r16 0.386244 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.356821 `c_meaning_web` Meaning: ウェブを検索する

### read_particle [particle_drop] このファイル読んで

gold=`c_meaning_read` rank=3 cosine=0.660302 gold_is_top=`False` gap_vs_second=-0.067069 delta_vs_clean=0.00556

- r1 0.727371 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.669373 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.660302 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.608644 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.554602 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.552863 `c_role_search` Target Role: search_files のワークスペース検索
- r7 0.551047 `c_focus_license` Focus path: LICENSE
- r8 0.513012 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r9 0.511134 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r10 0.500737 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.499333 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.456427 `c_role_web` Target Role: search_web のネット検索
- r13 0.448872 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r14 0.442774 `c_focus_search` Focus path: search_files query in workspace
- r15 0.434101 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.420422 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.417353 `c_meaning_web` Meaning: ウェブを検索する

### read_colloquial [colloquial] このファイルのやつ読んで

gold=`c_meaning_read` rank=2 cosine=0.645948 gold_is_top=`False` gap_vs_second=-0.012116 delta_vs_clean=-0.008794

- r1 0.658064 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.645948 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r3 0.642605 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.599565 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.560103 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.539524 `c_focus_license` Focus path: LICENSE
- r7 0.526193 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.504011 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.496842 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r10 0.495114 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.467959 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.467909 `c_role_web` Target Role: search_web のネット検索
- r13 0.44582 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.428552 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r15 0.427807 `c_meaning_web` Meaning: ウェブを検索する
- r16 0.419264 `c_focus_search` Focus path: search_files query in workspace
- r17 0.418412 `c_focus_web` Focus: search_web の検索クエリ

### read_filler [filler] えっとこのファイルを読んで

gold=`c_meaning_read` rank=3 cosine=0.638956 gold_is_top=`False` gap_vs_second=-0.061204 delta_vs_clean=-0.015786

- r1 0.70016 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.653421 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.638956 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.58947 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.553909 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.548228 `c_focus_license` Focus path: LICENSE
- r7 0.533854 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.523233 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r9 0.508639 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r10 0.49758 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.496735 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.467616 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r13 0.456048 `c_role_web` Target Role: search_web のネット検索
- r14 0.443268 `c_focus_web` Focus: search_web の検索クエリ
- r15 0.437642 `c_meaning_web` Meaning: ウェブを検索する
- r16 0.428368 `c_focus_search` Focus path: search_files query in workspace
- r17 0.412494 `c_role_followup` Target Role: followup_investigation の追加調査

### read_restatement [restatement] いや検索じゃなくてこのファイルを読んで

gold=`c_meaning_read` rank=4 cosine=0.602467 gold_is_top=`False` gap_vs_second=-0.093776 delta_vs_clean=-0.052275

- r1 0.696243 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.645594 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.616055 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r4 0.602467 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r5 0.598908 `c_role_search` Target Role: search_files のワークスペース検索
- r6 0.569329 `c_goal_web` Goal: ネットで調べて要点を返す
- r7 0.533404 `c_focus_license` Focus path: LICENSE
- r8 0.530914 `c_focus_web` Focus: search_web の検索クエリ
- r9 0.523219 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r10 0.522851 `c_meaning_create` Meaning: 新しいファイルを作る
- r11 0.519257 `c_focus_search` Focus path: search_files query in workspace
- r12 0.511195 `c_role_web` Target Role: search_web のネット検索
- r13 0.494788 `c_meaning_web` Meaning: ウェブを検索する
- r14 0.484546 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r15 0.472605 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.469669 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 0.437851 `c_role_followup` Target Role: followup_investigation の追加調査

### read_asr [asr_like] このファいるを呼んで

gold=`c_meaning_read` rank=8 cosine=0.456696 gold_is_top=`False` gap_vs_second=-0.070612 delta_vs_clean=-0.198046

- r1 0.527308 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.50574 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r3 0.502326 `c_meaning_create` Meaning: 新しいファイルを作る
- r4 0.499979 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.487686 `c_focus_web` Focus: search_web の検索クエリ
- r6 0.463877 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.458724 `c_role_web` Target Role: search_web のネット検索
- r8 0.456696 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r9 0.450326 `c_role_followup` Target Role: followup_investigation の追加調査
- r10 0.45022 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r11 0.449528 `c_focus_license` Focus path: LICENSE
- r12 0.443632 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.441051 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.423854 `c_meaning_web` Meaning: ウェブを検索する
- r15 0.413769 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.39507 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r17 0.345948 `c_focus_search` Focus path: search_files query in workspace

### read_demonstrative [demonstrative] そっちのファイル

gold=`c_meaning_read` rank=4 cosine=0.577613 gold_is_top=`False` gap_vs_second=-0.009086 delta_vs_clean=-0.077129

- r1 0.586699 `c_meaning_create` Meaning: 新しいファイルを作る
- r2 0.581699 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.578797 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.577613 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r5 0.566724 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r6 0.559144 `c_focus_license` Focus path: LICENSE
- r7 0.554557 `c_goal_web` Goal: ネットで調べて要点を返す
- r8 0.544882 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r9 0.508901 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r10 0.494867 `c_focus_search` Focus path: search_files query in workspace
- r11 0.488825 `c_goal_weather` Goal: 今日の天気を調べる
- r12 0.488043 `c_role_web` Target Role: search_web のネット検索
- r13 0.476443 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.46619 `c_focus_web` Focus: search_web の検索クエリ
- r15 0.45062 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r16 0.433946 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.433449 `c_meaning_web` Meaning: ウェブを検索する

### read_compound [compound] えっとこのファイルを呼んでくれるやつ

gold=`c_meaning_read` rank=3 cosine=0.568044 gold_is_top=`False` gap_vs_second=-0.065785 delta_vs_clean=-0.086698

- r1 0.633829 `c_role_read` Target Role: read_file のワークスペース読取
- r2 0.577697 `c_meaning_create` Meaning: 新しいファイルを作る
- r3 0.568044 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.545166 `c_role_search` Target Role: search_files のワークスペース検索
- r5 0.535411 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r6 0.529446 `c_goal_web` Goal: ネットで調べて要点を返す
- r7 0.498322 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r8 0.498262 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r9 0.497269 `c_role_web` Target Role: search_web のネット検索
- r10 0.494795 `c_focus_license` Focus path: LICENSE
- r11 0.460085 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.458676 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.452637 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.447506 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r15 0.427064 `c_meaning_web` Meaning: ウェブを検索する
- r16 0.4264 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r17 0.416522 `c_focus_search` Focus path: search_files query in workspace

### search_clean [clean] リポジトリの中を検索して

gold=`c_meaning_search` rank=3 cosine=0.665667 gold_is_top=`False` gap_vs_second=-0.226573 delta_vs_clean=None

- r1 0.89224 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.733702 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.665667 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r4 0.642895 `c_focus_search` Focus path: search_files query in workspace
- r5 0.60762 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.607322 `c_focus_web` Focus: search_web の検索クエリ
- r7 0.588754 `c_role_web` Target Role: search_web のネット検索
- r8 0.538115 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.506805 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r10 0.499325 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.489713 `c_focus_license` Focus path: LICENSE
- r12 0.473738 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.465761 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r14 0.429275 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.429254 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r16 0.427516 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.427035 `c_meaning_create` Meaning: 新しいファイルを作る

### search_typo [typo] りぽじとりの中を検索して

gold=`c_meaning_search` rank=4 cosine=0.605154 gold_is_top=`False` gap_vs_second=-0.083855 delta_vs_clean=-0.060513

- r1 0.689009 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.632017 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.606121 `c_role_web` Target Role: search_web のネット検索
- r4 0.605154 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.599169 `c_role_search` Target Role: search_files のワークスペース検索
- r6 0.591538 `c_focus_web` Focus: search_web の検索クエリ
- r7 0.545898 `c_goal_weather` Goal: 今日の天気を調べる
- r8 0.516819 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.507776 `c_focus_search` Focus path: search_files query in workspace
- r10 0.459228 `c_role_followup` Target Role: followup_investigation の追加調査
- r11 0.441477 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r12 0.429639 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.429564 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r14 0.424023 `c_role_read` Target Role: read_file のワークスペース読取
- r15 0.423894 `c_focus_license` Focus path: LICENSE
- r16 0.394322 `c_meaning_create` Meaning: 新しいファイルを作る
- r17 0.391095 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md

### search_conversion [conversion] リポジトリの中を件作して

gold=`c_meaning_search` rank=4 cosine=0.553699 gold_is_top=`False` gap_vs_second=-0.168081 delta_vs_clean=-0.111968

- r1 0.72178 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.60329 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.577402 `c_meaning_create` Meaning: 新しいファイルを作る
- r4 0.553699 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.538654 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r6 0.534807 `c_goal_web` Goal: ネットで調べて要点を返す
- r7 0.51788 `c_focus_search` Focus path: search_files query in workspace
- r8 0.50928 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r9 0.503626 `c_focus_license` Focus path: LICENSE
- r10 0.500289 `c_role_web` Target Role: search_web のネット検索
- r11 0.488102 `c_role_read` Target Role: read_file のワークスペース読取
- r12 0.463868 `c_role_followup` Target Role: followup_investigation の追加調査
- r13 0.462559 `c_focus_web` Focus: search_web の検索クエリ
- r14 0.437006 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.436333 `c_meaning_web` Meaning: ウェブを検索する
- r16 0.430869 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.404573 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_missing_char [missing_char] リポジトリの中を検

gold=`c_meaning_search` rank=3 cosine=0.611144 gold_is_top=`False` gap_vs_second=-0.209365 delta_vs_clean=-0.054523

- r1 0.820509 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.646767 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.611144 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r4 0.571814 `c_focus_search` Focus path: search_files query in workspace
- r5 0.538044 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.517384 `c_focus_license` Focus path: LICENSE
- r7 0.515183 `c_focus_web` Focus: search_web の検索クエリ
- r8 0.512217 `c_role_web` Target Role: search_web のネット検索
- r9 0.506698 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r10 0.486684 `c_meaning_web` Meaning: ウェブを検索する
- r11 0.481031 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r12 0.480752 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.438512 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.422196 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r15 0.421886 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.416405 `c_meaning_create` Meaning: 新しいファイルを作る
- r17 0.40447 `c_goal_read` Goal: 指定ファイルを読んで要約する

### search_particle [particle_drop] リポジトリ中を検索して

gold=`c_meaning_search` rank=3 cosine=0.650712 gold_is_top=`False` gap_vs_second=-0.235907 delta_vs_clean=-0.014955

- r1 0.886619 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.723962 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.650712 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r4 0.639925 `c_focus_search` Focus path: search_files query in workspace
- r5 0.603139 `c_focus_web` Focus: search_web の検索クエリ
- r6 0.589472 `c_goal_web` Goal: ネットで調べて要点を返す
- r7 0.57881 `c_role_web` Target Role: search_web のネット検索
- r8 0.526284 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.492161 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r10 0.490708 `c_focus_license` Focus path: LICENSE
- r11 0.482363 `c_goal_weather` Goal: 今日の天気を調べる
- r12 0.466571 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.464379 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r14 0.429398 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.429301 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.420397 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.41688 `c_meaning_create` Meaning: 新しいファイルを作る

### search_colloquial [colloquial] 中を探してるほう

gold=`c_role_search` rank=7 cosine=0.569166 gold_is_top=`False` gap_vs_second=-0.092909 delta_vs_clean=-0.096501

- r1 0.662075 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.646785 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.614379 `c_role_web` Target Role: search_web のネット検索
- r4 0.592306 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.588027 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r6 0.571532 `c_meaning_web` Meaning: ウェブを検索する
- r7 0.569166 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r8 0.545613 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.519291 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.489104 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.488742 `c_focus_search` Focus path: search_files query in workspace
- r12 0.484695 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r13 0.456471 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r14 0.434321 `c_focus_license` Focus path: LICENSE
- r15 0.431069 `c_role_read` Target Role: read_file のワークスペース読取
- r16 0.427733 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.412661 `c_meaning_create` Meaning: 新しいファイルを作る

### search_filler [filler] あのーリポジトリの中を検索してなんですけど

gold=`c_meaning_search` rank=2 cosine=0.538794 gold_is_top=`False` gap_vs_second=-0.148145 delta_vs_clean=-0.126873

- r1 0.686939 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.538794 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r3 0.507181 `c_role_search` Target Role: search_files のワークスペース検索
- r4 0.468237 `c_focus_search` Focus path: search_files query in workspace
- r5 0.463489 `c_meaning_web` Meaning: ウェブを検索する
- r6 0.461332 `c_role_web` Target Role: search_web のネット検索
- r7 0.460651 `c_focus_web` Focus: search_web の検索クエリ
- r8 0.443469 `c_goal_web` Goal: ネットで調べて要点を返す
- r9 0.410025 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r10 0.388752 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.370875 `c_focus_license` Focus path: LICENSE
- r12 0.361073 `c_goal_weather` Goal: 今日の天気を調べる
- r13 0.355669 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.3505 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.320031 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.305954 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.29345 `c_meaning_create` Meaning: 新しいファイルを作る

### search_restatement [restatement] ネットじゃなくてリポジトリの中を検索して

gold=`c_meaning_search` rank=6 cosine=0.604234 gold_is_top=`False` gap_vs_second=-0.246043 delta_vs_clean=-0.061433

- r1 0.850277 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.655675 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.629411 `c_focus_web` Focus: search_web の検索クエリ
- r4 0.620009 `c_role_web` Target Role: search_web のネット検索
- r5 0.613652 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.604234 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r7 0.583906 `c_focus_search` Focus path: search_files query in workspace
- r8 0.555593 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.493406 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.48802 `c_role_read` Target Role: read_file のワークスペース読取
- r11 0.487924 `c_focus_license` Focus path: LICENSE
- r12 0.475102 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r13 0.453111 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r14 0.452896 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.435136 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.428629 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.391254 `c_meaning_create` Meaning: 新しいファイルを作る

### search_asr [asr_like] リポジ鳥の中を件作して

gold=`c_meaning_search` rank=14 cosine=0.411548 gold_is_top=`False` gap_vs_second=-0.135908 delta_vs_clean=-0.254119

- r1 0.547456 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.522716 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.481119 `c_role_followup` Target Role: followup_investigation の追加調査
- r4 0.471611 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.462582 `c_role_web` Target Role: search_web のネット検索
- r6 0.459275 `c_focus_license` Focus path: LICENSE
- r7 0.447784 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.442487 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.441881 `c_role_search` Target Role: search_files のワークスペース検索
- r10 0.440526 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.431545 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r12 0.41891 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r13 0.412016 `c_focus_web` Focus: search_web の検索クエリ
- r14 0.411548 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r15 0.411329 `c_role_read` Target Role: read_file のワークスペース読取
- r16 0.391224 `c_meaning_web` Meaning: ウェブを検索する
- r17 0.3271 `c_focus_search` Focus path: search_files query in workspace

### search_demonstrative [demonstrative] ローカルのほう

gold=`c_role_search` rank=10 cosine=0.429509 gold_is_top=`False` gap_vs_second=-0.08448 delta_vs_clean=-0.236158

- r1 0.513989 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.498754 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r3 0.479212 `c_role_web` Target Role: search_web のネット検索
- r4 0.470063 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.455754 `c_role_followup` Target Role: followup_investigation の追加調査
- r6 0.439855 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r7 0.436225 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r8 0.436221 `c_focus_web` Focus: search_web の検索クエリ
- r9 0.43099 `c_focus_license` Focus path: LICENSE
- r10 0.429509 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r11 0.428715 `c_meaning_web` Meaning: ウェブを検索する
- r12 0.421493 `c_meaning_create` Meaning: 新しいファイルを作る
- r13 0.411536 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.409476 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r15 0.403951 `c_role_read` Target Role: read_file のワークスペース読取
- r16 0.396777 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.326139 `c_focus_search` Focus path: search_files query in workspace

### search_compound [compound] あの実際フォルダで探してるほう

gold=`c_role_search` rank=2 cosine=0.566125 gold_is_top=`False` gap_vs_second=-0.047187 delta_vs_clean=-0.099542

- r1 0.613312 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.566125 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r3 0.509822 `c_focus_search` Focus path: search_files query in workspace
- r4 0.509067 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r5 0.485115 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.474977 `c_role_web` Target Role: search_web のネット検索
- r7 0.466871 `c_focus_web` Focus: search_web の検索クエリ
- r8 0.465055 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r9 0.443369 `c_meaning_web` Meaning: ウェブを検索する
- r10 0.438415 `c_role_followup` Target Role: followup_investigation の追加調査
- r11 0.43419 `c_focus_license` Focus path: LICENSE
- r12 0.423126 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r13 0.421936 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.411467 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.392967 `c_meaning_create` Meaning: 新しいファイルを作る
- r16 0.362999 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.356708 `c_goal_read` Goal: 指定ファイルを読んで要約する

### web_clean [clean] ネットで調べて

gold=`c_meaning_web` rank=3 cosine=0.575483 gold_is_top=`False` gap_vs_second=-0.057396 delta_vs_clean=None

- r1 0.632879 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.6274 `c_role_web` Target Role: search_web のネット検索
- r3 0.575483 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r4 0.536146 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.482346 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.468178 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.427558 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r8 0.412153 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.411064 `c_role_followup` Target Role: followup_investigation の追加調査
- r10 0.397998 `c_role_search` Target Role: search_files のワークスペース検索
- r11 0.394243 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r12 0.388843 `c_meaning_create` Meaning: 新しいファイルを作る
- r13 0.324048 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.320345 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r15 0.31068 `c_focus_license` Focus path: LICENSE
- r16 0.307714 `c_focus_search` Focus path: search_files query in workspace
- r17 0.303349 `c_goal_read` Goal: 指定ファイルを読んで要約する

### web_typo [typo] ねっとで調べて

gold=`c_meaning_web` rank=4 cosine=0.578747 gold_is_top=`False` gap_vs_second=-0.150179 delta_vs_clean=0.003264

- r1 0.728926 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.6418 `c_role_web` Target Role: search_web のネット検索
- r3 0.578889 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.578747 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r5 0.56864 `c_focus_web` Focus: search_web の検索クエリ
- r6 0.562364 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.529628 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r8 0.518154 `c_role_search` Target Role: search_files のワークスペース検索
- r9 0.506368 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r10 0.504881 `c_meaning_create` Meaning: 新しいファイルを作る
- r11 0.498594 `c_role_followup` Target Role: followup_investigation の追加調査
- r12 0.477292 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r13 0.454042 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.433032 `c_role_read` Target Role: read_file のワークスペース読取
- r15 0.419911 `c_focus_license` Focus path: LICENSE
- r16 0.410632 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 0.401879 `c_focus_search` Focus path: search_files query in workspace

### web_conversion [conversion] 熱っとで調べて

gold=`c_meaning_web` rank=7 cosine=0.560621 gold_is_top=`False` gap_vs_second=-0.159992 delta_vs_clean=-0.014862

- r1 0.720613 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.63585 `c_role_web` Target Role: search_web のネット検索
- r3 0.615062 `c_goal_weather` Goal: 今日の天気を調べる
- r4 0.599474 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.582201 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.565702 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r7 0.560621 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r8 0.531641 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r9 0.530954 `c_role_search` Target Role: search_files のワークスペース検索
- r10 0.526557 `c_role_followup` Target Role: followup_investigation の追加調査
- r11 0.477591 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r12 0.461262 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r13 0.449596 `c_meaning_create` Meaning: 新しいファイルを作る
- r14 0.443686 `c_focus_license` Focus path: LICENSE
- r15 0.442777 `c_focus_search` Focus path: search_files query in workspace
- r16 0.426371 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 0.426217 `c_role_read` Target Role: read_file のワークスペース読取

### web_missing_char [missing_char] ネットで調

gold=`c_meaning_web` rank=4 cosine=0.525148 gold_is_top=`False` gap_vs_second=-0.074938 delta_vs_clean=-0.050335

- r1 0.600086 `c_role_web` Target Role: search_web のネット検索
- r2 0.599445 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.545419 `c_focus_web` Focus: search_web の検索クエリ
- r4 0.525148 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r5 0.496674 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.468811 `c_role_followup` Target Role: followup_investigation の追加調査
- r7 0.467154 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r8 0.4626 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.449787 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r10 0.430489 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r11 0.426766 `c_role_search` Target Role: search_files のワークスペース検索
- r12 0.410229 `c_meaning_create` Meaning: 新しいファイルを作る
- r13 0.395 `c_focus_license` Focus path: LICENSE
- r14 0.390794 `c_role_read` Target Role: read_file のワークスペース読取
- r15 0.383426 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.37285 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.334222 `c_focus_search` Focus path: search_files query in workspace

### web_particle [particle_drop] ネット調べて

gold=`c_meaning_web` rank=4 cosine=0.649619 gold_is_top=`False` gap_vs_second=-0.125222 delta_vs_clean=0.074136

- r1 0.774841 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.725185 `c_role_web` Target Role: search_web のネット検索
- r3 0.663886 `c_focus_web` Focus: search_web の検索クエリ
- r4 0.649619 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r5 0.620198 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.611469 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.566042 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.563394 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.531333 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r10 0.509251 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.500749 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r12 0.4699 `c_meaning_create` Meaning: 新しいファイルを作る
- r13 0.447088 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.445988 `c_focus_search` Focus path: search_files query in workspace
- r15 0.44287 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r16 0.426184 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 0.425253 `c_focus_license` Focus path: LICENSE

### web_colloquial [colloquial] ネットのやつ

gold=`c_role_web` rank=1 cosine=0.617561 gold_is_top=`True` gap_vs_second=0.014231 delta_vs_clean=0.042078

- r1 0.617561 `c_role_web` Target Role: search_web のネット検索 GOLD
- r2 0.60333 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.533064 `c_focus_web` Focus: search_web の検索クエリ
- r4 0.528271 `c_meaning_web` Meaning: ウェブを検索する
- r5 0.502699 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.466899 `c_meaning_create` Meaning: 新しいファイルを作る
- r7 0.466002 `c_role_followup` Target Role: followup_investigation の追加調査
- r8 0.45334 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r9 0.446679 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.426783 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r11 0.42647 `c_role_search` Target Role: search_files のワークスペース検索
- r12 0.398371 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.39139 `c_focus_license` Focus path: LICENSE
- r14 0.390793 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r15 0.390465 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r16 0.386083 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 0.308181 `c_focus_search` Focus path: search_files query in workspace

### web_filler [filler] まあネットで調べてかな

gold=`c_meaning_web` rank=3 cosine=0.545766 gold_is_top=`False` gap_vs_second=-0.069896 delta_vs_clean=-0.029717

- r1 0.615662 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.593405 `c_role_web` Target Role: search_web のネット検索
- r3 0.545766 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r4 0.532438 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.497249 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.487946 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.461118 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r8 0.424596 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r9 0.420879 `c_role_search` Target Role: search_files のワークスペース検索
- r10 0.385318 `c_role_followup` Target Role: followup_investigation の追加調査
- r11 0.373713 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r12 0.358593 `c_meaning_create` Meaning: 新しいファイルを作る
- r13 0.358079 `c_focus_search` Focus path: search_files query in workspace
- r14 0.340988 `c_focus_license` Focus path: LICENSE
- r15 0.328962 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.318029 `c_role_read` Target Role: read_file のワークスペース読取
- r17 0.2958 `c_goal_read` Goal: 指定ファイルを読んで要約する

### web_restatement [restatement] ローカルじゃなくてネットで調べて

gold=`c_meaning_web` rank=3 cosine=0.52519 gold_is_top=`False` gap_vs_second=-0.073477 delta_vs_clean=-0.050293

- r1 0.598667 `c_role_web` Target Role: search_web のネット検索
- r2 0.562748 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.52519 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r4 0.494219 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.473149 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.437512 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r7 0.431224 `c_goal_weather` Goal: 今日の天気を調べる
- r8 0.4184 `c_role_search` Target Role: search_files のワークスペース検索
- r9 0.412519 `c_role_followup` Target Role: followup_investigation の追加調査
- r10 0.381391 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r11 0.363502 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r12 0.358862 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.34194 `c_focus_search` Focus path: search_files query in workspace
- r14 0.325375 `c_meaning_create` Meaning: 新しいファイルを作る
- r15 0.316717 `c_focus_license` Focus path: LICENSE
- r16 0.309165 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.278806 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md

### web_asr [asr_like] 熱斗で調べて

gold=`c_meaning_web` rank=8 cosine=0.464936 gold_is_top=`False` gap_vs_second=-0.113374 delta_vs_clean=-0.110547

- r1 0.57831 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.551509 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r3 0.527617 `c_role_web` Target Role: search_web のネット検索
- r4 0.490169 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.484312 `c_focus_web` Focus: search_web の検索クエリ
- r6 0.476132 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r7 0.475063 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.464936 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r9 0.462636 `c_role_followup` Target Role: followup_investigation の追加調査
- r10 0.448437 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.395828 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r12 0.376066 `c_focus_search` Focus path: search_files query in workspace
- r13 0.353218 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.348251 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r15 0.338146 `c_meaning_create` Meaning: 新しいファイルを作る
- r16 0.338026 `c_focus_license` Focus path: LICENSE
- r17 0.326304 `c_goal_read` Goal: 指定ファイルを読んで要約する

### web_demonstrative [demonstrative] ネットのほう

gold=`c_role_web` rank=2 cosine=0.607877 gold_is_top=`False` gap_vs_second=-0.00409 delta_vs_clean=0.032394

- r1 0.611967 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.607877 `c_role_web` Target Role: search_web のネット検索 GOLD
- r3 0.565252 `c_meaning_web` Meaning: ウェブを検索する
- r4 0.543891 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.498746 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.490555 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.44013 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.433307 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r9 0.429238 `c_role_search` Target Role: search_files のワークスペース検索
- r10 0.424649 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r11 0.411481 `c_role_followup` Target Role: followup_investigation の追加調査
- r12 0.410603 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.404603 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r14 0.387295 `c_focus_license` Focus path: LICENSE
- r15 0.358899 `c_role_read` Target Role: read_file のワークスペース読取
- r16 0.339507 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.331143 `c_focus_search` Focus path: search_files query in workspace

### web_compound [compound] まあねっとで調べるのも

gold=`c_role_web` rank=2 cosine=0.527921 gold_is_top=`False` gap_vs_second=-0.050224 delta_vs_clean=-0.047562

- r1 0.578145 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.527921 `c_role_web` Target Role: search_web のネット検索 GOLD
- r3 0.505873 `c_meaning_web` Meaning: ウェブを検索する
- r4 0.468661 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.447277 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.432628 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r7 0.426803 `c_role_followup` Target Role: followup_investigation の追加調査
- r8 0.422818 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.409844 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.40593 `c_role_search` Target Role: search_files のワークスペース検索
- r11 0.383564 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r12 0.330983 `c_meaning_create` Meaning: 新しいファイルを作る
- r13 0.330621 `c_focus_search` Focus path: search_files query in workspace
- r14 0.324327 `c_role_read` Target Role: read_file のワークスペース読取
- r15 0.323172 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r16 0.267355 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 0.262804 `c_focus_license` Focus path: LICENSE
