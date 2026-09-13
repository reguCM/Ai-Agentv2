# Embedding similarity Japanese input noise v0

- run_id: `20260909T145551Z`
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

- baseline: VRAM 3765 / 12288 MiB, RAM used 39632 / 65277 MB
- after_embed: VRAM 3765 / 12288 MiB, RAM used 39671 / 65277 MB

## ノイズ種別まとめ

- `clean`: gold_top 3/3 mean_rank=1.0 mean_gap=0.324152 mean_delta_vs_clean=None failed=[]
- `typo`: gold_top 3/3 mean_rank=1.0 mean_gap=0.132023 mean_delta_vs_clean=-0.20001 failed=[]
- `conversion`: gold_top 2/3 mean_rank=2.0 mean_gap=0.134171 mean_delta_vs_clean=-0.181451 failed=['research_conversion']
- `missing_char`: gold_top 3/3 mean_rank=1.0 mean_gap=0.187387 mean_delta_vs_clean=-0.139514 failed=[]
- `particle_drop`: gold_top 3/3 mean_rank=1.0 mean_gap=0.310225 mean_delta_vs_clean=-0.01981 failed=[]
- `colloquial`: gold_top 3/3 mean_rank=1.0 mean_gap=0.200391 mean_delta_vs_clean=-0.126955 failed=[]
- `filler`: gold_top 3/3 mean_rank=1.0 mean_gap=0.219427 mean_delta_vs_clean=-0.169687 failed=[]
- `restatement`: gold_top 3/3 mean_rank=1.0 mean_gap=0.180364 mean_delta_vs_clean=-0.14512 failed=[]
- `asr_like`: gold_top 2/3 mean_rank=2.0 mean_gap=0.110696 mean_delta_vs_clean=-0.197937 failed=['research_asr']
- `demonstrative`: gold_top 3/3 mean_rank=1.0 mean_gap=0.216801 mean_delta_vs_clean=-0.120452 failed=[]
- `compound`: gold_top 2/3 mean_rank=1.333 mean_gap=0.045602 mean_delta_vs_clean=-0.326577 failed=['runtime_compound']

失敗したノイズ種別: ['conversion', 'asr_like', 'compound']

## 失敗ケース

- `runtime_compound` [compound] あの実際ゲームで使ってるほう gold_rank=2 gold_cos=0.596542 top=`c_board` 0.613708 delta_vs_clean=-0.342923
- `research_conversion` [conversion] 兼休用のもの gold_rank=4 gold_cos=0.508512 top=`c_score` 0.572932 delta_vs_clean=-0.430008
- `research_asr` [asr_like] 兼急用のもの gold_rank=4 gold_cos=0.529941 top=`c_prd` 0.564459 delta_vs_clean=-0.408579

## 各クエリ

### board_clean [clean] テトリスの盤面

gold=`c_board` rank=1 cosine=0.778096 gold_is_top=`True` gap_vs_second=0.242335 delta_vs_clean=None

- r1 0.778096 `c_board` ゲームの盤面状態 GOLD
- r2 0.535761 `c_score` ハイスコアの保存方法
- r3 0.532625 `c_theme` 画面の配色テーマ
- r4 0.531124 `c_runtime` 実行時の実装
- r5 0.520031 `c_prd` PRDの書き方
- r6 0.510193 `c_weather` 今日の天気と降水確率
- r7 0.501499 `c_cpu` CPU温度の取得方法
- r8 0.468016 `c_research` 研究用の実験
- r9 0.373873 `c_license` MIT license text for a Python package

### board_typo [typo] テとりすの盤面

gold=`c_board` rank=1 cosine=0.669371 gold_is_top=`True` gap_vs_second=0.119046 delta_vs_clean=-0.108725

- r1 0.669371 `c_board` ゲームの盤面状態 GOLD
- r2 0.550325 `c_score` ハイスコアの保存方法
- r3 0.547288 `c_runtime` 実行時の実装
- r4 0.536502 `c_theme` 画面の配色テーマ
- r5 0.536027 `c_prd` PRDの書き方
- r6 0.507733 `c_weather` 今日の天気と降水確率
- r7 0.483607 `c_research` 研究用の実験
- r8 0.477314 `c_cpu` CPU温度の取得方法
- r9 0.365487 `c_license` MIT license text for a Python package

