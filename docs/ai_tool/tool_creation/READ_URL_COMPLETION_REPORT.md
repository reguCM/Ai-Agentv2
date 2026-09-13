# New Tool Creation Phase 2 — `local:read_url_text` Completion Report

**日付:** 2026-08-28  
**Run:** `runs/ai_tool/20260828_062224_read_url_text_tool/`

---

## 1. Specification

| 項目 | 結果 |
|------|------|
| ファイル | `specs/local_read_url_text.json` |
| Validator | **ACCEPT** |
| Safety Policy | [URL_FETCH_SAFETY_POLICY.md](./URL_FETCH_SAFETY_POLICY.md) |

## 2. Validator / Tool Creation Layer 修正

| 変更 | 理由 |
|------|------|
| `safety_rules.py` | read_only + network_access は `network` ∈ allowed_operations なら許可 |

**分類:** Tool Creation Layer 側（Scoped Read 時は未発見）。Network Tool 作成で顕在化。

## 3. Implementation

| 項目 | 値 |
|------|-----|
| Path | `ai_tool/experimental/read_url/` |
| HTTP | urllib.request（stdlib、新規依存なし） |
| 分離 | `ssrf.py` / `http_client.py` / `reader.py` |

## 4. Test

| カテゴリ | 件数（概算） |
|----------|--------------|
| Normal | 2 |
| Boundary | 3 |
| Invalid | 4 |
| Safety/SSRF | 9+ |
| Failure | 7 |
| Redirect | 1 |

Tool Creation pytest: 35 passed（gold spec 4 件）

## 5. Safety

```text
unsafe_accept:    0
ssrf blocked:     localhost / private IP / metadata hostname
redirect re-check: 実装済（テスト済）
DNS rebinding:    UNKNOWN（政策に明記）
```

## 6. SSRF 対策範囲

**実装:** scheme 限定、hostname blocklist、IP literal 判定、DNS 解決後 private 拒否、redirect 各 hop 再検証、GET のみ、size/timeout

**未防御（明示）:** DNS rebinding TOCTOU、IDN homograph、HTTP_PROXY 経由

## 7. Catalog

```text
tool_status: unavailable
experiment_status: experimental
adoption_status: not_reviewed
```

Registry: **未登録**

## 8. 既存 Tool への影響

**なし** — agent/tools/registry/read_file 未変更

## 9. Scoped Read から改善された点

| 点 | 内容 |
|----|------|
| Validator | network read-only Tool が通るよう修正 |
| 新規作成 | Mapping なしで Specification から作成 |
| Safety 政策 | Network 専用 URL_FETCH_SAFETY_POLICY |

## 10. 再発 / Network 固有の問題

| 分類 | 問題 |
|------|------|
| Test | 実ネットワーク回避のため fetch_fn 注入パターン必須 |
| Test | local server テストは validate patch が必要 |
| Specification | risk medium + network — human_required 将来ゲート |
| Safety | 完全 SSRF 防御不可 — 「安全」と断定しない設計 |
| Tool Creation | TEST_CONTRACT 映射は依然手動 |

## 11. 実Tool作成工程の成功例か

**YES（experimental 隔離 Tool、ゼロから作成）**

Specification → Validator → Implementation → Test → Safety → Catalog Draft まで一周。

## 12. 次の作業候補（最大3）

1. SSRF テスト用 localhost server + validate 注入の共通 fixture 化
2. human_required ゲートと Network Tool の統合設計（Agent Phase）
3. MCP Fetch 比較実験（接続のみ、別 Phase）

## 13. テスト分類（Deterministic vs Real Web Smoke）— 2026-08-28 追記

### Deterministic Safety / Contract Tests

| 項目 | 内容 |
|------|------|
| ファイル | `tests/ai_tool/experimental/test_read_url_text.py` |
| 方式 | mock `fetch_fn` / `local_http_server` fixture |
| 目的 | SSRF、redirect、404/500、timeout、size、binary、契約 |
| 結果 | **28 passed**（ネットワーク非依存） |

`example.com/...` 等の URL 文字列は **mock 入力のみ**。実在ページの fixture として扱わない。

### Real Web Smoke Test

| 項目 | 内容 |
|------|------|
| ファイル | `tests/ai_tool/experimental/test_read_url_text_smoke.py` |
| マーカー | `@pytest.mark.real_web` |
| 実行 | `pytest -m real_web` または `python ai_tool/run_read_url_smoke.py` |
| 対象 URL | `https://example.com/`, `https://www.w3.org/robots.txt`, `https://www.iana.org/domains/example` |
| 目的 | 実 DNS/HTTP/公開ページ取得の基本動作確認 |
| 結果 | **5 passed**（2026-08-28） |
| Run | `runs/ai_tool/20260828_153616_read_url_real_web_smoke/` |

Golden test（本文完全一致）は行わない。ネットワーク障害時は Deterministic 合否と分離（`READ_URL_SKIP_REAL_WEB=1` で skip 可）。

MCP 比較 harness の `harness_fixture` は SSRF 通過用に **実在** `https://example.com/` を使用し、本文取得は `fetch_fn` → ローカル fixture server（架空 `/fixture/...` パスは使用しない）。

## STOP

Agent / Registry / MCP 本番接続 — 未着手

## 参照

- [LOCAL_VS_MCP_FETCH.md](./LOCAL_VS_MCP_FETCH.md)
- [URL_FETCH_SAFETY_POLICY.md](./URL_FETCH_SAFETY_POLICY.md)
