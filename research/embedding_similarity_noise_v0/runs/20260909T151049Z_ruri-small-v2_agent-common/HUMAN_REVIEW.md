# Embedding similarity Japanese input noise v0

- run_id: `20260909T151049Z_ruri-small-v2_agent-common`
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

- baseline: VRAM 3767 / 12288 MiB, RAM used 38910 / 65277 MB
- after_model_load: VRAM 3767 / 12288 MiB, RAM used 38990 / 65277 MB
- after_embed: VRAM 3766 / 12288 MiB, RAM used 39183 / 65277 MB

## Agent slot（Goal / Meaning / Focus / Target Role）

仮対応。Production スキーマではない。

- intended_slot_top: 5/30 (0.1667)
- correct_object_top: 24/30 (0.8)
- confusion: {'same_object_other_slot:goal': 14, 'unrelated:meaning': 4, 'intended_slot': 5, 'unrelated:goal': 1, 'same_object_other_slot:meaning': 1, 'other_object:read:focus': 1, 'same_object_other_slot:target_role': 4}
- top_slot_type: {'goal': 15, 'meaning': 8, 'focus': 1, 'target_role': 6}
- failed: ['read_typo', 'read_conversion', 'read_missing_char', 'read_particle', 'read_asr', 'read_demonstrative', 'read_compound', 'search_typo', 'search_conversion', 'search_missing_char', 'search_particle', 'search_colloquial', 'search_filler', 'search_restatement', 'search_asr', 'search_demonstrative', 'search_compound', 'web_typo', 'web_conversion', 'web_missing_char', 'web_particle', 'web_colloquial', 'web_filler', 'web_restatement', 'web_asr']

  - `read_typo` intended=`c_meaning_read` rank=2 top=`c_goal_read` same_object_other_slot:goal
  - `read_conversion` intended=`c_meaning_read` rank=3 top=`c_meaning_create` unrelated:meaning
  - `read_missing_char` intended=`c_meaning_read` rank=3 top=`c_goal_read` same_object_other_slot:goal
  - `read_particle` intended=`c_meaning_read` rank=2 top=`c_goal_read` same_object_other_slot:goal
  - `read_asr` intended=`c_meaning_read` rank=7 top=`c_goal_weather` unrelated:goal
  - `read_demonstrative` intended=`c_meaning_read` rank=3 top=`c_meaning_create` unrelated:meaning
  - `read_compound` intended=`c_meaning_read` rank=3 top=`c_goal_read` same_object_other_slot:goal
  - `search_typo` intended=`c_meaning_search` rank=4 top=`c_goal_search` same_object_other_slot:goal
  - `search_conversion` intended=`c_meaning_search` rank=6 top=`c_goal_search` same_object_other_slot:goal
  - `search_missing_char` intended=`c_meaning_search` rank=4 top=`c_goal_search` same_object_other_slot:goal
  - `search_particle` intended=`c_meaning_search` rank=3 top=`c_goal_search` same_object_other_slot:goal
  - `search_colloquial` intended=`c_role_search` rank=8 top=`c_meaning_search` same_object_other_slot:meaning
  - `search_filler` intended=`c_meaning_search` rank=4 top=`c_goal_search` same_object_other_slot:goal
  - `search_restatement` intended=`c_meaning_search` rank=6 top=`c_goal_search` same_object_other_slot:goal
  - `search_asr` intended=`c_meaning_search` rank=14 top=`c_goal_search` same_object_other_slot:goal
  - `search_demonstrative` intended=`c_role_search` rank=11 top=`c_focus_read` other_object:read:focus
  - `search_compound` intended=`c_role_search` rank=2 top=`c_goal_search` same_object_other_slot:goal
  - `web_typo` intended=`c_meaning_web` rank=3 top=`c_role_web` same_object_other_slot:target_role
  - `web_conversion` intended=`c_meaning_web` rank=8 top=`c_meaning_cpu` unrelated:meaning
  - `web_missing_char` intended=`c_meaning_web` rank=4 top=`c_goal_web` same_object_other_slot:goal
  - `web_particle` intended=`c_meaning_web` rank=3 top=`c_role_web` same_object_other_slot:target_role
  - `web_colloquial` intended=`c_role_web` rank=2 top=`c_goal_web` same_object_other_slot:goal
  - `web_filler` intended=`c_meaning_web` rank=3 top=`c_role_web` same_object_other_slot:target_role
  - `web_restatement` intended=`c_meaning_web` rank=5 top=`c_role_web` same_object_other_slot:target_role
  - `web_asr` intended=`c_meaning_web` rank=9 top=`c_meaning_cpu` unrelated:meaning

## ノイズ種別まとめ

- `clean`: gold_top 1/3 mean_rank=2.667 mean_gap=-0.03256 mean_delta_vs_clean=None failed=['search_clean', 'web_clean']
- `typo`: gold_top 0/3 mean_rank=3.0 mean_gap=-0.021558 mean_delta_vs_clean=-0.053217 failed=['read_typo', 'search_typo', 'web_typo']
- `conversion`: gold_top 0/3 mean_rank=5.667 mean_gap=-0.046625 mean_delta_vs_clean=-0.024646 failed=['read_conversion', 'search_conversion', 'web_conversion']
- `missing_char`: gold_top 0/3 mean_rank=3.667 mean_gap=-0.039258 mean_delta_vs_clean=-0.0194 failed=['read_missing_char', 'search_missing_char', 'web_missing_char']
- `particle_drop`: gold_top 0/3 mean_rank=2.667 mean_gap=-0.03149 mean_delta_vs_clean=0.000844 failed=['read_particle', 'search_particle', 'web_particle']
- `colloquial`: gold_top 1/3 mean_rank=3.667 mean_gap=-0.007417 mean_delta_vs_clean=-0.017408 failed=['search_colloquial', 'web_colloquial']
- `filler`: gold_top 1/3 mean_rank=2.667 mean_gap=-0.027144 mean_delta_vs_clean=-0.012402 failed=['search_filler', 'web_filler']
- `restatement`: gold_top 1/3 mean_rank=4.0 mean_gap=-0.025549 mean_delta_vs_clean=-0.022917 failed=['search_restatement', 'web_restatement']
- `asr_like`: gold_top 0/3 mean_rank=10.0 mean_gap=-0.055855 mean_delta_vs_clean=-0.083208 failed=['read_asr', 'search_asr', 'web_asr']
- `demonstrative`: gold_top 1/3 mean_rank=5.0 mean_gap=-0.015841 mean_delta_vs_clean=-0.051575 failed=['read_demonstrative', 'search_demonstrative']
- `compound`: gold_top 1/3 mean_rank=2.0 mean_gap=-0.000945 mean_delta_vs_clean=-0.024121 failed=['read_compound', 'search_compound']

