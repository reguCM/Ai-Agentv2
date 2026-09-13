# Local Agent 操作窓口・処理経路監査（R3.5-A）

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_195714_r3_5a_interface_audit`  
**Production 変更:** 0  
**新規 C3:** 0  
**既定 Workflow 変更:** なし（`facet_discovery="off"`）  
**最終判定:** `AUDIT_COMPLETE`（監査完了）

今回は実装を開始していない。コードを読んで、ユーザーの1メッセージがどこを通るかを記録した。  
Cursor で確認できた処理を、Local Agent 自身の能力としては書いていない。

---

## 判定理由

入口・LLM・Tool・Research・Memory の接続と非接続は、現行コードから特定できた。  
今回 `agent.py` は起動していない。Ollama が今生きているか、Tool Gate の確認画面が実際に出るかは **未確認** のまま残す。  
不明な実行時状態を推測で PASS にしていない。

---

## ① 現在の入口

```text
ユーザー
 ↓
環境変数 AI_AGENT_USER_REQUEST
  （未設定なら agent.py 内の既定1件）
 ↓
python agent.py
 ↓
Clarity（LLM。TTY なら input("> ") で確認）
 ↓
pre_web_answer_candidate（観測用の別会話。本番 Gate には接続しない）
 ↓
Ollama chat（tools= visibility=="agent"）
 ↓
Tool Call があれば execute_tool
 ↓
結果を messages に戻して再 chat
 ↓
stdout「最終回答」
```

**Chat UI は無い。** リポジトリ根に `.html` / `.tsx` / `.vue` のアプリ画面は無い。Streamlit / Flask / FastAPI / Gradio の窓口も `agent.py` には無い。

起動方法:

```text
python agent.py
```

要求の差し替え:

```text
AI_AGENT_USER_REQUEST=（1件の文章）
```

`input("> ")` は Clarity の確認と `agent_tool_gate` の人間確認用。メッセージ履歴のある対話ループではない。

TDA の `DevelopmentSessionState` は `agent.py` から呼ばれない。

---

## ② 現在の LLM 経路

### Production（Local Agent）

```text
User（1要求）
 ↓
agent.py
  SYSTEM_PROMPT + STATE（TaskState）+ 検証済み環境
 ↓
tools/system/llm.py  chat()
 ↓
ollama.Client.chat()
 ↓
既定モデル: config/pipeline.yaml の active_model
  → deepseek_coder_v2_16b
  → config/llm_models.yaml の deepseek-coder-v2:16b
  （AI_AGENT_MODEL で上書き可）
 ↓
tool_calls があれば execute_tool
 ↓
role=tool で結果を戻す
 ↓
最終 content を stdout
```

LLM へ渡しているもの（コード上）:

- ユーザー要求（1件）
- Clarity 後の `TaskState` スナップショット（facts / decisions 等。`research_history` は prompt に載せない）
- 検証済み環境
- Tool schema（`visibility=="agent"` のみ）
- Tool 実行の raw 結果

### TDA / R3（Experimental）

```text
pytest / ai_tool/run_tda_*.py
 ↓
run_standard_workflow(..., llm_enabled=False)
 ↓
実 Ollama は呼ばない
```

過去報告「R3 では実 LLM を呼んでいない」は **TDA harness について正しい**（`llm_enabled=True` が R3 ソースに無い）。  
`agent.py` 本番ループは実 Ollama を呼ぶ **実装あり**。今回その起動確認はしていない（未確認）。

---

## ③ Tool 経路

```text
発見: registry/tools.json を load_registry()
選択: Ollama が tool_calls を返す（visibility=="agent" だけ schema に載る）
実行: execute_tool() → agent_tool_gate → importlib で関数呼び出し
結果: messages に JSON で戻す。stdout は要約表示
LLM: 次の chat() が結果を読む
```

現行 `visibility=="agent"`（コード読取）:

- `get_gpu_status`
- `get_gpu_processes`
- `cpu_status`
- `get_cpu_status`
- `search_web`
- `read_url_text`

`production_bridge` の experimental overlay ID 集合は **空**。Registry 外の Tool は今は足されない。

`create_tool_proposal` は Registry にあるが `visibility` 未指定。Ollama 公開集合に入らない。  
`create_tool_implementation` / `register_tool` / `test_tool` 等は pipeline 側。Agent ループからは見えない。

ファイル Tool:

| もの | 状態 |
|------|------|
| `tools/file/workspace/list_files.py` 等 | コード **実装あり** |
| Registry `visibility=="agent"` | **実装なし**（名前が載っていない） |
| `write_file` | ファイル自体 **実装なし** |

SYSTEM_PROMPT は `list_files / read_file / search_files` を列挙している。Registry と一致しない。

---

## ④ Research 経路

### Local Agent（実際）

```text
Requirement（1件の USER_REQUEST）
 ↓