### board_conversion [conversion] テトリスの番面

gold=`c_board` rank=1 cosine=0.728993 gold_is_top=`True` gap_vs_second=0.185941 delta_vs_clean=-0.049103

- r1 0.728993 `c_board` ゲームの盤面状態 GOLD
- r2 0.543052 `c_score` ハイスコアの保存方法
- r3 0.533032 `c_theme` 画面の配色テーマ
- r4 0.528306 `c_runtime` 実行時の実装
- r5 0.506666 `c_cpu` CPU温度の取得方法
- r6 0.504798 `c_prd` PRDの書き方
- r7 0.49132 `c_weather` 今日の天気と降水確率
- r8 0.461326 `c_research` 研究用の実験
- r9 0.36603 `c_license` MIT license text for a Python package

### board_missing_char [missing_char] テトリスの盤

gold=`c_board` rank=1 cosine=0.744728 gold_is_top=`True` gap_vs_second=0.194271 delta_vs_clean=-0.033368

- r1 0.744728 `c_board` ゲームの盤面状態 GOLD
- r2 0.550457 `c_score` ハイスコアの保存方法
- r3 0.524079 `c_prd` PRDの書き方
- r4 0.520083 `c_runtime` 実行時の実装
- r5 0.509711 `c_weather` 今日の天気と降水確率
- r6 0.506455 `c_theme` 画面の配色テーマ
- r7 0.502639 `c_cpu` CPU温度の取得方法
- r8 0.461317 `c_research` 研究用の実験
- r9 0.378972 `c_license` MIT license text for a Python package

### board_particle [particle_drop] テトリス盤面

gold=`c_board` rank=1 cosine=0.779116 gold_is_top=`True` gap_vs_second=0.244639 delta_vs_clean=0.00102

- r1 0.779116 `c_board` ゲームの盤面状態 GOLD
- r2 0.534477 `c_theme` 画面の配色テーマ
- r3 0.508588 `c_runtime` 実行時の実装
- r4 0.504608 `c_prd` PRDの書き方
- r5 0.503255 `c_score` ハイスコアの保存方法
- r6 0.497141 `c_weather` 今日の天気と降水確率
- r7 0.484244 `c_cpu` CPU温度の取得方法
- r8 0.452516 `c_research` 研究用の実験
- r9 0.36671 `c_license` MIT license text for a Python package

### board_colloquial [colloquial] テトリスの盤面のやつ

gold=`c_board` rank=1 cosine=0.77335 gold_is_top=`True` gap_vs_second=0.240557 delta_vs_clean=-0.004746

- r1 0.77335 `c_board` ゲームの盤面状態 GOLD
- r2 0.532793 `c_theme` 画面の配色テーマ
- r3 0.528441 `c_runtime` 実行時の実装
- r4 0.525569 `c_score` ハイスコアの保存方法
- r5 0.513868 `c_prd` PRDの書き方
- r6 0.493612 `c_cpu` CPU温度の取得方法
- r7 0.492357 `c_weather` 今日の天気と降水確率
- r8 0.465027 `c_research` 研究用の実験
- r9 0.364074 `c_license` MIT license text for a Python package

### board_filler [filler] えっとテトリスの盤面

gold=`c_board` rank=1 cosine=0.750977 gold_is_top=`True` gap_vs_second=0.215548 delta_vs_clean=-0.027119

- r1 0.750977 `c_board` ゲームの盤面状態 GOLD
- r2 0.535429 `c_runtime` 実行時の実装
- r3 0.532552 `c_theme` 画面の配色テーマ
- r4 0.523982 `c_score` ハイスコアの保存方法
- r5 0.522898 `c_prd` PRDの書き方
- r6 0.509769 `c_weather` 今日の天気と降水確率
- r7 0.488095 `c_cpu` CPU温度の取得方法
- r8 0.466834 `c_research` 研究用の実験
- r9 0.375408 `c_license` MIT license text for a Python package