失敗したノイズ種別: ['typo', 'conversion', 'missing_char', 'particle_drop', 'colloquial', 'filler', 'restatement', 'asr_like', 'demonstrative', 'compound']

## 失敗ケース

- `read_typo` [typo] このふぁいるを読んで gold_rank=2 gold_cos=0.757719 top=`c_goal_read` 0.7592 delta_vs_clean=-0.1066
- `read_conversion` [conversion] このファイルを呼んで gold_rank=3 gold_cos=0.83822 top=`c_meaning_create` 0.849507 delta_vs_clean=-0.026099
- `read_missing_char` [missing_char] このファイルを読 gold_rank=3 gold_cos=0.86211 top=`c_goal_read` 0.868664 delta_vs_clean=-0.002209
- `read_particle` [particle_drop] このファイル読んで gold_rank=2 gold_cos=0.859727 top=`c_goal_read` 0.861075 delta_vs_clean=-0.004592
- `read_asr` [asr_like] このファいるを呼んで gold_rank=7 gold_cos=0.75972 top=`c_goal_weather` 0.784772 delta_vs_clean=-0.104599
- `read_demonstrative` [demonstrative] そっちのファイル gold_rank=3 gold_cos=0.78395 top=`c_meaning_create` 0.801972 delta_vs_clean=-0.080369
- `read_compound` [compound] えっとこのファイルを呼んでくれるやつ gold_rank=3 gold_cos=0.817703 top=`c_goal_read` 0.824239 delta_vs_clean=-0.046616
- `search_typo` [typo] りぽじとりの中を検索して gold_rank=4 gold_cos=0.794598 top=`c_goal_search` 0.839701 delta_vs_clean=-0.036602
- `search_conversion` [conversion] リポジトリの中を件作して gold_rank=6 gold_cos=0.807326 top=`c_goal_search` 0.883373 delta_vs_clean=-0.023874
- `search_missing_char` [missing_char] リポジトリの中を検 gold_rank=4 gold_cos=0.796289 top=`c_goal_search` 0.875725 delta_vs_clean=-0.034911
- `search_particle` [particle_drop] リポジトリ中を検索して gold_rank=3 gold_cos=0.826845 top=`c_goal_search` 0.891888 delta_vs_clean=-0.004355
- `search_colloquial` [colloquial] 中を探してるほう gold_rank=8 gold_cos=0.772384 top=`c_meaning_search` 0.803524 delta_vs_clean=-0.058816
- `search_filler` [filler] あのーリポジトリの中を検索してなんですけど gold_rank=4 gold_cos=0.821655 top=`c_goal_search` 0.884204 delta_vs_clean=-0.009545
- `search_restatement` [restatement] ネットじゃなくてリポジトリの中を検索して gold_rank=6 gold_cos=0.807408 top=`c_goal_search` 0.859068 delta_vs_clean=-0.023792
- `search_asr` [asr_like] リポジ鳥の中を件作して gold_rank=14 gold_cos=0.742871 top=`c_goal_search` 0.815565 delta_vs_clean=-0.088329
- `search_demonstrative` [demonstrative] ローカルのほう gold_rank=11 gold_cos=0.744183 top=`c_focus_read` 0.774858 delta_vs_clean=-0.087017
- `search_compound` [compound] あの実際フォルダで探してるほう gold_rank=2 gold_cos=0.808993 top=`c_goal_search` 0.813908 delta_vs_clean=-0.022207
- `web_typo` [typo] ねっとで調べて gold_rank=3 gold_cos=0.780493 top=`c_role_web` 0.798582 delta_vs_clean=-0.01645
- `web_conversion` [conversion] 熱っとで調べて gold_rank=8 gold_cos=0.772977 top=`c_meaning_cpu` 0.825517 delta_vs_clean=-0.023966
- `web_missing_char` [missing_char] ネットで調 gold_rank=4 gold_cos=0.775864 top=`c_goal_web` 0.807647 delta_vs_clean=-0.021079
- `web_particle` [particle_drop] ネット調べて gold_rank=3 gold_cos=0.808423 top=`c_role_web` 0.836501 delta_vs_clean=0.01148
- `web_colloquial` [colloquial] ネットのやつ gold_rank=2 gold_cos=0.804879 top=`c_goal_web` 0.806287 delta_vs_clean=0.007936
- `web_filler` [filler] まあネットで調べてかな gold_rank=3 gold_cos=0.780303 top=`c_role_web` 0.804557 delta_vs_clean=-0.01664
- `web_restatement` [restatement] ローカルじゃなくてネットで調べて gold_rank=5 gold_cos=0.783277 top=`c_role_web` 0.820153 delta_vs_clean=-0.013666
- `web_asr` [asr_like] 熱斗で調べて gold_rank=9 gold_cos=0.740247 top=`c_meaning_cpu` 0.810066 delta_vs_clean=-0.056696

## 各クエリ

### read_clean [clean] このファイルを読んで

