# Chat UI 開発プロセス可視化・接続構想

**日付:** 2026-08-30  
**状態:** 設計のみ。この文書の作成以外の実装はしていない。  
**Production 変更:** 0（`agent.py` / `pipeline.yaml` / Registry / Standard Workflow 未変更）  
**新規 Core:** 0（作らない）  
**Cursor API 接続:** なし（調査もしない・実装しない）  
**自動 pytest:** なし  
**判定:** `ARCHITECTURE_READY`

関連する先行調査: `docs/ai_tool/project_audit/TDA_CHAT_UI_DEV_VISIBILITY.md`（成果物の事後読み取り）。  
本書は「完成後の報告書表示」ではなく、**開発の途中経過を Chat UI で追えるか**を、現行コードの観測可能性から設計する。

---

## 判定

```text
ARCHITECTURE_READY

実装済み（現行）: 会話（Local Agent）と、作業後の Run / Report / Git / Test 未取得の読み取り
未実装（将来）:   開発途中のストリーミング、Development Job、会話風の開発イベント
取得不能:         Cursor のライブ実行状態（今何をしているか）
混同禁止:         Cursor報告 ≠ pytest実測 ≠ Local Agent の会話 Event
```

| ラベル | 採用しない理由 |
|--------|----------------|
| `PARTIAL_PASS` | ライブ Cursor 状態は「調査不足」ではなく **取得不能** と確定できた。現行構造で次の実装範囲を切れる |
| 実装の `PASS` | 今回は実装していない |

**設計上可能 ≠ 実装済み。** 以下で「いまあるもの」と「こうしたいもの」を分ける。

今回の調査で実装に進める状態になっても、**勝手に実装へ移行しない。** 実装範囲は確認後に指定する。

---

## 接続図（将来構想。現行は点線が切れている）

```text
ユーザー
 ↓
Chat UI（窓口）
 ↓
Local Agent（会話 / Session / Tool）     ← 現行の実線
 ↓
Development Request / Job                ← 未実装
 ↓
Cursor / 開発環境                        ← API なし。成果物だけが見える
 ↓
File / Git / Test / Run / Report         ← 現行は事後読み取り可能
 ↓
Development Events（REAL → SUMMARY → UI）← 未実装
 ↓
Chat UI（会話列とは別チャネルで表示）
```

現行の実線:

```text
Browser
 ↓  POST /api/chat
ChatHandler
 ↓  run_chat_turn   ※ agent.py は通らない
Ollama（tools.system.llm.chat）± Tool
 ↓
Session JSON + Chat Event
 ↓
「処理を見る」（会話処理）

別経路（読み取り専用・事後）:
Browser 「開発を見る」
 ↓  GET /api/dev/*
runs/ / docs/ / git status|diff
```

点線（無い）:

```text
Chat → Cursor へ自動依頼
Cursor 実行中ハートビート
pytest 機械 XML
Job ID の正式ライフサイクル
Development Event の会話列への挿入
```

---

## 1. 現在の Chat UI 構造

入口: `python ai_tool/run_chat_ui.py` → `http://127.0.0.1:8765/`  
実装: `ai_tool/chat_interface/server.py`（`ChatHandler`）、静的ファイル `static/index.html` / `app.js` / `app.css`。

### 会話 API（壊してはいけない）

| 方法 | 経路 | 役割 |
|------|------|------|
| GET | `/` `/app.css` `/app.js` | UI |
| GET | `/api/health` | Local Agent / Ollama / `cursor_connected: false` |
| GET | `/api/models` | 起動中 Ollama のモデル一覧 |
| GET | `/api/session/<id>` | 履歴復元 |
| POST | `/api/session` | 新規 Session |
| POST | `/api/session/model` | **今の Session のモデル切替のみ**（Ollama pull しない） |
| POST | `/api/chat` | `{ message, session_id? }` → `{ turn, session, ... }` |

`POST /api/chat` は会話専用。開発ジョブの開始口ではない。

### Session

保存: `runs/chat_ui/sessions/<session_id>.json`  
ID: `cs-YYYYMMDD_HHMMSS-<6hex>`

フィールド（`empty_session`）:

