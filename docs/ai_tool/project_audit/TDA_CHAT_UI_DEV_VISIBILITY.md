# Chat UI 開発状況・Cursor実行結果可視化（実装前調査）

**日付:** 2026-08-30  
**状態:** 設計完了（コード読取のみ。実装なし。Local Agent 未起動。Cursor 自動操作なし）  
**Production 変更:** 0  
**新規 Core:** 不要  
**判定:** `PARTIAL_PASS`

目的は「Cursor の代わりを Local Agent にさせる」ことではない。  
目的は「Cursor が実際に行った開発作業を、ブラウザから透明に確認できる」こと。

---

## 判定

```text
PARTIAL_PASS

できる:     作業後の成果物（Run JSON / 報告書 / Git 差分）を読む
できない:   Cursor が「今」何をしているかのライブ状態
混同注意:   報告書の「pytest 15 passed」は Cursor の報告。pytest の機械結果ファイルは無い
新しいCore: 不要
Cursor API: 今回の最小構成では不要（推測して作らない）
```

| ラベル | 採用しない理由 |
|--------|----------------|
| PASS | ライブ実行中状態と、pytest の機械結果ファイルが既存構造に無い |
| BLOCKED | 作業後の確認経路は既にある（runs / docs / git） |
| REJECT | 新 Core は不要。薄い Experimental API で足りる |

今回は実装しない。以下は「次に実装してよい範囲」と「まだやってはいけない範囲」を分けるための設計である。

---

## いま見えている事実

ユーザーから見えるもの:

```text
Cursor → 実装 → テスト → 報告書
```

リポジトリ上に既にあるもの（Chat UI はまだ読んでいない）:

```text
runs/ai_tool/<run_id>/summary.json
runs/ai_tool/<run_id>/observations.json
docs/ai_tool/project_audit/*.md
git status / git diff
runs/chat_ui/sessions/<session_id>.json
```

無いもの:

```text
Cursor 内部 API
pytest の junit.xml（0 件）
Chat Session と Run の正式な結び付き
last_test_result の自動更新（フィールドはあるが空）
「Cursor 実行中」のハートビート
```

---

## 1. 現在 Cursor の実行結果を取得できる場所

Cursor は IDE の内部状態を Chat UI へ渡していない。取得できるのは **Cursor がリポジトリに書いたファイル** だけである。

| 場所 | 内容 | 主体 |
|------|------|------|
| `docs/ai_tool/project_audit/*.md` | 日本語報告書。誰が実行したかを文章で書く | Cursor の報告 |
| `runs/ai_tool/<run_id>/observations.json` | 実測の詳細。`executor` / `local_agent_executed` を分離している例あり | 混在（書き手は Cursor、中身に Local Agent 実測を含む） |
| `runs/ai_tool/<run_id>/summary.json` | 短い判定。`tests` と `judgment` | 同上 |
| Chat 本文 | この会話の説明 | Cursor の報告 |
| `.cursor/projects/.../agent-transcripts` | 会話ログ | Cursor 内部。**API ではない。使わない** |
| `.cursor/projects/.../terminals` | ターミナル出力 | Cursor 内部。**使わない** |

R3.5-C の例: `observations.json` の `unit_tests.result = "15 passed"` は **Cursor が pytest を実行したと書いた記録** であり、pytest が残した XML ではない。

報告書だけを PASS としない。Cursor 報告と実測ファイルを別欄にする。

---

## 2. Run 情報を取得できる場所

```text
runs/ai_tool/<YYYYMMDD_HHMMSS>_<slug>/
  summary.json
  observations.json
  （任意）browser_session.json など
```

例: `runs/ai_tool/20260830_211406_r3_5c_local_agent_ui`

- `summary.json` に `run_id` / `judgment` / `tests` / `session_id` がある場合がある
- ディレクトリ名が Run ID
- 一覧はディレクトリ走査で足りる。新 Core は不要

Chat UI の Session（`cs-...`）と Run は別物。R3.5-C は `summary.json` に `session_id` を書いたが、これは慣例であり API ではない。

---

## 3. pytest 等のテスト結果を取得できる方法

既存経路:

```text
python -m pytest tests/ai_tool/chat_interface/... -q
```

設定ファイル: `docs/ai_tool/tool_creation/pytest.ini`（`testpaths = tests`）。リポジトリ直下に junit 出力は無い。

| 方法 | 今あるか | 備考 |
|------|----------|------|
| pytest を今実行する | できる | Chat から勝手に回すのは別承認 |
| `junit.xml` を読む | **無い**（0 件） | 機械結果の保存先が未整備 |
| `observations.unit_tests` | ある場合がある | Cursor 報告。pytest 本体ではない |
| `DevelopmentSessionState.last_test` | フィールドあり | Chat 経路では更新していない |
| Chat `last_test_result` | 常に `None` のまま | 使っていない |

