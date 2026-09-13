# Web Tool Security Review

**Phase:** Web Tool Formal Adoption Review Phase 2  
**HEAD:** `875cc47`  
**Scope:** `search_web` (WT) + `read_url_text` (HEAD)  
**Changes:** なし（読み取り専用）

---

## 分類凡例

| ラベル | 意味 |
|--------|------|
| PASS | 実装・テストで確認 |
| GAP | 既知の制限（仕様違反ではない） |
| UNKNOWN | 完全性未証明 |
| SAFETY_REVIEW_REQUIRED | 採用前に人間判断 |

---

## search_web

| 項目 | 判定 | 根拠 |
|------|------|------|
| network access | PASS（意図的） | DDG + Wikipedia API への HTTPS GET |
| ユーザー指定 URL fetch | **なし** | 固定 API endpoint のみ |
| SSRF（search 経路） | PASS | ユーザー URL を connect しない |
| localhost / private IP | N/A | search 自体は user URL 非使用 |
| redirect | N/A | API JSON 応答 |
| DNS resolution | 固定ホスト | api.duckduckgo.com, wikipedia.org |
| URL scheme 制限 | N/A | |
| timeout | PASS | `REQUEST_TIMEOUT=12s`（research.web.http_get） |
| response size | GAP | API JSON — 明示 max なし（backend limit=5） |
| filesystem write | PASS | なし |
| unexpected write | PASS | なし |
| agent_tool_gate | GAP | HEAD Registry 未登録 → Agent 未到達 |
| 固定値 / stub hits | PASS | テストで確認 — 空 query は error |
| observation semantics | GAP | GPU 型 unknown 体系は **不要** — Web hits は API 由来 |

### search_web リスク要約

Outbound search API のみ。**SSRF 面は read_url より低い。** 採用時は **network policy 文書化** と gate trust が HR 対象。

---

## read_url_text

| 項目 | 判定 | 根拠 |
|------|------|------|
| network access | PASS（意図的） | 任意 public http/https GET |
| SSRF | PASS | `ssrf.py` + DNS 解決後チェック |
| localhost | PASS | `test_safety_ssrf_blocked` |
| private IP | PASS | 10.x, 192.168.x, 169.254.x 等 |
| loopback | PASS | 127.0.0.1, ::1 |
| metadata.google.internal | PASS | BLOCKED_HOSTNAMES |
| redirect | PASS | 最大 5 hop、各 hop 再 validate |
| redirect → private | PASS | `test_redirect_revalidates_private_target` |
| URL scheme | PASS | http/https のみ |
| userinfo in URL | PASS | 拒否 |
| timeout | PASS | 既定 10s（max 60） |
| response size | PASS | max_bytes 65536 既定 |
| binary / PDF | PASS | content-type + sniff 拒否 |
| JavaScript | GAP | **非対応**（仕様 known_limitation） |
| HTML | GAP | raw decode — タグ除去なし |
| DNS rebinding TOCTOU | UNKNOWN | policy 明記 |
| HTTP_PROXY 悪用 | UNKNOWN | policy 明記 |
| filesystem write | PASS | なし |
| agent_tool_gate | PASS | experimental も gate 通過 |
| error semantics | PASS | ok=false + error 文字列 |

### read_url_text リスク要約

**medium risk**（catalog）。SSRF 防御はテスト済み。**正式採用時も SAFETY_REVIEW_REQUIRED**（DNS rebinding / proxy UNKNOWN の明示承認）。

---

## Agent Tool Gate 再利用

| Tool | gate 適用 |
|------|-----------|
| search_web（採用後） | `authorize_tool_execution` — 要 HR trust 方針 |
| read_url_text | 既に gate 経由（production_bridge） |

新 network policy ファイルは **今回作成しない**。採用時に `URL_FETCH_SAFETY_POLICY.md` 更新が HR 候補。

---

## 横断

| 項目 | 判定 |
|------|------|
| search + fetch 連続 outbound | 採用後は **意図的** — LLM 制御下 |
| unexpected filesystem | PASS |
| MCP 本番接続 | なし |

---

## 推奨（Security 観点）

1. search_web 採用時: Registry + gate auto_allow 方針を HR
2. read_url_text 昇格時: SSRF UNKNOWN を known limitation として HR 承認
3. 新 network policy: **DEFER** — 既存 policy 拡張で足りる見込み

**Overall Security for formal adoption:** **SAFETY_REVIEW_REQUIRED**（blocker ではない）
