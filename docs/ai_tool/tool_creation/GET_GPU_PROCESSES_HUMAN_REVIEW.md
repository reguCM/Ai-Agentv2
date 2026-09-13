# get_gpu_processes — Working Tree Change Human Review

**Review date:** 2026-08-28  
**Scope:** `tools/system/gpu/gpu_processes.py` HEAD vs working tree の正式採用判断材料  
**本 Phase:** 調査・比較・記録のみ（実装/Registry/Agent 変更なし、commit なし）

---

## A. Review 対象

| 項目 | 値 |
|------|-----|
| Tool ID | `local:get_gpu_processes` |
| Registry name | `get_gpu_processes` |
| HEAD commit | `88febb3` |
| Working tree path | `tools/system/gpu/gpu_processes.py` |
| Review scope | 上記ファイルの未コミット diff のみ |
| 除外 | `research/*`, 他 Tool, unrelated `registry/tools.json` 全体 diff（参照はするが判断対象外として分離） |

### Git 状態（作業開始時）

| 項目 | 値 |
|------|-----|
| branch | `master` |
| HEAD | `88febb3` |
| `gpu_processes.py` | **M**（本 Review 対象） |
| `registry/tools.json` | **M**（別 diff — 実装採用時の整合確認用に参照） |
| `agent.py` | 変更なし |

---

## B. HEAD 版 (`88febb3`)

### Implementation summary

```python
def get_gpu_processes():
    return [
        {"name": "ollama", "vram_used": 4500},
        {"name": "python.exe", "vram_used": 1200},
    ]
```

### Observed behavior

| 項目 | 値 |
|------|-----|
| 入力 | なし |
| 返却型 | **list**（dict ではない） |
| データ取得 | **なし**（subprocess / nvidia-smi 未使用） |
| 固定値 | ollama 4500 MiB, python.exe 1200 MiB |
| PID | なし |
| observation_source | なし |
| エラー経路 | なし（常に同一 2 件を返す） |

### Known limitations

- **実測ではない** — Registry description（HEAD）の「GPU使用プロセス情報」と内容的に乖離
- HEAD Registry に `observation_source` / `visibility: agent` なし（working tree Registry とは別状態）
- 正式 Specification なし

---

## C. Working Tree 版（現ファイル）

### Implementation summary

```text
get_gpu_processes()
  → query_gpu_processes()  [tools/system/gpu/nvidia_smi.py]
  → nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory
  → dict { processes, ok, status, error, observation_source, source }
```

### Observed behavior

| 項目 | 値 |
|------|-----|
| 入力 | なし |
| 返却型 | **dict**（6 top-level keys） |
| processes[] | `{ pid, name, vram_used }` |
| データ取得 | nvidia-smi 実測 |
| 固定値 | なし（ollama/python フォールバック禁止） |
| VRAM | 整数 MiB または `"unknown"`（`[N/A]` を 0 にしない） |
| observation_source | 常に `"real"` |
| 失敗時 | `processes=[]`, `ok=false`, `status=unavailable|error`, `error` コード |

### Known limitations

- VRAM per-process は **PARTIAL** — 環境によりほぼ全件 `"unknown"`（Migration Run: 33/33 unknown、pid は 33/33 match）
- GPU identifier per process 未返却
- 返却形状が HEAD の list から dict へ変更（後方互換コメントあり）

### 実測証拠（再利用 — 再実行なし）

| Run | 結果 |
|-----|------|
| `runs/ai_tool/20260828_161848_legacy_tool_audit/` | 33 processes, ok=true, VRAM mostly unknown |
| `runs/ai_tool/20260828_163325_get_gpu_processes_migration/` | pid match 33/33 PASS, VRAM unknown 33/33 |

---

## D. Difference Matrix

| 項目 | HEAD | Working Tree | Classification |
|------|------|--------------|----------------|
| return type | `list` | `dict` | **INTERFACE_CHANGE** |
| data source | hardcoded | nvidia-smi | **IMPROVEMENT** + **BEHAVIOR_CHANGE** |
| process count | always 2 | 0..N | **BEHAVIOR_CHANGE** |
| PID | absent | present | **INTERFACE_CHANGE** |
| name | ollama, python.exe | real process_name paths | **BEHAVIOR_CHANGE** |
| VRAM | fixed 4500/1200 | int or `"unknown"` | **IMPROVEMENT** + **BEHAVIOR_CHANGE** |
| fixed values | YES | NO | **IMPROVEMENT** |
| ok/status/error | absent | present | **INTERFACE_CHANGE** |
| observation_source | absent | `"real"` | **INTERFACE_CHANGE** |
| error on no GPU tool | never fails | empty + ok=false | **BEHAVIOR_CHANGE** |
| change author/intent | UNKNOWN | docstring: real obs | **UNKNOWN**（コミット履歴なし） |