### board_restatement [restatement] いやスコアじゃなくてテトリスの盤面

gold=`c_board` rank=1 cosine=0.653524 gold_is_top=`True` gap_vs_second=0.155081 delta_vs_clean=-0.124572

- r1 0.653524 `c_board` ゲームの盤面状態 GOLD
- r2 0.498443 `c_theme` 画面の配色テーマ
- r3 0.470815 `c_score` ハイスコアの保存方法
- r4 0.442529 `c_prd` PRDの書き方
- r5 0.435027 `c_runtime` 実行時の実装
- r6 0.399216 `c_cpu` CPU温度の取得方法
- r7 0.397791 `c_weather` 今日の天気と降水確率
- r8 0.397009 `c_research` 研究用の実験
- r9 0.310106 `c_license` MIT license text for a Python package

### board_asr [asr_like] 手取り巣の盤面

gold=`c_board` rank=1 cosine=0.676548 gold_is_top=`True` gap_vs_second=0.081532 delta_vs_clean=-0.101548

- r1 0.676548 `c_board` ゲームの盤面状態 GOLD
- r2 0.595016 `c_prd` PRDの書き方
- r3 0.585839 `c_runtime` 実行時の実装
- r4 0.577524 `c_score` ハイスコアの保存方法
- r5 0.56709 `c_theme` 画面の配色テーマ
- r6 0.510033 `c_research` 研究用の実験
- r7 0.49879 `c_weather` 今日の天気と降水確率
- r8 0.458087 `c_cpu` CPU温度の取得方法
- r9 0.349772 `c_license` MIT license text for a Python package

### board_demonstrative [demonstrative] そっちの盤面

gold=`c_board` rank=1 cosine=0.711475 gold_is_top=`True` gap_vs_second=0.169748 delta_vs_clean=-0.066621

- r1 0.711475 `c_board` ゲームの盤面状態 GOLD
- r2 0.541727 `c_theme` 画面の配色テーマ
- r3 0.536779 `c_score` ハイスコアの保存方法
- r4 0.532829 `c_prd` PRDの書き方
- r5 0.53252 `c_runtime` 実行時の実装
- r6 0.510958 `c_weather` 今日の天気と降水確率
- r7 0.448251 `c_research` 研究用の実験
- r8 0.436475 `c_cpu` CPU温度の取得方法
- r9 0.34322 `c_license` MIT license text for a Python package

### board_compound [compound] えっとテトリスの番面のやつ

gold=`c_board` rank=1 cosine=0.66431 gold_is_top=`True` gap_vs_second=0.14504 delta_vs_clean=-0.113786

- r1 0.66431 `c_board` ゲームの盤面状態 GOLD
- r2 0.51927 `c_theme` 画面の配色テーマ
- r3 0.510897 `c_runtime` 実行時の実装
- r4 0.508784 `c_score` ハイスコアの保存方法
- r5 0.486321 `c_prd` PRDの書き方
- r6 0.468485 `c_cpu` CPU温度の取得方法
- r7 0.460343 `c_weather` 今日の天気と降水確率
- r8 0.443429 `c_research` 研究用の実験
- r9 0.350474 `c_license` MIT license text for a Python package

### runtime_clean [clean] 実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.939465 gold_is_top=`True` gap_vs_second=0.367014 delta_vs_clean=None

- r1 0.939465 `c_runtime` 実行時の実装 GOLD
- r2 0.572451 `c_research` 研究用の実験
- r3 0.545588 `c_board` ゲームの盤面状態
- r4 0.478329 `c_cpu` CPU温度の取得方法
- r5 0.472516 `c_score` ハイスコアの保存方法
- r6 0.456681 `c_prd` PRDの書き方
- r7 0.437623 `c_theme` 画面の配色テーマ
- r8 0.414541 `c_weather` 今日の天気と降水確率
- r9 0.282617 `c_license` MIT license text for a Python package

### runtime_typo [typo] 実交時に動いている実装

gold=`c_runtime` rank=1 cosine=0.837585 gold_is_top=`True` gap_vs_second=0.270688 delta_vs_clean=-0.10188

