# Failure Case Analysis — Phase 2

意図的に壊した Specification 8 件と Validator の反応。

最新 run: `runs/ai_tool/20260828_052931_tool_creation_phase2/results.json`

## サマリ

| ID | 意図 | 期待 | 実際 | 検出層 |
|----|------|------|------|--------|
| fc01 | tool_id 欠落 | REJECT | REJECT | JSON Schema |
| fc02 | network_access 型不一致 | REJECT | REJECT | JSON Schema |
| fc03 | 不正 provider | REJECT | REJECT | JSON Schema enum |
| fc04 | read_only + network | REJECT | REJECT | safety_rules |
| fc05 | risk_level 欠落 | REJECT | REJECT | JSON Schema |
| fc06 | output と実装 key 不一致 | REJECT | REJECT | output_check |
| fc07 | side_effect 欠落 | REJECT | REJECT | JSON Schema |
| fc08 | 不正 catalog_hints | REJECT | REJECT | safety_rules |

**false accept: 0 / false reject: 0**

## 詳細

### fc01 — 必須フィールド欠落

```
(root): 'tool_id' is a required property
```

### fc02 — 型不一致

```
network_access: 'yes' is not of type 'boolean'
```

### fc03 — 不正 provider

```
provider: 'chatgpt_plugin' is not one of ['local', 'mcp', 'api', 'external', 'unknown']
```

### fc04 — side_effect と permission 矛盾

```
SIDE_EFFECT_NETWORK_CONFLICT: side_effect is read-only/none but network_access is true
```

### fc05 — risk 情報欠落

```
(root): 'risk_level' is a required property
```

### fc06 — output schema と実装 sample 不一致

fixture: `fixtures/get_gpu_status_sample_keys.json`（本番コードから読み取った key 一覧）

```
OUTPUT_SCHEMA_MISMATCH: output_schema properties do not overlap implementation sample keys
```

**注:** 本番 Tool は変更・実行していない。fixture は Phase 1 Mapping 由来の記録。

### fc07 — side_effect 未記載

```
(root): 'side_effect' is a required property
```

### fc08 — UNKNOWN を勝手に具体値へ置換

Schema 上は有効だが `catalog_hints` に `auto_approved` 等:

```
INVALID_CATALOG_HINTS: experiment_status must be one of [...]
```

Catalog draft 生成時も `UNKNOWN` に落とし、捏造なし（`coerced: false`）。

## Validator の限界（まだ検出しないもの）

- 実装が contract を守るか（実行テストが必要）
- description の意味的正確さ
- 本番 Registry との自動同期
- LLM が書いた Specification の「内容」の妥当性

## ラベル

| 項目 | 状態 |
|------|------|
| 8/8 Failure 検出 | ADOPT CANDIDATE |
| 意味的実行検証 | NOT READY |

---

## Phase 3-1 — pytest 回帰（2026-08-28）

Tool Creation Layer の pytest スイートで Phase 2 挙動を継続検証。

```powershell
cd docs/ai_tool/tool_creation
pytest tests -c pytest.ini -v
```

| 項目 | 結果 |
|------|------|
| pytest total | 34 |
| passed | 34 |
| false accept | 0 |
| false reject | 0（gold set 限定） |

テストファイル:

- `tests/test_failure_cases.py` — fc01–fc08 + 理由追跡
- `tests/test_phase2_regression.py` — 2/8/0/0 + 凍結 run 読取
- `tests/test_unknown_policy.py` — UNKNOWN 非捏造

詳細: [PHASE3_1_REPORT.md](./PHASE3_1_REPORT.md)

**NOT READY:** 本番 Tool 実行と fixture の動的照合（静的 fixture のみ pytest 化済み）

