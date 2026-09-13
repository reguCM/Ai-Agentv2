# AI-Agent Policy 機構 現状調査

**日付:** 2026-08-31  
**依頼:** 開発 Policy の定義・正本・Cursor/AI-Agent 参照・実行接続・強制を切り分ける。実装しない。  
**実行主体:** Cursor  
**Run:** `runs/ai_tool/20260831_113000_ai_agent_policy_mechanism`  
**判定:** `PASS`（調査項目を確認できた。Policy 機構が完成しているという意味ではない）

Cursor live: **NOT OBSERVED**  
Cursor → Local Agent: **NOT_CONNECTED**  
Machine Test: **NOT AVAILABLE**  
Production 変更: **0**  
Git commit: **していない**

---

## 判定の使い方

本文の `PASS` は調査完了のみ。次はすべて **未完成** として扱う。

- 開発 Policy Loader
- 開発 Policy の Agent CONNECTED
- 開発 Policy の ENFORCED
- 完成判定 Validator
- 仕様不足時の Human 相談経路（開発仕様）
- 仮仕様の状態保存

---

## 1. 既存 Policy / 指針の一覧

全部を列挙すると TDA・Tool 個別文書が膨大になる。ここでは **開発思想・Agent 拘束・実行 Gate** に関係するものに限定する。個別 Tool の SPECIFICATION / CHANGE_POLICY のコピー（`runs/` 配下）は正本候補から除外する。

| ファイル | 種類 | Agent.py が読むか | 備考 |
|----------|------|-------------------|------|
| `.cursor/rules/agent-development-policy.mdc` | Cursor Rule（`alwaysApply: true`） | **読まない** | 開発作業方針 v1.0 + v1.1 追記 |
| `PROJECT_SPEC.md` | プロジェクト意図 | **読まない**（§9 仕様比較でも未接続） | Tool 優先・人間承認・会話を仕様にしない |
| `docs/current_system_specification.md` | 構想 vs 実装の比較表 | **読まない** | 「仕様書を Agent が拘束する機構は無し」と明記 |
| `docs/ai_tool/project_audit/KNOWN_GAPS.md` | ギャップ記録 | **読まない** | 未完成の棚卸し |
| `docs/ai_tool/project_audit/README.md` | 監査の判定ルール | **読まない** | ファイル≠完成、テスト≠ Agent から使える |
| `docs/ai_tool/tool_creation/TOOL_CHANGE_POLICY.md` | Tool 変更方針 | **読まない** | 文書。自動判定 NOT READY |
| `docs/ai_tool/tool_creation/URL_FETCH_SAFETY_POLICY.md` 等 | Tool 作成系 | **読まない** | Validator は Tool 作成パイプライン側 |
| `tools/system/agent_tool_gate.py` | Tool 実行確認 Policy | **読む**（`execute_tool` → `authorize_tool_execution`） | 確認/auto_allow。開発完成判定ではない |
| `tools/ai/state/execution_gate.py` | Research Safety Gate | **読まない** | `agent.py` は非統合と明記 |
| `agent.py` `SYSTEM_PROMPT` | 実行時指示 | **LLM に渡す** | 観測の推測禁止。開発 Policy ファイルは埋め込まない |
| `ai_tool/chat_interface/agent_turn.py` `SYSTEM_PROMPT` | Chat 指示 | **Chat LLM に渡す** | 同上 |
| Matrix ingest の Entity/Source check | 保存前検証 | Matrix ingest 経路 | 開発 Policy ではない |
| `ai_tool/defensive_core_discovery_policy.py` | TDA 評価ハーネス | `agent.py` から呼ばない | HUMAN_REVIEW_REQUIRED 等は評価レポート用 |
| `docs/ai_tool/project_audit/DEFENSIVE_CORE_DISCOVERY_POLICY.md` | 上記の文書 | 読まない | |

`.cursor/rules/` は **1 ファイルのみ**。glob / Agent Requested / Manual の別ルールファイルは **無い**。

### `agent-development-policy.mdc` に既にある項目