最小で機械結果を残すなら（実装は後）:

```text
python -m pytest ... --junitxml=runs/ai_tool/<run_id>/pytest.xml
```

これも新 Core ではない。Run ディレクトリへファイルを足すだけ。

---

## 4. 変更ファイルを取得できる方法

安全なのは **Git の読み取り** である。

```text
git status --porcelain
git diff --name-status
git diff --stat
```

- 保存済みの作業ツリーだけが見える
- Cursor の未保存バッファは見えない
- commit / push はしない（読み取り専用）
- Production ファイルを変更する必要はない

`git` はリポジトリとして利用可能。新しい差分エンジンは作らない。

---

## 5. 報告書を取得できる方法

```text
docs/ai_tool/project_audit/*.md
```

読み取り専用で一覧・本文表示できる。  
報告書は **説明**。Run / pytest / Git は **証拠**。同じ画面に出してよいが、同じ判定には使わない。

---

## 6. Chat UI へ表示するための最小 API 構成

既存 Chat API（壊さない）:

```text
GET  /api/health
GET  /api/models
GET  /api/session/<id>
POST /api/session
POST /api/session/model
POST /api/chat
```

追加してよい範囲（Experimental、承認後）:

```text
GET /api/dev/status     開発状態（ファイルがあれば。無ければ unknown）
GET /api/dev/runs       runs/ai_tool の一覧
GET /api/dev/runs/<id>  summary + ファイル一覧
GET /api/dev/reports    project_audit の一覧
GET /api/dev/reports/<name>  markdown 本文（読み取り）
GET /api/dev/git        status / 変更ファイル名（読み取り）
GET /api/dev/tests      pytest 機械結果があれば返す。無ければ source=missing
```

UI はタブや「処理を見る」の拡張で読むだけ。`POST /api/chat` は今どおり会話専用。

スマホを阻害しないため、状態はブラウザメモリに置かず API が返す。

---

## 7. Session との関連付け方法

| ID | 場所 | 今の結び付き |
|----|------|----------------|
| Chat `session_id`（`cs-...`） | `runs/chat_ui/sessions/` | 会話・Event・モデル |
| Run ID | `runs/ai_tool/<run_id>/` | 実測 JSON |
| 報告書パス | `docs/ai_tool/project_audit/` | 手書きリンク |

今は正式な外部キーが無い。`summary.json` の `session_id` は任意。

最小の結び方（新 Core ではない）:

```text
Chat Session
  optional run_ids: ["20260830_211406_r3_5c_local_agent_ui"]

Run summary.json
  optional session_id: "cs-..."
  optional report_path: "docs/ai_tool/project_audit/TDA_R3_5C_LOCAL_AGENT_UI.md"
```

`DevelopmentSessionState` は TDA の Facet / 確認待ち用。Cursor 実行ログの入れ物としては使わない（流用すると意味が混ざる）。

---

## 8. Event として表示できる情報

既存 Chat Event（`type` + `timestamp`）:

`request` / `llm_send` / `tool_select` / `tool_result` / `web_search` / `error` / `model_change` / `final_answer`

足りないもの: **実行主体（actor）** と **Cursor / Test / Git の Event**。

将来の列（未実行を実行済みと書かない）:

```text
actor=user          入力
actor=local_agent   受信・経路選択
actor=llm           Ollama
actor=tool          get_gpu_status など（選択されたときだけ）
actor=cursor        報告。ファイル変更の主張
actor=test          pytest 機械結果（xml があるときだけ）
actor=system        git status の読取
```

Cursor 報告の「27 PASS」は `actor=cursor`。  
pytest の「27 passed」は `actor=test`。  
両方あるときだけ比較する。片方しか無いときは「未取得」と書く。

---

## 9. Cursor を直接操作する必要があるか

**最小の可視化には不要。**

必要なのは、Cursor が既に書いたリポジトリ成果物を読むこと。  
Cursor 内部 API を推測して実装しない（既存方針どおり）。

ライブの「実行中」だけは、操作なしでは分からない。

---

## 10. Cursor を直接操作せずに実装できる範囲

できる（承認後）:

- Run 一覧・詳細
- 報告書の閲覧
- Git の変更ファイル名
- Chat Event の actor 追加
- 「処理を見る」の横に開発タブ
- Cursor 報告と pytest 機械結果の二欄表示（機械結果が無ければ missing）

できない（操作なし）:

- 今まさに編集しているファイル
- 未保存バッファ
- Cursor が次に何をするか
- Cursor への作業指示の自動実行

---

## 11. 将来 Cursor への作業依頼まで拡張する場合の接続点

```text
Browser
  ↓  POST /api/chat または POST /api/dev/request（未実装）
Local Agent
  ↓  作業パッケージ JSON を runs/ に書く（指示。実行ではない）
人間または将来の Cursor 入口
  ↓  実装 / pytest
成果物（git / junit / observations）
  ↓  GET /api/dev/*
Browser
```

