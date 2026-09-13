# Tool Creation Layer — Phase 2 Report

**完了日:** 2026-08-28  
**実験 run:** `runs/ai_tool/20260828_052931_tool_creation_phase2/`

---

## 完了時報告（10 項目）

### 1. Specification Validator は機能したか

**はい（ADOPT CANDIDATE）。**

- 有効 Spec 2 件 → ACCEPT
- Failure 8 件 → REJECT
- false accept / false reject = 0

### 2. 意図的 Failure を正しく検出したか

**はい。** [FAILURE_ANALYSIS.md](./FAILURE_ANALYSIS.md) 参照。Schema / safety_rules / output_check の 3 層で検出。

### 3. Catalog Draft を安全に生成できたか

**はい（ADOPT CANDIDATE）。**

- `drafts/local_get_gpu_status.json`, `drafts/local_cpu_status.json` 生成
- `registry_modified: false`
- Registry / 本番 Catalog 未変更

### 4. UNKNOWN の捏造が発生しなかったか

**なし。**

- `catalog_hints` 無し → `experiment_status` / `adoption_status` = UNKNOWN
- 不正 hints（fc08）→ Validator REJECT、draft は `UNKNOWN` のみ（coerced: false）
- `_draft_meta.inferred_fields` で UNKNOWN 理由を記録

### 5. Test Contract Skeleton を生成できたか

**はい（ADOPT CANDIDATE）。**

- 6 テストクラス固定構造
- 実装期待値は `TODO` / `HUMAN_REQUIRED` / `pytest.skip`
- LLM 不使用

### 6. 既存 Tool Mapping を再現できたか

**はい。**

| Tool | Spec | Validator | Draft | Skeleton |
|------|------|-----------|-------|----------|
| get_gpu_status | specs/local_get_gpu_status.json | ACCEPT | ✓ | ✓ |
| cpu_status | specs/local_cpu_status.json | ACCEPT | ✓ | ✓ |

本番 `tools/`・`registry/tools.json` は未変更。

### 7. 本番コードへの変更がないか

**なし。** 実装は `docs/ai_tool/tool_creation/validator/` のみ。

### 8. Registry への変更がないか

**なし。** draft は `runs/ai_tool/.../drafts/` のみ。

### 9. LLM を使うべき部分 / 使わないべき部分

| 機械（今回） | 人間 / Cursor |
|--------------|---------------|
| JSON Schema 検証 | Tool の目的・正しい出力意味 |
| enum / 型 | 実装固有テスト期待値 |
| side_effect 明白な矛盾 | 実運用上の妥当性 |
| Catalog 機械転記 | 本番採用判断 |
| Test Contract 固定枠 | contract の意味設計 |
| fixture との key 照合 | fixture 作成・更新 |

**LLM に任せない:** Specification 構造検証、enum、schema validation、Catalog 転記、Test 固定部分。

### 10. Phase 3 で何をするべきか

[NEXT_STEPS.md](./NEXT_STEPS.md) 参照（最大 3 件）。

---

## 自動化できたこと vs 人間が必要なこと

### 自動化できた（ADOPT CANDIDATE）

```text
Tool Specification (JSON)
    → Mechanical Validation (ACCEPT/REJECT + reasons)
    → Catalog Draft (UNKNOWN 明示)
    → Test Skeleton (固定構造 + TODO)
```

### まだ人間 / Cursor が必要（NOT READY）

- Specification の**内容**作成（目的・I/O 意味）
- 実装コード
- テスト期待値の具体化
- Catalog draft のレビューと Registry 追記
- Agent 統合

---

## パイプライン成立状況

```text
Idea                    → 人間
Tool Specification      → 人間/Cursor（テンプレあり）
Mechanical Validation   → ✅ 機械
Implementation          → 人間/Cursor
Test Contract           → ✅ 枠生成 / 人間が中身
Safety Check            → ✅ 構造 / 人間が実行時
Catalog Draft           → ✅ 機械
Human Approval          → 人間
Registry                → 人間（Phase 3 以降）
```

**成功条件を満たす:** 「作成途中の不備を機械的に発見」は Phase 2 で成立。

---

## 成果物

| 種別 | パス |
|------|------|
| Validator | `docs/ai_tool/tool_creation/validator/` |
| Specs | `docs/ai_tool/tool_creation/specs/` |
| Failure cases | `docs/ai_tool/tool_creation/failure_cases/` |
| 実験結果 | `runs/ai_tool/20260828_052931_tool_creation_phase2/` |
| ドキュメント | PHASE2_PLAN, VALIDATOR, CATALOG_DRAFT, TEST_GENERATION, FAILURE_ANALYSIS, NEXT_STEPS |

## 状態ラベル

| コンポーネント | ラベル |
|----------------|--------|
| Specification Validator | ADOPT CANDIDATE |
| Catalog Draft Generator | ADOPT CANDIDATE |
| Test Skeleton Generator | ADOPT CANDIDATE |
| Output fixture 照合 | EXPERIMENTAL |
| CI 統合 | NOT READY |
| Agent / Registry 統合 | NOT READY |
