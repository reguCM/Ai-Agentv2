# Help System H4 Core — Technical Spec（Implementation Packet）

**状態:** **完了承認**（人間、2026-09-08）。H4 Core ≠ H4 製品全体。本 Packet は完了した実装契約。次 Goal の設計には使わない。  
**PRD:** [`docs/prds/help-system-h4-selection-core.md`](../prds/help-system-h4-selection-core.md)  
**根拠:** [`docs/prds/help-system-h4-selection-core-decision-log.md`](../prds/help-system-h4-selection-core-decision-log.md)  
**独立 ToDo（Core 外・未着手）:** 層1 PRD の「独立 ToDo」2本。本ファイルへ設計を足さない。

本ファイルは H4 Core の **実装契約** である。PRD を言い換えない。モジュール・不変条件・禁止・failure・テスト・影響面を定義する。

---

## Context

H4-1 はファイル観測の capability id 化のみ。本 Core は選択 / Gap / expectation 接続 / read-only bridge 判断 / Sandbox 注入判断を、Index + Registry + Help に載せる。現行 `candidate_tools[0]` と `look_first[0]` 黙読は欠陥であり、実装の出発点にしない。

---

## 採用仕様（契約の核）

PRD Requirements が行為の正本。実装時に次を満たす。

1. 正本: Index（意味・prefer・look_first・classifier・suggested_minimal_tool）/ Registry keywords / Registry security / Help describe。
2. Matcher: B + 日本語 substring + Latin 単語境界 + write-side ゲート + `プロファイル` 除外（matcher のみ）+ 横断共有非確定 + audit 降格 + read-only look_first 言及。
3. Resolve: capability ごと Help 確認。`selected_tool` は **1 Resolution あたり高々1件**。
4. Bridge: path 根拠のある read。list は `"."` 可（Residual）。search は query 機械抽出できるときだけ。複数 `next_action` は inject なし。
5. Sandbox: `dedicated_sandbox_required` かつその Tool が某 Resolution の `selected_tool`。Task 上にそのような Resolution が2+なら起動するが `required_mutation_tool()` は None。
6. leftover を削除して完成としない。

### Index データ契約

`registry/workspace_concepts.json` `schema_version`: `2`。

新規 capability（semantic id。Tool 名クローンにしない）:

| id | tools[] |
|---|---|
| `web_search` | `search_web` |
| `url_fetch` | `read_url_text` |
| `gpu_device_observation` | `get_gpu_status` |
| `gpu_process_observation` | `get_gpu_processes` |
| `cpu_observation` | `get_cpu_status`, `cpu_status` |

`prefer_when_ambiguous`: `workspace_file_read` / `gpu_device_observation` / `web_search`。

空 `tools[]` に `suggested_minimal_tool`（現行 `_MINIMAL_TOOLS` 相当。実行に使わない）:

`workspace_file_write`→`write_file`、`command_execution`→`run_command`、`python_execution`→`run_python`、`test_execution`→`run_tests`、`tool_validation`→`validate_tool`、`tool_registration`→`register_tool`。edit/create は `tools[]` があるので Gap 用 suggested は通常使わない。

ルート `classifier`（語彙ではない）:

```json
"classifier": {
  "match_exclusions": {
    "japanese_file_object_tokens": ["プロファイル"],
    "applies_to": [
      "h4_required_capabilities_matcher.file_object",
      "h4_required_capabilities_matcher.file_anchored_mutation_phrase"
    ],
    "does_not_apply_to": ["help_search", "tool_builder_search", "relevant_tools", "is_agent_task"]
  },
  "audit_intent": ["調査", "確認", "存在", "利用可能", "どこまで", "定義", "inspect", "audit", "check", "available"],
  "audit_demotes_capabilities": [
    "workspace_file_write", "workspace_file_edit", "workspace_file_create",
    "command_execution", "python_execution", "test_execution",
    "tool_validation", "tool_registration"
  ]
}
```

write/execution の既存 `look_first` は **削除しない**。

### Registry keywords 最小追加

- `edit_file`: `ファイルを編集`, `ファイル編集`, `ファイルを書き換え`, `ファイル書き換え`
- `create_file`: `ファイルを作`, `ファイル作成`, `新しいファイル`（既存 `新規作成` / `create` / `file` は残す）
- `search_files` / `list_files`: 英語 `file`（日本語 `ファイル` を mutation に足さない。search への日本語 `ファイル` は必須にしない）

