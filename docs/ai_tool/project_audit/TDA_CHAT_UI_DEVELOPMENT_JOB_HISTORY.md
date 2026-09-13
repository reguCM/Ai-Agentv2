# Chat UI 開発案件履歴

**日付:** 2026-08-30  
**起動:** `python ai_tool/run_chat_ui.py` → http://127.0.0.1:8765/  
**Server:** `LocalAgentChat/0.5`  
**実測 Session:** `cs-20260830_135741-a7b67b`  
**実測案件:** `run-20260830_224107_get_system_time`  
**Production 変更:** 0（`agent.py` / Registry 既存仕様 / 本番 Tool 本体 / `pipeline.yaml` 未変更）  
**新規 C3 / RAG / Knowledge Base / Cursor API:** 0  
**自動 pytest XML:** なし  
**判定:** `PASS`（第一目標：案件単位で Run / Report / Git / Test / Artifact を追える。Cursor の直接監視ではない）

---

## 判定

```text
PASS

見えるようになった: 開発タブを案件一覧 → 案件詳細へ再構成
同一案件として追える: get_system_time の Run / Report / 変更ファイル / Cursor Report / Test
Test 分離: [CURSOR REPORT] 28 passed と [MACHINE TEST] NOT_AVAILABLE は混ざらない
Actor: Cursor 由来は [ACTOR: CURSOR]、機械テストは [ACTOR: MECHANICAL]
まだ取得できない: Cursor 実行中、編集中ファイル、17/20 のライブ進捗、pytest XML
第一目標: ブラウザから Cursor が残した成果物を案件単位で後追いできる
```

Cursor を直接監視できるようになった、のではない。画面上部は引き続き `Cursor live status: NOT OBSERVED`。

---

## 実装前に確認したこと

| # | 対象 | 実際に取得できるか |
|---|------|--------------------|
| 1 | Development Timeline API | できる。`GET /api/dev/events` は維持 |
| 2 | Job データ | Session の `development_jobs[]`。Chat UI 依頼の記録。Cursor 実行の証明ではない |
| 3 | Run | できる。`runs/ai_tool/*/summary.json` + `observations.json` |
| 4 | Report | できる。`docs/ai_tool/project_audit/*.md`。Run slug がファイル名に含まれるときだけ紐付け |
| 5 | Git | できる。status / diff / log / branch / HEAD。書き込みなし |
| 6 | Cursor Report | Run の `observations.unit_tests` と `tests` 辞書があるときだけ |
| 7 | 機械 Test | **できない**（junit/pytest.xml は 0 件 → NOT AVAILABLE） |
| 8 | Artifact / 変更ファイル | observations の `files_created` / `files_modified` があるときだけ |
| 9 | Session 紐付け | get_system_time Run に `session_id` はない |
| 10 | Chat UI | 会話 / 処理 / 開発。`POST /api/chat` は未変更 |

禁止した推測: 「Cursor is running」「実装開始」「pytest 実行中」「17/20」「Git dirty だから実行中」。確認できた成果物だけを Timeline にする。

---

## 何が Chat UI から見えるようになったか

開発タブは次の構造になった。

```text
開発
├─ 開発案件一覧（フィルタ: 全案件 / 最新 / Cursor / Tool作成 / UI / Test / Research）
└─ 案件詳細
     ├─ 開発依頼（無ければ「依頼文：未取得」。Run slug からの推定は明示）
     ├─ 実行主体
     ├─ Status
     ├─ Timeline（ACTOR / SOURCE）
     ├─ 変更ファイル（この案件）
     ├─ Repository Status（リポジトリ全体。案件の変更とは限らない）
     ├─ Run / Report / Git / Test（個別に開ける）
```

`get_system_time` 実測（ブラウザ）:

