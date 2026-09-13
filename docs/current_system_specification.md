# Project 現状仕様書（実コード棚卸し）

**status:** 実コード根拠の棚卸しスナップショット
**date:** 2026-08-21  
**作成主体:** CURSOR_VALIDATION（棚卸し・文書化のみ。能力試験実績ではない）  
**前提:** F-002 追加実装は停止。本文書作成時点で**新規コード変更は行っていない**（既にディスク上にある実装を記述する）。

> **鮮度について:** 本文中の構成値は調査日時点の記録であり、現在のbranch、HEAD、
> working tree、設定値を固定する正本ではない。変動する値はSession開始時にRepositoryの
> 実態から再取得する。開発・Git・検証の手順は関連Policyを正本とし、本書は実装仕様を扱う。
>
> **入口追記（2026-09-09）:** §4.1 は調査日時点の `agent.py`（PROJECT_AGENT スクリプト）。
> 現行 Chat Production / Chat UI の入口は `run_chat_turn`（`ai_tool/chat_interface/agent_turn.py`）。
> `agent.py` 廃止ではない。Chat 経路の search hit 後 pending observation → Help 確認の
> `workspace_file_read` → Runtime 注入は H4 Core の Runtime bridge であり、意味判断の正本ではない。
> 本追記は入口と bridge の位置づけ同期であり、§4 本文の全面改訂ではない。

---

## 0. 文書の目的と読み方

| すること | しないこと |
|----------|------------|
| リポジトリに存在する経路・契約・境界を事実として記述する | あるべき理想アーキのみを書く |
| PROJECT_AGENT と RESEARCH_PIPELINE を分離して書く | 「Agent」と曖昧に総称する |
| 未実装・未完了・既知ギャップを明記する | 能力試験の合格宣言 |

関連するが役割が違う既存文書:

| 文書 | 役割 |
|------|------|
| 構想書（V1基本設計書） | 長期理念・原則・意図的未決定・将来像 |
| `docs/v1_basic_specification.md` | **V1で何を満たすか／将来機能を必須化しない規範** |
| `PROJECT_SPEC.md` | プロジェクト意図・環境の概要 |
| `docs/architecture.md` | 自己修復／Tool Builder パイプライン仕様 |
| `docs/autonomous_research_architecture.md` | Research/Judge/State の設計と Phase 経緯 |
| `docs/DEVELOPMENT_TEST_POLICY.md` | **テスト階層、E2E Goal Acceptance、Verification Budgetの正本** |
| **本仕様書** | **いま動くコードの棚卸し（現状）** |

---

## 1. リポジトリ構成（現状）

```text
D:\AI-Agent\
├─ agent.py                 # PROJECT_AGENT 入口（スクリプト実行）
├─ config/
│  ├─ pipeline.yaml         # active_model, rounds, Clarity/Pipeline設定
│  └─ llm_models.yaml       # LLMプロファイル
├─ registry/
│  └─ tools.json            # Tool登録 + visibility
├─ tools/
│  ├─ system/               # 機械側（LLM client, Tool Builder, GPU/CPU, network, file安全, identity）
│  ├─ file/workspace/       # Agent向け File Tool
│  └─ ai/                   # 材料・State・prompts・Judge周辺
├─ research/
│  ├─ llm_benchmarks/       # RESEARCH_PIPELINE ベンチ・観測（仕様本体ではない）
│  └─ benchmarks/           # Phase/KSS ベンチランナー・デバッグ（本番契約外）
├─ tests/                   # unittest
└─ docs/                    # 設計・観測メモ
```

Python 実行環境の慣例: `.venv`。LLM 実行時: Ollama（既定 `http://127.0.0.1:11434`、`OLLAMA_HOST` で上書き可）。

---

## 2. 実行主体の定義（コード上の名称）

`tools/system/execution_identity.py` に定数として存在する:

| 名称 | 意味（現状） |
|------|----------------|
| `PROJECT_AGENT` | `agent.py` を入口とする課題遂行 |
| `PROJECT_AGENT_LLM` | Agent から呼ばれる Ollama 上のモデル |
| `RESEARCH_PIPELINE` | `research.llm_benchmarks.research_implement` 等 |
| `LOCAL_JUDGE` / `GLOBAL_JUDGE` | 名称定数。Judge は**実行主体ではない** |
| `PLAN_GATE` | 名称のみ。**未実装** |
| `CURSOR_*` / `HUMAN` / `UNKNOWN` | 報告・ログ用ラベル |

