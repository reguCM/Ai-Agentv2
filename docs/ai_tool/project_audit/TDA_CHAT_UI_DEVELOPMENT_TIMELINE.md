# Chat UI Development Timeline

**日付:** 2026-08-30  
**起動:** `python ai_tool/run_chat_ui.py` → http://127.0.0.1:8765/  
**実測 Session:** `cs-20260830_131550-b93b6f`  
**実測 Job:** `dj-20260830_131710-4a3a5b`  
**Production 変更:** 0  
**新規 C3:** 0  
**Cursor API 接続:** なし  
**自動 pytest:** なし  
**判定:** `PASS`（第一目標：成果物と報告の時系列。Cursor の直接監視ではない）

---

## 判定

```text
PASS

見えるようになった: 会話 / 処理 / 開発 の画面分離と Development Timeline
取得できた Cursor: ライブ状態は NOT OBSERVED。取得できたのは Run に書かれた Cursor報告のみ
取得できた Git: status / diff / log / branch / HEAD（読み取り）
取得できた Test: 機械結果は NOT AVAILABLE。Cursor報告の一覧は Source: Cursor Report
まだ取得できない: Cursor 実行中、編集中ファイル、17/20 のライブ進捗
第一目標: Cursor が残した成果物・報告を時系列で見られるようになった
```

Cursor を直接監視できるようになった、のではない。

---

## 実装前に確認したこと（取得できる / できない）

| # | 対象 | 実際に取得できるか |
|---|------|--------------------|
| 1 | Chat Session | できる。`runs/chat_ui/sessions/*.json` |
| 2 | Development Event | 今回追加。Chat Event（`request`/`llm`/`tool_*`）とは別 `stream=development` |
| 3 | Run | できる。`runs/ai_tool/*/summary.json` |
| 4 | Report | できる。`docs/ai_tool/project_audit/*.md` |
| 5 | Git | できる。status / diff / log / branch / HEAD。書き込みなし |
| 6 | 機械 Test | **できない**（junit/pytest.xml は 0 件 → NOT AVAILABLE） |
| 7 | Cursor Report | Run の `observations.unit_tests` と `tests` 辞書があるときだけ |
| 8 | 既存 API | Chat API は維持。`GET /api/dev/*` を拡張 |
| 9 | UI Event | 「処理を見る」は会話処理。開発とは別タブ |
| 10 | Cursor ライブ | **取得不能** → `Cursor live status: NOT OBSERVED` |

禁止した推測: 「Cursor is running」「17/20」「今このファイルを編集中」。

---

## 何が Chat UI から見えるようになったか

画面上部に **会話 / 処理 / 開発** を分けた。

- **会話:** 従来の Local Agent Chat。モデル選択は維持
- **処理:** 直近ターンの LLM / Tool / Search / Session。Cursor ライブではないと明記
- **開発:** Development Timeline。Job フィルタ、Run / Report / Git / Test の個別閲覧

Timeline の例（実測）:

```text
[REAL][GIT_COMMIT]  Commit cdbf4559 ...
[CURSOR_REPORT][TEST_LIST]  A_Chat PASS  Source: Cursor Report
[REAL][TEST]  機械的テスト  NOT AVAILABLE
[REAL][RUN]  20260830_211406_r3_5c_local_agent_ui  PASS
[CURSOR_REPORT]  15 passed
[SUMMARY][LOCAL_AGENT]  開発依頼として受付
[REAL][REQUEST]  GPU温度取得Toolを作って
Cursor live status: NOT OBSERVED
```

---

## 追加 API（読み取り。POST /api/chat は未変更）

```text
GET /api/dev/events?session_id=&job_id=
GET /api/dev/jobs?session_id=
GET /api/dev/jobs/<id>?session_id=
GET /api/dev/runs
GET /api/dev/runs/<id>
GET /api/dev/reports
GET /api/dev/reports/<name>
GET /api/dev/git
GET /api/dev/tests
```

Job は Session JSON の `development_jobs[]`。新しい Core ではない。

---

## 実測（Test A–H）

| Test | 内容 | 結果 |
|------|------|------|
| A | `こんにちは` | `intent=CHAT`、Job なし、qwen3:8b で回答「こんにちは！」 |
| B | `GPU温度取得Toolを作って` | `intent=TOOL_CREATION`、Job `dj-20260830_131710-4a3a5b`、notice「開発依頼として記録」 |
| C | Cursor Report | Timeline に `15 passed` とテスト一覧。layer=`cursor_report` |
| D | Git | branch `master`、HEAD `f881ae87`、modified 36、diff、最近の commit |
| E | Test 分離 | Cursor Report あり / Machine Test: NOT AVAILABLE |
| F | 大量テスト一覧 | `A_Chat PASS` 等。すべて `Source: Cursor Report` |
| G | 時系列 | Request → Local Agent → Run → Cursor Report → Git → Test |
| H | ライブ状態 | `Cursor live status: NOT OBSERVED`。実行中表示なし |

補足: 新規 Session の既定モデル `deepseek-coder-v2:16b` は tools 非対応で 400 になった。モデル切替 UI で `qwen3:8b` に変えて Chat は通った。この失敗は Timeline 実装以前からの Ollama 制約であり、開発中とは表示していない。

回帰: `tests/ai_tool/chat_interface/` 29 passed（Cursor 実行の pytest。機械 XML は保存していない）。

---

## Cursor Report と機械結果

```text
Cursor Report: 15 passed / A_Chat PASS ...
Machine Test: NOT AVAILABLE
```

報告書や observations の passed を pytest 実測欄に写していない。

---

## Development Timeline の使い方

1. Chat UI を開く
2. **開発** を押す
3. 上部の `NOT OBSERVED` を読む（ライブ監視ではない）
4. Job があればフィルタできる
5. 時系列で REQUEST / CURSOR_REPORT / RUN / GIT / TEST を見る
6. 必要なら「成果物を個別に見る」で Run / Report / Git / Test

通常の「GPUの温度を教えて」は会話のまま。Tool 作成依頼だけ Job になる。

---

## Production への影響

- `agent.py` / `pipeline.yaml` / Registry / Standard Workflow: 未変更
- `facet_discovery` 既定: 未変更
- 新規 C3 / RAG / Vector DB / Knowledge Base: なし
- Git 書き込み / 自動 pytest / Cursor API: なし

---

## 変更ファイル

- `ai_tool/chat_interface/classify.py`
- `ai_tool/chat_interface/development_job.py`（追加）
- `ai_tool/chat_interface/dev_timeline.py`（追加）
- `ai_tool/chat_interface/dev_readonly.py`（git log / branch / HEAD）
- `ai_tool/chat_interface/chat_session.py`
- `ai_tool/chat_interface/agent_turn.py`
- `ai_tool/chat_interface/server.py`
- `ai_tool/chat_interface/static/index.html`
- `ai_tool/chat_interface/static/app.js`
- `ai_tool/chat_interface/static/app.css`
- `tests/ai_tool/chat_interface/test_dev_timeline.py`（追加）
- `tests/ai_tool/chat_interface/test_dev_readonly.py`
- 本報告書

---

## まだ取得できないもの

- Cursor が今動いているか
- Cursor が今編集しているファイル
- pytest のライブ 17/20
- junit.xml による機械 passed 件数
- ResearchRecord のディスク実体（フィールドだけ予約）