| 項目 | 文書上 |
|------|--------|
| 調査 → 観測 → 設計 → 実装 → 実測 → テスト → 回帰 → 報告 | **ある** |
| 推測禁止（原因） | **ある** |
| NOT_OBSERVED / NOT_DETERMINED / NOT_CONNECTED | **ある** |
| 最小＝簡単な実装ではない | **ある** |
| 既存を読んでから実装（再実装しない趣旨） | **部分**（手順 1。文言「再実装するな」は無し） |
| 部品と完成の混同禁止 | **ある**（v1.1） |
| 未完成を完成扱いしない | **ある**（v1.1） |
| 仕様未確定なら相談 | **ある**（v1.1） |
| 仮仕様なら明示 | **ある**（v1.1） |
| テスト成功≠仕様完成 | **ある**（v1.1） |
| 観測性優先 | **ある** |
| 再発防止優先 | **ある** |
| 過去原因を証拠なく追及しない | **ある** |

このファイルを今回 **書き換えていない**。

---

## 2. 正本

**POLICY_SOURCE_UNCLEAR**

勝手に一本化しない。根拠:

- Cursor 開発作業の正本候補: `.cursor/rules/agent-development-policy.mdc`（`alwaysApply`）
- プロジェクト意図の正本候補: `PROJECT_SPEC.md`
- 実装度比較の正本候補: `docs/current_system_specification.md`
- Tool 実行確認の正本: `agent_tool_gate.py`（コード。開発思想文書とは別系統）
- Research 実行 Gate の正本: `execution_gate.py`（`agent.py` と非統合）

重複: 「推測するな」「人間承認」が Cursor ルール / PROJECT_SPEC / SYSTEM_PROMPT / Tool Gate に別契約で存在する。  
食い違いの例（推測せず事実のみ）:

- Cursor ルールは開発の完成判定に PARTIAL_PASS を使う。Agent SYSTEM_PROMPT にはその語が無い。
- `agent_tool_gate` は人間確認。`execution_gate` は Safety/Compat。両者はコード上非統合（`agent.py` コメントおよび `agent_tool_gate.py` 先頭）。
- PROJECT_SPEC は「会話を仕様にするな」。Cursor ルールは会話中の Cursor に適用される。衝突というより **適用主体が違う**。

後から追記: Cursor ルールの「未完成・接続・仮仕様」節は **v1.1 追記** とファイル内に書いてある。PROJECT_SPEC 側への同期は **していない**。

---

## 3. Cursor の適用経路

| 層 | 確認できたこと | 判定 |
|----|----------------|------|
| DEFINED | `.cursor/rules/agent-development-policy.mdc` が存在する | DEFINED |
| REFERENCED | YAML `alwaysApply: true`。他ルールファイル無し。glob 無し | REFERENCED（Cursor Rules 指定） |
| CONNECTED | 本リポジトリの Python がこのファイルを `open` するコードは **無い**。Cursor 製品が Agent 文脈に入れることは、ファイル指定からは **想定される** が、Cursor 内部の注入を本調査で機械確認してはいない | CONNECTED は Cursor 製品仕様に依存。リポジトリコードからは **NOT_CONNECTED**。Cursor 作業への適用は **NOT_OBSERVED**（製品内部）／運用上は alwaysApply を根拠にするなら REFERENCED まで |
| ENFORCED | Cursor 出力を Policy 違反で reject するコードはリポジトリに **無い** | **NOT_IMPLEMENTED** |

厳密に書くと: **リポジトリ内では REFERENCED（alwaysApply フラグ）。実行時 CONNECTED / ENFORCED は Cursor ランタイムの範囲で、本コードベースでは NOT_OBSERVED / NOT_IMPLEMENTED。**

---

## 4–5. AI-Agent 参照経路

確認した起動経路:

```text
agent.py
  → registry/tools.json を読む
  → SYSTEM_PROMPT（ソース内リテラル）を messages へ
  → LLM
  → Tool 選択
  → execute_tool
      → agent_tool_gate.authorize_tool_execution
      → Tool
  → 結果を messages へ
```