**ログ:** `AI_AGENT_EXECUTION_LOG` または `logs/execution_identity.jsonl`。  
`agent.py` 起動時 `agent_start`、Tool 時 `tool_call` / `tool_result`。  
`research_implement.main` 起動時 `pipeline_start`（`RESEARCH_PIPELINE`）。

Judge に主体判定をさせる仕組みは**無い**。

---

## 3. 設定

### 3.1 `config/pipeline.yaml`（ファイル上の既定）

| キー | 現状値（ファイル） |
|------|-------------------|
| `active_model` | `qwen3_14b` |
| `max_tool_rounds` | `5` |
| `max_research_rounds` | `10` |
| `max_research_stagnation` | `3` |
| `max_clarity_rounds` | `5` |
| `max_repair_rounds` | `3` |
| `project_context.implementation_method_selection` | `Agent` |

### 3.2 モデル解決

- `tools.system.config.active_model_id()`: 環境変数 `AI_AGENT_MODEL` があれば優先、なければ `pipeline.yaml` の `active_model`
- プロファイル実体: `config/llm_models.yaml`（例: `qwen3_8b` → Ollama 名 `qwen3:8b`）

**注意:** 作業シェルに `AI_AGENT_MODEL=qwen3_8b` が残っている場合、ファイル既定と実行時モデルが一致しない。仕様上は「yaml 既定 + env 上書き」が正しい記述である。

### 3.3 LLM クライアント

`tools/system/llm.py`: `ollama.Client`、timeout / `num_predict` / `temperature` 等はプロファイルから。

---

## 4. 二つの主入口（最重要の分離）

### 4.1 PROJECT_AGENT — `agent.py`

```text
起動
 → execution_identity: agent_start (PROJECT_AGENT)
 → Clarity (run_clarity_gate)
 → clear でなければ終了
 → Registry から visibility=agent のみ Ollama tools 化
 → related_tools / reference（Builder Tool は検索から除外）
 → Tool ループ (max_tool_rounds)
      chat(tools=agent公開Tool)
      tool_calls があれば
        execute_tool
          → agent_tool_gate（未昇格は人間確認。Research Safety とは非統合）
          → 許可時のみ実関数実行 / 拒否時は blocked 結果を LLM へ
        messages に raw result を append   # F-001 修正後の能力経路
        stdout 用 summarize（失敗しても能力経路を止めない）
 → 最終テキスト / 提案検証（提案系は現行公開Tool外）
```

**特徴（現状）:**

- Research/Judge ループは **持たない**（`rule_partial` / `global_judge_trigger` / `create_research_judgment` を呼ばない）
- Ollama に載るのは `visibility=agent` の 7 Tool のみ
- Tool 実行は **デフォルト人間確認**（`tools/system/agent_tool_gate.py` + `registry/agent_tool_trust.json`）。`auto_allow` 昇格のみ確認省略。降格可。自動危険分類はしない
- **capability_route 観測**（`tools/system/capability_route_obs.py`）: Toolループ前に `pre_web_answer_candidate`、ループ後に `agent_continue` / `needs_new_tool` / `uncertain` 等を記録するだけ。**Pipeline起動・Tool実行許可・Web有益判定には使わない**
- `create_tool_proposal` 等は Registry に残るが **pipeline** のため Agent LLM には非公開
- `USER_REQUEST` は `agent.py` 内の定数（実験時に差し替える運用あり）

### 4.2 RESEARCH_PIPELINE — 主に `research/llm_benchmarks/research_implement.py`

```text
Clarity相当STATE / Case
 → Proposal → Research ↔ Judge（trigger / live skip）
 → progress 機械判定
 → Implementation → validate → register → test
```

詳細設計の正本は `docs/autonomous_research_architecture.md` / `docs/architecture.md`。  
ベンチ・観測スクリプトが `research/benchmarks/` と `research/llm_benchmarks/` に集約（`knowledge_source_obs` 等）。**これらは PROJECT_AGENT 能力実績ではない。**

---

## 5. Registry と Tool 公開契約

