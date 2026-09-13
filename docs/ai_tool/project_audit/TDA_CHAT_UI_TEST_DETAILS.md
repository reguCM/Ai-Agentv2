# Chat UI Test / PASS 詳細表示

**日付:** 2026-08-30  
**依頼:** 案件詳細の Test / PASS をクリックして詳細を見る  
**実行主体:** Cursor（Local Agent はこの実装をしていない）  
**Run:** `runs/ai_tool/20260830_233000_chat_ui_test_details`  
**Production 変更:** 0  
**判定:** `PASS`

---

## 何ができるようになったか

案件詳細の `28 passed` / 個別テスト名 / `[Test詳細]` から Test Details を開ける。

```text
Test Details
[CURSOR REPORT] 28 passed
Source: Cursor Report  Actor: CURSOR

A_DirectCall  PASS
B_ReturnShape  PASS
C_ExistingToolRegression  PASS

A_DirectCall を開くと observations にある executor 等だけ表示
詳細が無い項目は「詳細: 未取得」
Machine Test: NOT AVAILABLE  Actor: MECHANICAL
```

Cursor Report に無い説明（例: CPU/GPU の温度を確認した）は生成しない。

---

## 実測

- get_system_time 案件から `[詳細を見る]` → A/B/C 一覧
- A_DirectCall → `executor: cursor_python` / `local_agent_executed: false`
- Machine Test は NOT AVAILABLE のまま
- Cursor live status: NOT OBSERVED
- chat_interface 回帰: 33 passed（この Run 時点）

---

## 未変更

`agent.py` / `pipeline.yaml` / Production Workflow / Cursor API / ライブ監視