gold=`c_meaning_read` rank=1 cosine=0.864319 gold_is_top=`True` gap_vs_second=0.005186 delta_vs_clean=None

- r1 0.864319 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r2 0.859133 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.854773 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.824716 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.812151 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.807496 `c_focus_license` Focus path: LICENSE
- r7 0.79893 `c_goal_weather` Goal: 今日の天気を調べる
- r8 0.793193 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r9 0.792756 `c_meaning_web` Meaning: ウェブを検索する
- r10 0.79083 `c_focus_search` Focus path: search_files query in workspace
- r11 0.789529 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r12 0.787411 `c_goal_web` Goal: ネットで調べて要点を返す
- r13 0.776271 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.774884 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.772447 `c_focus_web` Focus: search_web の検索クエリ
- r16 0.772137 `c_role_web` Target Role: search_web のネット検索
- r17 0.771301 `c_role_search` Target Role: search_files のワークスペース検索

### read_typo [typo] このふぁいるを読んで

gold=`c_meaning_read` rank=2 cosine=0.757719 gold_is_top=`False` gap_vs_second=-0.001481 delta_vs_clean=-0.1066

- r1 0.7592 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r2 0.757719 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r3 0.757035 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.73736 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.736604 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.734719 `c_goal_web` Goal: ネットで調べて要点を返す
- r7 0.730204 `c_meaning_web` Meaning: ウェブを検索する
- r8 0.729897 `c_focus_license` Focus path: LICENSE
- r9 0.723402 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r10 0.715571 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.713441 `c_role_web` Target Role: search_web のネット検索
- r12 0.711907 `c_focus_web` Focus: search_web の検索クエリ
- r13 0.707872 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r14 0.706434 `c_focus_search` Focus path: search_files query in workspace
- r15 0.704975 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.699509 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.693859 `c_role_search` Target Role: search_files のワークスペース検索

### read_conversion [conversion] このファイルを呼んで

gold=`c_meaning_read` rank=3 cosine=0.83822 gold_is_top=`False` gap_vs_second=-0.011287 delta_vs_clean=-0.026099

- r1 0.849507 `c_meaning_create` Meaning: 新しいファイルを作る
- r2 0.847367 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.83822 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.835481 `c_role_read` Target Role: read_file のワークスペース読取
- r5 0.806071 `c_focus_license` Focus path: LICENSE
- r6 0.802748 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.79357 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r8 0.791588 `c_role_search` Target Role: search_files のワークスペース検索
- r9 0.788997 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r10 0.788087 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.784081 `c_goal_web` Goal: ネットで調べて要点を返す
- r12 0.782473 `c_focus_search` Focus path: search_files query in workspace
- r13 0.779328 `c_meaning_web` Meaning: ウェブを検索する
- r14 0.775189 `c_role_web` Target Role: search_web のネット検索
- r15 0.773408 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r16 0.770397 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.768885 `c_role_followup` Target Role: followup_investigation の追加調査

### read_missing_char [missing_char] このファイルを読

gold=`c_meaning_read` rank=3 cosine=0.86211 gold_is_top=`False` gap_vs_second=-0.006554 delta_vs_clean=-0.002209

- r1 0.868664 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r2 0.863104 `c_role_read` Target Role: read_file のワークスペース読取
- r3 0.86211 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.830953 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.827201 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.82431 `c_focus_license` Focus path: LICENSE
- r7 0.809268 `c_focus_search` Focus path: search_files query in workspace
- r8 0.805429 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r9 0.799371 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.792194 `c_focus_web` Focus: search_web の検索クエリ
- r11 0.79041 `c_goal_web` Goal: ネットで調べて要点を返す
- r12 0.790391 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r13 0.789975 `c_meaning_web` Meaning: ウェブを検索する
- r14 0.78611 `c_role_search` Target Role: search_files のワークスペース検索
- r15 0.78497 `c_role_web` Target Role: search_web のネット検索
- r16 0.77628 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.775304 `c_meaning_cpu` Meaning: CPU温度の取得方法

### read_particle [particle_drop] このファイル読んで

gold=`c_meaning_read` rank=2 cosine=0.859727 gold_is_top=`False` gap_vs_second=-0.001348 delta_vs_clean=-0.004592

- r1 0.861075 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r2 0.859727 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r3 0.858142 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.825164 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.812801 `c_focus_license` Focus path: LICENSE
- r6 0.80824 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.79256 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r8 0.791679 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.785399 `c_goal_web` Goal: ネットで調べて要点を返す
- r10 0.785204 `c_focus_search` Focus path: search_files query in workspace
- r11 0.784399 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r12 0.783521 `c_meaning_web` Meaning: ウェブを検索する
- r13 0.776211 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.773396 `c_role_web` Target Role: search_web のネット検索
- r15 0.771661 `c_role_followup` Target Role: followup_investigation の追加調査
- r16 0.771113 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.770252 `c_focus_web` Focus: search_web の検索クエリ

### read_colloquial [colloquial] このファイルのやつ読んで

gold=`c_meaning_read` rank=1 cosine=0.862975 gold_is_top=`True` gap_vs_second=0.010296 delta_vs_clean=-0.001344

- r1 0.862975 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r2 0.852679 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.849378 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.822483 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.813789 `c_focus_license` Focus path: LICENSE
- r6 0.804745 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.791934 `c_goal_weather` Goal: 今日の天気を調べる
- r8 0.790862 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.79021 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r10 0.784001 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r11 0.781685 `c_goal_web` Goal: ネットで調べて要点を返す
- r12 0.776106 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.772552 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.770819 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.770746 `c_focus_search` Focus path: search_files query in workspace
- r16 0.769144 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.768704 `c_role_web` Target Role: search_web のネット検索

### read_filler [filler] えっとこのファイルを読んで

gold=`c_meaning_read` rank=1 cosine=0.853298 gold_is_top=`True` gap_vs_second=0.00537 delta_vs_clean=-0.011021