`read_policy()` / Policy Loader / 開発 Policy の Context 注入は **無い**（リポジトリ grep: `read_policy` `load_policy` `policy_loader` `agent-development-policy` の Python 参照なし）。

Planner / Controller モジュールとしての開発 Policy 入力は **無い**。`agent.py` の Actor は `PROJECT_AGENT`。独立 Planner クラスは無い。

| 段階 | 開発 Policy ファイル | 別系統で存在するもの |
|------|----------------------|----------------------|
| A 読む | **なし** | `registry/tools.json`、trust JSON |
| B LLM へ | SYSTEM_PROMPT リテラルのみ。mdc / PROJECT_SPEC を連結しない | 観測ルール（unknown を埋めない等） |
| C 出力検証 | 開発 Policy Validator **なし** | Tool 名の Gate。Research の `decide_execution_gate` は **非接続** |
| D 違反で行動変化 | 開発 Policy 違反の Reject/Re-plan **なし** | Tool: deny / 確認待ち。Safety Gate: Block（Pipeline のみ） |

**「Policy を読んでいる」≠「開発思想 mdc を読んでいる」。** Tool trust を読むことは ENFORCED だが、対象は Tool 実行許可であり、未完成禁止・仮仕様・テスト≠完成ではない。

Chat 経路: `run_chat_turn` → 同様に `SYSTEM_PROMPT` リテラル + `authorize_tool_execution`。`alwaysApply` の mdc は渡さない。

---

## 6. System Prompt（文章 vs 強制）

### `agent.py` SYSTEM_PROMPT（確認した内容）

| 項目 | 文章 | 機械強制 |
|------|------|----------|
| 推測禁止（観測値） | ある（unknown を 0 で埋めない、想像するな、未確認と書け） | LLM 指示のみ。Validator なし → **CONNECTED して ENFORCED ではない** |
| Tool 結果の捏造禁止 | ある（hits/main_text に無い事実を補完するな） | 同上。一部は後段の web_status 等で **別系統 ENFORCED の可能性**（開発 Policy ではない） |
| 未完成を完成扱いしない | **無い** | — |
| 仕様不足時に相談 | **無い**（「未確認と書け」は相談経路ではない） | — |
| 仮仕様を明示 | **無い** | — |
| テスト≠仕様充足 | **無い** | — |
| 開発 Policy を遵守 | **無い** | — |

### Chat `agent_turn.py` SYSTEM_PROMPT

観測を求めたら Tool、Web 数値を補完するな、ファイル作成するな。開発完成・相談・仮仕様・Policy 遵守は **無い**。

---

## 7. 状態管理（要求→実装→検証→観測）

`CONNECTED` / `PARTIAL` / `NOT_IMPLEMENTED` を **Task 状態機械** として持つ機構は、`agent.py` のタスクループに **無い**。

存在する近いもの（別目的）:

- `task_state` / Clarity Gate（要求の明確化）。開発 Policy 状態ではない
- Chat `activity.py` の Event と `NOT_OBSERVED` ラベル（ターン観測。完成検査ではない）
- Research / TDA ハーネスの `PASS` / `PARTIAL_PASS` / `HUMAN_REVIEW_REQUIRED`（評価レポート。Agent ループに未接続）
- Matrix ask の `decision: SUFFICIENT|INSUFFICIENT`（知識十分性。開発 Policy ではない）

**開発 Task の項目別状態管理: NOT_IMPLEMENTED**

---

## 8. 完成判定

`COMPLETION_VALIDATION = NOT_IMPLEMENTED`

Agent が「実装完了」の前に要求項目ごとの CONNECTED 検査をするコードは **無い**。  
pytest 成功を完成ゲートにするコードも `agent.py` には **無い**（人間/Cursor の運用で pytest を走らせることはある。それは機構ではない）。

---

## 9. 仕様不足時の相談

