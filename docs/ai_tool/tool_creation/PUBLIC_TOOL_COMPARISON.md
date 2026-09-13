# Public MCP / Plugin Tool Comparison — First Real Tool Selection

**調査日:** 2026-08-28  
**目的:** 最初の自作実 Tool 題材の選定（**実装は行わない**）

**参照（重複説明は各文書へ委譲）:**

- [TOOL_SPECIFICATION.md](./TOOL_SPECIFICATION.md) / [TOOL_CONTRACT.md](./TOOL_CONTRACT.md) / [TEST_CONTRACT.md](./TEST_CONTRACT.md)
- [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) / [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md)
- [PROVIDER_BOUNDARY.md](./PROVIDER_BOUNDARY.md) / [VALIDATOR.md](./VALIDATOR.md)
- [../../CURRENT_STATUS.md](../../CURRENT_STATUS.md)（AI-TOOL Phase 1）
- [candidate_research/](./candidate_research/)（候補別メモ）

**公式ソース:** [MCP Examples](https://modelcontextprotocol.io/examples) / [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)

---

## 1. 調査した公開 Tool

| # | Tool / Server | 提供元 | 備考 |
|---|---------------|--------|------|
| 1 | **Fetch** | MCP 公式 | `mcp-server-fetch` |
| 2 | **Filesystem** | MCP 公式 | `@modelcontextprotocol/server-filesystem` |
| 3 | **Git** | MCP 公式 | `mcp-server-git` |
| 4 | **Memory** | MCP 公式 | `@modelcontextprotocol/server-memory` |
| 5 | **Time** | MCP 公式 + 本プロジェクト実験 | EXP-001 済み |
| 6 | **Everything** | MCP 公式 | テスト・プロトコル検証用 |
| 7 | **Apps SDK Examples** | OpenAI | Pizzaz, Kitchen Sink 等（MCP + UI） |

Apps SDK は MCP Server 必須。[Apps SDK Quickstart](https://developers.openai.com/apps-sdk/quickstart) — `registerAppTool`, `inputSchema`/`outputSchema`, `_meta`（UI）, `readOnlyHint` 等。本プロジェクトは ChatGPT ホストではないため **MCP tool 層のみ**比較材料とする。

**技術的注意:** 公式 Fetch/Git/Time は **MCP Python SDK 1.x** 記載。本プロジェクト AI-TOOL は **MCP 2.x**（[CURRENT_STATUS.md](../../CURRENT_STATUS.md)）。MCP 比較実験時は SDK 互換を別途確認する。

---

## 2. 候補比較表

| 項目 | Fetch | Filesystem (read-only) | Git (read-only) | Memory | Time | Everything |
|------|-------|------------------------|-----------------|--------|------|------------|
| **Tool名** | `fetch` | `read_text_file` 等 | `git_status`, `git_log` 等 | `read_graph` 等 | `get_current_time` | 複数（テスト用） |
| **提供元** | MCP 公式 | MCP 公式 | MCP 公式 | MCP 公式 | MCP 公式 | MCP 公式 |
| **主目的** | URL 本文取得→markdown | 許可ディレクトリ内ファイル操作 | リポジトリ操作 | 知識グラフ永続化 | 時刻・TZ 変換 | MCP 機能デモ |
| **Input** | url, max_length, … | path, head/tail, … | repo_path, … | entity/relation 構造 | timezone | 各種 |
| **Output** | markdown text | text / base64 / listing | text / commit list | graph JSON | structured time | 各種 |
| **Side Effect** | read-only + **network** | read 系 / write 系混在 | read + **write 混在** | **write 主体** | read-only | 混在 |
| **Network** | あり | なし | なし | なし | なし | なし |
| **Filesystem** | なし | **あり** | 間接（.git） | あり（JSONL） | なし | あり |
| **Authentication** | 不要 | 不要 | 不要 | 不要 | 不要 | 不要 |
| **Risk** | 中〜高（SSRF） | 中（path） / 高（write 含む場合） | 中〜高 | 中 | 低 | 低（本番不向き） |
| **実装難度** | 中 | 低〜中 | 中 | 中〜高 | **低** | 高（題材不適） |
| **Specification化** | 可 | 可 | 可（read 限定なら） | 可 | **済**（ベースライン） | 可だが不要 |
| **Test Contract** | 中（network） | **高**（決定論的） | 中 | 中 | 高 | 低 |
| **Safety境界** | network/SSRF | **allowlist/traversal** | repo + write 混在 | write | 明確 | デモのみ |
| **Local/MCP比較** | **可** | **可** | 可（read 抽出） | 可 | **済** | 不要 |
| **比較価値** | **高** | **高** | 中 | 低 | 低（新規性） | 低 |

---

## 3. Fetch vs Filesystem 深掘り

### Fetch（URL → 本文）

```text
url → validation → HTTP GET → markdown / raw → chunk (start_index)
```

| 論点 | 内容 |
|------|------|
| URL validation | scheme/host 制限、SSRF（127.0.0.1, metadata IP） |
| HTTP error | 4xx/5xx を error_format で返す設計が必要 |
| timeout | Test Contract Failure カテゴリ |
| redirect | 追跡可否・回数制限 |
| content-type | raw vs markdown 変換 |
| size limit | `max_length`（公式 5000） |
| network_access | Specification で `true`、Safety で human_required |
| output contract | `{ url, content, truncated, status?, error? }` 等 |

**既存 Agent:** `search_web` は検索結果リスト。Fetch は**単一 URL 本文** — 補完関係。

### Filesystem read-only（path → 内容）

```text
path → allowlist 検証 → normalize → read → structured result
```

| 論点 | 内容 |
|------|------|
| allowed path | 実験用 `docs/ai_tool/` や `runs/ai_tool/` のみ等 |
| path traversal | `..`, symlink — **must_not** で明示 |
| existence | Failure: ファイル不存在 |
| permission | OS 権限エラー |
| size limit | max bytes / head-tail |
| binary/text | text のみ初手推奨 |
| read-only safety | `side_effect: read_only`, write tool は初手禁止 |

**既存 Agent:** `list_files` / `read_file` あり。新 Tool は **Tool Creation Layer 検証用の experimental 別 ID**（例: `workspace_read_text_scoped`）とし、本番 Tool は [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md) に従い置換しない。

### 深掘り結論

| 観点 | Fetch | Filesystem read-only |
|------|-------|----------------------|
| Safety 設計の実地検証 | network / SSRF 軸 | **path allowlist 軸（より決定論的）** |
| Test Contract | 非決定論的要素あり | **pytest 向き** |
| 将来 Agent 価値 | URL 本文取得は有用 | 既存 file tools と重複しうる |
| MCP 公式比較 | 単一 tool で明快 | read tool サブセットで可 |

---

## 4. Time の位置づけ

- Phase 1 EXP-001 済み — **「最初の自作 Tool」の新規性は低い**
- Local/MCP / Specification / Audit の**ベースライン**として記録（[candidate_research/time.md](./candidate_research/time.md)）
- 比較実験の再実行には有用、題材選定の主役にはしない

---

## 5. ランキング

### ① 最初に作るべき Tool

**推奨: Scoped Filesystem Read（ワークスペース限定・read-only テキスト読取）**

| 評価軸 | 理由 |
|--------|------|
| 実装難度 | 低〜中（既存 `read_file` 参考にしつつ新 Specification で作成） |
| Safety 検証価値 | **最高** — allowlist, traversal, read-only を [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) で実証 |
| Tool Creation Layer 検証 | Specification / Validator / Test Contract / Catalog 全層を**決定論的**に試せる |
| MCP 比較価値 | 公式 `read_text_file` と Local 実装を 1 機能で比較可 |
| 実用価値 | 中（既存 file tools あり）— ただし**層の検証**が主目的なら最適 |

**提案 tool_id（案）:** `local:workspace_read_text_scoped`（experimental、Registry 本番追記は人間承認後）

### ② 次に作る候補

**Fetch URL Read-only（単一 URL → markdown/text、allowlist + SSRF 対策付き）**

| 評価軸 | 理由 |
|--------|------|
| Safety 検証価値 | 高（network_access, SSRF） |
| MCP 比較 | 公式 `mcp-server-fetch` と 1:1 |
| 実用価値 | **高**（`search_web` と非重複） |
| Test Contract | ネットワークで flakey — ②番目が妥当 |

### ③ 今は作らない候補

| Tool | 理由 |
|------|------|
| **Memory** | write 主体 — 初手 Safety 方針と矛盾 |
| **Git（公式そのまま）** | write tool 混在 — read サブセット設計が先 |
| **Everything** | プロトコルテスト用のみ |
| **Time（新規）** | EXP-001 ベースラインで足りる |
| **Filesystem write 系** | write 自動実行禁止 |
| **Apps SDK UI 付き** | 本プロジェクトスコープ外 |

---

## 6. 最有力候補 — Tool Creation Workflow 適合評価

**対象:** Scoped Filesystem Read（①）

```text
Idea
 ↓  ✅ 文書化可能（「許可パス内のテキストファイルを読む」）
Tool Specification
 ↓  ✅ [TOOL_SPECIFICATION.md](./TOOL_SPECIFICATION.md) 全フィールド記述可
Mechanical Validation
 ↓  ✅ [validator/](./validator/) + pytest（Phase 3-1）
Implementation
 ↓  ✅ 新規 experimental モジュール（本番 tools/ 変更は別 Phase・人間承認）
Test Contract
 ↓  ✅ Normal/Invalid/Failure/Safety を temp dir で具体化可
Safety
 ↓  ✅ read_only + allowlist — [SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md) 直結
Catalog Draft
 ↓  ✅ [catalog_draft.py](./validator/catalog_draft.py)
Human Approval
 ↓  ✅ 必須（Registry 手動）
Registry
 ↓  ⏳ 本番追記は承認後のみ
```

### 不足機能の分類

| 分類 | 項目 |
|------|------|
| **必須（実装前）** | 許可ルート設定ファイル（例: `allowed_roots.json`）のポリシー文書化；path 正規化仕様の Specification への明記 |
| **あれば便利** | Compatibility diff（変更時 — [TOOL_CHANGE_POLICY.md](./TOOL_CHANGE_POLICY.md)）；実行時 output スナップショット pytest |
| **将来課題** | Agent 統合；公式 MCP Filesystem（Node）との stdio 接続；MCP SDK 1.x/2.x 差の吸収 |

---

## 7. この Tool で試される現在の設計

| レイヤ | 試される点 |
|--------|------------|
| **Tool Specification** | input `path`, output schema, `side_effect: read_only` |
| **Tool Contract** | `must_not: path_outside_allowlist`, `cannot: write` |
| **Test Contract** | traversal, missing file, boundary size |
| **Safety Boundary** | read vs write 分離、Validator とは別の実行時 allowlist |
| **Provider Model** | LocalToolProvider + 将来 MCPToolProvider（read_text_file） |
| **Catalog** | experiment_status / adoption_status 三層 |
| **Validator / pytest** | 新 spec JSON を gold set に追加（Phase 3-2） |
| **Audit** | `runs/ai_tool/audit.jsonl` に read 実行記録 |
| **TOOL_CHANGE_POLICY** | 既存 `read_file` との共存（新 ID、非置換） |

**試されないもの（今回）:** Agent Ollama 公開、Registry 自動マージ、write Tool

---

## 8. OpenAI Apps SDK からの比較材料（要約）

| Apps SDK 概念 | AI-TOOL / Tool Creation 対応 |
|---------------|------------------------------|
| `inputSchema` / `outputSchema` | [TOOL_SPECIFICATION.md](./TOOL_SPECIFICATION.md) `input_schema` / `output_schema` |
| `readOnlyHint` 等 annotations | **信用しない** — クライアント側 `side_effect` で再定義（[PROVIDER_BOUNDARY.md](./PROVIDER_BOUNDARY.md)） |
| `structuredContent` | `ToolExecutionResult.result` / MCP `structured_content` |
| Human approval | `agent_tool_gate` + `evaluate_tool_safety` human_required |
| UI / `_meta.ui` | スコープ外 |

---

## 9. 実装前に整備すべきもの（完了: 2026-08-28）

| # | 項目 | 成果物 |
|---|------|--------|
| 1 | allowlist ポリシー | [ALLOWLIST_POLICY.md](./ALLOWLIST_POLICY.md) + [allowed_roots.experimental.json](./allowed_roots.experimental.json) |
| 2 | Specification ドラフト | [specs/local_workspace_read_text_scoped.json](./specs/local_workspace_read_text_scoped.json) |
| 3 | MCP SDK 互換メモ | [MCP_SDK_COMPATIBILITY.md](./MCP_SDK_COMPATIBILITY.md) |
| 4 | 既存 `read_file` 差分 | [EXISTING_READ_FILE_RELATION.md](./EXISTING_READ_FILE_RELATION.md) |

まとめ: [FIRST_TOOL_PREP.md](./FIRST_TOOL_PREP.md) — Validator **ACCEPT** 確認済み。実装・Registry は未着手。

---

## 10. 最終提案

> **最初に作るべき実 Tool は、「ワークスペース限定・read-only・テキストファイル読取」（Scoped Filesystem Read）とする。**

**理由（要約）:** Tool Creation Layer Phase 1〜3-1 で構築した Specification / Contract / Safety / Validator / pytest を、**決定論的かつ Safety 中心**に一通り実証できる。MCP 公式 Filesystem の read-only tool との Local/MCP 比較も可能。Fetch は②番目として network/SSRF 軸の検証に最適。

**実装は今回行わない。**

---

## 変更なし確認

- `agent.py`, `tools/`, `registry/tools.json` — **未変更**
- 既存 `runs/` — **未変更**
- 公開実装のコピー・組み込み — **なし**