足さない: 裸 `編集` `作成` `作って` `書き換え`、mutation への日本語 `ファイル` 単独。

---

## Decomposition

- **CapabilityIndexData** — Index JSON のフィールドと検証（`load_workspace_index`）
- **RequestCapabilityClassifier** — 要求テキスト → capability id のリスト
- **CapabilityResolver** — 1 capability → 1 `CapabilityResolution`（Help 確認、status、Gap）
- **OrchestratorResolutionStore** — Task あたり複数 Resolution、snapshot flatten、単数 wrapper、reconcile
- **NextActionPolicy** — `next_action` / pending inject
- **SandboxInjectionPolicy** — Dedicated Sandbox 起動判断
- **H4CoreRegressionTests** — PRD 回帰の固定

---

## 不変条件

1. 1 `CapabilityResolution.selected_tool` は `None` または candidate のうちちょうど1つの名前。リストでもカンマ区切りでもない。
2. `status == "RESOLVED"` ⇔ `selected_tool` が非空。2+ available → `CANDIDATES_AVAILABLE` かつ `selected_tool is None`。
3. Core 内部は `required_capability()` / `detect_required_tool_gap()` を呼ばない。
4. 単数 compat: 0→None、1→その値、2+→明示エラー（`None` に折らない）。
5. snapshot `capability_resolution` は `list[dict]`（flat）。memory は `dict[task_id, list[CapabilityResolution]]`。
6. 同一 `task_id` + 同一 capability id は upsert（現行を置換）。履歴スキーマは Core で増やさない。
7. `required_capabilities` の新しい集合が現在の真理。落ちた capability の resolution と対応 `runtime.tool_gaps` を同じ reconcile で落とす。
8. Gap は Help 確認済み available が **0** のときだけ。`suggested_minimal_tool` で Tool を実行しない、`selected_tool` にしない。
9. 除外表は matcher の file対象 / file付き mutation 表層にだけ効く。Help/Discovery に効かせない。初期トークンは `プロファイル` のみ。
10. 日本語 `ファイル` の同一script埋没除外を matcher に入れない。
11. write/execution の Index `look_first` を削除しない。選択 signal に使わない。
12. `look_first[0]` を path 根拠なしの `read_file` 引数にしない。`_VERIFIED_ROUTES` を正本にしない。
13. pending inject 対象を Tool 名集合で正本化しない。`side_effect` が sandbox-write/write なら inject しない。
14. Sandbox 起動を `{create_file, edit_file}` 名集合で正本化しない。
15. 「mutation が2+」は **Task 上の複数 Resolution** が各1件の mutation `selected_tool` を持つ状態を指す。1 Resolution が複数 selected することはない。
16. 概念 `look_first` と capability `look_first` を同一関数に畳まない。
17. `registry_read` と `workspace_file_read` を `read_file` 共有でマージしない。
18. leftover を削除したことを H4 Core 完了としない。

---

## やってはいけないこと

- `selected_tool = candidate_tools[0]` を残す、または 2+ で「一番それらしい」を選ぶ
- path なし read を緑にするため `look_first[0]` / `_VERIFIED_ROUTES` を戻す
- 除外表に予見で2件目を足す、裸 `編集` を Registry に足す、mutation に日本語 `ファイル` を足す
- `_RULES` / `_MINIMAL_TOOLS` / `_CAPABILITY_QUERIES` / file-in-text を正本に残す
- `detect_tool_gap` 内部や Help 英語検索を「ついでに直して完成」にする
- LLM Tool スキーマを capability でフィルタする（本 Core 外）
- スキル本文 `.agents/skills/**/SKILL.md` を書き換える
- merge / push / promote / 破壊的 git
- pytest 件数を Machine Test や仕様充足と報告する
- 存在しない Event を作る。CONNECTED を欄の存在だけで宣言する

---

## 具体的 failure scenario

