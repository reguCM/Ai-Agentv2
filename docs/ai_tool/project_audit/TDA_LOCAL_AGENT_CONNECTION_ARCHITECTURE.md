# Local Agent 接続構想（実装前設計）

**日付:** 2026-08-30  
**状態:** 設計完了（コード読取のみ。実LLM / Tool / 検索 / Research は未実行）  
**Production 変更:** 0  
**既定 Workflow:** 変更しない（`facet_discovery="off"` を維持する前提）

この文書は実装指示ではない。  
ユーザーが内容を確認してから、実装範囲を指定する。

過去の R1〜R3 で Cursor / ハーネス（Harness）が通した処理を、Local Agent 自身の能力としては書かない。

---

## 判定ラベル（このフェーズ）

| ラベル | 意味 |
|--------|------|
| 設計完了 | コード上の接続関係を特定し、案を書いた |
| 要確認 | 設計上の選択が残っている。ユーザー判断が先 |
| 未確認 | 実行しないと分からない（モデル導入、実ネット、実 Tool 選択） |

動作確認は次フェーズ。本フェーズで「動いた」とは書かない。

---

## 0. 調査で確定した「二つの入口」

現状、入口は一本ではない。

```text
入口A  python agent.py
        1要求（環境変数 AI_AGENT_USER_REQUEST）
        Clarity / 観測 JSONL / Tool Gate（TTY 確認）
        Ollama + visibility=agent の Tool

入口B  python ai_tool/run_chat_ui.py
        ブラウザ http://127.0.0.1:8765/
        run_chat_turn（agent.py は import しない）
        同じ llm.chat と Registry Tool を別ループで呼ぶ
```

R3.5-A 時点の「Chat UI は無い」は、その後 R3.5-B で入口 B が追加された。  
ただし入口 B は **agent.py 本体の呼び出しではない。** 処理の二重化が接続不足の中心である。

---

## A. Local Agent（コード上）

| 項目 | 場所 | 現状 |
|------|------|------|
| メイン CLI | `agent.py`（`if __name__` なし。ファイル実行で全ループが走る） | 設計完了 |
| LLM | `tools/system/llm.py` → `ollama.Client.chat()` | 構造あり。実応答は未確認 |
| 既定モデル | `config/pipeline.yaml` の `active_model: deepseek_coder_v2_16b` → `deepseek-coder-v2:16b` | 過去観測で 404。本フェーズでは再確認していない |
| Tool 公開 | `create_ollama_tools()` が `visibility=="agent"` のみ | 設計完了 |
| Tool 実行 | `execute_tool()`（Registry importlib + `agent_tool_gate`） | 設計完了 |
| 入力 | 環境変数 1 件。対話履歴ループではない | 設計完了 |
| 出力 | stdout「最終回答」 | 設計完了 |
| エラー | Tool 例外はログして再送出。Gate 拒否は blocked 結果 | 設計完了 |
| Session（本番） | `TaskState` はプロセス内。次の `python agent.py` では消える | 設計完了 |
| Session（TDA） | `DevelopmentSessionState` は `agent.py` から呼ばれない | 設計完了 |
| Chat 側 Session | `runs/chat_ui/sessions/` の JSON。新 Core ではない | 設計完了 |

---

## B. Tool

Registry で `visibility=="agent"` の既存 Tool（新規作成しない前提）:

- `get_gpu_status`
- `get_gpu_processes`
- `cpu_status`
- `get_cpu_status`
- `search_web`
- `read_url_text`

確認事項（構造のみ）:

| # | 問い | 判定 | 根拠 |
|---|------|------|------|
| 1 | Agent は Tool 一覧を取得できるか | できる | `registry/tools.json` を読む |
| 2 | LLM に Tool 仕様を渡せるか | できる | Ollama `tools=` schema |
| 3 | LLM が Tool を選ぶ仕組みがあるか | **構造はある** | `tool_calls`。実選択は未確認 |
| 4 | 選んだ Tool を Agent が実行できるか | できる（コード） | `execute_tool` / Chat の `_execute_agent_tool` |
| 5 | 結果を LLM へ戻せるか | できる | `role=tool` で messages に戻す |
| 6 | 複数 Tool を連続実行できるか | できる | 同一応答の複数 call + `max_tool_rounds`（既定 5） |
| 7 | 失敗時の再試行・別 Tool | **専用機構は無い** | 次ラウンドで LLM が別 call する余地のみ。ポリシー未設計 |

`create_tool_proposal` は Registry にあるが `visibility` 未指定。Ollama 公開集合に入らない。

ファイル Tool（`list_files` 等）はコードがあるが、現行 Registry の agent 公開には無い。SYSTEM_PROMPT との不一致は R3.5-A で記録済み。**本設計では直さない。**

---

## C. Web Search

`search_web` という Tool が **存在する**ことと、Local Agent がユーザー要求を見て **自律選択する**ことは別である。

```text
構造上の経路（コード）:

User → Agent ループ → Ollama（tools に search_web）
     → LLM が search_web を tool_calls に出す場合のみ
     → general_web_search
     → 結果を LLM へ戻す
     → 必要なら LLM が read_url_text を出す
```

| 事実 | 判定 |
|------|------|
| search_web が Registry にある | 設計完了（存在する） |
| Agent ループが呼べる | 設計完了（構造あり） |
| LLM が「調べて」で必ず選ぶ | 未確認（実測が必要。本フェーズ禁止） |
| 検索結果を ResearchRecord に保存する | **しない**（現状未接続） |

Cursor が検索して Agent に渡す経路は、設計上も採用しない。

---

## D. ResearchRecord

実装は `ai_tool/experimental/development_assistance/research_record.py` 等。  
**experimental。agent.py / 既定 Workflow には未配線。**

| 操作 | Local Agent から | Harness / Cursor から |
|------|------------------|------------------------|
| 作成 | 未接続 | `add_from_run` 等 |
| 保存 | しない（Chat Event も「保存なし」） | メモリ内 `ResearchStore` |
| 検索・再利用 | 未接続 | `research_reuse.py`（既定 Discovery off） |
| Session 関連 | Chat は空 store | `DevelopmentSessionState.last_research_id` |
| version / evidence / conflict / unknown / facet | Adapter にある | R1〜R3 でハーネス検証 |

将来の望ましい流れ:

```text
過去 ResearchRecord
 ↓
Session が last_research_id を持つ
 ↓
今回の要求
 ↓
機械的 bind / diff / select
 ↓
必要 Facet だけ LLM へ
```

これは **接続可能性はある**（関数が既にある）。  
**今は実行しない。全件を LLM に渡す設計は採用しない。**

---

## E. Session（三種を混同しない）

| 名前 | 保持するもの | 継続性 |
|------|----------------|--------|
| `TaskState` | facts / decisions / open_questions。prompt 用 | **1 プロセスだけ** |
| `DevelopmentSessionState` | last_research_id、Facet スロット、last_test_result、awaiting_human_review | ハーネス内。agent.py 未使用 |
| Chat JSON Session | session_id、開始時刻、会話、Event、experimental_session のコピー | ファイル。会話は続く。ResearchRecord は空 |

将来「会話 → Session → 過去の記憶 → 今回の要求」をやるなら、  
**Chat Session を表紙にし、中身の Facet / Record 参照は既存 `DevelopmentSessionState` を再利用する。** 新しい Session Core は作らない。

---

## F. 要求の分岐（設計のみ。実行しない）

現状コード: 正規表現で `tool_creation` とそれ以外（`chat`）の二択。  
Web / 既存 Tool / Research / 開発は **LLM の Tool 選択に任せている。** 独立した分類器 Core は無い。

将来案（確定ではない）:

```text
User Request
      ↓
機械的ゲート（先にやる）
      ├─ 空・危険操作 → 停止 / ユーザー確認
      ├─ 「Toolを作って」等 → Tool作成（Proposal まで。Registry 書かない）
      ├─ Session に bind 可能な指示語 → pointer（推測で技術名を作らない）
      └─ 上記以外 → LLM
            ├─ 挨拶等 → Tool なし
            ├─ 観測要求 → 既存 Tool
            ├─ 調べて → search_web（必要なら read_url_text）
            ├─ 開発・実装 → 将来。今は「未接続」と返す
            └─ 不明 → ユーザーへ確認
```

### 機械的に処理すべき候補

- Tool 作成キーワード
- Python / CUDA / OS / Docker の **明示的な置換文**（既存 `python_version_delta` / `apply_requirement`）
- Session に ID があるときの pointer bind（解けなければ UNRESOLVED。推測しない）
- Registry に無いファイル作成の禁止

### LLM に任せる候補（今回確定しない）

**案1（狭い）:** Tool 名の選択と、Tool 結果の日本語説明だけ。  
**案2（中）:** 案1 + 「検索が要るか」の判断。  
**案3（広い・非推奨）:** 記憶の整理・正解の統合・safe/feasible。**採用しない。**

推奨は案1から始め、案2は実測後に足す。

---

## G. 処理の見せ方（Event）

内部の思考過程は出さない。観測可能な Event だけ。

最小セット（コードに近いものもある）:

```text
request / route
llm_input（件数。本文の全 Memory は保存しない）
tool_call（name, 安全な引数）
tool_result（要約）
web_search / url_fetch
research_record（saved: false を明示）
session_updated
error
final_answer
```

UI は最終回答 + 「処理を見る」。  
将来 Avatar / 通知は Event を購読するだけで足せる（今回作らない）。

---

## H. LLM へ渡す情報量

R1〜P-7 の方針を維持する。

```text
全記憶
 ↓
機械的 bind（紐付け）
 ↓
機械的 diff（差分比較）
 ↓
機械的 select（選択）
 ↓
必要な Evidence だけ
 ↓
LLM
```

全記憶を LLM に渡して整理させる構造は **採用しない。**

Chat 現状: ResearchStore が空なので、材料は「会話の直近」と Tool 結果だけ。これは意図した縮小ではなく、**Record 未接続の結果**である。接続するときは dump_all を渡さないこと。

---

## I. 機械的に先にできる条件（既存 Adapter、未配線）

`apply_requirement` / `parse_python_version_delta` がコード上扱える例:

| 変化 | 機械的にできること | できないこと |
|------|--------------------|--------------|
| Python 3.12 → 3.13 | 差分 Facet を UNKNOWN にする。他 Facet を保持。旧 Evidence を 3.13 にコピーしない | 3.13 で動くかの判定（feasible 禁止） |
| CUDA 12.3 → 12.4 | 要求文から CUDA を抜き、未カバーなら UNKNOWN | ドライバ互換の断定 |
| Windows → Linux | OS スロット更新。他は保持 | 全依存の再調査を自動完了 |
| Docker あり → なし | 制約スロット | 代替構成の発明 |

曖昧（「もっといい環境で」等）は機械的確定不可 → 停止またはユーザー確認。

**本フェーズでは実測しない。**

---

## J. Chat UI の将来像（実装しない）

最小窓口は既に入口 B にある（文字チャット + 処理を見る）。  
将来足せるが今回対象外: Avatar、過去 Session 一覧、Research タブ、開発状態、完了通知。

スマホは同じ HTTP API を認証付きで LAN / トンネルに出す設計が可能。アプリは作らない。

---

## K. Cursor と Local Agent の分担（評価。未決定）

提案分担は既存コードと整合する。

| 主体 | 向いていること | 現状 |
|------|----------------|------|
| Cursor | コード編集、pytest、Git、接続の調査 | 実際にそれをしている |
| Local Agent | 対話、Tool 選択・実行、検索、結果説明 | **構造はある。実選択は未確認。Research 未接続** |