- r1 0.853298 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r2 0.847928 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.836032 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.816054 `c_meaning_create` Meaning: 新しいファイルを作る
- r5 0.797059 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.795232 `c_focus_license` Focus path: LICENSE
- r7 0.788449 `c_meaning_web` Meaning: ウェブを検索する
- r8 0.781696 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r9 0.778051 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.778044 `c_focus_search` Focus path: search_files query in workspace
- r11 0.777394 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r12 0.776411 `c_goal_web` Goal: ネットで調べて要点を返す
- r13 0.770769 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r14 0.763698 `c_role_search` Target Role: search_files のワークスペース検索
- r15 0.762993 `c_role_web` Target Role: search_web のネット検索
- r16 0.758229 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.755329 `c_role_followup` Target Role: followup_investigation の追加調査

### read_restatement [restatement] いや検索じゃなくてこのファイルを読んで

gold=`c_meaning_read` rank=1 cosine=0.833025 gold_is_top=`True` gap_vs_second=0.01189 delta_vs_clean=-0.031294

- r1 0.833025 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r2 0.821135 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.818081 `c_role_read` Target Role: read_file のワークスペース読取
- r4 0.813109 `c_focus_search` Focus path: search_files query in workspace
- r5 0.811403 `c_focus_web` Focus: search_web の検索クエリ
- r6 0.80836 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.806415 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r8 0.806318 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.799447 `c_role_web` Target Role: search_web のネット検索
- r10 0.798926 `c_role_search` Target Role: search_files のワークスペース検索
- r11 0.795975 `c_meaning_create` Meaning: 新しいファイルを作る
- r12 0.78304 `c_focus_license` Focus path: LICENSE
- r13 0.779119 `c_goal_web` Goal: ネットで調べて要点を返す
- r14 0.772402 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r15 0.767985 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.754886 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.752572 `c_meaning_cpu` Meaning: CPU温度の取得方法

### read_asr [asr_like] このファいるを呼んで

gold=`c_meaning_read` rank=7 cosine=0.75972 gold_is_top=`False` gap_vs_second=-0.025052 delta_vs_clean=-0.104599

- r1 0.784772 `c_goal_weather` Goal: 今日の天気を調べる
- r2 0.784069 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.77661 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r4 0.770104 `c_focus_license` Focus path: LICENSE
- r5 0.76806 `c_meaning_create` Meaning: 新しいファイルを作る
- r6 0.76315 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.75972 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r8 0.755315 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.753552 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.751912 `c_role_read` Target Role: read_file のワークスペース読取
- r11 0.750594 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.742786 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r13 0.741418 `c_role_web` Target Role: search_web のネット検索
- r14 0.739468 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.739232 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.734594 `c_focus_search` Focus path: search_files query in workspace
- r17 0.721808 `c_role_search` Target Role: search_files のワークスペース検索

### read_demonstrative [demonstrative] そっちのファイル

gold=`c_meaning_read` rank=3 cosine=0.78395 gold_is_top=`False` gap_vs_second=-0.018022 delta_vs_clean=-0.080369

- r1 0.801972 `c_meaning_create` Meaning: 新しいファイルを作る
- r2 0.789017 `c_role_read` Target Role: read_file のワークスペース読取
- r3 0.78395 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.779757 `c_focus_license` Focus path: LICENSE
- r5 0.773307 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r6 0.770908 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r7 0.761921 `c_focus_search` Focus path: search_files query in workspace
- r8 0.757265 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r9 0.753147 `c_role_search` Target Role: search_files のワークスペース検索
- r10 0.742797 `c_goal_weather` Goal: 今日の天気を調べる
- r11 0.735817 `c_role_web` Target Role: search_web のネット検索
- r12 0.734748 `c_focus_web` Focus: search_web の検索クエリ
- r13 0.733803 `c_meaning_web` Meaning: ウェブを検索する
- r14 0.733715 `c_goal_web` Goal: ネットで調べて要点を返す
- r15 0.733226 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r16 0.721837 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.72027 `c_role_followup` Target Role: followup_investigation の追加調査

### read_compound [compound] えっとこのファイルを呼んでくれるやつ

gold=`c_meaning_read` rank=3 cosine=0.817703 gold_is_top=`False` gap_vs_second=-0.006536 delta_vs_clean=-0.046616

- r1 0.824239 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r2 0.818625 `c_meaning_create` Meaning: 新しいファイルを作る
- r3 0.817703 `c_meaning_read` Meaning: ワークスペースのファイルを読む GOLD
- r4 0.810583 `c_role_read` Target Role: read_file のワークスペース読取
- r5 0.785182 `c_focus_license` Focus path: LICENSE
- r6 0.782603 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.780935 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.776527 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r9 0.772769 `c_goal_weather` Goal: 今日の天気を調べる
- r10 0.77137 `c_goal_web` Goal: ネットで調べて要点を返す
- r11 0.758568 `c_focus_search` Focus path: search_files query in workspace
- r12 0.758543 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.758212 `c_meaning_web` Meaning: ウェブを検索する
- r14 0.756442 `c_role_web` Target Role: search_web のネット検索
- r15 0.755702 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.748835 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.742472 `c_role_followup` Target Role: followup_investigation の追加調査

### search_clean [clean] リポジトリの中を検索して

gold=`c_meaning_search` rank=4 cosine=0.8312 gold_is_top=`False` gap_vs_second=-0.065991 delta_vs_clean=None

