# get_memory_status 追加

**日付:** 2026-08-30  
**依頼:** get_system_time より少し複雑な小規模 observation Tool を追加し、開発案件履歴で追跡できるか確認する  
**実行主体:** Cursor（Local Agent / Local LLM はこの実装をしていない）  
**選定した Tool:** `get_memory_status`（CPU と同じ CIM 実測。時刻よりフィールドが多い）  
**Run:** `runs/ai_tool/20260830_233232_get_memory_status`  
**Production 変更:** 0（`agent.py` / `pipeline.yaml` / 既存 Tool 本体 / Workflow / `AGENT_VISIBLE_DEFAULT` 未変更）  
**判定:** `PASS`

---

## 開発依頼の内容

既存コードを少し調査し、小規模実装・複数ファイル・新規テスト・既存回帰が発生する Tool を追加する。Production の大幅変更はしない。

Cursor が具体名として `get_memory_status` を選んだ。ユーザーがこの名前を指定したわけではない。

---

## 調査した既存ファイル（コードを読んで判断）

| ファイル | 分かったこと |
|----------|----------------|
| `tools/system/cpu/get_cpu_status.py` | Win32 CIM、失敗時は unknown、`observation_source=real` |
| `tools/system/time/get_system_time.py` | 最小 observation Tool。Registry `visibility=agent` |
| `tools/system/gpu/gpu_status.py` | 実測、固定値フォールバックなし |
| `registry/tools.json` | エントリ追加のみ |
| `ai_tool/chat_interface/agent_turn.py` | `AGENT_VISIBLE_DEFAULT` は **未変更**（Chat からこの Tool を使う実装ではない） |

---

## 作成・変更したファイル

作成:

- `tools/system/memory/get_memory_status.py`
- `tests/test_get_memory_status.py`

変更:

- `registry/tools.json`（`get_memory_status` エントリのみ追加）

触っていない:

- `agent.py`
- `pipeline.yaml`
- 既存 CPU / GPU / time Tool 実装
- `AGENT_VISIBLE_DEFAULT`

---

## 実装内容

`Win32_OperatingSystem` の `TotalVisibleMemorySize` / `FreePhysicalMemory`（KB）を CIM で読み、MB と使用率にする。

```text
total_mb / used_mb / free_mb / used_percent
ok / status / error / observation_source=real
source=win32_operating_system_cim
```

非 Windows は `unavailable`。失敗時は unknown。架空容量は返さない。

---

## 実行した Test と実測結果

直接実行（Cursor の Python。Local Agent ではない）:

```text
total_mb: 65277
used_mb: 29302
free_mb: 35974
used_percent: 45
ok: true
```

pytest（Cursor 実行。XML なし）: **69 passed**

対象: `test_get_memory_status.py` + 既存 CPU/GPU/time + Chat UI 回帰。

Machine Test（pytest.xml）: **NOT AVAILABLE**

---

## Chat UI 追跡

この Run は Chat UI の開発タブで `run-20260830_233232_get_memory_status` として見える想定。  
Chat UI から Cursor を操作したわけではない。依頼文は Cursor チャット（本指示）側。