- 会話: `messages[]`（`role` / `content` / `timestamp` / `session_id` / `model`）
- ターン: `turns[]`（`pipeline` / `events` / `tools` 等。`status_lines` は保存しない）
- Event 蓄積: `events[]`
- 常に `executor: "local_agent"`, `cursor_connected: false`
- 枠だけある未使用: `last_test_result`（Chat 経路では更新されない）, `research_record_id`, `research_saved`
- `experimental_session`: `DevelopmentSessionState.as_session_dict()` の同梱。Chat は中身を回していない

`role` の実使用: `user` / `assistant` / `notice` / `error`。UI の `processing` は DOM 一時表示で、履歴 JSON には残さない。

### Event（会話処理）

`ai_tool/chat_interface/events.py` の `event(type, ...)` → `{ type, timestamp, ... }`。

実使用 `type`: `request`, `route`, `memory_select`, `tool_gate`, `llm_send`, `llm`, `llm_input`, `llm_output`, `tool_needed`, `tool_select`, `tool_call`, `tool_result`, `tool`, `web_search`, `url_fetch`, `tool_create`, `final_answer`, `research_record`, `error`, `model_change`。

表示の三層（会話側・既にある）:

| 層 | 関数 | 今の用途 |
|----|------|----------|
| 機械ログ | `events[]` | Session に保存。UI はほぼ `error` 以外出さない |
| 日本語行 | `status_lines` / `public_status_lines()` | 「処理を見る」 |
| 経路図 | `pipeline_steps()` | バブル横の短い User → Local Agent → LLM → Tool |

これは **Chat 処理 Event** である。Development Event と混ぜない。

### 履歴・Tool・モデル・処理表示

- 履歴: `localStorage.localAgentSessionId` → `GET /api/session/<id>` → `messages` を再描画。対応する `turns[]` で「処理を見る」を復元
- Tool: LLM の `tool_calls`。UI は `summary` のみ。実行は `_execute_agent_tool`
- モデル: ツールバーのワンクリック。`POST /api/session/model`
- 「処理を見る」: そのターンの Local Agent / LLM / Tool。**開発ジョブの途中経過ではない**
- 送信中: 「処理中…」バブル。Ollama 応答待ち。Cursor 待ちではない

### 「開発を見る」（現行・事後読み取り）

`index.html` の折りたたみパネル。タブ: Run / Report / Git / Test。  
API: `GET /api/dev/runs`, `/runs/<id>`, `/reports`, `/reports/<name>`, `/git`, `/tests`。  
実装: `ai_tool/chat_interface/dev_readonly.py`。Git 書き込み・pytest 実行・Cursor API はしない。

**できること:** 作業がファイルになった後の確認。  
**できないこと:** 「いまコードを書いている」「いまテスト 17/20」のライブ表示。

---

## 2. 現在の Local Agent 構造

Chat UI は **`agent.py` を import しない。** ターンは `ai_tool/chat_interface/agent_turn.py` の `run_chat_turn`。

共有しているもの:

- `tools.system.llm.chat` → `ollama.Client.chat()`
- Registry の `visibility=agent` Tool
- `pipeline.yaml` の `max_tool_rounds` とモデル解決（Chat は Session モデルで上書き可）

通らないもの:

- `agent.py` の Clarity / pre_web / capability 観測 / TTY Gate
- `standard_workflow.py`（既定 `facet_discovery="off"` のまま。Chat は呼ばない）
- ResearchRecord のディスク保存（Event は常に `saved: false`）
- 全 Memory の LLM 投入（`dump_all_passed_to_llm: false`。履歴は直近最大 8 件）

Tool 経路（現行・実測可能）:

```text
classify_request → chat | tool_creation
chat: ollama_chat(tools=...)
  → tool_calls なら _execute_agent_tool
  → role=tool で raw JSON を LLM へ戻す
  → 最終 content が回答
tool_creation: 仕様文のみ。Registry 書込なし
```

「GPUの状態を取得するToolを作ってみたい」を Chat に送ると、現行は **会話と仕様文** まで。Cursor がファイルを作る処理は **この経路に乗っていない。**

---

## 3. Cursor との境界

| 側 | 現行 | 将来も守る線 |
|----|------|----------------|
| Local Agent | 会話、要求理解、Session、Tool 選択・実行、説明 | 開発環境を直接編集しない |
| Cursor | この IDE 上の実装・pytest・Git・ファイル操作 | Chat UI から操作しない（今回も禁止） |
| Chat UI | 窓口。会話と（事後の）成果物表示 | Cursor 内部状態を推測して「実行中」と書かない |

