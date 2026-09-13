# Chat UI Local Agent 利用可視化

**日付:** 2026-08-30  
**実行主体:** Cursor（Local Agent はこの実装をしていない）  
**Server:** `LocalAgentChat/0.7`  
**Production 変更:** 0  
**Cursor API:** なし  
**判定:** `PARTIAL_PASS`

観測できる Local Agent / LLM / Tool は Session Event として残し、開発タブに出した。  
Cursor が Local Agent を呼ぶ経路は **NOT CONNECTED** のまま。無理に作っていない。

---

## 調査結果（実装前）

| # | 対象 | 結果 |
|---|------|------|
| 1 | Local Agent Tool 呼び出し | `agent_turn._chat_turn` の `tool_call` / `tool_result`。Session `turns[].tools` |
| 2 | LLM 呼び出し | 同関数の `llm` / `llm_send`。モデル名は Session の `model` |
| 3 | Search | `search_web` 実行時のみ `web_search` Event。存在だけでは記録しない |
| 4 | Tool 結果 | `summarize_tool_result`（巨大本文は切る） |
| 5 | Research / Matrix 書き込み | Agent Chat では保存しない。`research_saved=False` |
| 6 | Cursor → Local Agent | **経路なし。** Chat UI はブラウザユーザー → Local Agent のみ |
| 7 | 将来の接続点 | Chat API `POST /api/chat` を Cursor から呼ぶ場合のみ。今回は作らない |
| 8 | Event 保存 | 既存 `runs/chat_ui/sessions/*.json` の `events` / `turns` |
| 9 | 表示 | 開発タブの「Local Agent 処理（この Session）」。案件詳細は NOT CONNECTED |
| 10 | Correlation | ターン単位の `ac-...`。Git dirty や Tool 存在からは結ばない |

---

## 実測可能な経路

```text
Cursor ライブ          NOT OBSERVED
Cursor → Local Agent  NOT CONNECTED
ユーザー → Local Agent → LLM → Tool   観測できる（Chat UI Session）
Search                実際に search_web を実行したときだけ
Research / Matrix     NOT OBSERVED
Cursor 実装 / Run     既存の案件（成果物）
Test                  Cursor Report と Machine Test は従来どおり分離
```

---

## 変更ファイル

- 追加: `ai_tool/chat_interface/activity.py`
- 変更: `agent_turn.py`（correlation stamp。Production agent.py ではない）
- 変更: `server.py`（`GET /api/dev/activity`、cases に activity）
- 変更: `dev_cases.py` / `dev_timeline.py` / `static/app.js`
- 追加: `tests/ai_tool/chat_interface/test_activity.py`

未変更: `agent.py`, `pipeline.yaml`, `AGENT_VISIBLE_DEFAULT`, 既存 Tool 本体, Cursor API
