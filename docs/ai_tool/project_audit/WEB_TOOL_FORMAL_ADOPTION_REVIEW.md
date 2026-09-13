# Web Tool Formal Adoption Review

**Phase:** Web Tool Formal Adoption Review Phase 2  
**Date:** 2026-08-28  
**HEAD:** `875cc47` — `ai-agent: freeze current development state`  
**Prior investigation:** [WEB_TOOL_CURRENT_STATE.md](./WEB_TOOL_CURRENT_STATE.md)  
**Security:** [WEB_TOOL_SECURITY_REVIEW.md](./WEB_TOOL_SECURITY_REVIEW.md)  
**Git commit:** **禁止**（本 Phase）

---

## Git 記録

| 項目 | 値 |
|------|-----|
| HEAD | `875cc47` |
| Branch | `master` |
| `tools/system/network/` | `??` WT only（HEAD 未コミット） |
| `registry/tools.json` search_web | **HEAD に不在** |
| read_url_text impl | HEAD committed |
| production_bridge overlay | HEAD committed |

---

## 1. search_web — 正式採用前チェック

| # | 項目 | 判定 | 詳細 |
|---|------|------|------|
| 1 | 実装 | PASS（WT） | `search_web.py` → `general_web_search.py` |
| 2 | 入力 schema | PASS | `query` (required), `limit` (optional int) |
| 3 | 出力 schema | PASS | `{query, hits[], backends_tried, error, fetch_limit, return_limit, candidates_collected?}` |
| 4 | エラー | PASS | 空 query / 不正 limit / 全 backend 失敗 → error 文字列、hits=[] |
| 5 | timeout | PASS | 12s per http_get |
| 6 | network | PASS（意図的） | DDG + Wikipedia API |
| 7 | SSRF | PASS | ユーザー URL connect なし |
| 8 | 検索結果 URL | PASS | hits[].url — 本文 fetch しない |
| 9 | 最大件数 | PASS | return_limit 既定 5 |
| 10 | 空結果 | PASS | hits=[], error 設定 |
| 11 | backend 障害 | PASS | 他 backend 継続、errors 連結 |
| 12 | stub/推測 | PASS | 固定 hits なし |
| 13 | observation semantics | GAP | Web hits 用体系未定義 — GPU 型 unknown は **不要** |
| 14 | Agent 安全境界 | GAP | HEAD 未公開のため未到達；採用後 gate HR |

### Discovery Tool 確認

> search_web は **検索するだけの Discovery Tool** — **PASS**

- ページ本文取得: **なし**
- 意図解析 / crawl / 要約 / 複数ページ比較: **なし**

### 意味レベル

| Level | 該当 |
|-------|------|
| A — LLM query 生成 | **主** |
| B — token rank | **あり**（`rank_hits_for_query`） |
| C — Research Engine | **なし** |

---

## 2. read_url_text — 正式 Registry 昇格条件

| 項目 | 判定 |
|------|------|
| SSRF | PASS |
| localhost / private | PASS |
| redirect 安全 | PASS |
| http/https のみ | PASS |
| size / timeout | PASS |
| HTML raw | GAP |
| PDF / binary | PASS（拒否） |
| JavaScript | GAP（非対応） |
| error semantics | PASS |
| Registry 登録 | **未実施** — HUMAN_REVIEW_REQUIRED |
| adoption_status | `not_reviewed`（catalog） |

**実装改善:** 今回 **なし**。GAP は記録のみ。

---

## 3. 責務境界

| 状況 | Tool | 判定 |
|------|------|------|
| URL が分からない | search_web | PASS |
| Web 上から候補を探す | search_web | PASS |
| snippet だけで十分 | search_web | PASS |
| URL が既知 | read_url_text | PASS |
| 特定ページ本文 | read_url_text | PASS |
| 検索結果 URL を深読 | read_url_text | PASS |

**search_web への追加機能（意図解析、crawl、本文、要約等）:** **不要** — DEFER / 将来は別 Tool

**Responsibility boundary: PASS**

---

## 4. `search_web_include_mean` 改名評価

| 質問 | 結論 |
|------|------|
| 改名必要か | **RENAME NOT REQUIRED** |
| 理由 | 責務は Level A+B の **Discovery**。「意味を含めた検索」は **LLM 側（A）** + 軽 rank（B）。Level C は **別 Research Tool** 候補 |
| コード内 `search_web_include_mean` | **存在しない** |