- r1 0.897191 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.836785 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.831216 `c_focus_search` Focus path: search_files query in workspace
- r4 0.8312 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.823835 `c_role_read` Target Role: read_file のワークスペース読取
- r6 0.81983 `c_focus_web` Focus: search_web の検索クエリ
- r7 0.815885 `c_role_web` Target Role: search_web のネット検索
- r8 0.81375 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r9 0.809105 `c_meaning_web` Meaning: ウェブを検索する
- r10 0.80174 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.800075 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r12 0.796812 `c_role_followup` Target Role: followup_investigation の追加調査
- r13 0.79569 `c_goal_web` Goal: ネットで調べて要点を返す
- r14 0.786105 `c_meaning_create` Meaning: 新しいファイルを作る
- r15 0.774006 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.772133 `c_focus_license` Focus path: LICENSE
- r17 0.751459 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_typo [typo] りぽじとりの中を検索して

gold=`c_meaning_search` rank=4 cosine=0.794598 gold_is_top=`False` gap_vs_second=-0.045103 delta_vs_clean=-0.036602

- r1 0.839701 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.799276 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.795339 `c_focus_search` Focus path: search_files query in workspace
- r4 0.794598 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.788722 `c_focus_web` Focus: search_web の検索クエリ
- r6 0.787661 `c_role_web` Target Role: search_web のネット検索
- r7 0.785445 `c_meaning_web` Meaning: ウェブを検索する
- r8 0.78319 `c_goal_web` Goal: ネットで調べて要点を返す
- r9 0.77991 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.770397 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r11 0.769366 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r12 0.769158 `c_focus_license` Focus path: LICENSE
- r13 0.768551 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.767346 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.763127 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.746554 `c_meaning_create` Meaning: 新しいファイルを作る
- r17 0.730121 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_conversion [conversion] リポジトリの中を件作して

gold=`c_meaning_search` rank=6 cosine=0.807326 gold_is_top=`False` gap_vs_second=-0.076047 delta_vs_clean=-0.023874

- r1 0.883373 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.82512 `c_role_read` Target Role: read_file のワークスペース読取
- r3 0.812018 `c_role_search` Target Role: search_files のワークスペース検索
- r4 0.811427 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r5 0.808848 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r6 0.807326 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r7 0.807217 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r8 0.804375 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.801936 `c_meaning_create` Meaning: 新しいファイルを作る
- r10 0.797607 `c_focus_search` Focus path: search_files query in workspace
- r11 0.789268 `c_goal_web` Goal: ネットで調べて要点を返す
- r12 0.780133 `c_role_web` Target Role: search_web のネット検索
- r13 0.776425 `c_meaning_web` Meaning: ウェブを検索する
- r14 0.774125 `c_focus_web` Focus: search_web の検索クエリ
- r15 0.772862 `c_focus_license` Focus path: LICENSE
- r16 0.762687 `c_goal_weather` Goal: 今日の天気を調べる
- r17 0.748436 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_missing_char [missing_char] リポジトリの中を検

gold=`c_meaning_search` rank=4 cosine=0.796289 gold_is_top=`False` gap_vs_second=-0.079436 delta_vs_clean=-0.034911

- r1 0.875725 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.812659 `c_role_read` Target Role: read_file のワークスペース読取
- r3 0.807158 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r4 0.796289 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.791519 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r6 0.791258 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r7 0.791026 `c_role_followup` Target Role: followup_investigation の追加調査
- r8 0.789598 `c_focus_search` Focus path: search_files query in workspace
- r9 0.784392 `c_goal_web` Goal: ネットで調べて要点を返す
- r10 0.782945 `c_role_search` Target Role: search_files のワークスペース検索
- r11 0.778115 `c_meaning_create` Meaning: 新しいファイルを作る
- r12 0.775319 `c_meaning_web` Meaning: ウェブを検索する
- r13 0.774704 `c_focus_license` Focus path: LICENSE
- r14 0.773943 `c_goal_weather` Goal: 今日の天気を調べる
- r15 0.767223 `c_role_web` Target Role: search_web のネット検索
- r16 0.766135 `c_focus_web` Focus: search_web の検索クエリ
- r17 0.752974 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_particle [particle_drop] リポジトリ中を検索して

gold=`c_meaning_search` rank=3 cosine=0.826845 gold_is_top=`False` gap_vs_second=-0.065043 delta_vs_clean=-0.004355

- r1 0.891888 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.82855 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.826845 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r4 0.822048 `c_focus_search` Focus path: search_files query in workspace
- r5 0.821056 `c_role_read` Target Role: read_file のワークスペース読取
- r6 0.809639 `c_focus_web` Focus: search_web の検索クエリ
- r7 0.808831 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.806771 `c_role_web` Target Role: search_web のネット検索
- r9 0.802008 `c_meaning_web` Meaning: ウェブを検索する
- r10 0.799536 `c_role_followup` Target Role: followup_investigation の追加調査
- r11 0.795647 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r12 0.795619 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r13 0.790569 `c_goal_web` Goal: ネットで調べて要点を返す
- r14 0.783056 `c_meaning_create` Meaning: 新しいファイルを作る
- r15 0.770797 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.768253 `c_focus_license` Focus path: LICENSE
- r17 0.754705 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_colloquial [colloquial] 中を探してるほう

gold=`c_role_search` rank=8 cosine=0.772384 gold_is_top=`False` gap_vs_second=-0.03114 delta_vs_clean=-0.058816

- r1 0.803524 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r2 0.790529 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r3 0.785221 `c_meaning_web` Meaning: ウェブを検索する
- r4 0.784949 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r5 0.777449 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.77572 `c_focus_search` Focus path: search_files query in workspace
- r7 0.773327 `c_goal_web` Goal: ネットで調べて要点を返す
- r8 0.772384 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r9 0.764469 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.763154 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.762105 `c_meaning_create` Meaning: 新しいファイルを作る
- r12 0.760388 `c_role_web` Target Role: search_web のネット検索
- r13 0.758782 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.75449 `c_focus_license` Focus path: LICENSE
- r15 0.749041 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r16 0.742647 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r17 0.735351 `c_role_followup` Target Role: followup_investigation の追加調査

### search_filler [filler] あのーリポジトリの中を検索してなんですけど

