# Embedding similarity v0 run

- run_id: `20260909T141840Z`
- embed_model: `qwen3-embedding:0.6b`
- gen_model: `qwen3:14b`
- Production / Grill 接続: なし

## 同時利用

{
  "gen_loaded_before_embed": true,
  "both_listed_during_embed": true,
  "gen_responded_after_embed": true,
  "note": "Resident-in-VRAM vs sequential Ollama swap are recorded separately.",
  "gen_warmup": {
    "ok": true,
    "elapsed_ms": 7757.2,
    "content": "",
    "error": null
  },
  "ollama_ps_after_embed": "NAME                    ID              SIZE      PROCESSOR    CONTEXT    UNTIL               \nqwen3-embedding:0.6b    ac6da0dfba84    2.4 GB    100% GPU     4096       29 minutes from now    \nqwen3:14b               bdbd181c33f2    9.6 GB    100% GPU     4096       29 minutes from now",
  "first_embed_ms": 2923.4,
  "gen_reping": {
    "ok": true,
    "elapsed_ms": 1651.4,
    "content": "",
    "error": null
  }
}

## 資源

- baseline: VRAM 2059 / 12288 MiB, RAM used 38296 / 65277 MB
- after_gen_warmup: VRAM 11385 / 12288 MiB, RAM used 39234 / 65277 MB
- after_embed: VRAM 11933 / 12288 MiB, RAM used 41263 / 65277 MB
- after_gen_reping: VRAM 11933 / 12288 MiB, RAM used 42288 / 65277 MB

## 類似度

### q_board: テトリスの盤面

top=`c_board_en` expected_near_hit=`True`

- r1 0.62101 `c_board_en` game board state
- r2 0.510193 `c_unrelated_weather` 今日の天気と降水確率
- r3 0.505042 `c_runtime_en` runtime implementation
- r4 0.501499 `c_unrelated_cpu` CPU温度の取得方法
- r5 0.480075 `c_research_code` research/ experiment harness
- r6 0.468611 `c_research_en` research experiment
- r7 0.412605 `c_runtime_code` production runtime path
- r8 0.373873 `c_unrelated_license` MIT license text for a Python package

### q_runtime: 実際のゲームで使っている方

top=`c_board_en` expected_near_hit=`False`

- r1 0.467997 `c_board_en` game board state
- r2 0.459901 `c_runtime_en` runtime implementation
- r3 0.408951 `c_unrelated_cpu` CPU温度の取得方法
- r4 0.408639 `c_research_code` research/ experiment harness
- r5 0.4056 `c_research_en` research experiment
- r6 0.347196 `c_unrelated_weather` 今日の天気と降水確率
- r7 0.331324 `c_runtime_code` production runtime path
- r8 0.257132 `c_unrelated_license` MIT license text for a Python package

### q_research: 研究用のもの

top=`c_research_en` expected_near_hit=`True`

- r1 0.756724 `c_research_en` research experiment
- r2 0.646167 `c_research_code` research/ experiment harness
- r3 0.523563 `c_runtime_en` runtime implementation
- r4 0.454538 `c_unrelated_cpu` CPU温度の取得方法
- r5 0.418587 `c_unrelated_weather` 今日の天気と降水確率
- r6 0.410544 `c_runtime_code` production runtime path
- r7 0.384425 `c_board_en` game board state
- r8 0.322165 `c_unrelated_license` MIT license text for a Python package

### q_runtime_ja: 実行時に動いている実装

top=`c_runtime_en` expected_near_hit=`True`

- r1 0.718644 `c_runtime_en` runtime implementation
- r2 0.526192 `c_research_code` research/ experiment harness
- r3 0.503209 `c_runtime_code` production runtime path
- r4 0.500866 `c_research_en` research experiment
- r5 0.478329 `c_unrelated_cpu` CPU温度の取得方法
- r6 0.431851 `c_board_en` game board state
- r7 0.414541 `c_unrelated_weather` 今日の天気と降水確率
- r8 0.282617 `c_unrelated_license` MIT license text for a Python package