---

## E. Compatibility

| 軸 | 判定 | 根拠 |
|----|------|------|
| Input compatibility | **COMPATIBLE** | 両版とも引数なし |
| Output compatibility | **CHANGED** | list → dict；process item に pid 追加 |
| Semantic compatibility | **CHANGED** | 固定 stub → 実測；件数・内容が動的 |
| Error compatibility | **CHANGED** | HEAD は常成功；WT は失敗メタあり |
| Safety compatibility | **COMPATIBLE** | いずれも read-only subprocess（WT）/ 副作用なし（HEAD stub） |
| Agent compatibility | **COMPATIBLE** | `execute_tool` は raw 返却；`summarize_tool_result` は dict/list 両対応。list 専用ロジックなし |
| Registry compatibility | **CHANGED** | WT Registry は nvidia-smi + observation_source=real（別 uncommitted diff）。HEAD Registry 記述は汎用説明 |
| Test compatibility | **CHANGED** | 既存 GPU 実測テスト・Migration テストは WT 契約前提 |

### HEAD へ戻した場合（静的影響、revert 未実行）

- Migration spec `get_gpu_processes_legacy_migrated.json` と矛盾
- `tests/ai_tool/tool_creation/test_get_gpu_processes_migration.py` 失敗
- `tests/test_gpu_real_observation.py::test_processes_not_fixed_ollama_python` 失敗
- Registry working tree 記述（nvidia-smi 実測）と HEAD stub が **MISMATCH**

### Working Tree 正式採用時（静的影響）

- Migration 成果物・Legacy Audit と整合
- `get_gpu_status` と同型の real observation パターン
- **リスク:** list を期待する外部利用者がいれば破壊 — **in-repo では該当なし**（grep 静的調査）
- Registry diff（`observation_source`, description）は **別途** 人間が同時採用するか判断

---

## F. Evidence

| 種別 | 参照 |
|------|------|
| HEAD ソース | `git show 88febb3:tools/system/gpu/gpu_processes.py` |
| Working tree ソース | `tools/system/gpu/gpu_processes.py` |
| git diff | `git diff -- tools/system/gpu/gpu_processes.py` |
| Legacy Audit | `docs/ai_tool/project_audit/LEGACY_TOOL_AUDIT.md` §3.2 |
| Migration spec | `docs/ai_tool/tool_creation/specs/get_gpu_processes_legacy_migrated.json` (ACCEPT) |
| Migration Run | `runs/ai_tool/20260828_163325_get_gpu_processes_migration/` |
| Legacy Audit Run | `runs/ai_tool/20260828_161848_legacy_tool_audit/` |
| Agent 経路 | `agent.py` `execute_tool` / `summarize_tool_result`（list/dict 分岐確認） |
| Consumer grep | `get_gpu_processes(` — 実装・テスト・run スクリプトのみ |

---

## G. Decision

### recommended_decision

```text
ADOPT_WORKING_TREE
```

**理由（候補提示のみ — 最終決定ではない）:**

1. HEAD は明らかな **hardcoded stub** で、Tool 目的（GPU 使用プロセス実測）と矛盾
2. Working tree は nvidia-smi 経路が監査・独立観測で確認済み（pid PASS）
3. Safety 問題なし；Agent は dict 返却を処理可能
4. Tool Creation Migration 成果物はすべて WT 基準で整備済み
5. INTERFACE_CHANGE（list→dict）は **Breaking** だが、リポジトリ内 list 依存は未検出

### human_decision

```text
PENDING
```

### 代替候補

| 決定 | 条件 |
|------|------|
| **KEEP_HEAD** | 外部 list 依存が存在する、または stub を意図的に維持する理由がある場合 |
| **REBUILD_FROM_SPEC** | WT にも根本問題があり仕様から作り直す方が安全な場合 — 現時点証拠不足 |
| **DEFER** | 外部利用者調査が必要な場合 |

### 採用時の注意（Human 向け）

- `gpu_processes.py` の commit だけでは不十分な可能性 — **Registry working tree**（description, observation_source, visibility）との **セット採用** を検討
- `nvidia_smi.py` も working tree 新規ファイル（`??`）— 実装採用時は依存関係を一緒に判断
- commit / push は **Human Decision 後** の別 Phase

---

## Safety gates

```text
unsafe_accept = 0
wrong_file_inclusion = 0
secret_inclusion = 0
allowlist_violation = 0
```

---

## Run 記録

`runs/ai_tool/20260828_164546_get_gpu_processes_human_review/`

生成: `python ai_tool/run_get_gpu_processes_human_review.py`

---

## STOP

**YES — HUMAN DECISION REQUIRED**

Working tree が技術的に優れていても、本 Phase では正式採用しない。
