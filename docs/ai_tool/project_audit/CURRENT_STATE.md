# Current State — AI-Agent Project

**監査日:** 2026-08-28

## 一枚サマリ

| 領域 | 実装状態（監査分類） | 既存ラベル（参考） | Agent 統合 |
|------|---------------------|-------------------|------------|
| **Agent Core** | **ACTIVE** | — | 本体 |
| **Existing Tool System** (`tools/` + `registry/tools.json`) | **ACTIVE** | 本番 21 Tool | **7 Tool** が LLM 公開 |
| **AI-TOOL Layer** (`ai_tool/`) | **EXPERIMENTAL** | NOT READY（Layer 全体） | **なし** |
| **Tool Creation Layer** | **EXPERIMENTAL** | Validator: ADOPT CANDIDATE | **なし** |
| **Context Builder** | **EXPERIMENTAL** | Phase 1–2 完了 | **なし** |
| **External Help Package** | **EXPERIMENTAL** | Phase 2 生成のみ | **なし** |
| **Experimental Tools** (scoped read, read_url) | **EXPERIMENTAL** | Catalog draft / not_reviewed | **なし** |
| **MCP Integration** | **NOT_READY** | Provider: EXPERIMENTAL | **なし** |
| **Diagnostic Framework** | **FROZEN** | PARTIALLY_READY | **なし** |

## Agent が実際に LLM へ公開する Tool（2026-08-28 時点）

`registry/tools.json` の `visibility: "agent"` — **7 件**:

- `get_gpu_status`, `get_gpu_processes`, `cpu_status`
- `search_web`
- `list_files`, `read_file`, `search_files`

**Agent が使えない（Registry 未登録）:** `local:workspace_read_text_scoped`, `local:read_url_text`, その他 `ai_tool/experimental/`

## Tool Creation 工程の到達点

```text
Idea → Specification → Mechanical Validation → Implementation → Test → Safety → Catalog Draft
  ✅        ✅                  ✅                  ✅ (experimental)  ✅      ✅         ✅

Human Review → Registry → Agent
  ⚠️ 部分        ❌          ❌
```

- **一周確認済み（experimental Tool）:** `workspace_read_text_scoped`, `read_url_text`
- **Registry / Agent への統合:** 未実施

## 凍結済み研究基盤

| 基盤 | 状態 | 範囲 |
|------|------|------|
| Diagnostic Framework | **FROZEN**（2026-08-28） | NH1–NH14 |
| MCP Fetch Comparison | **FROZEN**（Phase 1） | Run `20260828_153335_mcp_fetch_comparison` |

## 本番変更禁止（監査時点で維持）

- `agent.py`, `tools/`, `registry/tools.json` — 監査で未変更
- Diagnostic Framework runs — 未変更
- 既存 experiment runs — 未変更