「Local Agent が Cursor に作業指示を出す」は将来候補。今は API も無い。  
**Cursor が検索・Tool 結果を偽造して Agent に渡す経路は作らない。**

この分担は適切だと評価する。ただし Local Agent 側の実 LLM Tool 選択が確認できるまでは、能力の報告を分けたままにする。

---

## L. スマートフォン等

```text
スマートフォン
  ↓  HTTPS + 認証（将来）
Chat と同じ API（今は 127.0.0.1:8765 の POST /api/chat）
  ↓
Local Agent ループ
  ↓
LLM / Tool / 将来 Research
```

拡張性: **ある**（入口が HTTP なら端末は問わない）。  
今回: アプリを作らない。`127.0.0.1` のみは意図的な安全側。

---

## 2. 接続点一覧

| 接続 | 現状 | 将来案 | 実装難度 |
|------|------|--------|----------|
| Chat → Agent | △ 入口 B は独自ループ。agent.py 非 import | 入口を一本化するか、共通 `run_turn` に寄せる | 中（二重ループの整理） |
| Agent → LLM | ○ コードあり | 導入済みモデルを使う。pipeline.yaml は勝手に変えない | 低〜中（モデル導入は環境） |
| LLM → Tool | ○ schema + tool_calls | 実測で選択を確認 | 低（構造済み） |
| Tool → Agent | ○ 実行して messages へ戻す | そのまま | 低 |
| Agent → Research | × 未接続 | Search 成功後に任意保存。自動全件保存はしない | 中 |
| Session → Memory | △ 会話 JSON のみ。Record 空 | Chat Session + 既存 DevelopmentSessionState | 中 |
| Agent → Cursor | × | 指示パッケージ出力が先。本番 API は後 | 高 |
| Smartphone → Agent | × | 同一 API + 認証 | 中（認証設計） |

○ コード上つながっている / △ 部分的 / × 無い

---

## 3. 条件・境界

```text
機械的に処理する
        ↓
曖昧なら停止
        ↓
必要なら LLM
        ↓
それでも不明ならユーザーへ確認
```

| 区分 | 例 |
|------|-----|
| 機械的に確定可能 | Registry の有無、明示 Version 置換、pointer が Session ID で一意、Tool 作成キーワード |
| LLM に解釈させる | 「GPUの状態」「調べて」の Tool 選択、結果の説明 |
| ユーザー確認が必要 | Registry 登録、本番ファイル変更、Gate（CLI）、Tool 作成の実装着手 |
| 実行してはいけない | dump_all、推測 bind、feasible/safe/correct、Cursor による偽 Search |
| 将来機能 | Avatar、スマホアプリ、Cursor API、自動 Git |

---

## 最小接続案（実装はユーザー承認後）

**一本の実行者を決める。**

推奨: 日常窓口は Chat（入口 B）。実行は「Registry + `llm.chat` + Tool 実行」。  
`agent.py` は CLI / 収集バッチ用として残し、**同じ実行関数を共有する**のが望ましい（今は共有していない。要確認）。

第一関門（次フェーズで実測する案）:

```text
Chat → Local Agent → LLM → Tool選択 → get_gpu_status / search_web → 結果 → 回答
Event で「誰が選んだか」を残す
Research はまだ保存しない（未使用と表示）
```

モデル: `pipeline.yaml` は維持。Chat だけ別モデルを使うなら、理由・対象・影響を書いてから環境変数等で上書き。既定の書き換えはユーザー承認が先。

---

## 推奨接続順序（承認後）

1. 導入済み Ollama モデルの確認（実行フェーズ）
2. Chat → LLM がエラーなく返る
3. LLM が `get_gpu_status` を自分で選んで実行
4. LLM が `search_web` を自分で選んで実行（Cursor は検索しない）
5. Event / Session 表示の固定（誰が実行したかを観測）
6. Tool 作成は Proposal + ユーザー確認まで（Registry 書かない）
7. その後初めて ResearchRecord 保存の任意接続
8. bind / diff / select を「表示」から「LLM 材料」へ（dump_all 禁止）
9. Cursor / スマホはさらに後