**Cursor API は存在しない前提で設計する。** リポジトリに Cursor 接続実装は無い。`cursor_connected` は常に `false`。`.cursor/hooks.json` も無い。

観測できるのは **ディスクと Git に残ったもの** だけ。

使わない（内部ログであり API ではない）:

- `.cursor/projects/.../agent-transcripts`
- `.cursor/projects/.../terminals`

---

## 4. 現在取得可能な情報

| 情報 | 場所 | 取得手段 | 主体 |
|------|------|----------|------|
| 会話履歴 | `runs/chat_ui/sessions/*.json` | Chat API | Local Agent |
| Chat Event | 同上 `events[]` | 同上 | Local Agent |
| 使用モデル | Session / Ollama `/api/tags` 相当 | `/api/models` | Ollama |
| Tool 実行要約 | `turn.tools` | `/api/chat` 応答 | Local Agent |
| Run 判定・概要 | `runs/ai_tool/*/summary.json` | `GET /api/dev/runs` | 主に Cursor が書いた JSON |
| Run 詳細 | `observations.json` | `GET /api/dev/runs/<id>` | 混在（書き手は Cursor、中身に Local Agent 実測を含む場合あり） |
| 報告書 | `docs/ai_tool/project_audit/*.md` | `GET /api/dev/reports` | Cursor の説明 |
| 作業ツリー | Git | `GET /api/dev/git`（status / diff --stat / diff） | 保存済みファイル |
| 「機械的テスト未取得」 | junit/pytest XML が 0 件 | `GET /api/dev/tests` | 欠測そのものが事実 |
| Cursor の pytest 報告 | `observations.unit_tests.result` がある場合 | Run 詳細の `cursor_test_report` | **Cursor報告**。`counts_as_pytest: false` |

時刻の根拠（Run）: ディレクトリ名の `YYYYMMDD_HHMMSS` と `summary.json` の mtime。内部の start/end フィールドは通常無い。

---

## 5. 取得できない情報

| 情報 | 理由 |
|------|------|
| Cursor が今実行中か | プロセスもハートビートも無い。**取得不能** |
| Cursor の現在ツール / キー入力 / 未保存バッファ | IDE 内部。Git にも出ない |
| ライブの pytest ストリーム（running 15/20） | XML もソケットも無い |
| 開発開始・終了の正確な時刻 | Run は事後ディレクトリ。開始マーカー無し |
| ResearchRecord の永続内容 | メモリ内 `ResearchStore` のみ。ディスク 0 件 |
| Chat Session と Run の正式 FK | `summary.session_id` は任意の慣例 |
| `last_test_result` の実データ | フィールドはあるが Chat では常に空 |
| Production Workflow の進行 | Chat は Workflow を走らせない |
| Cursor が「20 kinds のテスト」を何件目まで終えたか | 報告文面以外に機械カウンタが無い |

禁止: 最終成果物の時刻や Git の dirty から「Cursor 実行中」と推測し続けること。

---

## 6. Run との関連付け

現行:

```text
Run ID = runs/ai_tool/<folder>/
任意で summary.session_id = cs-...
任意で observations.browser_session_id
```

正式な外部キーではない。同じ作業でも Run 無し・Session 無しがあり得る。

将来（新 Core なし）:

- Job が `run_id` を **後から** 付ける（Run ディレクトリが現れたら bind）
- 無い間は `run_id: null`, `run_link: "unbound"`
- 推測で「この Chat の直後の Run 全部」を自動結合しない（時刻近接は候補表示まで）

---

## 7. Session との関連付け

現行 Session は会話の入れ物。Development Job フィールドは無い。

将来、Session に足してよい薄い配列（Session Core 化しない）:

```text
development_jobs: [
  {
    "job_id": "dj-...",
    "requested_at": "...",
    "user_text": "...",
    "run_ids": [],
    "status_source": "unknown" | "artifacts" | "heartbeat"
  }
]
```

`messages[]` にはユーザー実発言と Local Agent 実回答だけを残す。  
開発途中の演出文は `messages` の `role: user|assistant` に書かない。

`DevelopmentSessionState` は Facet / Spec / 実験ハーネス用。Job オーケストレータにしない。

---

## 8. Git との関連付け

現行: リポジトリ全体の今の status/diff。Job 単位のベースラインは無い。

将来:

| 時点 | 取れるもの | 意味 |
|------|------------|------|
| Job 記録時 | `git status --porcelain` のスナップショット | 起点 |
| ポーリング時 | 同じコマンドの差分 | **保存済み**変更 |
| 未保存バッファ | 取れない | 表示しない |

禁止: commit / reset / checkout / push / pull を Chat UI から行うこと。  
表示例の「index.html が modified」は porcelain の事実。Cursor が今編集中とは書かない。

大量 untracked（現状数千）は一覧省略してよい。件数は REAL。

---

## 9. Test との関連付け

三欄を永久に分ける。

```text
Cursor報告:     observations.unit_tests.result があるときだけ
                例: 「15 passed」  source=cursor_report
機械的テスト:   pytest.xml / junit.xml があるときだけ
                無い: 「機械的テスト結果：未取得」 source=missing
Local Agent:    Chat の Tool 実行。pytest ではない
```

現行: 機械 XML は `runs/` 配下 0 件。パネルは「未取得」が正しい。

大量テストの `[17/20]` を出す条件:

- **REAL:** pytest の収集結果（junit の testcase、または明示的な JSON 成果物）がある
- **SUMMARY:** その件数を日本語にした行（source を残す）
- **禁止:** Cursor の一文「20 tests passed」を 20 行の進捗バーに展開すること

`session.last_test_result` を pytest 実測の代わりにしない（今は空。実験ハーネス専用の名残）。

---

## 10. Development Event 案

確定仕様ではない。既存 Chat Event と **名前空間を分ける。**

提案（最小）:

```text
共通:
  stream: "development"     ← chat event と衝突させない
  kind: "development"
  layer: "real" | "summary" | "ui"
  source: "git" | "run" | "pytest_xml" | "cursor_report" | "file" | "job"
  job_id: "dj-..." | null
  timestamp: ISO
  type: 下記
```

候補 `type`（仮）:

| type | REAL の条件 | 無いときの扱い |
|------|-------------|----------------|
| `DEVELOPMENT_REQUEST` | ユーザーが開発依頼と分かった発言、または明示ジョブ作成 | 推測分類は SUMMARY。自動で Cursor を起動しない |
| `INVESTIGATION` | 読んだファイルパスが残っている | 残っていなければ出さない |
| `FILE_READ` / `IMPLEMENTATION` | Git または Run にパスがある | Cursor の「読んだつもり」は記録しない |
| `TEST_START` | pytest プロセスまたは XML の生成開始が観測できる | **現行は観測不能 → 出さない** |
| `TEST_RESULT` | XML または Cursor報告を **source 付きで** | 混同しない |
| `GIT_CHANGE` | porcelain / diff --stat | 可 |
| `ERROR` / `FIX` / `RETEST` | 対応する成果物 | 物語で補完しない |
| `COMPLETED` | Run `judgment` または Job を人手で閉じた | Git dirty 消失だけでは完了にしない |

既存 Chat `type`（`request`, `llm`, `tool_*` …）は変更しない。  
`user` / `cursor` / `test` を Chat Event の `type` に流用しない。

pipeline の `id`（`user_input`, `local_agent`, `llm` …）も触らない。開発用は別リストにする。

---

## 11. REAL / SUMMARY / UI の区別

必須。保存と表示を分ける。

### REAL

実際に観測したデータ。補完しない。

```text
pytest.xml がある → tests=15 failures=0
git diff --stat → 3 files
runtime.py が modified
summary.judgment = PASS
```

### SUMMARY

REAL から作った人間向け一文。`source` と `layer: "summary"` を持つ。  
REAL が無ければ SUMMARY も無い。

```text
（source=git）変更ファイルが 3 件あります
（source=cursor_report）Cursor報告：15 passed
```

### UI / NARRATIVE

臨場感用。永続履歴の「誰が言ったか」に混ぜない。

```text
🔎 開発環境を確認中...
```

ルール:

1. UI 文を `messages[].role = assistant` として保存しない
2. UI 文を REAL の証拠にしない
3. Cursor 操作が観測されていなくても UI で「コードを作成しています」と出さない
4. 絵文字は任意。意味は `type` + `layer` で持つ

会話風表示の内部判別:

| 画面上のラベル | 内部 | `messages` に入るか |
|----------------|------|---------------------|
| あなた / ユーザー | `role: user` | 入る（実発言） |
| Local Agent | `role: assistant` | 入る（実回答） |
| Cursor / 開発処理 | `stream: development` の描画 | **入らない**（または `display_only` レコード） |