gold=`c_meaning_search` rank=4 cosine=0.821655 gold_is_top=`False` gap_vs_second=-0.062549 delta_vs_clean=-0.009545

- r1 0.884204 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.831198 `c_role_search` Target Role: search_files のワークスペース検索
- r3 0.822277 `c_focus_search` Focus path: search_files query in workspace
- r4 0.821655 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r5 0.821446 `c_focus_web` Focus: search_web の検索クエリ
- r6 0.818127 `c_role_web` Target Role: search_web のネット検索
- r7 0.809518 `c_role_read` Target Role: read_file のワークスペース読取
- r8 0.799624 `c_meaning_web` Meaning: ウェブを検索する
- r9 0.795319 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r10 0.791688 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.789892 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r12 0.787164 `c_goal_web` Goal: ネットで調べて要点を返す
- r13 0.786834 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.77282 `c_focus_license` Focus path: LICENSE
- r15 0.771498 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.770153 `c_meaning_create` Meaning: 新しいファイルを作る
- r17 0.741713 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_restatement [restatement] ネットじゃなくてリポジトリの中を検索して

gold=`c_meaning_search` rank=6 cosine=0.807408 gold_is_top=`False` gap_vs_second=-0.05166 delta_vs_clean=-0.023792

- r1 0.859068 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.837198 `c_role_web` Target Role: search_web のネット検索
- r3 0.821991 `c_role_search` Target Role: search_files のワークスペース検索
- r4 0.816789 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.809905 `c_meaning_web` Meaning: ウェブを検索する
- r6 0.807408 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r7 0.80487 `c_focus_search` Focus path: search_files query in workspace
- r8 0.803495 `c_goal_web` Goal: ネットで調べて要点を返す
- r9 0.795733 `c_role_read` Target Role: read_file のワークスペース読取
- r10 0.790726 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r11 0.789853 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r12 0.78166 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r13 0.770198 `c_focus_license` Focus path: LICENSE
- r14 0.769605 `c_role_followup` Target Role: followup_investigation の追加調査
- r15 0.763368 `c_meaning_create` Meaning: 新しいファイルを作る
- r16 0.759947 `c_goal_weather` Goal: 今日の天気を調べる
- r17 0.744755 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_asr [asr_like] リポジ鳥の中を件作して

gold=`c_meaning_search` rank=14 cosine=0.742871 gold_is_top=`False` gap_vs_second=-0.072694 delta_vs_clean=-0.088329

- r1 0.815565 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.771702 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r3 0.764452 `c_role_followup` Target Role: followup_investigation の追加調査
- r4 0.762591 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.762586 `c_goal_web` Goal: ネットで調べて要点を返す
- r6 0.755434 `c_meaning_create` Meaning: 新しいファイルを作る
- r7 0.752959 `c_role_read` Target Role: read_file のワークスペース読取
- r8 0.752653 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r9 0.7517 `c_focus_license` Focus path: LICENSE
- r10 0.750374 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.749099 `c_focus_search` Focus path: search_files query in workspace
- r12 0.745486 `c_meaning_web` Meaning: ウェブを検索する
- r13 0.744857 `c_focus_web` Focus: search_web の検索クエリ
- r14 0.742871 `c_meaning_search` Meaning: ワークスペース内を文字列検索する GOLD
- r15 0.73801 `c_role_web` Target Role: search_web のネット検索
- r16 0.737849 `c_role_search` Target Role: search_files のワークスペース検索
- r17 0.731671 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_demonstrative [demonstrative] ローカルのほう

gold=`c_role_search` rank=11 cosine=0.744183 gold_is_top=`False` gap_vs_second=-0.030675 delta_vs_clean=-0.087017

- r1 0.774858 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r2 0.774493 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r3 0.771553 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.771336 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.758327 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r6 0.757328 `c_focus_license` Focus path: LICENSE
- r7 0.754758 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r8 0.753348 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r9 0.74982 `c_meaning_web` Meaning: ウェブを検索する
- r10 0.74526 `c_role_web` Target Role: search_web のネット検索
- r11 0.744183 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r12 0.742234 `c_role_read` Target Role: read_file のワークスペース読取
- r13 0.73957 `c_focus_search` Focus path: search_files query in workspace
- r14 0.737945 `c_meaning_create` Meaning: 新しいファイルを作る
- r15 0.730026 `c_focus_web` Focus: search_web の検索クエリ
- r16 0.726272 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.725611 `c_meaning_cpu` Meaning: CPU温度の取得方法

### search_compound [compound] あの実際フォルダで探してるほう

gold=`c_role_search` rank=2 cosine=0.808993 gold_is_top=`False` gap_vs_second=-0.004915 delta_vs_clean=-0.022207

- r1 0.813908 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r2 0.808993 `c_role_search` Target Role: search_files のワークスペース検索 GOLD
- r3 0.804614 `c_focus_search` Focus path: search_files query in workspace
- r4 0.803609 `c_role_read` Target Role: read_file のワークスペース読取
- r5 0.793418 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r6 0.793053 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r7 0.781334 `c_meaning_create` Meaning: 新しいファイルを作る
- r8 0.776885 `c_focus_web` Focus: search_web の検索クエリ
- r9 0.7748 `c_role_web` Target Role: search_web のネット検索
- r10 0.770564 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.7701 `c_focus_license` Focus path: LICENSE
- r12 0.76967 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r13 0.768721 `c_goal_web` Goal: ネットで調べて要点を返す
- r14 0.762585 `c_meaning_web` Meaning: ウェブを検索する
- r15 0.751767 `c_goal_weather` Goal: 今日の天気を調べる
- r16 0.741027 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.737075 `c_meaning_cpu` Meaning: CPU温度の取得方法

### web_clean [clean] ネットで調べて

gold=`c_meaning_web` rank=3 cosine=0.796943 gold_is_top=`False` gap_vs_second=-0.036876 delta_vs_clean=None