- r1 0.837585 `c_runtime` 実行時の実装 GOLD
- r2 0.566897 `c_board` ゲームの盤面状態
- r3 0.519584 `c_research` 研究用の実験
- r4 0.496961 `c_score` ハイスコアの保存方法
- r5 0.475209 `c_prd` PRDの書き方
- r6 0.451415 `c_theme` 画面の配色テーマ
- r7 0.439691 `c_weather` 今日の天気と降水確率
- r8 0.436543 `c_cpu` CPU温度の取得方法
- r9 0.28848 `c_license` MIT license text for a Python package

### runtime_conversion [conversion] 実効時に動いている実装

gold=`c_runtime` rank=1 cosine=0.874223 gold_is_top=`True` gap_vs_second=0.280992 delta_vs_clean=-0.065242

- r1 0.874223 `c_runtime` 実行時の実装 GOLD
- r2 0.593231 `c_research` 研究用の実験
- r3 0.556537 `c_board` ゲームの盤面状態
- r4 0.535934 `c_prd` PRDの書き方
- r5 0.503427 `c_score` ハイスコアの保存方法
- r6 0.473641 `c_cpu` CPU温度の取得方法
- r7 0.459989 `c_theme` 画面の配色テーマ
- r8 0.456501 `c_weather` 今日の天気と降水確率
- r9 0.302729 `c_license` MIT license text for a Python package

### runtime_missing_char [missing_char] 実行時に動いている実

gold=`c_runtime` rank=1 cosine=0.783649 gold_is_top=`True` gap_vs_second=0.296043 delta_vs_clean=-0.155816

- r1 0.783649 `c_runtime` 実行時の実装 GOLD
- r2 0.487606 `c_research` 研究用の実験
- r3 0.47974 `c_board` ゲームの盤面状態
- r4 0.385274 `c_cpu` CPU温度の取得方法
- r5 0.384717 `c_theme` 画面の配色テーマ
- r6 0.379301 `c_weather` 今日の天気と降水確率
- r7 0.366076 `c_prd` PRDの書き方
- r8 0.345773 `c_score` ハイスコアの保存方法
- r9 0.209294 `c_license` MIT license text for a Python package

### runtime_particle [particle_drop] 実行時動いている実装

gold=`c_runtime` rank=1 cosine=0.905696 gold_is_top=`True` gap_vs_second=0.335062 delta_vs_clean=-0.033769

- r1 0.905696 `c_runtime` 実行時の実装 GOLD
- r2 0.570634 `c_board` ゲームの盤面状態
- r3 0.568877 `c_research` 研究用の実験
- r4 0.47482 `c_prd` PRDの書き方
- r5 0.468863 `c_score` ハイスコアの保存方法
- r6 0.465018 `c_cpu` CPU温度の取得方法
- r7 0.455392 `c_theme` 画面の配色テーマ
- r8 0.451744 `c_weather` 今日の天気と降水確率
- r9 0.300418 `c_license` MIT license text for a Python package

### runtime_colloquial [colloquial] 実際に動いてるほう

gold=`c_runtime` rank=1 cosine=0.590041 gold_is_top=`True` gap_vs_second=0.001354 delta_vs_clean=-0.349424

- r1 0.590041 `c_runtime` 実行時の実装 GOLD
- r2 0.588687 `c_board` ゲームの盤面状態
- r3 0.506929 `c_theme` 画面の配色テーマ
- r4 0.481565 `c_research` 研究用の実験
- r5 0.478544 `c_weather` 今日の天気と降水確率
- r6 0.416717 `c_prd` PRDの書き方
- r7 0.416054 `c_score` ハイスコアの保存方法
- r8 0.403408 `c_cpu` CPU温度の取得方法
- r9 0.246694 `c_license` MIT license text for a Python package

### runtime_filler [filler] あのー実行時に動いている実装なんですけど

gold=`c_runtime` rank=1 cosine=0.708859 gold_is_top=`True` gap_vs_second=0.275691 delta_vs_clean=-0.230606