| ID | 入力 | 誤った実装 | 正しい結果 |
|---|---|---|---|
| F1 | ログファイルを編集して | 同一script除外 | `workspace_file_edit` |
| F2 | ユーザープロファイルを編集 | 除外なし / 裸 `編集` | write-side なし |
| F3 | 設定を編集して | 裸 `編集` keyword | write-side なし |
| F4 | ファイルを読んで（path なし） | look_first[0] | `next_action is None` |
| F5 | registry/tools.json を読んで | 黙読禁止を全 read に拡大しすぎ | その path の read `next_action` |
| F6 | 検索して | web+file 両方 RESOLVED | どちらも keyword だけでは確定しない |
| F7 | ファイル検索 | web_search も selected / prefer で read も足す | file search。web も read も足さない（検索が exclusive。prefer は共有だけ） |
| F8 | CPU を見て | `[0]` で get_cpu_status | `CANDIDATES_AVAILABLE`、selected なし |
| F9 | 使用率 | GPU+CPU 両方 | 確定しない |
| F10 | edit と create が各 Resolution で selected | 1 Resolution に selected を2つ入れる | 各1件。Sandbox 起動。required 名 None |
| F11 | list 誤分類 | （Residual）`list_files(".")` が走り得る | 仕様上残る。分類で list を誤って唯一件にしない |
| F12 | LLM が edit_file、selected なし | 実行成功 | `sandbox_session_required` |
| F13 | 既存コードを修正する | `_RULES` を残し edit | write-side ではない |
| F14 | Gap 時 suggested を呼ぶ | 実行 | 呼ばない |
| F15 | 2 capability で単数 API | None | 明示エラー |

---

## 必要な Regression Test

PRD「保持すべき回帰」を機械テストにする。新規ファイル推奨: `tests/ai_tool/chat_interface/test_h4_selection_core.py`（名前は任意。意図を散らさない）。

**必須ケース**は PRD の回帰リストと F1–F15 に一致させる。加えて:

- Index `tools[]` ∈ Registry かつ `visibility=agent`
- `load_workspace_index` は write 側 `look_first` が残っていてもパス実在なら通る
- 除外は Help `_match_query` を変えない（`/h 編集` が `ファイルを編集` に当たる Residual は残る）
- `test_safe_mutation_tools_p218.py` / P2-17 sandbox を壊さない
- H4-1: `fallback="read_file"` しない。web/gpu/cpu の **Tool 名返り** assertion は capability id に更新
- `test_capability_classification_read_edit_create_and_pytest` の「既存コードを修正する」→ edit 期待を捨てる。「新規ファイルを作る」は残す
- look_first 黙読を期待するテストは Q25 に合わせて直す（デフォルト読取を戻さない）

pytest 件数を完了報告に使わない。

---

## 影響する API / State / Registry / Help / Test

| 面 | 変更 | しないこと |
|---|---|---|
| `registry/workspace_concepts.json` | schema 2、5 capability、classifier、prefer、suggested_minimal | write 側 look_first 削除、概念/category の look_first 変更 |
| `registry/tools.json` | mutation file付き keywords、search/list に `file` | 裸 verb、mutation に日本語 `ファイル` |
| `capability_resolution.py` | `_RULES`/`_VERIFIED_ROUTES`/`_MINIMAL_TOOLS` を正本から外す。`required_capabilities`、status に `CANDIDATES_AVAILABLE`、next_action 政策 | 単数関数の削除 |
| `task_orchestration.py` | resolutions を list、複数形 Gap、pending の side_effect、search-hit の Help 確認 Tool、`required_capability` は wrapper | `detect_tool_gap` 内部呼び出し先の書き換え |
| `agent_turn.py` | Sandbox 起動をフラグ+全 Resolution 走査 | LLM tools の絞り込み |
| `ai_tool/help/api.py` | コメント/Discoveries 以上に **必須変更なし**。解決は Index+describe | `_CAPABILITY_QUERIES` 一般化を完成扱い |
| `concept_resolution.py` | **変更しない**（Q46） | capability look_first と統合 |
| snapshot / `run_human_summary.py` / `agent_test_runner.py` | flat list のまま読める | ネスト dict に変える |
| `tools/ai/task_runtime.py` `detect_tool_gap` | シグネチャ・内部 matcher 変更なし | needle 仕様の「直し」 |
| Tests | 上記回帰。P216 / P2169 / P218 / H4-1 の更新 | テスト合わせで仕様を歪める |

### Public インターフェース（実装時の形）