- r1 0.833819 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.827609 `c_role_web` Target Role: search_web のネット検索
- r3 0.796943 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r4 0.78896 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.784218 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.783206 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.776704 `c_focus_license` Focus path: LICENSE
- r8 0.77009 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.765551 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r10 0.764891 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r11 0.764091 `c_role_search` Target Role: search_files のワークスペース検索
- r12 0.759737 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.758691 `c_focus_search` Focus path: search_files query in workspace
- r14 0.753314 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r15 0.749447 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r16 0.748906 `c_role_read` Target Role: read_file のワークスペース読取
- r17 0.739062 `c_meaning_create` Meaning: 新しいファイルを作る

### web_typo [typo] ねっとで調べて

gold=`c_meaning_web` rank=3 cosine=0.780493 gold_is_top=`False` gap_vs_second=-0.018089 delta_vs_clean=-0.01645

- r1 0.798582 `c_role_web` Target Role: search_web のネット検索
- r2 0.790247 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.780493 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r4 0.779311 `c_goal_weather` Goal: 今日の天気を調べる
- r5 0.775681 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r6 0.775089 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.773624 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.77244 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.772031 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.768105 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r11 0.765108 `c_focus_license` Focus path: LICENSE
- r12 0.761476 `c_focus_search` Focus path: search_files query in workspace
- r13 0.757119 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.752791 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r15 0.750299 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.74918 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r17 0.731899 `c_meaning_create` Meaning: 新しいファイルを作る

### web_conversion [conversion] 熱っとで調べて

gold=`c_meaning_web` rank=8 cosine=0.772977 gold_is_top=`False` gap_vs_second=-0.05254 delta_vs_clean=-0.023966

- r1 0.825517 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r2 0.81037 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.803009 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.779228 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r5 0.778878 `c_role_web` Target Role: search_web のネット検索
- r6 0.777157 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r7 0.773034 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r8 0.772977 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r9 0.769215 `c_focus_web` Focus: search_web の検索クエリ
- r10 0.768921 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r11 0.768862 `c_role_followup` Target Role: followup_investigation の追加調査
- r12 0.766657 `c_focus_search` Focus path: search_files query in workspace
- r13 0.751187 `c_role_search` Target Role: search_files のワークスペース検索
- r14 0.749118 `c_role_read` Target Role: read_file のワークスペース読取
- r15 0.745526 `c_focus_license` Focus path: LICENSE
- r16 0.743856 `c_meaning_create` Meaning: 新しいファイルを作る
- r17 0.73881 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md

### web_missing_char [missing_char] ネットで調

gold=`c_meaning_web` rank=4 cosine=0.775864 gold_is_top=`False` gap_vs_second=-0.031783 delta_vs_clean=-0.021079

- r1 0.807647 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.79273 `c_role_web` Target Role: search_web のネット検索
- r3 0.788904 `c_focus_license` Focus path: LICENSE
- r4 0.775864 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r5 0.768457 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r6 0.764173 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.76327 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r8 0.761128 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r9 0.7562 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r10 0.755381 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r11 0.754461 `c_focus_web` Focus: search_web の検索クエリ
- r12 0.751503 `c_meaning_create` Meaning: 新しいファイルを作る
- r13 0.747109 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.747077 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r15 0.743395 `c_role_search` Target Role: search_files のワークスペース検索
- r16 0.733521 `c_role_followup` Target Role: followup_investigation の追加調査
- r17 0.729102 `c_focus_search` Focus path: search_files query in workspace

### web_particle [particle_drop] ネット調べて

gold=`c_meaning_web` rank=3 cosine=0.808423 gold_is_top=`False` gap_vs_second=-0.028078 delta_vs_clean=0.01148

- r1 0.836501 `c_role_web` Target Role: search_web のネット検索
- r2 0.836219 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.808423 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r4 0.792733 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.783396 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.780792 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.772907 `c_role_followup` Target Role: followup_investigation の追加調査
- r8 0.772175 `c_focus_license` Focus path: LICENSE
- r9 0.765013 `c_role_search` Target Role: search_files のワークスペース検索
- r10 0.762749 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r11 0.762193 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r12 0.760188 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r13 0.757023 `c_focus_search` Focus path: search_files query in workspace
- r14 0.756598 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r15 0.750954 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r16 0.746728 `c_role_read` Target Role: read_file のワークスペース読取
- r17 0.738126 `c_meaning_create` Meaning: 新しいファイルを作る

### web_colloquial [colloquial] ネットのやつ

gold=`c_role_web` rank=2 cosine=0.804879 gold_is_top=`False` gap_vs_second=-0.001408 delta_vs_clean=0.007936

- r1 0.806287 `c_goal_web` Goal: ネットで調べて要点を返す
- r2 0.804879 `c_role_web` Target Role: search_web のネット検索 GOLD
- r3 0.79068 `c_meaning_web` Meaning: ウェブを検索する
- r4 0.783715 `c_focus_license` Focus path: LICENSE
- r5 0.769329 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r6 0.765926 `c_focus_web` Focus: search_web の検索クエリ
- r7 0.765408 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r8 0.76229 `c_goal_weather` Goal: 今日の天気を調べる
- r9 0.757005 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r10 0.756398 `c_role_search` Target Role: search_files のワークスペース検索
- r11 0.756119 `c_meaning_create` Meaning: 新しいファイルを作る
- r12 0.754601 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r13 0.753817 `c_role_read` Target Role: read_file のワークスペース読取
- r14 0.753289 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r15 0.741412 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r16 0.732159 `c_focus_search` Focus path: search_files query in workspace
- r17 0.731341 `c_role_followup` Target Role: followup_investigation の追加調査

### web_filler [filler] まあネットで調べてかな

gold=`c_meaning_web` rank=3 cosine=0.780303 gold_is_top=`False` gap_vs_second=-0.024254 delta_vs_clean=-0.01664