- r1 0.708859 `c_runtime` 実行時の実装 GOLD
- r2 0.433168 `c_research` 研究用の実験
- r3 0.417419 `c_board` ゲームの盤面状態
- r4 0.346551 `c_prd` PRDの書き方
- r5 0.341314 `c_theme` 画面の配色テーマ
- r6 0.337382 `c_score` ハイスコアの保存方法
- r7 0.316329 `c_weather` 今日の天気と降水確率
- r8 0.303263 `c_cpu` CPU温度の取得方法
- r9 0.170058 `c_license` MIT license text for a Python package

### runtime_restatement [restatement] 実験用じゃなくて実行時に動いている実装

gold=`c_runtime` rank=1 cosine=0.866028 gold_is_top=`True` gap_vs_second=0.205121 delta_vs_clean=-0.073437

- r1 0.866028 `c_runtime` 実行時の実装 GOLD
- r2 0.660907 `c_research` 研究用の実験
- r3 0.515246 `c_board` ゲームの盤面状態
- r4 0.475628 `c_score` ハイスコアの保存方法
- r5 0.456346 `c_prd` PRDの書き方
- r6 0.442339 `c_theme` 画面の配色テーマ
- r7 0.43776 `c_cpu` CPU温度の取得方法
- r8 0.400471 `c_weather` 今日の天気と降水確率
- r9 0.280571 `c_license` MIT license text for a Python package

### runtime_asr [asr_like] 実効時に動いてる実装

gold=`c_runtime` rank=1 cosine=0.855782 gold_is_top=`True` gap_vs_second=0.285074 delta_vs_clean=-0.083683

- r1 0.855782 `c_runtime` 実行時の実装 GOLD
- r2 0.570708 `c_research` 研究用の実験
- r3 0.559242 `c_board` ゲームの盤面状態
- r4 0.517107 `c_prd` PRDの書き方
- r5 0.488738 `c_score` ハイスコアの保存方法
- r6 0.46451 `c_cpu` CPU温度の取得方法
- r7 0.445967 `c_theme` 画面の配色テーマ
- r8 0.44579 `c_weather` 今日の天気と降水確率
- r9 0.293446 `c_license` MIT license text for a Python package

### runtime_demonstrative [demonstrative] 実際に使ってる方

gold=`c_runtime` rank=1 cosine=0.658591 gold_is_top=`True` gap_vs_second=0.114154 delta_vs_clean=-0.280874

- r1 0.658591 `c_runtime` 実行時の実装 GOLD
- r2 0.544437 `c_board` ゲームの盤面状態
- r3 0.530379 `c_research` 研究用の実験
- r4 0.477491 `c_weather` 今日の天気と降水確率
- r5 0.466673 `c_prd` PRDの書き方
- r6 0.461033 `c_score` ハイスコアの保存方法
- r7 0.455266 `c_theme` 画面の配色テーマ
- r8 0.441104 `c_cpu` CPU温度の取得方法
- r9 0.291027 `c_license` MIT license text for a Python package

### runtime_compound [compound] あの実際ゲームで使ってるほう

gold=`c_runtime` rank=2 cosine=0.596542 gold_is_top=`False` gap_vs_second=-0.017166 delta_vs_clean=-0.342923

- r1 0.613708 `c_board` ゲームの盤面状態
- r2 0.596542 `c_runtime` 実行時の実装 GOLD
- r3 0.471128 `c_research` 研究用の実験
- r4 0.467429 `c_score` ハイスコアの保存方法
- r5 0.448066 `c_theme` 画面の配色テーマ
- r6 0.417568 `c_cpu` CPU温度の取得方法
- r7 0.383604 `c_prd` PRDの書き方
- r8 0.374837 `c_weather` 今日の天気と降水確率
- r9 0.247088 `c_license` MIT license text for a Python package

### research_clean [clean] 研究用のもの

gold=`c_research` rank=1 cosine=0.93852 gold_is_top=`True` gap_vs_second=0.363106 delta_vs_clean=None

