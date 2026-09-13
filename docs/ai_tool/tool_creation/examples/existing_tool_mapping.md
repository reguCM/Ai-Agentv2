# Existing Tool Mapping — Summary

既存 Tool を新 Tool Specification へ**移行せず**、表現可能性のみ検証した結果。

## 対象

| Tool | Mapping 文書 | 結果 |
|------|--------------|------|
| `get_gpu_status` | [existing_get_gpu_status.md](./existing_get_gpu_status.md) | 十分に表現可能（参照モデル） |
| `cpu_status` | [existing_cpu_status.md](./existing_cpu_status.md) | 表現可能（legacy・契約薄） |

## 共通してマッピングできた領域

- Identity（name, provider=local, source=registry）
- Input（空 object）
- Security（risk, visibility, network/filesystem）
- Catalog 三層状態（既存 Tool は available / tested or unknown / approved）

## 共通ギャップ（既存 Registry → 新 Spec）

| 既存 | 新 Spec での補完 |
|------|------------------|
| `output` ほぼ未記載 | `output_schema` + `error_format` |
| 副作用の明示なし | `side_effect` を Mapping 時に推論 |
| Contract なし | `contract` ブロックを逆算 |
| `validate_tool_spec` 15 項目 | Tool Specification は別スキーマ |

## 変更していないもの

- `tools/system/gpu/gpu_status.py`
- `tools/system/cpu/cpu_status.py`
- `registry/tools.json`
- `agent.py`