- r1 0.804557 `c_role_web` Target Role: search_web のネット検索
- r2 0.804127 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.780303 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r4 0.774839 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.762509 `c_goal_weather` Goal: 今日の天気を調べる
- r6 0.754996 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r7 0.747454 `c_focus_license` Focus path: LICENSE
- r8 0.746797 `c_role_followup` Target Role: followup_investigation の追加調査
- r9 0.744186 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r10 0.743558 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r11 0.740089 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r12 0.739214 `c_role_search` Target Role: search_files のワークスペース検索
- r13 0.735767 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r14 0.733345 `c_focus_search` Focus path: search_files query in workspace
- r15 0.732294 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r16 0.725858 `c_role_read` Target Role: read_file のワークスペース読取
- r17 0.719689 `c_meaning_create` Meaning: 新しいファイルを作る

### web_restatement [restatement] ローカルじゃなくてネットで調べて

gold=`c_meaning_web` rank=5 cosine=0.783277 gold_is_top=`False` gap_vs_second=-0.036876 delta_vs_clean=-0.013666

- r1 0.820153 `c_role_web` Target Role: search_web のネット検索
- r2 0.807276 `c_goal_web` Goal: ネットで調べて要点を返す
- r3 0.798332 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r4 0.793833 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.783277 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r6 0.779893 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.779589 `c_role_search` Target Role: search_files のワークスペース検索
- r8 0.773534 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r9 0.766814 `c_focus_search` Focus path: search_files query in workspace
- r10 0.762231 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r11 0.761132 `c_focus_license` Focus path: LICENSE
- r12 0.756251 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r13 0.743218 `c_role_followup` Target Role: followup_investigation の追加調査
- r14 0.739251 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r15 0.736623 `c_role_read` Target Role: read_file のワークスペース読取
- r16 0.736184 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r17 0.720399 `c_meaning_create` Meaning: 新しいファイルを作る

### web_asr [asr_like] 熱斗で調べて

gold=`c_meaning_web` rank=9 cosine=0.740247 gold_is_top=`False` gap_vs_second=-0.069819 delta_vs_clean=-0.056696

- r1 0.810066 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r2 0.784817 `c_goal_weather` Goal: 今日の天気を調べる
- r3 0.7785 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.758264 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r5 0.757295 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.755478 `c_role_followup` Target Role: followup_investigation の追加調査
- r7 0.750561 `c_role_web` Target Role: search_web のネット検索
- r8 0.744296 `c_focus_web` Focus: search_web の検索クエリ
- r9 0.740247 `c_meaning_web` Meaning: ウェブを検索する GOLD
- r10 0.73904 `c_meaning_create` Meaning: 新しいファイルを作る
- r11 0.737647 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r12 0.733621 `c_focus_search` Focus path: search_files query in workspace
- r13 0.733446 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r14 0.730686 `c_focus_license` Focus path: LICENSE
- r15 0.726995 `c_role_search` Target Role: search_files のワークスペース検索
- r16 0.725281 `c_role_read` Target Role: read_file のワークスペース読取
- r17 0.720413 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md

### web_demonstrative [demonstrative] ネットのほう

gold=`c_role_web` rank=1 cosine=0.809604 gold_is_top=`True` gap_vs_second=0.001175 delta_vs_clean=0.012661

- r1 0.809604 `c_role_web` Target Role: search_web のネット検索 GOLD
- r2 0.808429 `c_meaning_web` Meaning: ウェブを検索する
- r3 0.794489 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.77956 `c_focus_license` Focus path: LICENSE
- r5 0.772021 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r6 0.768259 `c_focus_web` Focus: search_web の検索クエリ
- r7 0.7621 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r8 0.756542 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r9 0.752312 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.750076 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r11 0.749786 `c_role_read` Target Role: read_file のワークスペース読取
- r12 0.74957 `c_role_search` Target Role: search_files のワークスペース検索
- r13 0.749448 `c_goal_weather` Goal: 今日の天気を調べる
- r14 0.749433 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r15 0.749 `c_focus_search` Focus path: search_files query in workspace
- r16 0.748068 `c_meaning_create` Meaning: 新しいファイルを作る
- r17 0.727199 `c_role_followup` Target Role: followup_investigation の追加調査

### web_compound [compound] まあねっとで調べるのも

gold=`c_role_web` rank=1 cosine=0.793404 gold_is_top=`True` gap_vs_second=0.008616 delta_vs_clean=-0.003539

- r1 0.793404 `c_role_web` Target Role: search_web のネット検索 GOLD
- r2 0.784788 `c_meaning_web` Meaning: ウェブを検索する
- r3 0.78342 `c_goal_web` Goal: ネットで調べて要点を返す
- r4 0.771273 `c_focus_web` Focus: search_web の検索クエリ
- r5 0.764987 `c_goal_search` Goal: リポジトリ内を検索して該当箇所を探す
- r6 0.764867 `c_goal_weather` Goal: 今日の天気を調べる
- r7 0.764598 `c_role_followup` Target Role: followup_investigation の追加調査
- r8 0.761705 `c_role_search` Target Role: search_files のワークスペース検索
- r9 0.757861 `c_meaning_cpu` Meaning: CPU温度の取得方法
- r10 0.751331 `c_meaning_search` Meaning: ワークスペース内を文字列検索する
- r11 0.748811 `c_focus_search` Focus path: search_files query in workspace
- r12 0.741738 `c_focus_read` Focus path: docs/CURRENT_DEVELOPMENT_STATE.md
- r13 0.74149 `c_goal_read` Goal: 指定ファイルを読んで要約する
- r14 0.741474 `c_meaning_read` Meaning: ワークスペースのファイルを読む
- r15 0.740253 `c_focus_license` Focus path: LICENSE
- r16 0.734984 `c_role_read` Target Role: read_file のワークスペース読取
- r17 0.721661 `c_meaning_create` Meaning: 新しいファイルを作る