ファイル: `registry/tools.json`

### 5.1 `visibility`

| 値 | 意味（現状実装） |
|----|------------------|
| `agent` | `create_ollama_tools()` が Ollama へ公開 |
| `pipeline` | Registry には残るが Agent の Ollama tools には載せない |
| `internal` | フィールドとしては導入済みの概念。現状 Registry エントリは agent/pipeline のみ |

### 5.2 Agent 公開 Tool（7）

| name | module | 役割要約 |
|------|--------|----------|
| `get_gpu_status` | `tools.system.gpu.gpu_status` | nvidia-smi 実測 |
| `get_gpu_processes` | `tools.system.gpu.gpu_processes` | GPU プロセス実測 |
| `cpu_status` | `tools.system.cpu.cpu_status` | CPU 負荷取得 |
| `search_web` | `tools.system.network.search_web` | **一般Web検索**（下記） |
| `list_files` | `tools.file.workspace.list_files` | Workspace 一覧 |
| `read_file` | `tools.file.workspace.read_file` | テキスト読取 |
| `search_files` | `tools.file.workspace.search_files` | テキスト検索 |

`create_ollama_tools`: `input` の `required: true` から Ollama `parameters.required` を生成。

### 5.3 Pipeline 登録 Tool（14・非Ollama）

`create_tool_proposal`, `create_tool_implementation`, `validate_*`, `register_tool`, `test_tool`, `repair_tool`, `apply_repair`, `research_tool`, `research_executor`, **`web_research`**, `research_verifier`, `research_result_validator`, `research_result`

**`web_research`:** 検索実行ではない。検索結果の**材料化**。Agent 非公開。説明文でも「Web検索を実行するToolではない」と明記。

### 5.4 `BUILDER_TOOLS`（`tools/system/tool_builder/search.py`）

関連 Tool 検索から Builder/Research 名を除外。Ollama 公開フィルタ（visibility）とは別レイヤ。

---

## 6. Web 検索（二重経路）

### 6.1 PROJECT_AGENT 向け（現状ディスク）

```text
agent search_web
 → tools.system.network.general_web_search.general_web_search
 → backends: duckduckgo, wikipedia-ja, wikipedia-en
 → fetch_limit で候補収集 → query語句 ranking → return_limit 件
 → HIT_KEYWORDS / Microsoft Learn は使わない
```

| 項目 | 現状 |
|------|------|
| 既定 return | `DEFAULT_RETURN_LIMIT = 5` |
| fetch | `max(DEFAULT_FETCH_LIMIT, return_limit)`。`limit=1` でも内部は複数寄せてから絞る |
| Pipeline コア呼び出し | **しない**（`research.web.search_web` を呼ばない） |

`agent.py` SYSTEM_PROMPT に「Web調査の手順」（関連性確認・再検索・hitsのみ根拠・確認不能時は未確認）が**既に含まれている**。

### 6.2 RESEARCH_PIPELINE 向け（未変更方針の対象）

```text
research.executor
 → tools.system.tool_builder.research.web.search_web
 → learn.microsoft-en/ja → duckduckgo → wikipedia(ja)
 → rank_hits(HIT_KEYWORDS) …
 → （別途）filter_relevant_hits
 → web_research 材料化 等
```

**F-002 対応としてこのファイルを変えない、が現行方針。** 実ファイルも MS Learn + HIT_KEYWORDS のまま。

### 6.3 既知ギャップ（棚卸し時点）

- Agent 一般検索経路はコード上分離済みだが、直近の PROJECT_AGENT 再試験では **backends は一般系でも hits が空**となるケースが観測された（DDG Instant Answer の空/JSONDecode 等）。  
- 「一般検索の品質完遂」「hits 根拠回答の安定」は**未完了課題**として残る。  
- F-002 追加実装は**停止中**。

---

## 7. File Tool（Workspace）

| Tool | 制約（`tools/file/workspace/_paths.py`） |
|------|------------------------------------------|
| root | リポジトリ root（`registry/tools.json` 存在で固定）。**cwd 非依存** |
| 禁止 | `..`、root 外絶対パス、解決後の root 外（symlink 抜け含む） |
| 上限 | list 件数、read バイト、search 走査/マッチ数 |
| バイナリ | 無制限読取禁止 |