- r1 0.93852 `c_research` 研究用の実験 GOLD
- r2 0.575414 `c_runtime` 実行時の実装
- r3 0.549232 `c_prd` PRDの書き方
- r4 0.497804 `c_score` ハイスコアの保存方法
- r5 0.496517 `c_board` ゲームの盤面状態
- r6 0.48177 `c_theme` 画面の配色テーマ
- r7 0.454538 `c_cpu` CPU温度の取得方法
- r8 0.418587 `c_weather` 今日の天気と降水確率
- r9 0.322165 `c_license` MIT license text for a Python package

### research_typo [typo] けんきゅう用のもの

gold=`c_research` rank=1 cosine=0.549096 gold_is_top=`True` gap_vs_second=0.006335 delta_vs_clean=-0.389424

- r1 0.549096 `c_research` 研究用の実験 GOLD
- r2 0.542761 `c_score` ハイスコアの保存方法
- r3 0.539582 `c_board` ゲームの盤面状態
- r4 0.508311 `c_prd` PRDの書き方
- r5 0.504555 `c_theme` 画面の配色テーマ
- r6 0.496553 `c_runtime` 実行時の実装
- r7 0.491396 `c_weather` 今日の天気と降水確率
- r8 0.430509 `c_cpu` CPU温度の取得方法
- r9 0.358441 `c_license` MIT license text for a Python package

### research_conversion [conversion] 兼休用のもの

gold=`c_research` rank=4 cosine=0.508512 gold_is_top=`False` gap_vs_second=-0.06442 delta_vs_clean=-0.430008

- r1 0.572932 `c_score` ハイスコアの保存方法
- r2 0.549927 `c_board` ゲームの盤面状態
- r3 0.534004 `c_runtime` 実行時の実装
- r4 0.508512 `c_research` 研究用の実験 GOLD
- r5 0.4941 `c_prd` PRDの書き方
- r6 0.49401 `c_theme` 画面の配色テーマ
- r7 0.413845 `c_weather` 今日の天気と降水確率
- r8 0.410217 `c_cpu` CPU温度の取得方法
- r9 0.348057 `c_license` MIT license text for a Python package

### research_missing_char [missing_char] 究用のもの

gold=`c_research` rank=1 cosine=0.709162 gold_is_top=`True` gap_vs_second=0.071848 delta_vs_clean=-0.229358

- r1 0.709162 `c_research` 研究用の実験 GOLD
- r2 0.637314 `c_runtime` 実行時の実装
- r3 0.595856 `c_board` ゲームの盤面状態
- r4 0.59479 `c_prd` PRDの書き方
- r5 0.585705 `c_score` ハイスコアの保存方法
- r6 0.529831 `c_theme` 画面の配色テーマ
- r7 0.521363 `c_weather` 今日の天気と降水確率
- r8 0.517767 `c_cpu` CPU温度の取得方法
- r9 0.402398 `c_license` MIT license text for a Python package

### research_particle [particle_drop] 研究用もの

gold=`c_research` rank=1 cosine=0.911839 gold_is_top=`True` gap_vs_second=0.350975 delta_vs_clean=-0.026681

- r1 0.911839 `c_research` 研究用の実験 GOLD
- r2 0.560864 `c_runtime` 実行時の実装
- r3 0.526135 `c_prd` PRDの書き方
- r4 0.500377 `c_board` ゲームの盤面状態
- r5 0.493965 `c_theme` 画面の配色テーマ
- r6 0.491212 `c_score` ハイスコアの保存方法
- r7 0.461981 `c_cpu` CPU温度の取得方法
- r8 0.420646 `c_weather` 今日の天気と降水確率
- r9 0.316213 `c_license` MIT license text for a Python package

### research_colloquial [colloquial] 研究用のやつ

gold=`c_research` rank=1 cosine=0.911826 gold_is_top=`True` gap_vs_second=0.359263 delta_vs_clean=-0.026694

- r1 0.911826 `c_research` 研究用の実験 GOLD
- r2 0.552563 `c_runtime` 実行時の実装
- r3 0.535179 `c_prd` PRDの書き方
- r4 0.482334 `c_score` ハイスコアの保存方法
- r5 0.476996 `c_theme` 画面の配色テーマ
- r6 0.474413 `c_board` ゲームの盤面状態
- r7 0.445291 `c_cpu` CPU温度の取得方法
- r8 0.401705 `c_weather` 今日の天気と降水確率
- r9 0.325305 `c_license` MIT license text for a Python package