```python
def required_capabilities(task: Any, *, expectation: Any = None) -> list[str]:
    ...

def detect_required_tool_gaps(...) -> list:  # 1 capability 1 gap 要素
    ...

def infer_required_capability(...) -> str | None:
    """compat: 0 None, 1 value, 2+ raise explicit error."""

def resolve_capability(...) -> CapabilityResolution:
    """1 capability。selected_tool は candidate がちょうど1のときだけ。"""

def next_capability_action(resolution, task, spec) -> dict | None:
    """selected_tool 必須。read は path 根拠。list は '.' 可。search は query 機械抽出時のみ。"""
```

`ChatTaskOrchestrator.capability_resolutions`: `dict[str, list[CapabilityResolution]]`。  
`required_mutation_tool()`: 現在 Task の全 Resolution を見る。mutation selected がちょうど1 Resolution ならその Tool 名。0 なら None。2+ Resolution なら None（Sandbox は agent_turn 側でフラグ走査して起動可）。  
`pending_capability_action()`: 現在 Task の next_action が read-only かつちょうど1件のときだけ返す。

`CAPABILITY_STATUSES` に `CANDIDATES_AVAILABLE` を追加。

---

## Modules

### CapabilityIndexData

**Responsibility:** Index を読み、paths 検証し、classifier / prefer / suggested / tools を他モジュールへ渡す。語彙をここで増やさない。

**Public interface:** 既存 `load_workspace_index()`。未知キーを無視してよいが `classifier.match_exclusions` 欠落時は除外なし（空リスト）とし、予見トークンをコードに埋め込まない。

**Invariants:** `look_first` が無い capability は合法。有るなら実在ファイル。`capabilities` と `categories`/`concepts` を混同しない。

**Failure modes:** 欠落 path → 既存どおり `ValueError`。

**Tests:** write 側 look_first 残存でも load できる。tools[] は実在 agent Tool。

### RequestCapabilityClassifier

**Responsibility:** 要求テキスト → 順序安定な capability id リスト。Tool を選ばない。

**Public interface:**

```python
def required_capabilities(task: Any, *, expectation: Any = None) -> list[str]:
    ...
```

**Invariants:** PRD の一致規則。除外は write-side 根拠だけ。横断共有だけでは確定しない。audit は Index の語と降格集合。look_first 選択は read-only（と `registry_read`）のみ。

**Failure modes:** ヒットなし → `[]`。推測で web/gpu を足さない。

**Tests:** PRD 回帰の分類列。F1–F3, F6–F9, F13。

### CapabilityResolver

**Responsibility:** 1 capability を Help 確認し、candidate / selected / Gap / suggested を埋める。

**Public interface:** 既存 `resolve_capability` を「与えられた capability id」前提に再定義（内部が classifier 単数に依存しない）。

**Invariants:** Help は Index tools + describe/`local:`。`fallback` 名推測なし。selected は len(available)==1。suggested は Index のみ。実行に使わない。

**Failure modes:** Index に無い id → `NO_MATCH`。available 0 → Gap 候補（confirm は既存 evidence 規則）。

**Tests:** 2 candidate で selected なし。CPU。空 tools の Gap。

### OrchestratorResolutionStore

**Responsibility:** Task 複数 Resolution、flatten snapshot、単数 wrapper、reconcile。

**Invariants:** 不変条件 3–7, 15。

**Failure modes:** 単数 API 2+ → 明示例外。メッセージは「複数 capability を単数 API に折っていない」ことが分かる程度でよい。

### NextActionPolicy

**Responsibility:** resolution+task+spec → next_action。pending の inject 可否。

**Invariants:** Q25/Q29/Q30/Q31/Q32。概念層は触らない。search hit 後は Help 確認した `workspace_file_read` Tool + hit path。

**Failure modes:** path 根拠なし read → None。query なし search → None。next_action 2+ → pending None。

**Tests:** F4, F5, F11（Residual として list "." は **起こりうる** とドキュメントし、誤分類 list を回帰で防ぐ）。

### SandboxInjectionPolicy

**Responsibility:** 現在 Task の Resolution 列から Dedicated Sandbox が要るか、required 名を返すか。

**Public interface:** `required_mutation_tool()` と agent_turn の起動条件をフラグ走査に合わせる。

**Invariants:** 不変条件 14–15。名集合に戻さない。

**Tests:** F10, F12。P218 実行契約は維持。

### H4CoreRegressionTests

**Responsibility:** PRD 回帰をコードから外れないように固定する。

---

## Sequence

