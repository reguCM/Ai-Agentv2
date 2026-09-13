# Failure Analysis — MCP Fetch Comparison Phase 1

**Run:** `runs/ai_tool/20260828_153335_mcp_fetch_comparison/`

「実験上の不一致」「Tool Safety Failure」「インフラ/timeout 想定内」を混同しない。

---

## 1. 分類の定義（本 doc）

| 分類 | 意味 |
|------|------|
| **Expected mismatch** | Local と MCP の設計差により ok 不一致が予期される |
| **Tool error (both sides)** | 両方 ok false — HTTP 4xx/5xx 等の failure カテゴリ |
| **Safety block (Local)** | Local SSRF が fetch 前に拒否 — Safety 機能として意図された失敗 |
| **MCP reach + outcome** | MCP がネットワーク到達後、成功または Server-side error |
| **Infra / timeout artifact** | クライアント切断・ReadTimeout・fixture server ConnectionAbortedError |

---

## 2. ok 不一致 6 ケース

| case_id | Local | MCP | 分類 | 説明（Run 事実） |
|---------|-------|-----|------|------------------|
| boundary_redirect | ok | not ok | **Infra / timeout artifact** | MCP: `ReadTimeout('')`, 30901 ms。Local harness: redirect 処理成功。 |
| failure_timeout | not ok | ok | **Expected mismatch** | Local: `timeout` @ 3009 ms（timeout_seconds=3）。MCP: ok @ 27122 ms。MCP schema に timeout なし。 |
| safety_localhost | not ok | ok | **Safety block vs MCP reach** | Local: SSRF block。MCP: localhost 本文取得成功。 |
| safety_private_ip | not ok | ok | **Safety block vs MCP reach** | Local: SSRF block。MCP: 192.168.0.1 応答成功。 |
| safety_link_local_metadata | not ok | not ok | **Safety block + MCP connect fail** | Local: SSRF block。MCP: ConnectError（到達試行あり）。 |
| safety_redirect_private | not ok | not ok | **Safety block + MCP timeout** | Local: 起点 URL が loopback のため SSRF block。MCP: ReadTimeout 30843 ms。 |

---

## 3. 両方 not ok — failure カテゴリ

| case_id | Local error | MCP error text（要約） | 分類 |
|---------|-------------|------------------------|------|
| failure_404 | `http error: 404` | `status code 404` | **Tool error (both sides)** |
| failure_500 | `http error: 500` | `status code 500` | **Tool error (both sides)** |

---

## 4. MCP not ok のみ（Local ok 以外）

| case_id | MCP message | 分類 |
|---------|-------------|------|
| boundary_redirect | `Failed to fetch .../redirect: ReadTimeout('')` | **Infra / timeout artifact** |
| safety_link_local_metadata | `ConnectError('All connection attempts failed')` | **MCP reach + outcome** |
| safety_redirect_private | `ReadTimeout('')` | **Infra / timeout artifact** |

---

## 5. `/slow` と ConnectionAbortedError

### Run 内記録

- **case:** `failure_timeout`
- **fixture path:** `/slow`（fixture server は `slow_seconds: 15.0` で sleep）
- **Local:** `error: "timeout"`, duration **3009.731 ms**（timeout_seconds=**3**）
- **MCP:** ok **true**, duration **27122 ms**, 本文取得

### ターミナルログ（Run 実行時）

fixture server 側で `ConnectionAbortedError [WinError 10053]` が `/slow` 応答中に記録された（クライアントが先に切断）。

### 分類

| 側 | 解釈 |
|----|------|
| Local timeout | **Expected mismatch** — Local timeout パラメータが機能し、3s で打ち切り。Tool Failure ではなく **timeout 設計どおり**。 |
| Server ConnectionAbortedError | **Infra / timeout artifact** — クライアント切断に伴う server 側例外。実験 Run の exit code は **0**（実験失敗ではない）。 |
| MCP 27122 ms success | **Expected mismatch** — MCP は同一 slow endpoint を **より長い時間**かけて成功。timeout 制御の差の観測。 |

**結論（Run 根拠）:** `/slow` の ConnectionAbortedError は **Local クライアント timeout による想定内の副次現象**であり、Phase 1 実験全体の失敗原因ではない。Local の `failure_timeout` ok=false も **Safety/Failure テストとして意図された Tool エラー表現**（timeout）である。

---

## 6. Safety Failure との区別

| 事象 | Safety Failure? | 理由 |
|------|-----------------|------|
| Local SSRF block（safety_*） | **No（Local 意図動作）** | 政策どおり fetch 前拒否 |
| MCP localhost 成功 | **Not Local Safety Failure** | Local 側はブロック成功。MCP 側は別 trust boundary。 |
| MCP private IP 成功 | 同上 | 観測事実として記録；「MCP が安全」とは記載しない |
| failure_404 / 500 | **No** | HTTP error ハンドリングテスト |

---

## 7. Run 内 FAILURE_ANALYSIS.md（原文サマリ）

Run 生成時点で divergent ok flags として列挙された case:

- boundary_redirect
- failure_404, failure_500
- failure_timeout
- safety_localhost, safety_private_ip

（safety_link_local_metadata / safety_redirect_private は両方 not ok のため Run 簡易 MD には未列挙 — 本 doc で補完）

---

## 8. 実験失敗ではないもの

- evaluation.json: `success_criteria_met: true`
- 14/14 ケース結果が `comparison.json` に存在
- ok 不一致は比較実験の **データ** であり、runner クラッシュではない
