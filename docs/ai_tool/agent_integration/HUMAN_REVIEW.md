# Human Review Flow — Phase 3

**状態:** Phase 3 実装済み  
**スコープ:** Catalog metadata の `adoption_status` 更新のみ

---

## 目的

Experimental Tool に対し、人間が採用判断（approve / reject / defer / candidate）を記録し、その結果を **AI-TOOL Catalog** に保存する。

```text
Human Review
    ↓
adoption_status (+ human_review 記録)
    ↓
Catalog に判断を保存
```

---

## 三つの独立した段階

### 1. Human Review ≠ Adoption（実行権）

Review は **判断の記録** であり、Tool の実行権限を与えない。

| 操作 | 変更するもの | 変更しないもの |
|------|-------------|---------------|
| Human Review | `adoption_status`, `human_review` | `tool_status`, `experiment_status`, Registry, LLM schema |

### 2. Adoption ≠ Registry

`adoption_status=approved` でも **Registry へ自動登録しない**。

```text
approved（Catalog）
    ↓
Registry 登録は別 Phase（NOT READY）
```

### 3. Registry ≠ Agent Execution

Registry 登録後も、Agent / LLM 公開は **visibility=agent** 等の別判断が必要（既存本番フロー）。

---

## Review 状態モデル

### adoption_status（Catalog スキーマ — 既存 enum を優先）

出典: [`docs/ai_tool/catalog/catalog_entry.schema.json`](../catalog/catalog_entry.schema.json)

| 値 | 意味 |
|----|------|
| `not_reviewed` | 未レビュー |
| `candidate` | 採用候補 |
| `approved` | 本番採用承認（Catalog 上の判断のみ） |
| `rejected` | 採用拒否 |

### review_status（Human Review 記録層）

| 値 | adoption_status への反映 |
|----|-------------------------|
| `approved` | → `approved` |
| `rejected` | → `rejected` |
| `candidate` | → `candidate` |
| `deferred` | **変更なし**（`not_reviewed` のまま） |

**UNKNOWN / 仕様外:** `deferred` は Catalog `adoption_status` enum に存在しないため、判断延期は `human_review.review_status` と audit にのみ記録し、`adoption_status` は更新しない。

---

## API

```python
from ai_tool.catalog.review import apply_human_review, get_reviewable_tool

entry = get_reviewable_tool("local:read_url_text")  # read-only

result = apply_human_review(
    "local:read_url_text",
    "approved",
    reason="policy reviewed",
    notes="sandbox adoption only",
)
# result.agent_available == False （常に experimental 統合前）
```

### 記録フィールド（`human_review` ブロック）

- `review_status`
- `reviewed_at`
- `reviewer`（抽象値 `"human"` 等 — 個人情報不要）
- `reason`
- `notes`

### Audit

`ai_tool.core.audit.append_audit` を再利用:

```text
event: human_review_catalog_update
tool_id, before_status, after_status, review_action, timestamp
```

---

## Discovery との関係

Phase 2 Discovery Hook は Catalog の更新を **読み取り** で反映する。

| 状態 | discovery_category | agent_available |
|------|-------------------|-----------------|
| experimental + not_reviewed | experimental | false |
| experimental + approved | experimental | **false** |
| experimental + rejected | unavailable | false |

`approved` でも `experimental_not_integrated` が維持される（Registry 未統合のため）。

---

## Safety 境界

Human Review 処理中に **発生させない** もの:

- Tool 実行
- MCP 接続
- network access
- Registry 変更
- Ollama Tool Schema 変更
- `agent_available` の true 化

**許可:** `ai_tool/catalog/entries/*.json` の metadata 更新のみ。

---

## 再レビュー

既存 Policy に明示的な状態遷移表は **UNKNOWN**。

Phase 3 実装:

- デフォルト `allow_rereview=True`（監査付きで上書き可）
- `allow_rereview=False` かつ既レビュー済み → `rereview_not_allowed`

---

## 関連

- [STATUS_MODEL.md](./STATUS_MODEL.md)
- [DISCOVERY_HOOK.md](./DISCOVERY_HOOK.md)
- [PHASE3_REPORT.md](./PHASE3_REPORT.md)