SYSTEM_PROMPT の Web 手順（Search → Fetch）
 ↓
LLM が search_web / read_url_text を選ぶ場合のみ
 ↓
tools/system/network/search_web.py → general_web_search
 ↓
結果は messages と観測ログ（logs/capability_route.jsonl）
 ↓
ResearchRecord には保存しない
```

### TDA（Experimental。Agent 未接続）

```text
Requirement
 ↓
run_standard_workflow / run_tda_case
 ↓
Gate / Goal /（任意）Discovery / Coverage
 ↓
Evidence を ResearchRecord へ（harness の ResearchStore。メモリ）
 ↓
Reuse / Routing は facet_discovery 既定 off
 ↓
DecisionFactor / LLM 材料は experimental Adapter
```

指示書の仮想経路:

```text
User → Agent → Goal → Gate → Discovery → Coverage → Memory → Reuse → Web → Evidence → Decision Support → LLM → User
```

**実際の Agent 経路はこれではない。** Goal / Gate / Discovery / Coverage / ResearchRecord / Reuse / Decision Support は `agent.py` に接続していない。

---

## ⑤ Memory

| 名前 | 何を保存するか | どこに保存するか | いつ保存するか | 誰が読むか | 次の要求でどう参照されるか |
|------|----------------|------------------|----------------|------------|------------------------------|
| ResearchRecord | 調査の候補・Version・環境・unknowns 等 | harness 内 `ResearchStore`（メモリ） | TDA run / ingest | TDA Adapter | Agent は参照しない |
| Session（`DevelopmentSessionState`） | 束縛 Facet、last_test_result、awaiting_human_review | experimental Adapter（メモリ） | TDA 開発ループ | TDA harness | Agent は参照しない |
| RequirementFacets | 要求から抜いた技術・Python・CUDA 等 | 関数戻り値 | Reuse 判定時 | `research_reuse.py` | Agent 未接続。既定 Workflow は Discovery off |
| facet_records | Record 内の Facet 一覧 | ResearchRecord フィールド | ingest / `derive_facet_records` | bind / select / LLM 材料 | Agent 未接続 |
| DecisionFactor | 候補ごとの version / license 等 | 計算結果（永続DBなし） | Decision Support harness | TDA | Agent 未接続 |
| ResearchReuse | full / partial / no_reuse | 判定結果 | Workflow（Discovery 有効時） | TDA | 既定は off。Agent 未接続 |
| TaskState | 確定 facts / decisions / open_questions | プロセス内。prompt 用 snapshot | Clarity 後 | `agent.py` SYSTEM_PROMPT | **同一プロセス内のみ。** 次の `python agent.py` では新規 |
| research_history（TaskState） | 調査履歴 | persistence_snapshot。prompt には載せない | 一部ベンチ | 機械側 | Agent 日常経路では未確認 |
| Registry | Tool 定義 | `registry/tools.json` | 人間 / pipeline | Agent 起動時 | 次起動でも同じファイル |
| 観測ログ | capability_route / pre_web | `logs/capability_route.jsonl` | Agent 実行時 | 人間・監査 | LLM には自動では戻さない |

「A」の Follow-up 特定（TDA のみ）:

- Session の `last_research_id` / `bound_label` を使う bind（`pointer_resolution.py`）
- 推測で技術名を作らない。解けなければ `UNRESOLVED`
- ResearchRecord ID をユーザーが直接打つ前提ではない
- 文字列正規表現（「前に調べたA」等）
- Python 3.13 だけを差分にする処理は `python_version_delta.py` と Session の Version 隔離（experimental）
- 3.12 の Evidence を 3.13 にコピーしない仕組みは TDA Session 側。**Agent には無い**

---

## ⑥ Cursor との境界

| 処理 | Local Agent | Cursor | fixtureのみ | 未確認 |
|------|----------:|-----:|--------:|---:|
| Chat | 1（CLI 1要求） | 0 | 0 | UI有無はコード上 実装なし |
| LLM | 1（Ollama 実装） | 0 | 0 | 今回の実起動 |
| Tool | 1（agent 公開 6件） | 0 | 0 | Gate 対話の実操作 |
| Web Research | 1（search_web 実装） | 0 | TDA ingest | 実インターネット成功 |
| Memory（TDA） | 0 | 0 | 1 | — |
| Memory（TaskState） | 1（プロセス内） | 0 | 0 | ディスク永続 |
| File変更 | 0 | 1（編集は Cursor） | R3 runtime.py | — |
| Test | 0（Agent 自動なし） | 1（pytest 実行） | R3 fixture | — |
| Tool作成 | 0（Agent 非公開） | 1（実装作業） | pipeline 関数 | 自律一連 |

読み方: 「1」はその列の主体でコード上確認できた、という意味。Cursor 列の File変更 / Test / Tool作成は、日常の開発作業として Cursor が行っていることを指す。それを Local Agent の能力とは呼ばない。

---

## ⑦ 現在できること（コード上）

Local Agent（`python agent.py`）として言えること:

- 1件の要求を環境変数または既定文で受け取る
- Clarity で要求を確認する（LLM + 任意で TTY 入力）
- Ollama に chat し、`visibility=="agent"` の Tool を選ばせる **実装**
- GPU / CPU 状態の実測 Tool を実行する経路
- `search_web` / `read_url_text` を実行し、結果を LLM に戻す経路
- Tool 実行前の人間確認 Gate（`agent_tool_gate`）
- 観測 JSONL を残す（判断や Web 許可には使わない）
- 最終回答を stdout に出す

TDA experimental（pytest / `ai_tool/run_tda_*.py`、**Agent ではない**）:

- bind / diff / select
- Facet を少数だけ LLM 材料にする（実 LLM は R3 では未使用）
- fixture の runtime.py を変えて Test する
- Session に Test 結果を戻す

---

## ⑧ 現在できないこと

### 実装なし

- Chat 画面、メッセージ履歴 UI、Session 表示、Avatar
- 対話の第2メッセージ（Follow-up ループ）
- `write_file` によるファイル作成
- Agent から pytest / 開発 Test を自動実行して結果を返す
- Agent から ResearchRecord / DevelopmentSession を読む
- Cursor 本番 API
- 新しい Reasoning Core / Graph / RAG / Vector DB
- Tool 作成の「Proposal → 実装 → Test → Registry」自動一連を Agent が回すこと

### fixtureのみ（Cursor が harness を走らせた結果）

- R1〜R3 の bind / Coverage / Reuse / Development Spec / fixture Test
- pointer bind（「前に調べたA」）
- 3.12 Evidence を 3.13 に誤用しない Session 隔離

### 未接続

- `run_standard_workflow` と `agent.py`
- `create_tool_proposal` と Ollama schema
- ファイル Tool コードと Registry
- experimental overlay（ID 集合が空）

### 未確認（今回起動していない）

- 今このマシンで Ollama が応答するか
- `search_web` が実ネットでヒットを返すか
- Tool Gate を人間が承認したあとの実測

---

## ケース追跡

### ケース1：「hello.pyを作ってください」

指示書の矢印のうち、**実際にあるもの**と **無いもの**:

```text
User → Chat UI          実装なし（CLI 1要求のみ）
Chat → Agent            実装あり（起動すれば）
Agent → LLM             実装あり（Ollama）
LLM → Tool              実装あり（ただし write 系 Tool が Registry に無い）
Tool → File             実装なし
File → Test             実装なし
Test → Result → User    実装なし（stdout の最終回答のみ）
```

Cursor で hello.py を書くことはできる。それは Local Agent の能力ではない。

### ケース2：「Python 3.13でAが使えるか調べてください」

**実際の Agent 経路:**

```text
User → agent.py → Clarity → Ollama
  →（LLM が選べば）search_web / read_url_text
  → 結果を LLM へ → stdout