```text
実行主体  CURSOR
状態      PASS
依頼      既存Tool構造に合わせて get_system_time を追加する。…

[ACTOR: CURSOR] [SOURCE: RUN]
[ARTIFACT] tools/system/time/get_system_time.py  追加
[ARTIFACT] tests/test_get_system_time.py  追加
[ARTIFACT] registry/tools.json  変更
[ACTOR: CURSOR] [SOURCE: REPORT]
[REPORT] TDA_GET_SYSTEM_TIME.md
[ACTOR: CURSOR] [SOURCE: RUN]
[RUN] 20260830_224107_get_system_time  PASS
[ACTOR: CURSOR] [SOURCE: CURSOR_REPORT]
[CURSOR_REPORT] 28 passed
  A_DirectCall PASS  Source: Cursor Report
  B_ReturnShape PASS  Source: Cursor Report
  C_ExistingToolRegression PASS  Source: Cursor Report
[ACTOR: MECHANICAL] [SOURCE: MISSING]
[TEST] 機械的テスト  NOT AVAILABLE

変更ファイル（この案件）
+ tools/system/time/get_system_time.py
+ tests/test_get_system_time.py
M registry/tools.json

Repository Status
modified: 37  untracked: 6120
（リポジトリ全体。この案件の変更とは限りません）
```

Git commit は未作成のため Timeline に commit を紐付けていない。commit message からの断定はしていない。

「GPUの温度を教えて」は Chat（intent: CHAT、`get_gpu_status`）。開発案件にはしていない。`chat_jobs` は空。

---

## 追加 API（読み取り。POST /api/chat は未変更）

```text
GET /api/dev/cases?filter=all|latest|cursor|tool|ui|test|research&session_id=
GET /api/dev/cases/<id>
```

既存の `GET /api/dev/events` / `jobs` / `runs` / `reports` / `git` / `tests` は維持。

案件 ID は `run-<run_id>`。新しい Reasoning Core ではない。

各イベントは薄く `actor` / `source` / `confidence` を持つ。Cursor ライブ状態は入れない。

---

## 実測 A–J

| 項 | 内容 | 結果 |
|----|------|------|
| A | `こんにちは` が通常 Chat | PASS。qwen3:8b が挨拶を返した。Tool 未使用 |
| B | モデル変更 | PASS。`deepseek-coder-v2:16b` → `qwen3:8b` |
| C | 既存 Tool | PASS。`GPUの温度を教えて` → `get_gpu_status` 実測（68°C） |
| D | 既存 Timeline / Run / Report / Git | PASS。API `GET /api/dev/events` 53 件。個別パネルで Run 一覧・Git・Report を確認 |
| E | get_system_time 同一案件 | PASS。上記のとおり |
| F | Test 分離 | PASS。Cursor Report `28 passed` を機械結果にコピーしていない |
| G | Actor 表示 | PASS。成果物/Run/Report は CURSOR。機械テストは MECHANICAL |
| H | 不明情報 | PASS。ライブは NOT OBSERVED。機械テストは NOT AVAILABLE。依頼が無い案件は「依頼文：未取得」 |
| I | 大量 Test | PASS。Cursor Report の A/B/C を一覧表示。機械結果とは別 |
| J | 回帰 | PASS。chat_interface + `test_get_system_time` 37 passed |

---

## まだ見えないもの

- Cursor が現在実行中かどうか
- 編集中の未保存バッファ
- `[17/20]` のような途中経過
- Cursor 内部の思考
- pytest XML による機械的テスト結果
- Chat UI から取得できない Cursor チャットの依頼文（Run observations に書かれている場合だけ表示）

Git の dirty 件数から実行中とは判断していない。

---

## 変更ファイル

- 追加: `ai_tool/chat_interface/dev_cases.py`
- 変更: `ai_tool/chat_interface/server.py`（`LocalAgentChat/0.5`、`/api/dev/cases`）
- 変更: `ai_tool/chat_interface/static/index.html` / `app.js` / `app.css`
- 追加: `tests/ai_tool/chat_interface/test_dev_cases.py`
- 変更: `tests/ai_tool/chat_interface/test_dev_readonly.py`

未変更: `agent.py`、`pipeline.yaml`、既存 Tool 実装、Registry の get_system_time 以外。