「システムが開発過程を会話風に見せている」ことと「ユーザーが発言した」ことを同じ配列の同じ `role` で表さない。

---

## 12. 開発中表示案

将来 UI 例:

```text
開発中...
現在: （最終観測）git に変更あり
経過: 最終確認から 02:31
最新 REAL: git diff --stat に runtime.py
```

現行で許す表示:

- 「最終確認時刻」（ポーリングした時計）
- 「最後に読めた成果物」
- status_source が `unknown` なら **「実行中かは不明」**

禁止:

- ハートビート無しで経過時間だけ増やし「処理中」と出し続ける
- 「Cursor 実行中」の推測
- Chat の「処理中…」（Ollama 待ち）を開発待ちと兼用する

ハートビート（任意・将来）: `runs/dev_status/current.json` のような **明示ファイル** があるときだけ `status_source: "heartbeat"`。ファイルが古い・無いときは unknown。Cursor が書いてくれなければ永遠に unknown で正しい。

ストリーミング（SSE/WebSocket）は現行 Chat に無い。最初はポーリングで足りる。

---

## 13. 大量テスト表示案

望ましい画面（**pytest 実測がある場合だけ**）:

```text
開発テスト（source=pytest_xml）
[1/20] test_basic     PASS
...
[17/20] test_gpu_none FAIL
[20/20] ...
総合 19/20
```

Cursor に「20種類テストして」と依頼し、返ってきたのが一文だけの場合:

```text
Cursor報告：20 tests passed
機械的テスト結果：未取得
```

進捗バーに展開しない。FAIL 後の「原因を調査中…」「修正中…」は、対応する REAL（新しい diff、新しい XML、新しい Run）が来るまで出さない。

---

## 14. Cursor報告と実測結果の区別

既に Run 詳細 API で分離している（実装済み・読み取り）:

```text
cursor_test_report.text = "15 passed"
cursor_test_report.counts_as_pytest = false
mechanical_tests.source = missing
mechanical_tests.user_message = 機械的テスト結果：未取得
```

将来もこの契約を崩さない。報告書本文の「27 passed」を Test 欄の pytest にコピーしない。

---

## 15. 最小実装案（承認後。今回はやらない）

既存の「開発を見る」（事後）を壊さず、会話列への **読み取り専用ポーリング** を足す程度。新 Core・Cursor API・`agent.py` 変更なし。

提案スライス（小さい順）:

1. **Job レコード（任意）**  
   Chat が「作って」と分類したとき `job_id` を Session に付けるだけ。Cursor は起動しない。
2. **成果物ポーリング**  
   開いている Job に対し `GET /api/dev/git` と runs 一覧を間欠取得。変化があれば `GIT_CHANGE` / 新 Run を `stream=development` で UI に足す。
3. **TEST_RESULT の二欄表示を会話列でも使う**  
   パネルと同じ分離をバブルに出す。
4. **会話風ラベル**  
   描画だけ。`messages` は変更しない。
5. **pytest.xml を Run に残す運用**（人間または Cursor の手順。Chat から pytest を自動実行しない）

まだやってはいけない:

- Cursor への自動入力
- 「開発処理: コードを作成しています」のフィクション
- `POST /api/chat` の意味変更
- Production 接続、RAG、スマホアプリ

---

## 16. 将来的な拡張案

承認後の段階:

```text
Chat
 ↓
Development Request（分類または明示ボタン）
 ↓
Job（dj-...）↔ Session
 ↓
（人間が Cursor に依頼。API ではない）
 ↓
成果物: File / Git / pytest.xml / Run / Report
 ↓
Development Events（REAL 必須）
 ↓
Chat UI（会話チャネルと開発チャネル）
```

その先（別承認）:

- Cursor API が公式に使えるならハートビート
- junit を機械欄に接続
- Job 完了を Run `judgment` と人手確認の両方で閉じる
- 大量テストの testcase 一覧

やらない（本書の範囲外）:

- Local Agent を Cursor の代わりにする
- 新しい Reasoning / Graph / RAG / Vector DB / Knowledge Base
- 全 Memory を LLM へ渡す

---

## 17. 実装時のリスク

