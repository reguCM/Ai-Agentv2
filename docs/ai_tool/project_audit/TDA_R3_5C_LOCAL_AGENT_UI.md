# Local Agent UI（R3.5-C）

**日付:** 2026-08-30  
**起動:** `python ai_tool/run_chat_ui.py` → http://127.0.0.1:8765/  
**Run:** `runs/ai_tool/20260830_211406_r3_5c_local_agent_ui`  
**実測 Session:** `cs-20260830_120745-3f8e08`  
**Production 変更:** 0（`agent.py` / `pipeline.yaml` / Registry 未変更）  
**Experimental 変更:** Chat UI / Chat API のみ  
**新規 C3:** 0  
**既定 Workflow:** `facet_discovery="off"`  
**Cursor 接続:** なし  
**判定:** `PASS`（最低目標）／ Web Search の有用な検索結果は `FAIL`

---

## 判定

```text
R3.5-C
判定: PASS（最低目標）

UI: Chat / 履歴 / 使用モデル表示 / ワンクリックモデル切替 / 処理中 / エラー分離 / Event
Ollama: 起動中。/api/tags 相当で 5 モデルを取得
実LLM: Local Agent が qwen3:8b で実際に回答した
モデル切替: deepseek-coder-v2:16b → qwen3:8b。次の LLM リクエストは qwen3:8b
履歴: 「GPUは何？」の後「温度は？」で直前の GPU 文脈を利用。llm_send.history_turns = 1 → 2
Tool選択: LLM が get_gpu_status を選択（Python 直呼びではない）
Web Search: LLM が search_web を選択し実行。hit_count=0
Production: 変更 0
Cursor接続: なし
ResearchRecord: 保存なし
```

「コード上存在する」と「Local Agent が実際に使えた」は分けて記録した。

---

## 実装前の確認（再利用 / 追加 / 触らない）

### 再利用した

- 既存 Chat UI（`ai_tool/chat_interface/`、`python ai_tool/run_chat_ui.py`）
- `tools.system.llm.chat`（新しい LLM クライアントは作っていない。`model=` を渡すだけ）
- Session JSON（`runs/chat_ui/sessions/`）
- `ollama list` / 起動中 Ollama の `/api/tags`
- Registry `visibility=agent` Tool（`get_gpu_status` / `search_web` など）

### 今回追加した（Experimental）

- `GET /api/models` … 起動中 Ollama のモデル一覧
- `POST /api/session/model` … **今の Chat Session** のモデル変更のみ
- Chat が `session.model` を `run_chat_turn(..., model=)` に渡す
- モデル選択 UI、使用モデル表示、新規チャット、処理中、エラーバブル
- メッセージに `role` / `content` / `timestamp` / `session_id` / `model`
- Event の短い経路表示（未実行を実行済みと書かない）
- Ollama 停止 / モデル不存在 / LLM エラーの日本語表示（Agent 回答に偽装しない）

### 今回触っていない

- `agent.py`
- `pipeline.yaml`
- Production Workflow / Registry
- Reasoning / Graph / RAG / Vector DB / Knowledge Base
- 新しい Memory Core / Facet Core / C3
- ResearchRecord の本番接続
- Cursor API
- `ollama pull` / モデル削除 / `OLLAMA_MODELS` 変更 / Ollama 再起動
- スマホアプリ

---

## 実際の経路（今回実測）

```text
Browser Chat UI
 ↓
Chat API（127.0.0.1:8765）
 ↓
run_chat_turn
 ↓
tools.system.llm.chat(model=session.model)
 ↓
Ollama
  ├─ 回答のみ
  ├─ LLM が get_gpu_status を選択 → Tool 実行 → 回答
  └─ LLM が search_web を選択 → 検索実行 → 回答
```

実行主体は Local Agent。Cursor は UI 操作とコード補助のみ。

---

## 誰が何をしたか

| 行為 | 実行者 | Local Agent 成功に数えるか |
|------|--------|---------------------------|
| Chat UI / API の実装 | Cursor | 数えない |
| pytest 15 件（mock） | Cursor | 数えない |
| ブラウザでボタンをクリック | Cursor（操作） | 操作そのものは数えない |
| `GET /api/models` で 5 モデル取得 | Local Agent（Chat API → Ollama） | 数える |
| モデル切替 `POST /api/session/model` | Local Agent | 数える |
| 「こんにちは」への日本語回答 | Local Agent（Ollama `qwen3:8b`） | **数える** |
| `get_gpu_status` の選択 | Local Agent の LLM | **数える** |
| GPU 実測（RTX 3060 / 58–60℃） | Local Agent の Tool | **数える** |
| `search_web` の選択と実行 | Local Agent の LLM + Tool | **数える** |
| 有用な検索ヒット | なし（0 件） | 成功にしない |
| `agent.py` の実行 | していない | — |

---

## Test A — Chat

**実施:** ブラウザ Chat UI。Session `cs-20260830_120745-3f8e08`。

```text
ユーザー: こんにちは
Local Agent: こんにちは！何かお手伝いできることがありましたら、お知らせください。
モデル: qwen3:8b（切替後）
Tool: なし
Search 実行: なし
```

Event:

```text
ユーザー入力
 ↓
Local Agent
 ↓
LLM（モデル: qwen3:8b）
 ↓
回答
[能力] Search Tool available / Search 実行 = なし
```

**判定:** `PASS`  
**Local Agent が実行:** はい  
**注:** 既定表示の `deepseek-coder-v2:16b` での挨拶は未実施。切替後の選択モデルで実LLMを確認した。

---

## Test B — Model Change

UI 操作のみ（`ollama pull` なし）。

```text
使用モデル: deepseek-coder-v2:16b
 ↓
モデル一覧をクリック（Ollama が認識している 5 件）
 ↓
qwen3:8b を選択
 ↓
お知らせ: モデルを deepseek-coder-v2:16b から qwen3:8b に変更しました
 ↓
次の質問「こんにちは」
 ↓
llm_send.model = qwen3:8b
```

一覧（固定文字列ではない。起動中 Ollama から取得）:

- `gemma3:12b`
- `qwen2.5-coder:7b`
- `qwen3:14b`
- `deepseek-coder-v2:16b`
- `qwen3:8b`

**判定:** `PASS`  
**Local Agent が実行:** はい（一覧取得・Session モデル変更・次リクエストのモデル指定）

---

## Test C — 会話維持

```text
GPUは何？
 ↓
温度は？
```

- 2 件目の `llm_send.history_turns = 2`（会話履歴を LLM に渡した）
- 2 件目の回答: 「GPUの現在温度は **60.0°C** です。」
- LLM は 2 件目でも `get_gpu_status` を選び直した（履歴だけに頼らず再実測）

**判定:** `PASS`  
**Local Agent が実行:** はい

永続 Memory / ResearchRecord / Vector DB へは保存していない。ブラウザ Session 中の JSON のみ。

---

## Test D — Tool 選択

```text
ユーザー: GPUは何？
LLM → get_gpu_status（selected_by=llm）
Tool Result: NVIDIA GeForce RTX 3060 / temperature 58 / utilization 97 / VRAM 8061/12288
Agent: GPUはNVIDIA GeForce RTX 3060です。温度: 58.0°C ...
```

Event に `tool_select` / `tool_call` / `tool_result` がある。  
Python から Tool を直呼びした成功ではない。

**判定:** `PASS`  
**Local Agent が実行:** はい（LLM が選択し、Local Agent が実行）

---

## Test E — Web Search

```text
ユーザー: RTX 3060について最新情報を調べて
LLM → search_web
query: RTX 3060 最新情報
hit_count: 0
error: 検索結果がありません
Agent: 最新情報の検索が成功しませんでした。… Web検索が確認できませんでした。
```

```text
Search Tool存在 = PASS
Search実行     = PASS（LLM が選択し、web_search Event あり）
有用なヒット   = FAIL（0 件）
```

未実行なのに「Web Search completed」とは出していない。  
実行時は `Search 実行 = あり`。未実行時は `Search 実行 = なし`。

**判定:** `PARTIAL_PASS`  
**Local Agent が実行:** 選択と実行はした。有用な結果は得ていない。

---

## エラー表示

エラーは Agent の通常回答として出さない（`role=error`）。

| 状況 | UI |
|------|-----|
| Ollama 停止 | Ollamaに接続できません。Ollamaが起動しているか確認してください。 |
| モデル不存在 | 選択されたモデルがOllamaから見つかりません。 |
| LLM エラー | LLM処理中にエラーが発生しました。詳細は処理ログを確認してください。 |
| モデル 0 件 | 利用可能なLLMモデルがありません |

今回の実測では Ollama は起動しており、上記の失敗系は **ユニットテスト（Cursor）** で確認。実機での Ollama 停止テストはしていない（未確認）。

---

## コード上存在するだけのもの

- `search_web` / `read_url_text` の **存在**（能力表示）
- Tool 作成経路（`classify_request` → proposal。今回の実測では未使用）
- Experimental bind/diff/select の表示用 overlay
- 将来の長い経路（Requirement → Gate → Discovery → …）の Event 余地

存在 ≠ 実行。能力行は `Search Tool available` とし、実行は `Search 実行 = あり/なし` で分けた。

---

## 未確認 / 失敗 / 未実施

- `deepseek-coder-v2:16b` での実チャット（一覧と初期表示のみ）
- Ollama を止めた状態の UI 実機確認
- 検索ヒットが 1 件以上取れること
- ResearchRecord / Memory / Cursor API / スマホ
- Production Workflow 接続

---

## Production 変更 / Experimental 変更

| 区分 | 内容 |
|------|------|
| Production | **0**。`agent.py` / `pipeline.yaml` / Registry / 本番 trust を変更していない |
| Experimental | Chat UI、`/api/models`、`/api/session/model`、Session の `model`、Event/エラー表示 |

---

## ユニットテスト（Cursor。Local Agent 成功に数えない）

```text
python -m pytest tests/ai_tool/chat_interface/test_r35b_chat_interface.py tests/ai_tool/chat_interface/test_r35c_local_agent_ui.py -q
15 passed
```

---

## 起動

```text
python ai_tool/run_chat_ui.py
```

ブラウザ: http://127.0.0.1:8765/

Avatar / 音声 / スマホ / Cursor API / 自動 Registry 登録 / 全 Memory の LLM 投入 / `ollama pull` は作っていない。
