# Tool Creation Layer Phase 3-1 Report

**完了日:** 2026-08-28  
**判定:** **SUPPORTED**

---

## Tool Creation Layer Phase 3-1 — 完了報告

### 実装場所

```text
docs/ai_tool/tool_creation/
├── tests/
│   ├── conftest.py
│   ├── test_spec_validator.py
│   ├── test_failure_cases.py
│   ├── test_catalog_draft.py
│   ├── test_test_skeleton.py
│   ├── test_unknown_policy.py
│   ├── test_fixture_check.py
│   └── test_phase2_regression.py
├── pytest.ini
├── requirements-dev.txt
└── validator/          # Phase 2 実装（変更なし）

.github/workflows/tool_creation_tests.yml
```

### CI

- GitHub Actions: `tool_creation_tests.yml`
- トリガー: `docs/ai_tool/tool_creation/**` の push / PR
- 対象: Tool Creation Layer の pytest のみ（本番 Agent / tools 対象外）
- 依存: `pytest`, `jsonschema`（有料 API なし）

### pytest

```powershell
cd D:\AI-Agent\docs\ai_tool\tool_creation
..\..\..\.venv\Scripts\python.exe -m pytest tests -c pytest.ini -v
```

| 項目 | 値 |
|------|-----|
| total | 34 |
| passed | 34 |
| failed | 0 |
| skipped | 0 |
| errors | 0 |

### Coverage（参考・品質保証そのものではない）

| モジュール | Cover |
|------------|-------|
| catalog_draft.py | 100% |
| test_skeleton.py | 100% |
| validate.py | 96% |
| output_check.py | 92% |
| safety_rules.py | 80% |
| run_phase2.py | 0%（CLI runner・pytest 対象外） |
| **TOTAL** | **72%** |

### Phase 2 regression

| 指標 | 値 |
|------|-----|
| valid | 2 |
| failure | 8 |
| false accept | 0 |
| false reject | 0 |

※ false_reject=0 は **現在の gold set（specs/ 2 件）** に対する結果。一般完全性の主張ではない。

凍結 run `runs/ai_tool/20260828_052931_tool_creation_phase2/results.json` は**読み取りのみ**（未改変）。

### UNKNOWN fabrication

- `catalog_hints` 無し → `experiment_status` / `adoption_status` = `UNKNOWN` ✅
- `required_permission` 無し → `permissions` = `["UNKNOWN"]` ✅
- 不正 `catalog_hints` → Validator REJECT、draft は `UNKNOWN`（捏造なし）✅

### Registry変更

**なし**

### 本番コード変更

**なし**（`agent.py`, `tools/`, `registry/tools.json` 未変更）

### 判定

**SUPPORTED**

- pytest で Phase 2 重要挙動を再現
- fc01〜fc08 継続検出 + REJECT 理由追跡
- false accept なし
- UNKNOWN 非捏造確認
- 本番領域変更なし
- CI から再実行可能

### 主な Failure

なし（34/34 passed）

### 次候補（Phase 3-2 以降）

1. **隔離環境での実行時 output 照合** — fixture のみでなく import 実行（NOT READY）
2. **Catalog draft レビュー CLI** — Registry export は人間確認のみ
3. **run_phase2.py の pytest ラッパ** — 任意（現状 regression テストで代替済み）

---

## LLM を使うべき / 使わないべき（再確認）

| 機械（pytest） | 人間 / Cursor |
|----------------|---------------|
| Schema / enum / contract 構造 | Tool 目的・正しい出力意味 |
| fc01–fc08 検出 | 実装固有テスト期待値 |
| Catalog 機械転記 | 本番採用判断 |
| Skeleton 固定枠 | contract の意味設計 |
| UNKNOWN 非捏造 | fixture 拡充（不足分は NOT READY） |

**Phase 3-1 では LLM 未使用。**

---

## テスト分類

| ファイル | 内容 |
|----------|------|
| test_spec_validator.py | 有効 Spec 2 件 ACCEPT |
| test_failure_cases.py | fc01–fc08 REJECT + 理由 |
| test_catalog_draft.py | Draft 生成・Registry 非変更 |
| test_test_skeleton.py | 固定 6 クラス + HUMAN_REQUIRED |
| test_unknown_policy.py | UNKNOWN 非捏造 |
| test_fixture_check.py | output fixture 照合（静的） |
| test_phase2_regression.py | 2/8/0/0 + 凍結 run 読取 |

---

## 禁止事項遵守

- Tool 自動生成: なし
- Registry 自動登録: なし
- Agent 統合: なし
- auto_fix: なし
- 有料 API: なし
- 既存 Phase 2 run 上書き: なし