LLM がディスクを直接見ることはない。Tool 経由のみ。

---

## 8. F-001（stdout 要約と能力経路）— 現状は修正済み

```text
execute_tool → raw result
  ├─ messages.append(raw)     # 先（能力経路）
  └─ print_tool_result_for_stdout / summarize  # 後・失敗しても握りつぶし
```

`registry_tool_count` は `create_tool_proposal` 要約専用。非 proposal は参照しない。

---

## 9. Judge / Research 監督（Pipeline 側）

| 部品 | 場所 | 役割（要約） |
|------|------|----------------|
| Rule Partial | `tools/ai/state/rule_partial.py` | verify 後の局所 State / escalation |
| Research Judge | `tools/ai/tool_builder/research_judge.py` | satisfies_request / missing 材料 |
| Global Judge trigger | `tools/ai/state/global_judge_trigger.py` | LLM Judge の間引き・shadow |
| Progress | `tools/system/tool_builder/research/progress.py` | IMPLEMENT/CONTINUE/STOP 機械判定 |
| Memory Judge | `tools/ai/state/memory_judge.py` | 既定 OFF 寄りの選別 |

**PROJECT_AGENT（agent.py）はこれらを実行しない。**  
Judge は結果の妥当性評価であり、実行主体の証明ではない。

---

## 10. Safety / Trusted Personal / Observation

### 10.1 PROJECT_AGENT Tool Gate（V1最小・別系統）

- 実装: `tools/system/agent_tool_gate.py`
- 信頼リスト: `registry/agent_tool_trust.json`（初期 `auto_allow: []`＝全Tool確認）
- 配線: `agent.py` の `execute_tool` のみ
- 昇格/降格: `python -m tools.system.agent_tool_gate promote|demote|list <name>`、または確認プロンプトで `always`
- 退避: `AI_AGENT_TOOL_GATE=off`（常用しない）。IDENTITY_SMOKE のみ `bypass_tool_gate=True`
- **Research の `decide_execution_gate` / Trusted Personal とは混同・統合しない**

### 10.1b capability_route 観測（G2・実行非接続）

- 実装: `tools/system/capability_route_obs.py`
- **pre_web**: Toolループ**前** — `pre_web_answer_candidate`（Webなしで生成可能な回答候補。本番 `messages` には混ぜない。Web未実行時も記録）
- **Stage 1** 配線: `agent.py` Toolループ**後** — `capability_route_observation`（判断記録のみ）
- **Stage 2** 配線: 最終回答（提案修正後を含む）の**後** — `capability_outcome_compare`（判断→実行→回答表面の比較）
- 同一 `observation_id` で `pre_web_answer_candidate` / `web_search.judgment` / `web_search.execution` / `final_answer` を関連付け
- Stage2 `chain` は `web_search_results`（検索結果ダイジェスト）と `final_answer` を**分離**して記録する
- ログ: `logs/capability_route.jsonl`（`AI_AGENT_CAPABILITY_ROUTE_LOG`）+ identity イベント `pre_web_answer_candidate_observed` / `capability_route_observed` / `capability_outcome_compared`
- `web_search.judgment` と `web_search.execution` を分離。Stage2は `chain` + `web_pattern`（例: `web_judged_called_empty_hits_answer_failure_candidate`）
- 回答の `success_candidate` / `failure_candidate` は**表面プロキシ**であり真の正誤ではない（`not_ground_truth`）
- **Webあり／なしの正誤・有益性の自動判定はしない**（人間比較用データのみ）
- **Stage 3** 誤判定分類・**Stage 4** 判定方式改善は未実装（`misjudgment_classification: null`）
- **route / pattern / pre_web は Pipeline起動・Gate許可・Web実行許可に使わない**
- 観測スキップ（収集以外の緊急時）: `AI_AGENT_SKIP_PRE_WEB=1`（本番経路の常用は想定しない）
- **ログ収集**: 普段の `agent.py` 利用で `logs/capability_route.jsonl` に蓄積。意図的多様ケースは `research/llm_benchmarks/capability_route_cases/`（`run_collection.py`）。収集時は `AI_AGENT_TOOL_GATE=off` を使わず collection trust で公開Toolを昇格

### 10.2 RESEARCH_PIPELINE 側（従来）

