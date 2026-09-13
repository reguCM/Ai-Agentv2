# URL Fetch Safety Policy — `local:read_url_text`

**状態:** EXPERIMENTAL  
**Tool:** `local:read_url_text`

Interface compatibility と Safety compatibility は分離する（[SAFETY_BOUNDARY.md](./SAFETY_BOUNDARY.md)）。

## 許可 scheme

| scheme | 許可 |
|--------|------|
| `http` | 許可 |
| `https` | 許可 |
| その他 (`file`, `ftp`, `gopher`, …) | **拒否** |

## URL 検証

| チェック | 実装方針 |
|----------|----------|
| malformed URL | `urlparse` — scheme/netloc 必須 |
| empty URL | 拒否 |
| userinfo (`user:pass@`) | **拒否** |
| 非標準ポート | 許可（ただし SSRF 再検証は hostname/IP 基準） |

## SSRF 防御（実装する範囲）

### 文字列レベル

| 対象 | 処理 |
|------|------|
| IP literal (IPv4/IPv6) | private / loopback / link-local / reserved → 拒否 |
| hostname `localhost` | 拒否 |
| suffix `.localhost` | 拒否 |
| `metadata.google.internal` 等 | 拒否（固定リスト） |

### DNS 解決後

接続前に `getaddrinfo` で解決し、**返却された全アドレス**が public であることを確認。

### Redirect

| 項目 | 方針 |
|------|------|
| 追跡 | 最大 5 回 |
| 各 hop | URL 再検証 + DNS 再検証 |
| 301/302/303/307/308 | GET のみ |

## 防御できない / UNKNOWN（隠さない）

| ケース | 状態 |
|--------|------|
| DNS rebinding（検証後〜接続前の TOCTOU） | **UNKNOWN** — 完全防御なし |
| 二段 redirect + 時間差 rebind | **UNKNOWN** |
| IDN homograph | 最小実装では未対応 |
| IPv6 zone ID | 拒否試行、完全性 UNKNOWN |
| プロキシ環境変数 `HTTP_PROXY` 悪用 | urllib は尊重 — **UNKNOWN**（experimental 注意） |

## Network 応答

| 項目 | デフォルト |
|------|------------|
| timeout | 10s |
| max_bytes | 65536 |
| HTTP メソッド | GET のみ |
| 4xx/5xx | error（本文は返さない） |
| binary | sniff 拒否 |
| Content-Type | text/* / json / xml / html 系のみ許可（experimental リスト） |

## 禁止

POST/PUT/PATCH/DELETE、Cookie 保存、credential、任意ヘッダ注入、ファイル書込。

## MCP Fetch との関係

比較のみ: [LOCAL_VS_MCP_FETCH.md](./LOCAL_VS_MCP_FETCH.md) — 本番 MCP 接続なし。

## 参照

- [specs/local_read_url_text.json](./specs/local_read_url_text.json)
- [candidate_research/fetch.md](./candidate_research/fetch.md)
