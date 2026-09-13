# Tool Creation Layer — Phase 1

新規 Tool を増やす**前**に、「作る・検証する・登録する・比較する」手順を標準化するための設計層。

## 目的

- 自作 Local Tool / MCP / API / External を同じ考え方で扱える基盤
- 既存 Tool・Registry・Agent・Diagnostic Framework を**変更しない**
- 既存 Tool の**移行は行わない**（Mapping による表現可能性の確認のみ）
- 既存 Tool の**変更・拡張**は [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) を参照

## ドキュメント一覧

| ファイル | 内容 | 状態 |
|----------|------|------|
| [TOOL_SPECIFICATION.md](./TOOL_SPECIFICATION.md) | Tool 仕様書フォーマット | ADOPT CANDIDATE |
| [tool_spec.schema.json](./tool_spec.schema.json) | 仕様 JSON Schema（ドラフト） | EXPERIMENTAL |
| [CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md) | 作成〜登録の標準フロー | ADOPT CANDIDATE |
| [TEST_CONTRACT.md](./TEST_CONTRACT.md) | 共通テスト契約 | ADOPT CANDIDATE |
| [TOOL_CONTRACT.md](./TOOL_CONTRACT.md) | CAN/CANNOT/MUST/MUST_NOT | ADOPT CANDIDATE |
| [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) | 既存 Tool 変更・後方互換 | ADOPT CANDIDATE |
| [PUBLIC_TOOL_COMPARISON.md](./PUBLIC_TOOL_COMPARISON.md) | 公開 MCP 題材選定 | ADOPT CANDIDATE |
| [FIRST_TOOL_PREP.md](./FIRST_TOOL_PREP.md) | 第1実 Tool（Local 実装済） | ADOPT CANDIDATE |
| [LOCAL_IMPLEMENTATION_REPORT.md](./LOCAL_IMPLEMENTATION_REPORT.md) | Local Phase 完了報告 | SUPPORTED |
| [TOOL_COMPLETION_REPORT.md](./TOOL_COMPLETION_REPORT.md) | 実Tool完成 Phase 1 | SUPPORTED |
| [IMPLEMENTATION_REVIEW.md](./IMPLEMENTATION_REVIEW.md) | 実装レビュー | ADOPT CANDIDATE |
| [SPEC_FINAL_REVIEW.md](./SPEC_FINAL_REVIEW.md) | Specification 最終確認 | ADOPT CANDIDATE |
| [READ_URL_COMPLETION_REPORT.md](./READ_URL_COMPLETION_REPORT.md) | read_url_text Phase 2 完成 | SUPPORTED |
| [URL_FETCH_SAFETY_POLICY.md](./URL_FETCH_SAFETY_POLICY.md) | Network Tool Safety | ADOPT CANDIDATE |
| [LOCAL_VS_MCP_FETCH.md](./LOCAL_VS_MCP_FETCH.md) | Local vs MCP Fetch 比較 | ADOPT CANDIDATE |
| [ALLOWLIST_POLICY.md](./ALLOWLIST_POLICY.md) | experimental allowlist | ADOPT CANDIDATE |
| [MCP_SDK_COMPATIBILITY.md](./MCP_SDK_COMPATIBILITY.md) | MCP 1.x / 2.x 互換メモ | EXPERIMENTAL |
| [EXISTING_READ_FILE_RELATION.md](./EXISTING_READ_FILE_RELATION.md) | 本番 read_file 非置換 | ADOPT CANDIDATE |
| [candidate_research/](./candidate_research/) | 候補別調査メモ | — |
| [HUMAN_GUIDE.md](./HUMAN_GUIDE.md) | 人間向け作成手順 | ADOPT CANDIDATE |
| [PROVIDER_BOUNDARY.md](./PROVIDER_BOUNDARY.md) | Provider 共通化境界 | EXPERIMENTAL |
| [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) | DISCOVER→AUDIT 分離 | ADOPT CANDIDATE |
| [CATALOG.md](./CATALOG.md) | Catalog 設計・状態分離 | EXPERIMENTAL |
| [examples/](./examples/) | 既存 Tool Mapping（移行なし） | ADOPT CANDIDATE |
| [PHASE1_REPORT.md](./PHASE1_REPORT.md) | Phase 1 最終報告 | — |
| [PHASE2_PLAN.md](./PHASE2_PLAN.md) | Phase 2 機械化計画 | — |
| [PHASE2_REPORT.md](./PHASE2_REPORT.md) | Phase 2 最終報告 | ADOPT CANDIDATE |
| [PHASE3_1_REPORT.md](./PHASE3_1_REPORT.md) | Phase 3-1 pytest/CI | SUPPORTED |
| [validator/](./validator/) | Validator / Draft / Test 生成 | ADOPT CANDIDATE |
| [tests/](./tests/) | pytest スイート（隔離） | SUPPORTED |