コード上存在する主なもの（詳細は各モジュール・Phase 文書）:

- `execution_gate`, `generated_code_safety`, `llm_safety_analysis`, `safety_assessment`
- `trusted_personal_policy`, `execution_observation`, `git_workspace_facts`
- GPU は `observation_source: real`（nvidia-smi）

Observation Validator の本格導入は、過去方針上「まだ」の整理が残る領域（本棚卸しでは「存在する観測・Safety 部品」まで）。

---

## 11. テストと検証の層

| 層 | 例 | 能力実績 |
|----|-----|----------|
| unittest | `tests/test_*.py` | CURSOR_VALIDATION |
| 検証スクリプト | `research/benchmarks/verify/_verify_*.py` | CURSOR_VALIDATION |
| ベンチ | `research/llm_benchmarks/*`, `research/benchmarks/phases/*` | RESEARCH_PIPELINE / 観測 |
| `agent.py` + identity ログ | 手動/Controller 起動 | **PROJECT_AGENT** のみ認定可 |

---

## 12. 能力測定で使う正式分類（運用契約）

| 分類 | 意味 |
|------|------|
| PROJECT_AGENT_SUCCESS / FAILURE / PARTIAL | agent.py 経路の結果 |
| RESEARCH_PIPELINE | research_implement 等 |
| CURSOR_VALIDATION | Cursor の単体・構造確認 |
| CURSOR_EXPLORER / CURSOR_SHELL | 代行調査・直接実行 |
| HUMAN_RUN | 人間直接起動 |
| UNKNOWN | 主体証明不可 |

「Agentが成功した」という曖昧表現は使わない。

---

## 13. 未実装・明示的に無いもの

| 項目 | 現状 |
|------|------|
| PLAN_GATE（構想承認ゲート） | 未実装（定数名のみ） |
| Observation Validator 本実装 | 方針議論あり・本仕様では未完了扱い |
| agent.py 内 Local/Global Judge | 無し |
| Agent と Pipeline の単一統合ループ | 無し（二入口） |
| F-002「一般検索で安定して非空・関連 hits → 根拠回答」 | **未完了**（経路分離コードは存在） |

---

## 14. 最近の変更履歴（棚卸し上の事実）

| ID | 内容 | 状態 |
|----|------|------|
| Tool visibility | agent/pipeline 分離、Ollama は agent のみ | 実装済 |
| Agent File Tool | list/read/search + root 固定 | 実装済 |
| Actor Identity | start/tool ログ | 実装済 |
| F-001 | summarize と messages 分離 | **修正済** |
| F-002 | Agent 一般検索分離 + SYSTEM 手順 | **コード一部投入済・追加実装停止・品質完遂は未確認** |

---

## 15. 現状の一行まとめ

このリポジトリは、(1) **`agent.py` による薄い Tool-calling Agent（観測・File・一般Web）** と、(2) **`research_implement` 系の重い Tool Builder / Research / Judge パイプライン** が並存する。Registry の `visibility` と execution_identity で境界を記録する段階まで来ているが、**一般Web Research の「関連ヒット取得〜根拠回答」は未完了**であり、F-002 追加実装は停止中である。

---

## 16. 改訂ルール

- 本仕様書を更新するときは、推測ではなく **ファイルパスと現行挙動**を根拠にする。  
- 理想設計の変更は `docs/architecture.md` / `autonomous_research_architecture.md` 側。  
- 能力試験結果は本仕様書に「合格」として書かず、試験ログと主体ラベルで別管理する。

---

## 17. 構想書（V1基本設計）との比較 — 実コード検証版

**比較対象構想:** ユーザー提示「AI開発パートナー・エージェント V1 基本設計書」（チャット上の全文。リポジトリ内に同名ファイルが無い場合は、本節が比較の記録となる）。

**検証方針（混入禁止）:**

| 含めてよい | 含めない |
|------------|----------|
| ファイル・関数・Registry・設定の有無 | 「こうあるべき」だけの理想 |
| 入口が分かれている等の構造事実 | PROJECT_AGENT 能力試験の合否・ランク |
| コードに無いものを「未」と書くこと | Cursor/GPTが調査した結論を実装済み扱いすること |
| 開発運用が構想§5に沿っていることの**明示的な運用注記** | 運用をコード実装と混同すること |