```

Goal / Gate / Discovery / Coverage / ResearchRecord / Reuse / Decision Support は通らない。

TDA 経路は `python ai_tool/run_tda_*.py` または pytest。ユーザーの日常 Chat ではない。

### ケース3：「前に調べたAをPython 3.13で使えるか調べて」

- 「A」の特定: TDA では Session の bind + 正規表現。Agent では **無い**
- Session ID: TDA Session のみ。Agent は使わない
- ResearchRecord ID: store 内照合。Agent は持たない
- 文字列一致: pointer 正規表現（experimental）
- bind: `classify_pointer`。標準 Workflow 既定には未配線
- 既存 Facet: Session のスロット。Agent 未接続
- Python 3.13 だけ差分: experimental Adapter。Agent 未接続
- 3.12 Evidence 誤用防止: TDA Session。Agent 未接続

Agent に同じ文を渡すと、前の調査記憶は無く、通常の Web Tool 依頼として扱われる（LLM 次第）。

### ケース4：「GPU温度を取得するToolを作ってください」

```text
User → Chat → Agent → 要求分類 → Tool作成判定 → Proposal → 仕様 → Code → Test → Registry
```

| 段階 | 状態 |
|------|------|
| Chat | CLI 1要求のみ |
| Agent | 実装あり |
| 要求分類 | SYSTEM_PROMPT の説明。独立した分類器は無い |
| Tool作成判定 | LLM が `create_tool_proposal` を呼べるか → **呼べない**（非公開） |
| Proposal 関数 | `tools/ai/tool_builder/proposal.py` **実装あり**（pipeline） |
| 仕様→Code→Test→Registry 自動 | **未統合** |

既存の `get_gpu_status` を **呼ぶ** ことと、**新しい Tool を作る** ことは別である。

---

## UI 監査

必須項目はすべて **存在しない**（作っていない）:

- Chat 画面 / メッセージ履歴 / Agent 回答の画面表示
- Tool 実行表示（stdout の print のみ）
- Research 表示 / エラー画面 / 実行中スピナー / Session 表示

任意項目（Tool作成、Research履歴、Memory、Facet、Test結果、Avatar）も **UI としては無い**。  
無理に作っていない。

Cursor Canvas は IDE 脇の分析画面であり、Local Agent の操作窓口ではない。

---

## 発見した問題（未修正）

1. **Prompt と Registry の不一致**（ファイル Tool）  
   影響: ファイル操作の Tool Call が失敗し得る。hello.py 作成は Agent では成立しない。  
   修正案: 名前を一致させるか、Prompt から外す。

2. **`create_tool_proposal` が Agent 非公開**  
   影響: 「Tool を作って」が提案関数に届かない。  
   修正案: 非公開を Prompt に明示するか、公開設計を別 Phase で行う。

3. **TDA が Agent 未接続**  
   影響: R1〜R3 の記憶選択は日常窓口から使えない。  
   修正案: 接続は別判断。既定 Discovery は off のまま。

4. **入口が単発 CLI**  
   影響: Follow-up と履歴が無い。  
   修正案: Chat 入口は R3.5-B 候補。

5. **experimental overlay が空**  
   影響: Registry 外 Tool は載らない。  
   修正案: 必要なものは正式登録。

---

## ⑩ UI 改良に向けた最小構成案（実装しない）

現状の `agent.py` stdout を、同じ責務のまま画面に出す程度。TDA 記憶は出さない（接続していないため）。

```text
┌─────────────────────────────┐
│ Local Agent                 │
├─────────────────────────────┤
│ Chat                        │
│                             │
│ User: ...                   │
│ Agent: ...                  │
│                             │
│ [Tool] search_web           │
│ [Gate] 確認待ち             │
│                             │
├─────────────────────────────┤
│ Chat                        │
│ （Research / Tools は後で。 │
│  今は Agent に未接続）      │
├─────────────────────────────┤
│ メッセージ             [送信]│
└─────────────────────────────┘
```

将来候補（今回対象外）: Avatar、スマートフォン、Cursor 連携、Research / Facet / Session タブ（experimental と明記する場合のみ）。

将来の責務分離（設計メモ。未実装）:

```text
Chat
 ├─ 通常依頼
 ├─ Research依頼
 ├─ Tool作成依頼
 └─ 開発依頼

