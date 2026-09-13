# get_system_summary 追加

**日付:** 2026-08-31  
**依頼:** 既存 observation Tool を合成する `get_system_summary` を作る  
**実行主体:** Cursor（Local Agent / Local LLM はこの実装をしていない）  
**Run:** `runs/ai_tool/20260831_000202_get_system_summary`  
**Production 変更:** 0  
**AGENT_VISIBLE_DEFAULT:** 未変更（Local Agent には今回公開しない）  
**判定:** `PASS`

---

## 実装内容

`tools/system/summary/get_system_summary.py` は次だけを呼ぶ。

- `get_system_time()`
- `get_cpu_status()`
- `get_memory_status()`
- `get_gpu_status()`

含めない: `cpu_status`, `get_gpu_processes`

トップレベル:

```text
status: ok | partial | error
observation_source: composed  （real ではない）
source: existing_observation_tools
sections: 子Toolの戻り値をそのまま
derived.ok_by_section: 派生（実測ではない）
```

欠測の補完はしない。一部失敗は `partial`、全部失敗は `error`。

---

## 直接実行（Cursor の Python）

```text
status: ok
time: 2026-08-31T00:02:02+09:00
cpu: 12th Gen Intel(R) Core(TM) i5-12400
memory: 65277 MB / 45%
gpu: NVIDIA GeForce RTX 3060 / 60.0 C
observation_source: composed
各 section の observation_source: real（子Tool側）
```

---

## Test

Cursor Report: **40 passed**（XML なし）

Machine Test: **NOT AVAILABLE**

A DirectCall / B 戻り値 / C 既存関数利用（ソースに CIM/nvidia-smi なし）/ D 部分失敗 mock で partial

---

## 未変更

`agent.py` / `pipeline.yaml` / 既存 Tool 本体 / `AGENT_VISIBLE_DEFAULT` / Chat UI / Cursor API