## Phase 2（機械化）

```powershell
.\.venv\Scripts\python.exe docs\ai_tool\tool_creation\validator\run_phase2.py
```

出力: `runs/ai_tool/<timestamp>_tool_creation_phase2/`

## Phase 3-1（pytest / CI）

```powershell
cd docs\ai_tool\tool_creation
..\..\..\.venv\Scripts\python.exe -m pytest tests -c pytest.ini -v
```

CI: `.github/workflows/tool_creation_tests.yml`

## Phase 0: 現状（リポジトリ事実）

### Tool 配置

```text
tools/
├── system/     # GPU, CPU, network, tool_builder, agent_tool_gate
├── file/       # workspace 操作
└── ai/         # tool_builder (proposal/implementation), state, llm
```

命名: `tools/<category>/<subcategory>/<module>.py`  
Registry `module`: `tools.<category>.<subcategory>.<module>`

### 登録フロー（実装済み）

1. `search_tools()` — `tools/system/tool_builder/search.py`
2. `create_tool_proposal()` — 材料 dict（ファイル未作成）— `tools/ai/tool_builder/proposal.py`
3. `validate_tool_spec()` — 15 必須フィールド — `tools/system/tool_builder/validate/spec.py`
4. `create_tool_implementation()` — `tools/ai/tool_builder/implementation.py`
5. `validate_tool_implementation()` — AST 検証
6. `register_tool()` — `.py` 作成 + `tools.json` append — `tools/system/tool_builder/register.py`
7. `test_tool()` — **引数なし** 1 回実行 + AST Safety — `tools/system/tool_builder/test.py`
8. `validate_tool_result()` — 提案 `output` フィールド照合

### Agent 実行フロー（本番・変更対象外）

1. `load_registry()` → `create_ollama_tools()`（`visibility=="agent"` のみ、7 Tool）
2. LLM tool_call → `execute_tool()` → `agent_tool_gate` → `importlib` → `function(**arguments)`
3. 結果を `messages` に raw JSON で返却（`summarize_tool_result` は stdout 専用）

### Registry 実フィールド（`registry/tools.json`）

実際に使われる: `name`, `description`, `input`, `visibility`, `module`, `function`, `category`, `subcategory`, `keywords`, `risk`, `observation_source`（一部）

`output` は Registry にほぼ未記載（`cpu_status` のみ `["status"]`）。`validate_tool_spec` では必須だが登録後は参照されないケースが多い。

### 関連レジストリ（別系統）

| ファイル | 用途 |
|----------|------|
| `registry/tools.json` | 本番（21 Tool） |
| `registry/ai_tool_catalog.json` | AI-TOOL 実験用手動カタログ |
| `registry/agent_tool_trust.json` | Agent Tool Gate |

### Tool Builder 状態

- パイプライン実装済み（`visibility: pipeline`、Agent Ollama 公開外）
- `research/llm_benchmarks/research_implement.py` からオーケストレート
- AI-TOOL Layer / Tool Creation Layer との自動連携は**未接続**

### Diagnostic Framework

- 2026-08-28 凍結（NH1–NH14）。本番 Tool コードは本作業でも未変更
- 「実験 SUPPORTED ≠ 本番採用」を Catalog 状態設計に反映

## 本 Phase で作らないもの

新規 Tool 本体、MCP 実装、外部 API、自律登録、Selector 本番接続、DF 再開、NH15+

## 関連

- [AI-TOOL Layer Phase 1](../README.md) — 外部 Tool 実験（`ai_tool/`）
- [PROJECT_SPEC.md](../../../PROJECT_SPEC.md) — プロジェクト Tool 方針
