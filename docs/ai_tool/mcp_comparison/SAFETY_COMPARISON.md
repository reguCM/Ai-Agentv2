# Safety Comparison — Local vs MCP Fetch

**Run:** `runs/ai_tool/20260828_153335_mcp_fetch_comparison/`

SPECIFICATION（仕様・調査メモ）と OBSERVED（当 Run で確認）を分離する。

---

## Local `read_url_text`

### SPECIFICATION / 政策（実装前から文書化）

出典: [tool_creation/URL_FETCH_SAFETY_POLICY.md](../tool_creation/URL_FETCH_SAFETY_POLICY.md), [tool_creation/specs/local_read_url_text.json](../tool_creation/specs/local_read_url_text.json)

| 項目 | 方針 |
|------|------|
| scheme | `http` / `https` のみ |
| localhost / loopback | 拒否 |
| private IP | 拒否 |
| link-local | 拒否 |
| metadata hostname | 固定リスト拒否 |
| DNS 解決後 IP 検証 | 全アドレス public 必須 |
| redirect | 最大 5 hop、各 hop 再検証 |
| timeout | デフォルト 10s（引数で変更可） |
| max_bytes | デフォルト 65536 |
| binary | content-type + sniff 拒否 |
| DNS rebinding TOCTOU | **UNKNOWN**（政策に明記） |

### OBSERVED — safety カテゴリ 4 ケース（当 Run）

| case_id | URL（Run 記録） | Local | MCP |
|---------|-----------------|-------|-----|
| safety_localhost | `http://127.0.0.1:58447/plain` | **blocked** — `ssrf blocked: private or loopback IP` | ** reached ** — ok true |
| safety_private_ip | `http://192.168.0.1/` | **blocked** — 同上 | ** reached ** — ok true |
| safety_link_local_metadata | `http://169.254.169.254/latest/meta-data/` | **blocked** — 同上 | ** reached ** — ok false（ConnectError） |
| safety_redirect_private | `http://127.0.0.1:58447/redirect_private` | **blocked** — 同上（fetch 前） | ** reached ** — ok false（ReadTimeout） |

`safety_results.json` → `per_case_safety`:

| case_id | local_blocked_before_fetch | mcp_reached_network |
|---------|---------------------------|---------------------|
| safety_localhost | **true** | **true** |
| safety_private_ip | **true** | **true** |
| safety_link_local_metadata | **true** | **true** |
| safety_redirect_private | **true** | **true** |

### OBSERVED — AI-TOOL Layer 機械 Safety Gate（descriptor ベース）

出典: `safety_results.json`

| 対象 | verdict | reason |
|------|---------|--------|
| Local descriptor | **allow** | `local_read_low_risk` |
| MCP（trust_external=false） | **human_required** | `external_tool_requires_explicit_trust` |
| MCP（trust_external=true） | **human_required** | `external_tool_default_confirm` |

---

## MCP Fetch（`mcp-server-fetch` 2026.8.18）

### SPECIFICATION（調査メモ — 当 Run 前）

出典: [tool_creation/candidate_research/fetch.md](../tool_creation/candidate_research/fetch.md)

| 項目 | 調査記録 |
|------|----------|
| SSRF / 内部 IP | 公式 **CAUTION**: ローカル/内部 IP アクセス**可能**と記載 |
| max_length | デフォルト 5000 |
| robots.txt | デフォルト遵守（`--ignore-robots-txt` で回避可） |
| Tool annotations | README 上 Fetch 単体 tool に表なし |
| MCP SDK | パッケージは MCP **1.x** 系（`mcp<2`） |

### OBSERVED — 当 Run

| 項目 | 観測 |
|------|------|
| `annotations` | **null**（`outputs.json` → `mcp_descriptor.annotations`） |
| localhost fetch | **成功**（safety_localhost） |
| private IP fetch | **HTTP 応答あり**（safety_private_ip, ok true） |
| link-local metadata | **接続失敗**（ConnectError）— 到達は試行された |
| redirect → private | **ReadTimeout**（safety_redirect_private） |
| readOnlyHint 等 | Run 時 **未提供**（annotations null） |

### Annotation ポリシー（Run 記録）

`safety_results.json`:

```text
annotation_policy: Annotations recorded as untrusted metadata; not used as safety facts.
```

Phase 1 では:

```text
Annotation → Untrusted Metadata → Client-side Policy → 実行可否
```

MCP Server の read-only 自己申告を Safety Fact としては扱わない設計と整合（annotations 自体が null）。

---

## Safety 差分まとめ（OBSERVED のみ）

| 観点 | Local（当 Run） | MCP（当 Run） |
|------|-----------------|---------------|
| loopback URL | fetch 前ブロック | 取得試行・成功（localhost fixture） |
| private IP literal | fetch 前ブロック | 取得試行・成功（192.168.0.1） |
| link-local metadata | fetch 前ブロック | 取得試行・ConnectError |
| redirect → private | production モードでは起点 URL が loopback のためブロック | ReadTimeout（約 31s） |
| Client-side trust gate | local provider → allow（descriptor） | external → human_required |

**記述上の注意:** 「MCP が防御した」ではなく、「当 Run では MCP が SSRF 相当のブロックを Local と同様には行わなかったケースが観測された」と記録する。

---

## Trust Boundary（設計整理 — 解釈ラベル付き）

| 層 | Local | MCP |
|----|-------|-----|
| Safety 実装主体 | 自実装（`ssrf.py` 等） | 外部 Server 実装 |
| Client 再評価 | SSRF + Tool Creation Validator | `evaluate_tool_safety` が external を human_required |
| 信頼前提 | コードベース内 | **外部 Server を信頼しない**前提が Run 結果と整合 |

当 Run だけから「Client-side Safety 再評価が必須」と**断定する採用判断**は行わない。観測として、safety 不一致 3 件 + safety gate の external 扱いが記録されている。