接続点は **ファイル契約** が先。Cursor 本番 API は後。  
「Local Agent が Cursor を動かす」は、可視化の次の段階。今回の対象外。

---

## 12. スマートフォン対応を考慮した場合の API 境界

```text
Browser / 将来のスマホ
        ↓
   Chat API + Dev API（同じホスト）
        ↓
   ファイル読取（runs / docs / git）
        ↓
   Local Agent（会話時のみ）
```

- UI 状態（開いているタブ）はクライアント側
- 実行状態・Run・テスト結果は API
- 今は `127.0.0.1` のみ。公開しない
- スマホアプリは作らない

---

## 13. 新しい Core が本当に必要か

**不要。**

既存で足りるもの:

- Chat Session JSON
- Event 関数
- `runs/ai_tool/`
- `docs/ai_tool/project_audit/`
- Git
- 「処理を見る」UI

作らないもの: Memory Core / Reasoning / Graph / RAG / 新しい Session Core / 新しい C3。

`DevelopmentSessionState` を Cursor ログ用に拡張しない。

---

## 14. 既存 Session / Run / Test 情報だけでどこまで可能か

| 欲しい表示 | 既存だけで可能か |
|------------|------------------|
| 待機中 / 完了 / 失敗（作業後） | 一部。Run の `judgment` と Git の有無 |
| 実行中（ライブ） | **不可** |
| 変更ファイル | **可**（git） |
| テスト件数の機械結果 | **不可**（junit が無い） |
| Cursor が書いたテスト件数 | 可（報告書 / observations。報告扱い） |
| Run ID 追跡 | **可** |
| 報告書 | **可** |
| Chat 履歴 / モデル / Tool Event | **可**（既存 Chat） |
| ユーザー確認待ち | Chat の Tool 作成のみ。Cursor 作業の確認待ちは無い |

---

## 15. 最小実装案（承認後。今回はやらない）

1. 読み取り専用 `GET /api/dev/runs` / `reports` / `git`
2. UI に「開発状況」パネル。既存 Chat は壊さない
3. 各項目に `source`: `run_file` / `git` / `cursor_report` / `pytest_xml` / `missing`
4. pytest は **既存の xml があれば表示**。無ければ「機械結果なし」。Chat から pytest を起動しない
5. Cursor 報告と機械結果を並べる。報告だけで PASS にしない
6. `agent.py` / `pipeline.yaml` / Registry / Workflow は触らない

任意の次ステップ（別承認）: pytest 実行時に `pytest.xml` を Run へ残す。Cursor が作業開始時に `runs/dev_status/current.json` を書く習慣（ハートビート。API ではない）。

---

## 16. 将来拡張案

```text
Browser ─ Local Agent ─ Cursor（作業パッケージ）
                 │
                 ├─ Ollama / Tool（既存 Chat）
                 ├─ runs / git / pytest.xml（観測）
                 └─ 通知（完了・失敗）─ スマホ（同一 API）
```

順序:

1. 観測（本設計の最小実装）
2. pytest 機械結果の保存
3. Session と Run の明示リンク
4. 作業パッケージ（依頼）。実行は人間または将来入口
5. 認証付きリモート API とスマホ

途中で止まってよい。4 より前に Cursor API を作らない。

---

## 実装してよい範囲 / 今回やってはいけない範囲

### 今回（本報告）

実装しない。Local Agent を動かさない。

### 次フェーズで実装してよい（ユーザー承認後）

- Experimental な `GET /api/dev/*`（読み取り）
- Chat UI の表示追加（既存チャットを壊さない）
- Event の `actor` フィールド
- Git 読み取り

### まだやってはいけない

- `agent.py` / `pipeline.yaml` / Registry / Standard Workflow / `facet_discovery` 既定
- ResearchRecord 接続
- Cursor 内部 API
- Chat からの自動 pytest / 自動 commit
- 新 Core
- スマホアプリ
- 外部公開

---

## データの流れ（観測専用）

```text
Cursor がファイルを書く / pytest を回す / 報告書を書く
        ↓
リポジトリ（runs / docs / git）
        ↓
GET /api/dev/*   ← まだ無い。設計のみ
        ↓
Chat UI「開発状況」
```

会話の流れ（既存。壊さない）:

```text
Browser → POST /api/chat → Local Agent → Ollama / Tool → Event
```

この二つは混ぜない。Chat の回答を Cursor のテスト結果として扱わない。

---

## 起動・参照（現状）

Chat: `python ai_tool/run_chat_ui.py` → http://127.0.0.1:8765/  
Cursor 接続: なし（UI も `cursor_connected: false`）

次はユーザーが実装範囲を指定する。この報告のあと、勝手に実装へ進まない。
