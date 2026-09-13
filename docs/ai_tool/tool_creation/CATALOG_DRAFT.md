# Catalog Entry Draft Generator

**状態:** ADOPT CANDIDATE（draft のみ。Registry 書き込みなし）

## 配置

`docs/ai_tool/tool_creation/validator/catalog_draft.py`

## 動作

Tool Specification から `catalog_entry.schema.json` 互換の **draft JSON** を機械生成。

```python
from validator.catalog_draft import generate_catalog_draft, write_catalog_draft

draft = generate_catalog_draft(spec, spec_ref="specs/local_get_gpu_status.json")
write_catalog_draft(spec, Path("drafts/"))
```

## マッピング規則

| Catalog フィールド | ソース |
|--------------------|--------|
| tool_id, name, provider, version, description | Spec 直写 |
| capabilities | Spec `capability` |
| input_schema, output_schema | Spec 直写 |
| side_effect, risk_level, cost, tool_status | Spec 直写 |
| permissions | Spec `required_permission` または `UNKNOWN` |
| network_access, filesystem_access | Spec 直写（無ければ `UNKNOWN`） |
| experiment_status, adoption_status | Spec `catalog_hints` のみ。無ければ `UNKNOWN` |
| provider_specific | Spec 直写 |
| spec_ref | 引数または `UNKNOWN` |

## UNKNOWN 方針

- Specification に**明示されていない** Catalog 専用フィールドは `UNKNOWN`
- `catalog_hints` に不正 enum 値がある場合は Validator が **REJECT**（捏造しない）
- `_draft_meta.inferred_fields` に UNKNOWN になったキーを記録

## 出力例

`runs/ai_tool/<timestamp>_tool_creation_phase2/drafts/local_get_gpu_status.json`

```json
{
  "experiment_status": "tested",
  "adoption_status": "approved",
  "_draft_meta": {
    "registry_modified": false,
    "inferred_fields": []
  }
}
```

`cpu_status` は `catalog_hints.experiment_status: unknown` のみ明示 → draft も `unknown`（捏造なし）。

## 禁止

- `registry/tools.json` への書き込み
- `registry/ai_tool_catalog.json` への自動マージ
- adoption_status の自動 `approved` 昇格

## Phase 2 結果

| Tool | experiment_status | adoption_status | 捏造 |
|------|-------------------|-----------------|------|
| get_gpu_status | tested（hints 由来） | approved（hints 由来） | なし |
| cpu_status | unknown（hints 由来） | approved（hints 由来） | なし |
| fc08 | N/A（Validator REJECT） | — | draft 生成時 UNKNOWN のみ |