| リスク | 結果 | 避け方 |
|--------|------|--------|
| 演出を実履歴に書く | 「Agent が開発した」ように見える | `stream` と `role` を分ける |
| Cursor報告を pytest にする | 機械検証したと誤認 | 二欄固定 |
| 実行中の推測 | 止まっているのに「開発中」 | unknown を正式状態にする |
| Chat Event に開発 type を混ぜる | 「処理を見る」が崩壊 | `kind` / `stream` |
| Job を新 Core にする | 既存 Session と二重管理 | Session の薄い配列 |
| Git 書き込み | 本番履歴破壊 | 読み取りホワイトリスト維持 |
| 自動 pytest | 環境破壊・時間・誤帰属 | Chat から実行しない |
| `agent.py` / Workflow 接続 | Production 汚染 | Chat 経路を維持 |
| 近接時刻で Run を自動 bind | 別作業の Run を混ぜる | unbound + 候補表示 |

---

## 18. 今回実装しない理由

1. 指示が調査・設計のみである  
2. 最終目標の「途中経過」は **Cursor ライブが取得不能** なため、先に境界を文章化する必要がある  
3. フィクションの開発ログを実データとして保存すると、以降の実測が壊れる  
4. 事後確認（Run / Git / Report / Test 未取得）は既に別スライスである。途中経過は別承認が要る  
5. `POST /api/chat`・`agent.py`・Registry・Workflow を巻き込まないとできない、という話ではない。巻き込んではいけない  

実装へ進む条件（ユーザー指定後）:

- スライス番号が明示されている
- REAL が無い UI 文を出さないことがテスト項目にある
- Cursor API を「無いまま推測で埋めない」ことがテスト項目にある

---

## 役割分担（成立するか）

**成立する。** ただし「Chat が Cursor を駆動する」は現行では成立しない。成立するのは次の分担である。

| 役割 | 現行 | 将来（API 無し） |
|------|------|------------------|
| Local Agent | 会話・Tool・説明 | 依頼の受付、Job メタ、結果の説明 |
| Cursor | IDE 上の実装（Chat から不可視のライブ） | 同じ。成果物をリポジトリに残す |
| Chat UI | 会話 + 事後パネル | + 成果物ポーリングの開発チャネル |

「Local Agent が既存 GPU Tool を確認します」は、**Agent が Tool を呼んだ REAL** があるときだけ会話 Event として正しい。  
Cursor が `gpu_status.py` を開いたことは、Git にも Run にも残らなければ **表示しない。**

---

## Job 調査の答え（実装しない）

| 問い | 答え |
|------|------|
| Job ID を持たせられるか | できる。Session JSON の配列で足りる。新 Core 不要 |
| Session と関連付けられるか | `job.session_id` で可。現行は未フィールド |
| Run と関連付けられるか | 事後に `run_ids[]`。正式 FK はまだ無い |
| Git と関連付けられるか | Job 開始時スナップショット対比は設計可能。ライブ編集は不可 |
| pytest と関連付けられるか | XML が Run に載れば可。今は missing |
| 開始・終了を検出できるか | **正確には不能。** 成果物の出現と人手完了だけ |
| 途中状態を取得できるか | ハートビート無しでは **unknown** |
| Cursor が作ったファイルを検出できるか | 保存後の Git なら可。作者が Cursor である証明は無い |
| Cursor が実行したテストを検出できるか | 報告文か、XML。XML が無ければ報告のみ |

---

## 実験ハーネスとの関係

`ai_tool/experimental/development_assistance/` の Phase ハーネスは **fixture / 一時ディレクトリ** で Spec・テストループを回し、結果を `runs/ai_tool/` に書く。Chat UI からは呼ばれない。Cursor API も使わない（`cursor_equiv_fixture` は名前だけ）。

これを Chat の裏で自動起動するのは別案件。本書の最小案はハーネスを Production に接続しない。

---

## 変更ファイル（この作業）

- 追加: `docs/ai_tool/project_audit/TDA_CHAT_UI_DEVELOPMENT_VISIBILITY_ARCHITECTURE.md`
- コード変更: なし
- Production 変更数: 0
- 新規 C3: 0
- Cursor API 接続: なし
- 自動 pytest 実行: なし

---

## ブラウザから「いま」実際に確認できること

会話の処理（User / Local Agent / LLM / Tool）と、作業後の Run / 報告書 / Git / 「機械的テスト未取得」まで。  
**開発の途中経過（Cursor が今テスト 17/20）は確認できない。** それは欠測であり、次の実装で捏造しない。
