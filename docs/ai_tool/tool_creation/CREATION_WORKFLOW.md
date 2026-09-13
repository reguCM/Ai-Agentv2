# Tool Creation Workflow

**状態:** ADOPT CANDIDATE（手順文書。自動化は Phase 1 外）

## 標準フロー

```text
Tool Idea
    ↓
Tool Specification          ← TOOL_SPECIFICATION.md / tool_spec.schema.json
    ↓
Specification Validation    ← 人間レビュー + 将来スキーマ検証
    ↓
Implementation              ← tools/ または Provider 固有実装
    ↓
Schema Validation           ← input/output が Specification と一致
    ↓
Unit Test                   ← TEST_CONTRACT.md
    ↓
Integration Test            ← Registry / Provider 経由（将来）
    ↓
Safety Test                 ← side_effect / prohibited_operations
    ↓
Registration                ← registry/tools.json（人間承認後）
    ↓
Catalog Entry               ← CATALOG.md
    ↓
Manual Review
    ↓
Available
```

## 既存 Tool の変更

新規作成と同様の層を使うが、**互換性分類**を追加する。詳細は [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) を参照（本文書に重複記載しない）。

```text
変更前 Contract 保存
    ↓
Compatibility 分類（Safe Extension / Review / Breaking Change）
    ↓
（以降は上記標準フロー + 既存利用パターンの回帰確認）
```

Breaking Change の場合は新 Tool・deprecated・Migration を検討する。

## 各ステップの詳細

### 1. Tool Idea

- ユーザー要求または能力ギャップを 1 文で記述
- 既存 Tool 検索: `search_tools()` または Registry 手動確認
- 新規が必要な理由を記録

### 2. Tool Specification

- [TOOL_SPECIFICATION.md](./TOOL_SPECIFICATION.md) に従い 1 ファイル作成
- 推奨配置: `docs/ai_tool/tool_creation/specs/<tool_id>.md` または JSON（将来）
- **実装前に** Input / Output / Side Effect / Contract を確定

### 3. Specification Validation

| チェック | 担当 |
|----------|------|
| 必須フィールド充足 | スキーマ（将来）/ 人間 |
| 既存 Tool 重複 | `search_tools` / Registry |
| side_effect と prohibited_operations の整合 | 人間 |
| risk_level と allowed_operations の整合 | 人間 |

既存 `validate_tool_spec()` は Tool Builder パイプライン用。**今回は置き換えない**。

### 4. Implementation

#### Logical Structure（Provider 非依存）

```text
Tool
├── Identity
├── Capability + Contract
├── Input / Output
├── Side Effect
└── Security
```

#### Physical Structure — Local（新規 Tool 推奨）

```text
tools/
└── <category>/
    └── <subcategory>/
        └── <tool_name>/
            ├── tool.py          # または <tool_name>.py（既存慣習）
            ├── schema.json      # input/output（任意）
            ├── README.md
            └── tests/
                └── test_<tool_name>.py
```

**既存 Tool は移動しない。** 上記は新規作成時の推奨のみ。

既存慣習（単一 `.py`）も許容:

```text
tools/system/gpu/gpu_status.py
```

#### Physical Structure — MCP（将来）

```text
ai_tool/providers/mcp/<server_name>/
├── server.py
├── tool_spec.json
└── README.md
```

MCP は同一ディレクトリツリーにならない → Logical / Physical 分離を維持。

### 5. Schema Validation

- `input_schema` と関数シグネチャ一致
- `output_schema` と実際の戻り値形状（代表ケース）
- Registry `input` 形式への変換が必要なら文書化

### 6. Unit Test

[TEST_CONTRACT.md](./TEST_CONTRACT.md) の必須カテゴリを満たす。不要項目は `NOT_APPLICABLE`。

既存 `test_tool()` は**引数なし 1 回実行**のみ — 新 Tool は `tests/` に pytest を推奨。

### 7. Integration Test

- Local: `execute_tool(name, args)` 相当（将来 AI-TOOL アダプタ）
- MCP: Provider `call_tool`（AI-TOOL Phase 1 実験参照）
- **Phase 1 では自動化しない**

### 8. Safety Test

- `prohibited_operations` に違反するコードパスがないこと
- write/modify Tool は自動実行テストから除外
- 既存 AST Safety（`assess_generated_code_safety`）は Builder パイプラインで継続利用

### 9. Registration

本番 Registry への追記は**人間承認後**:

1. `build_registry_entry()` 互換フィールドを生成
2. `registry/tools.json` に append
3. `visibility` を明示（`agent` / `pipeline`）

**自動登録は Phase 1 禁止。**

### 10. Catalog Entry

[CATALOG.md](./CATALOG.md) の Catalog Entry を作成。`experiment_status` / `adoption_status` を分離記録。

### 11. Manual Review

- Specification ↔ 実装 ↔ Test ↔ Registry の 4 点一致
- Diagnostic Framework 知見: 実験合格 ≠ 本番採用

### 12. Available

`tool_status: available` + `adoption_status: approved` の両方が揃って初めて「本番利用可」とみなす（将来運用）。

## 既存 Tool Builder パイプラインとの関係

```text
[既存・維持]                    [新・並立]
create_tool_proposal      ↔    Tool Specification
validate_tool_spec        ↔    tool_spec.schema.json（将来）
register_tool             ↔    Registration（人間承認）
test_tool                 ↔    TEST_CONTRACT + pytest
```

Builder コードは変更しない。新 Workflow は「人間が読む標準」として先に整備。

## 自動化しないもの（Phase 1）

- Specification → 実装コード生成
- Registry 自動 append
- Catalog 自動マージ
- Selector 接続
