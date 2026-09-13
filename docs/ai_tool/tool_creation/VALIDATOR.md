# Specification Validator

**状態:** ADOPT CANDIDATE（構造検証。意味的正しさは保証しない）

## 配置

```text
docs/ai_tool/tool_creation/validator/
├── validate.py          # JSON Schema + 構造 Safety
├── safety_rules.py      # side_effect / contract / catalog_hints
├── output_check.py      # 任意: fixture との output 照合
└── run_phase2.py        # 実験ランナー
```

## 検証レイヤ

### 1. JSON Schema（`tool_spec.schema.json`）

- 必須フィールド、型、enum（provider, side_effect, risk_level, cost 等）
- `jsonschema` Draft 2020-12

### 2. 構造 Safety（`safety_rules.py`）

| コード | 内容 |
|--------|------|
| `SIDE_EFFECT_NETWORK_CONFLICT` | read_only + network_access=true |
| `SIDE_EFFECT_FILESYSTEM_CONFLICT` | read_only + filesystem write |
| `OPERATION_CONTRADICTION` | allowed/prohibited 矛盾 |
| `CONTRACT_MISSING` / `CONTRACT_INCOMPLETE` | contract 4 キー必須 |
| `INPUT_SCHEMA_INVALID` | input_schema 形状 |
| `OUTPUT_SCHEMA_MISSING` | output_schema 必須 |
| `INVALID_CATALOG_HINTS` | catalog_hints の enum 外値 |

### 3. Output Fixture 照合（任意）

`output_validation_fixture` が Spec にある場合のみ。本番 Tool は実行しない。

## 判定

| verdict | 条件 |
|---------|------|
| `ACCEPT` | schema エラーなし、error 級 safety なし |
| `REJECT` | 上記いずれか失敗 |

## API

```python
from validator.validate import validate_tool_spec_file

result = validate_tool_spec_file(Path("specs/local_get_gpu_status.json"))
# result.verdict → "ACCEPT" | "REJECT"
# result.schema_errors, result.safety_issues
```

## 混同しないこと

| 検証できる | 検証できない |
|------------|--------------|
| Schema 上の構造 | 実行時の正しい戻り値 |
| contract ブロックの存在 | contract の意味的妥当性 |
| side_effect と permission の明白な矛盾 | 実装が contract を守るか |
| fixture との key 重複 | 全エッジケースの網羅 |

## Phase 2 実験結果

| 種別 | ACCEPT | REJECT |
|------|--------|--------|
| 有効 Spec 2 件 | 2 | 0 |
| Failure 8 件 | 0 | 8 |
| false accept | 0 | |
| false reject | 0 | |

最新 run: `runs/ai_tool/20260828_052931_tool_creation_phase2/results.json`
