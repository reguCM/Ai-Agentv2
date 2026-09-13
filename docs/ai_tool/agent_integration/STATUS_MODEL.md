# Status Model — Agent Discovery

**状態:** Phase 1 固定

## 二つの独立した分類軸

### 1. Catalog 三層（既存 AI-TOOL — 変更しない）

```text
tool_status         — Tool そのものの可用性
experiment_status   — 実験ライフサイクル
adoption_status     — 採用レビュー
```

出典: [../tool_creation/CATALOG.md](../tool_creation/CATALOG.md)

**ルール:** 三層を単一 `status` に潰さない。

例（experimental Tool — そのまま保持）:

```json
{
  "tool_status": "unavailable",
  "experiment_status": "experimental",
  "adoption_status": "not_reviewed"
}
```

### 2. Discovery category（Agent Integration 派生）

Agent が「どう扱うか」の読み取り専用ラベル:

| discovery_category | 意味 | agent_available (Phase 1) |
|--------------------|------|---------------------------|
| `production` | Registry visibility=agent | **true** |
| `experimental` | AI-TOOL catalog / MCP manual、未統合 | **false** |
| `not_ready` | Registry pipeline 等、Agent 公開条件未成立 | **false** |
| `unavailable` | tool_status 等により利用不可 | **false** |

---

## availability + reason（Agent 向け派生）

| フィールド | 例 |
|-----------|-----|
| `availability` | `available` / `not_available` |
| `unavailability_reason` | `experimental_not_integrated` |

```text
catalog_status (三層, 保持)
        ↓
discovery_category (派生, 別軸)
        ↓
agent_available (bool)
        ↓
availability + unavailability_reason
```

---

## 混同禁止

| 誤り | 正しい |
|------|--------|
| Catalog に存在 = Agent が使える | `agent_available` を見る |
| experiment_status=experimental → 三層削除 | 三層維持 + discovery_category=experimental |
| discovery_category=production → adoption_status 省略 | Registry 由来も三層派生値を記録 |

---

## Registry vs Catalog entries

| ソース | 三層の扱い |
|--------|-----------|
| registry/tools.json | 機械派生（`status_derivation=derived_from_registry_*`） |
| ai_tool/catalog/entries/ | JSON フィールドをそのまま（`from_catalog_entry`） |
| ai_tool_catalog.json (MCP) | 派生 + experimental 固定 |

---

## Phase 1 以降

- Human Review 後の `adoption_status` 更新 → discovery 読み取り反映（**Phase 3 実装済** — [HUMAN_REVIEW.md](./HUMAN_REVIEW.md)）
- Registry 登録 → `discovery_category` 遷移（NOT READY）
- MCP trust tier（NOT READY）