**検証日:** 2026-08-21（追記時に `agent.py` / `registry/tools.json` / `tools/**` / `research/llm_benchmarks/research_implement.py` を再確認）。

### 17.1 構造ギャップ（コード事実）

構想が想定する一本化フロー（要望→仕様合意→委任実装→改善）に対し、実コードは二入口:

| 入口 | パス | コードで確認できる範囲 |
|------|------|------------------------|
| PROJECT_AGENT | `agent.py` | Clarity → `visibility=agent` Tool → raw結果を messages へ。**Research Judge / rule_partial / global_judge を呼ばない**（`agent.py` 内に該当シンボル無し） |
| RESEARCH_PIPELINE | 例: `research/llm_benchmarks/research_implement.py` | Proposal〜Research〜Judge〜Implement 等の重いループ |

この分離は推測ではなく、入口ファイルと import の有無による。

### 17.2 章対応表（実装度）

凡例:

- **済** … 対応する実体がコードまたは Registry 設定として存在する  
- **部分** … 関連モジュールはあるが、構想の範囲・統合・運用契約までは満たさない  
- **未** … 該当する製品機能がコードに見当たらない  
- **未決定どおり** … 構想§31で固定しないとされた事項で、コードも固定していない  
- **運用** … リポジトリ外の開発手順。コード実装ではない（混同禁止のため別列）

| 構想 | 要旨 | 実装度 | 実コード根拠（検証） | 注記（推測排除） |
|------|------|--------|----------------------|------------------|
| §2–3 | 目的理解〜改善まで尽力するAgent | **部分** | Pipeline: `research_implement.py` 等。Agent: `agent.py` は Tool ループ中心 | 「パートナー全工程」の単一実装は無い |
| §4.1 | 人間の最終判断・承認 | **部分** | 例: `tools/ai/state/safety_assessment.py` の `apply_human_decision`。Trusted Personal / execution_gate 系 | 「仕様変更・自律範囲」の体系的承認フローUIは未確認＝**未**扱い |
| §4.2 | Agentの分析〜実装〜報告 | **部分** | Builder/Research系は `visibility=pipeline`（`registry/tools.json`）。History/ログ類は `tools/ai/state/*` | `agent.py` 単体では Builder 非公開 |
| §4.3 | 上位LLM（GPT）への相談 | **未** | `agent.py` / `tools/system/llm.py` は Ollama クライアント。GPT相談専用モジュール無し | 開発時のGPT利用は**運用**であり実装ではない |
| §5 | 完成前は人間+Cursor+GPT | **運用** | （コード項目なし） | 構想の開発段階記述。実装チェック対象外 |
| §6 | 要望→分析→選択肢→仕様確定 | **部分** | Clarity: `tools/system/tool_builder/clarity.py` + `agent.py` の `run_clarity_gate`。`PLAN_GATE` は `execution_identity.py` の定数のみで**未実装** | 暫定案付き多肢比較の専用機構は無し |
| §7 | 多軸での選択肢比較 | **未** | 比較マトリクス専用モジュール無し | Judge材料に断片があっても§7の評価軸実装とは呼ばない |
| §8 | 調査量・追加調査基準 | **未決定どおり** | Agent SYSTEM に再検索手順の**文言**あり（`agent.py`）。数値基準の設定無し | 基準未固定は構想§31と一致 |
| §9 | 仕様書＝実装の正式基準 | **部分** | 文書: `PROJECT_SPEC.md`, `docs/architecture.md`, 本ファイル等 | Agentが仕様書を読み拘束する実行機構は無し |
| §10 | 仕様確定後の委任実装 | **部分** | Pipeline の implement/validate/repair 経路 | 「仕様確定後に自動委任」のゲートは無し |
| §11 | 新規Tool＝設計〜テスト一体 | **部分** | `create_tool_*` / `research_*` / `register_tool` / `test_tool` / `repair_*`（Registry pipeline） | Agent Ollama 公開外 |
| §12 | Webは自己開発の重要能力 | **部分** | Agent: `tools/system/network/search_web.py` → `general_web_search.py`。Pipeline: `tools/system/tool_builder/research/web.py` | 「重要」という位置づけは設計意図。コードは経路存在まで |
| §13 | Web評価＝答えられたか | **未**（評価運用） | 試験用スクリプト・ログはリポジトリにあるが、構想§13の成功定義をコードが自動判定する仕組みは無し | **能力試験の合否は本表に書かない**（§16改訂ルール） |
| §14 | 完成前は人間側でWeb改善 | **運用** | （コード項目なし） | F-002追加実装停止は運用判断の記録（§14の「現状履歴」§参照可） |
| §15 | 成功＝要求に答えられた | **部分** | ベンチは `ok`/`pass` 等を持つ（`research_implement` 結果JSON等） | 構想の成功定義とベンチ指標の同一性は未保証→部分 |
| §16 | 外部テスト評価・90%目安 | **部分** / 閾値は **未決定どおり** | `tests/`, `research/llm_benchmarks/` | 90%昇格のコード無し |
| §17 | 実績に応じた自律拡大 | **未** | 委任範囲を実績で拡大するモジュール無し | |
| §18 | 自己改善・評価法改善の提案 | **未** | Memory Judge等はPipeline補助。Agent自己チャレンジ製品機能は無し | |
| §19–20 | 安全装置・人間承認必須 | **部分** | `execution_gate`, `safety_assessment`, `trusted_personal_policy` 等 | 「安全装置変更の承認」専用フローは未 |
| §21 | Tool版管理・上書き禁止 | **未** | `register.py` に v1/v2 並存・昇格の実装無し（grep上 version昇格フロー無し） | Registry更新・repairは存在するが版管理ではない |
| §22 | 廃止・隔離 | **未** | 隔離領域・廃止承認フロー無し | |
| §23 | ストレージ区分 | **未** | | |
| §24–25 | 経験蓄積・失敗は禁止にしない | **部分** | `research_history`, `memory_recall*`（有効化は設定/env依存） | 「失敗＝禁止」ハードコードは主経路に無し（部分） |
| §26 | NN再学習しない | **済（否定的確認）** | 学習・finetune専用モジュール無し | 「無い」ことの確認 |
| §27–28 | 報告・選択理由の記録 | **部分** | `execution_identity`, decision_evidence / round 詳細類 | 用途別報告プロファイルは無し |
| §29 | V1＝自己改善チャレンジ構造 | **未到達** | §18相当の製品サイクル無し | 到達判定は構造有無のみ。試験スコアで判定しない |
| §30 | 将来3タイプ | **未** | | 構想どおり将来構想 |
| §31 | 意図的未決定事項 | **未決定どおり** | 該当を固定する設定キー群は見当たらない | |
| §32–34 | 進化型・土台優先 | **運用** | （プロセス） | コード完成度の主張ではない |