| 経路 | 有無 |
|------|------|
| SYSTEM の「相談してください」 | 開発仕様については **無い** |
| Tool 実行前の人間確認 | **ある**（`agent_tool_gate`、Chat も `authorize_tool_execution`） |
| `apply_human_decision` | **ある**が `execution_gate` 系。`agent.py` 非統合 |
| 仕様不足 → Question 生成 → Pending → 停止 → 回答後再開 | **NOT_IMPLEMENTED** |
| 仕様不足 → 仮仕様明示して継続 | 文章契約は Cursor ルールのみ。Agent 経路 **NOT_IMPLEMENTED** |
| 仕様不足 → 勝手に決定 | 禁止する機械は無い。LLM は SYSTEM どおり動く可能性。**ENFORCED ではない** |

Tool 確認待ちを「仕様相談」と同一視しない。

---

## 10. 仮仕様

`EXPERIMENTAL` / `PROVISIONAL` / `ASSUMPTION` を開発仕様の状態として保存する Agent 機構は **無い**。

Catalog の `tool_status` や文書の EXPERIMENTAL は Tool ライフサイクルであり、仮仕様レジストリではない。

LLM が文章で「仮です」と書くことだけなら **INTERFACE_ONLY**（契約も保存も無し）。

---

## 11. 1対1 対応表

| Policy / 仕様 | 定義場所 | Agent参照 | 実行時接続 | 強制 | テスト | 状態 |
| ----------- | ---- | ------- | ----- | ----- | ----- | --- |
| 未完成を完成扱いしない | Cursor ルール v1.1。KNOWN_GAPS / 監査 README | なし | なし | なし | 方針ファイルのテストなし | DEFINED（Cursor）。Agent: NOT_CONNECTED |
| 仕様不足時に相談 | Cursor v1.1。PROJECT_SPEC §3.3 はアーキ変更の人間承認 | なし（開発仕様） | Tool Gate のみ別系統 | Tool 実行確認はあり。仕様相談はなし | Tool Gate のテストあり | 仕様相談: NOT_IMPLEMENTED。Tool 確認: ENFORCED（別Policy） |
| 仮仕様の明示 | Cursor v1.1 | なし | なし | なし | なし | DEFINED（Cursor）。Agent: NOT_IMPLEMENTED |
| 推測禁止 | Cursor（原因）。agent.py / Chat SYSTEM（観測） | SYSTEM を読む | LLM 入力 CONNECTED | 開発原因は強制なし。観測捏造は指示のみ | 観測ラベルのテストは部分あり | Cursor DEFINED。Agent 観測: CONNECTED 非 ENFORCED |
| 最小＝簡単ではない | Cursor ルール | なし | なし | なし | なし | DEFINED（Cursor）。Agent: NOT_CONNECTED |
| テスト≠仕様完成 | Cursor v1.1。監査 README | なし | なし | なし | pytest≠完成の機械Gateなし | DEFINED（Cursor）。Agent: NOT_CONNECTED |
| 調査→報告の順序 | Cursor ルール | なし | なし | なし | なし | DEFINED（Cursor）。NOT_CONNECTED |
| 既存機能を再実装しない | Cursor 手順1。PROJECT_SPEC 3.2 | なし（Registry は読む） | Tool 発見は Registry。方針検査なし | なし | なし | DEFINED 部分。ENFORCED なし |
| Tool 実行の人間確認 | `agent_tool_gate.py` | あり | `execute_tool` / Chat | **ENFORCED** | `tests/test_agent_tool_gate.py` | CONNECTED + ENFORCED（Tool許可のみ） |
| Research Safety Gate | `execution_gate.py` | agent.py からなし | Pipeline の verify 等 | Pipeline 内 ENFORCED | `tests/test_phase_d*.py` | Agent 経路: NOT_CONNECTED |
| Matrix Entity/Source | ingest | Matrix ask/ingest | write 直前 | **ENFORCED**（保存拒否） | matrix テスト | 開発 Policy ではない。知識保存の ENFORCED |

---

## 12. Cursor と AI-Agent の差