---

## 5. HEAD vs WT 不一致

| 層 | search_web | read_url_text |
|----|------------|---------------|
| 実装 WT | ✅ disk | — |
| 実装 HEAD | ❌ | ✅ |
| Registry visibility=agent | ❌ | ❌ |
| Agent schema | ❌ | ✅ overlay |
| System Prompt | ✅ 言及 | ✅ 言及 |
| Catalog | ❌ | ✅ local:read_url_text |

**Registry: GAP** | **Agent schema: GAP**（search_web）| **System Prompt: GAP**

---

## 6. Search → Fetch Agent Loop

| 項目 | 判定 |
|------|------|
| 設計上の経路 | User → LLM → search_web → hits → LLM URL 選択 → read_url_text → LLM |
| HEAD production schema | **PARTIAL** — search_web 非公開 |
| read_url_text | PASS（overlay） |
| MAX_TOOL_ROUNDS | 5 — 多段 loop **可能** |
| tool message | raw JSON — PASS |
| 空結果継続 | LLM 判断 — **Agent 責務** |
| fetch 失敗→再検索 | **未規定** — LLM 判断 |
| Trial deterministic 2-round | **PASS**（`test_search_fetch_two_round_trial_deterministic`） |
| Live LLM E2E | UNKNOWN — 本 Phase 未実施（HEAD schema 制約） |

**Search → Fetch loop: PARTIAL**（Registry 採用で PASS 見込み）

---

## 7. Human Review 判定材料

| ID | 質問 | 推奨 | 判定 |
|----|------|------|------|
| **HR-1** | search_web を Registry agent 登録するか | **YES** — WT commit + visibility | **HUMAN_REVIEW_REQUIRED** |
| **HR-2** | read_url_text を experimental から正式昇格 | **YES** — Registry 登録 | **HUMAN_REVIEW_REQUIRED** |
| **HR-3** | search_web output schema 現状維持 | **YES** | **PASS** |
| **HR-4** | read_url_text output schema 現状維持 | **YES**（HTML raw は GAP 文書化） | **PASS** + GAP |
| **HR-5** | System Prompt と Registry 一致 | **YES** — 採用時に整合 | **SPEC_CHANGE_REQUIRED** |
| **HR-6** | Search→Fetch を基本 Web workflow | **YES** | **HUMAN_REVIEW_REQUIRED** |
| **HR-7** | 将来 Research Tool 別途必要か | **DEFER** — Level C 要求時 | **UNKNOWN** |

---

## 8. 推奨アクション（実装は次 Phase）

| Tool | Recommended action |
|------|-------------------|
| search_web | **ADOPT** — selective WT commit + Registry HR + gate trust |
| read_url_text | **ADOPT** — Registry HR（overlay → 正式） |
| System Prompt | **REPAIR** — HR-5 と同時 |
| Research Tool | **DEFER** |

---

## 9. テスト（読み取り実行）

| Suite | 結果 |
|-------|------|
| `tests/test_general_web_search.py` | 45 tests context — PASS |
| `tests/ai_tool/experimental/test_read_url_text.py` | PASS |
| `tests/ai_tool/agent_integration/test_production_bridge.py` | PASS |
| `tests/ai_tool/project_audit/test_web_tool_formal_adoption_review.py` | 新規 — 実行要 |

---

## 10. 最終報告（必須形式）

```
Tool:
search_web
Purpose:
Discovery

Tool:
read_url_text
Purpose:
Fetch

Responsibility boundary:
PASS

Search → Fetch loop:
PARTIAL

Agent schema:
GAP

Registry:
GAP

System Prompt:
GAP

Security:
SAFETY_REVIEW_REQUIRED

SSRF:
PASS (read_url_text) / N/A (search_web API-only)

Compatibility:
CHANGE (Registry + Prompt alignment required for full adoption)

Human Review Required:
YES

Recommended action:
ADOPT (both tools, with HR gates)

Production changes:
NONE

Git commit:
NONE

STOP:
YES
```

### `search_web_include_mean` への改名

> **RENAME NOT REQUIRED**

Discovery Tool として責務が成立。意味理解は LLM（Level A）。Tool 改名は混乱を招くのみ。

---

## 関連 Run

`runs/ai_tool/<timestamp>_web_tool_formal_adoption_review/`

**STOP — Human Review 判断待ち**