途中で止まってよい。7 より前に Memory を巨大化しない。

---

## 最終報告（指定 10 項）

### 1. 現在 Local Agent 自身ができること（コード上）

- 1 要求を受け、Ollama に chat する経路
- agent 公開 Tool を schema として渡し、`tool_calls` なら実行して結果を戻す
- `search_web` / `read_url_text` / GPU / CPU の実行関数そのもの
- Chat 入口（ブラウザ）と Event・JSON Session
- Tool 作成キーワードの機械的分岐と `create_tool_proposal`（登録なし）

実 LLM が Tool を選んだことは、**本フェーズでは確認していない。**

### 2. 現在 Cursor / ハーネス側だけができること

- R1〜R3 の bind / diff / select、fixture の Spec→Test
- コード編集、pytest、文書
- ResearchStore への ingest
- `facet_discovery` を実験フラグで回すこと（既定は off）

### 3. 接続不足

- `agent.py` と Chat ループが別
- ResearchRecord / 既定 Workflow が入口に未接続
- 設定モデルと導入モデルの不一致（過去 404。今回未再測）
- Prompt と Registry のファイル Tool 不一致
- `create_tool_proposal` が LLM schema に無い
- Tool 失敗時の再選択ポリシーが無い
- Cursor API が無い

### 4. 最小接続案

Chat を窓口にし、既存 6 Tool と Ollama だけを実測する。Research はまだ繋がない。

### 5. 推奨接続順序

上記「推奨接続順序」1→5 が第一関門。6 以降は別承認。

### 6. 機械的処理と LLM の境界

機械: ID bind、Version diff、Facet 選択、作成要求の正規表現、禁止操作。  
LLM: 自然言語、既存 Tool の選択、検索文の理解、説明。  
記憶の整理と正解の統合は LLM に渡さない。

### 7. ユーザー確認が必要な境界

Registry 登録、本番変更、モデル既定の変更、Discovery 既定の変更、曖昧な環境変更。

### 8. スマホへの拡張性

同じ Chat API を認証付きで出せば拡張できる。今回は作らない。

### 9. 実装すると壊す可能性がある箇所

- `agent.py` を大きく切ると CLI / 収集バッチ
- `facet_discovery` 既定を on にすると Phase F
- Chat と `execute_tool` の二重実装が分岐すると「Agent ができる」報告が嘘になる
- Research を全件 prompt に載せる
- 本番 `agent_tool_trust.json` を Chat が書き換える

### 10. 次に実装してよい範囲（提案。未承認）

ユーザー承認後に限り:

- 導入モデルの確認と、Chat 経路だけのモデル解決（pipeline.yaml は原則維持）
- Chat → LLM → 既存 Tool 選択の実測と Event 固定
- 失敗時に「LLM が選んでいない」と偽らないこと

承認前に実装へ進まない。

---

## 実装単位（承認後の切り方）

| 単位 | 内容 | 触ってよいもの | 触ってはいけないもの |
|------|------|----------------|----------------------|
| U1 | モデル解決と LLM 応答 | Chat 起動、環境変数 | pipeline.yaml 既定、Registry |
| U2 | GPU Tool 実選択 | Chat ループ、Event | 新 Tool、新 Core |
| U3 | search_web 実選択 | 同上 | Research 自動保存 |
| U4 | 共通 run_turn への寄せ | agent.py の関数化は要慎重 | 既定 Workflow |
| U5 | Research 任意保存 | experimental Adapter | dump_all、Discovery 既定 |
| U6 | bind 材料を LLM へ | llm_materials 再利用 | 全 Record 投入 |

---

## このフェーズでやらなかったこと

Local Agent 起動、実 LLM、Tool 実行、Web Search、Research、Registry 変更、pytest による開発ループ、Git、Production Workflow 接続、Chat 本実装の追加、スマホアプリ、Reasoning Core / Graph / RAG。