```text
                    Cursor                         AI-Agent (agent.py / Chat)
Policy定義          mdc v1.0+v1.1 DEFINED          開発思想は未読込。観測ルールは SYSTEM リテラル
Policy参照          alwaysApply REFERENCED         開発mdc 参照コードなし
LLM入力             Cursor製品（NOT_OBSERVED）     SYSTEM_PROMPT リテラル CONNECTED
状態管理            なし（報告運用）               開発項目状態 NOT_IMPLEMENTED
Validator           NOT_IMPLEMENTED                開発Policy NOT_IMPLEMENTED
Tool制御            なし（IDE）                    agent_tool_gate ENFORCED
完成判定            方針文のみ                     NOT_IMPLEMENTED
Human相談           方針「相談する」               Tool確認のみ。仕様相談 NOT_IMPLEMENTED
仮仕様管理          方針文のみ                     NOT_IMPLEMENTED
テスト              ルールファイル未テスト         Tool Gate / 観測ラベルはテストあり
Policy違反検出      NOT_IMPLEMENTED                開発Policy NOT_IMPLEMENTED
```

Cursor の alwaysApply を Agent に移植する必要はない。Agent 側で強くできる箇所（候補であり未実装）:

- 要求項目の構造化状態（CONNECTED/PARTIAL/…）
- 完成 Validator（全項目検査）
- 仕様不明の Pending + 人間質問
- LLM 判断の機械検証（SYSTEM 文章の強制ではない）
- Tool Gate とは別の「開発 Policy Gate」

既存の `agent_tool_gate` と `execution_gate` を流用するなら、**統合しないと明記されている**ので、勝手にマージしない。次設計の相談事項。

---

## 13. 理想構造との差分

```text
理想                         現状
Policy                       複数文書。Loader なし
Task                         agent.py はユーザー要求 + Tool ループ
Requirements Extraction      Clarity Gate は部分。開発要件分解ではない
Plan                         独立 Planner なし
LLM                          SYSTEM リテラル
Structured Decision          なし（Tool call JSON のみ）
Policy Validator             なし
Tool Controller              execute_tool + tool_gate（許可のみ）
Tool                         Registry
Observation                  Tool 結果 + Chat activity
State Update                 messages 履歴。項目状態なし
Completion Validator         なし
  未完成 → 継続              なし
  不足 → Research            Chat/agent から TDA Research は NOT_CONNECTED
  仕様不明 → Human           Tool 確認のみ
  Policy違反 → Reject        開発Policy なし。Tool deny はある
  全項目確認 → Complete      なし
```

---

## 14. 次の実装候補（最大 5。今回は作らない）

調査結果で **未存在** のものだけ。Tool Gate の再提案はしない。

1. **開発 Policy の正本を決める（設計相談）** — Loader の前に POLICY_SOURCE_UNCLEAR を解消しないと二重拘束になる。  
2. **項目別状態（CONNECTED / PARTIAL / NOT_*）を Task に持つ** — Completion Validator の前提。  
3. **Completion Validator** — 「完了しました」の前に項目検査。pytest 成功を完成に使わない。  
4. **仕様不足 Human Gate** — Question / Pending / 再開。既存 Tool 確認と混ぜない。  
5. **Structured Decision + 開発 Policy 検査** — LLM 出力を文章遵守に頼らない。SYSTEM に mdc 全文を貼るだけは ENFORCED にならない。

Policy Loader 単体や SYSTEM への全文注入は、正本未確定のままやるとドリフトする。1 より後がよい。

---

## 調査完了チェック

- 既存 Policy 列挙: した  
- 正本: **POLICY_SOURCE_UNCLEAR**  
- Cursor 適用: alwaysApply REFERENCED。コード CONNECTED/ENFORCED なし  
- AI-Agent 適用: 開発 mdc **NOT_CONNECTED**。観測 SYSTEM **CONNECTED 非 ENFORCED**  
- SYSTEM 接続: リテラルのみ  
- Tool Controller: 実行許可 Gate のみ  
- 開発 Validator: **NOT_IMPLEMENTED**  
- 完成判定: **NOT_IMPLEMENTED**  
- Human 仕様相談: **NOT_IMPLEMENTED**  
- 仮仕様管理: **NOT_IMPLEMENTED**  
- 対応表: 本ファイル  
- 理想差分: 本ファイル  
- 候補 5 件: 実装していない  
- コード変更: **なし**