1. **CapabilityIndexData + Registry keywords**（データ。matcher が空振りしない）
2. **RequestCapabilityClassifier**（単体テストで F1–F3, F6 が先に赤/緑になる）
3. **CapabilityResolver** + 1 capability の orchestrator 接続  
   ← **tracer:** path 付き「registry/tools.json を読んで」→ `workspace_file_read` → unique `read_file` → その path の next_action。path なし file-read は next_action なし
4. **OrchestratorResolutionStore**（複数 capability、snapshot、単数エラー）
5. **NextActionPolicy**（list/search/複数 inject、search-hit）
6. **write-side + 除外 + SandboxInjectionPolicy**
7. **H4-1 / P2169 assertion 更新と leftover 非削除の確認**
8. **H4CoreRegressionTests の残り**（GPU/CPU/web/URI）

tracer の後に ranking や Help 検索一般化を入れない。

---

## Deferred事項

PRD Non-Goals に同じ。再掲のみ: 形態素、Help `_CAPABILITY_QUERIES`、legacy ranking（CPU 含む）、`detect_tool_gap` 内部、`create_ollama_tools`、Help Registry、Chat UI search_web、trust bootstrap、expected_tool 複数形、LLM Tool フィルタ、time/memory/summary Index、単数 API 削除、英語 Discovery 是正、概念 look_first 廃止、write 側 look_first 削除、list `"."` を Q25 同型に閉じる、merge/push。

---

## do_not_assume

- H4-1 完了や本 PRD 存在を実装完了としない
- 現行 `[0]` / look_first[0] を正としない
- Help `search(capability)` 0 件を即 Gap としない。`describe("read_file")` 失敗を `local:read_file` 失敗としない
- 除外表を語彙や Help フィルタとしない
- 1 Resolution が selected_tool を複数持てるとしない
- 概念 look_first と capability look_first が同じ仕事をしているとしない
- `registry_read` と `workspace_file_read` が同じとしない
- leftover 削除 = 完成、としない
- Q25–Q38 を「ユーザーが一行ずつ署名した」以上に書かない（レビュー済み Packet として扱う）
- out-of-tree が単数 API を使っていない、としない（だから削除しない）
- pytest PASS を仕様の正しさの証明にしない

---

## revisit_trigger

1. 除外表に2件目を足したくなる → 形態素 H4+。Core で積まない
2. 除外が `ファイル` 接尾以外に必要
3. Xファイルを拾うために除外を緩め、プロファイル mutation FP が再発
4. path なし read のために look_first[0] を戻したくなる → 戻すな
5. Q36 を直すために Tool 名/category allowlist が増え始める
6. Discovery 過候補が Sandbox なしで mutation **成功** する
7. `CANDIDATES_AVAILABLE` 回避に `[0]` を入れる
8. `classifier` に Tool 意味語を増やし始める
9. capability が Tool 名のコピーになる
10. `suggested_minimal_tool` で実 Tool を呼ぶ
11. list `"."` の自動実行が実害として連続する → 別forkで Q25 同型を検討（本 Core 中に黙って変えない）
12. write 側 look_first の人間向け消費者が観測された → 削除可否を再確認（今は残す）
13. 空 `tools[]` capability（`test_execution` 等）を自然言語から Tool Gap したい → Classifier B では到達不能。`_RULES` を戻すな。Index 外の語彙正本か、最小 agent Tool を `tools[]` に載せる設計を別forkで検討

---

## Open Questions

H4 Core についてなし。Residual は Deferred / Known Issues。Core を再開しない。

独立 ToDo 2本（Task / Action Ownership、Tool Gap → Tool Builder Bridge）は層1 PRD。本 Packet に設計判断を足さない。

## Ambiguity Report

```
Ambiguity Report:
  Goals:        0.0   ✓ モジュール境界が PRD 行為に対応
  Acceptance:   0.25  ✓ 回帰は列挙。Q36 の「カテゴリ」実装は Registry category/subcategory に依存（Allowlist化トリガ 5）
  Boundaries:   0.0   ✓ Non-Goals / leftover / 禁止が実装契約にある
  Alternatives: 0.0   ✓ ranking・look_first削除・裸verb は不採用のまま
  Assumptions:  0.25  ✓ Help describe 経路と sandbox フラグはコードで観測済み。out-of-tree は NOT_OBSERVED
  ──────────────────────────────
  Aggregate:    0.10  ✓ below threshold (0.2 spec)
```

Caller: tech-spec。指摘完了済みのため再面接なし。Passive self-review。