### research_filler [filler] まあ研究用のものかな

gold=`c_research` rank=1 cosine=0.687184 gold_is_top=`True` gap_vs_second=0.167043 delta_vs_clean=-0.251336

- r1 0.687184 `c_research` 研究用の実験 GOLD
- r2 0.520141 `c_prd` PRDの書き方
- r3 0.49431 `c_runtime` 実行時の実装
- r4 0.463452 `c_board` ゲームの盤面状態
- r5 0.46266 `c_theme` 画面の配色テーマ
- r6 0.460644 `c_score` ハイスコアの保存方法
- r7 0.444814 `c_cpu` CPU温度の取得方法
- r8 0.41604 `c_weather` 今日の天気と降水確率
- r9 0.330571 `c_license` MIT license text for a Python package

### research_restatement [restatement] 本番じゃなくて研究用のもの

gold=`c_research` rank=1 cosine=0.701169 gold_is_top=`True` gap_vs_second=0.180891 delta_vs_clean=-0.237351

- r1 0.701169 `c_research` 研究用の実験 GOLD
- r2 0.520278 `c_runtime` 実行時の実装
- r3 0.507219 `c_prd` PRDの書き方
- r4 0.49026 `c_board` ゲームの盤面状態
- r5 0.484921 `c_score` ハイスコアの保存方法
- r6 0.484842 `c_theme` 画面の配色テーマ
- r7 0.403723 `c_cpu` CPU温度の取得方法
- r8 0.403304 `c_weather` 今日の天気と降水確率
- r9 0.309539 `c_license` MIT license text for a Python package

### research_asr [asr_like] 兼急用のもの

gold=`c_research` rank=4 cosine=0.529941 gold_is_top=`False` gap_vs_second=-0.034518 delta_vs_clean=-0.408579

- r1 0.564459 `c_prd` PRDの書き方
- r2 0.546981 `c_runtime` 実行時の実装
- r3 0.539634 `c_score` ハイスコアの保存方法
- r4 0.529941 `c_research` 研究用の実験 GOLD
- r5 0.517863 `c_board` ゲームの盤面状態
- r6 0.506197 `c_weather` 今日の天気と降水確率
- r7 0.49427 `c_theme` 画面の配色テーマ
- r8 0.432699 `c_cpu` CPU温度の取得方法
- r9 0.352104 `c_license` MIT license text for a Python package

### research_demonstrative [demonstrative] 研究用のほう

gold=`c_research` rank=1 cosine=0.924659 gold_is_top=`True` gap_vs_second=0.366502 delta_vs_clean=-0.013861

- r1 0.924659 `c_research` 研究用の実験 GOLD
- r2 0.558157 `c_runtime` 実行時の実装
- r3 0.517601 `c_prd` PRDの書き方
- r4 0.473426 `c_board` ゲームの盤面状態
- r5 0.466487 `c_theme` 画面の配色テーマ
- r6 0.462298 `c_score` ハイスコアの保存方法
- r7 0.442389 `c_cpu` CPU温度の取得方法
- r8 0.396849 `c_weather` 今日の天気と降水確率
- r9 0.286772 `c_license` MIT license text for a Python package

### research_compound [compound] まあけんきゅう用のも

gold=`c_research` rank=1 cosine=0.415498 gold_is_top=`True` gap_vs_second=0.008932 delta_vs_clean=-0.523022

- r1 0.415498 `c_research` 研究用の実験 GOLD
- r2 0.406566 `c_board` ゲームの盤面状態
- r3 0.367524 `c_theme` 画面の配色テーマ
- r4 0.358047 `c_prd` PRDの書き方
- r5 0.353555 `c_weather` 今日の天気と降水確率
- r6 0.346111 `c_score` ハイスコアの保存方法
- r7 0.345385 `c_runtime` 実行時の実装
- r8 0.309236 `c_cpu` CPU温度の取得方法
- r9 0.239437 `c_license` MIT license text for a Python package