Agent
 ├─ Requirement
 ├─ Goal
 ├─ Memory
 ├─ Research
 ├─ Tool
 ├─ Development
 └─ Test
```

今の実装はこの図のようには分かれていない。入口はほぼ「通常依頼 + Web Tool」だけである。

---

## 次の Phase（監査後の再判定）

指示書の順を、接続実態に合わせて調整する。

| 候補 | 内容 | 今回の判断 |
|------|------|------------|
| **R3.5-B** | 最小 Chat 入口（1往復を画面または対話に出す） | **次として妥当。** TDA は載せない |
| Prompt/Registry 一致 | ファイル Tool 名の修正 | UI より先に直した方が誤解が減るが、今回は禁止範囲のため提案のみ |
| **R3.5-C** | Tool 実行可視化 | stdout を UI に写す段階。公開 Tool が 6 件の前提 |
| **R3.5-D** | Research 可視化 | **延期推奨。** 今出すと TDA を Agent 能力と誤解する |
| **R4** | 実 LLM による最小実装 | Agent 側の Ollama 経路は既にある。TDA 側の実 LLM は別件 |
| **R5** | Tool 作成 | pipeline 関数はある。Agent 公開と自動一連は未接続 |
| **R6** | Cursor 連携 | 本番 API はまだしない |
| **R7以降** | Avatar / スマートフォン | 窓口が安定してから |

---

## 作らないもの（守った）

Standard Workflow 変更 / Production 経路変更 / facet_discovery 既定変更 / ResearchRecord・Session 仕様変更 / Tool Registry 変更 / Cursor API / 新しい Reasoning Core / Graph / RAG / Vector DB / 新しい C3 / UI 本実装 / Avatar