### 17.3 前回口頭比較からの修正・除外（検証）

| 除外・修正した点 | 理由 |
|------------------|------|
| 「Web検索能力試験でここまで確認できた」等の合否 | 能力試験結果の混入禁止。経路の**コード有無**のみ残す |
| 「F-002でMSヒットが出た／空hits」等の個別ラン結果 | 試験ログ事実であり仕様比較表の実装度判定に使わない |
| 「開発が構想どおり回っている」を**済（実装）**としない | §5/§32は**運用**列に分離 |
| Tool版管理を「部分（registerがある）」と過大評価しない | register≠v1/v2昇格。**未**に修正 |

### 17.4 検証サマリ（混入チェック結果）

| チェック | 結果 |
|----------|------|
| 実コード／Registry根拠を列に持つか | **Yes**（§17.2） |
| 理想設計のみの「実装済み」主張が無いか | **排除済み** |
| 能力試験の合否が実装度に混ざっていないか | **排除済み**（§13は評価運用／未） |
| 運用（人間+Cursor+GPT）をコード実装と混同していないか | **運用列で分離** |
| 構想§31の未決定を「未実装バグ」扱いにしていないか | **未決定どおり**で区別 |

### 17.5 一文（比較結論・構造のみ）

構想の単一AIパートナー像に対し、実コードは **Tool利用半身（`agent.py`）と Tool開発半身（Research Pipeline）の並存**までが確認でき、仕様合意ゲート・版管理・自己改善チャレンジ・上位LLM相談の製品化は未である。Web経路はコード上存在するが、構想§13の成功定義による評価自動化や能力完遂の主張は本比較に含めない。
