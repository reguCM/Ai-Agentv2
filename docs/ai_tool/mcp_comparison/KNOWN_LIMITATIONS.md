# Known Limitations — MCP Fetch Comparison Phase 1

**Run:** `runs/ai_tool/20260828_153335_mcp_fetch_comparison/`

当 Run に**存在しない**事項は記載しない。14 ケース外は **NOT EVALUATED**。

---

## 1. 比較範囲の制限（Run 根拠あり）

| 項目 | 状態 |
|------|------|
| ケース数 | **14 のみ**（`inputs.json` cases 配列長 14） |
| MCP Server | `mcp-server-fetch` **2026.8.18** のみ |
| MCP 起動 | stdio subprocess、`--ignore-robots-txt` 付き |
| ネットワーク | 主に `127.0.0.1` fixture + `normal_https` の 1 URL |
| Local harness | 10 ケースは `fetch_fn` fixture 再生（production HTTP ではない） |
| 既存 MCPToolProvider | list_descriptors **失敗**（当 Run）— Provider 経由の比較は未完了 |

---

## 2. 機能・挙動（14 ケースで NOT EVALUATED）

| 項目 | 根拠 |
|------|------|
| MCP `start_index` chunk 取得 | 14 cases の inputs に未使用 |
| MCP robots.txt デフォルト動作 | Run は `--ignore-robots-txt` |
| MCP output_schema | descriptor 上 null —  structured 出力未評価 |
| MCP annotations（readOnlyHint 等） | Run 時 **null** — hint の信頼性評価不可 |
| Local DNS rebinding TOCTOU | 政策上 UNKNOWN — 本 Run 未テスト |
| Local binary sniff 全パターン | 14 cases に binary ケースなし |
| redirect → public → private（Local production 起点） | safety_redirect_private は起点 loopback |
| 並列 fetch | Run 設計に無し |
| persistent MCP session / connection reuse | execution note: per-call subprocess |
| Agent Tool Selection | evaluation: agent_integration false |
| Registry 統合 | evaluation: registry_registration false |

---

## 3. 環境依存

| 項目 | 記録 |
|------|------|
| normal_https | inputs notes: **Environment-dependent** |
| safety_private_ip MCP success | 192.168.0.1 への応答内容はネットワーク環境依存 |
| MCP SDK 版本 | Run notes: venv で MCP **1.x**（本番 requirements は 2.x） |
| Node.js / NPM | mcp-server-fetch 警告ログ（Readability.js fallback）— 比較結果への影響は **Run 未計測** |

---

## 4. 設計評価（Run hypotheses — 限定的）

以下は `comparison.json` hypotheses に記録された**設計上の仮説ラベル**。14 ケースだけでは確定しない。

| 項目 | Run verdict | 意味 |
|------|-------------|------|
| Trust model 詳細 | H-MCP-5: SUPPORTED | catalog trust tier 不足の指摘 — **実装提案ではない** |
| Provider I/O 完全互換 | H-MCP-2: PARTIALLY_SUPPORTED | adapter 必要の示唆 |
| Common contract | H-MCP-6: PARTIALLY_SUPPORTED | I/O 形状差 |

---

## 5. 意図的に行っていないこと（evaluation.json + Phase 1 スコープ）

- Agent 統合
- Registry 登録
- MCP 本番接続 / allowlist
- MCP 自動選択・自動インストール
- Tool 自動生成
- 有料 API

---

## 6. Local Tool 関連（Phase 1 外だが混同防止）

| 項目 | 状態 |
|------|------|
| Real Web Smoke Test | **別 Run**（`20260828_153616_read_url_real_web_smoke`）— 本 14 case Run には含まれない |
| Deterministic pytest | **別ゲート**（mock / local server） |
| `local:read_url_text` 正式採用 | **未実施** |

---

## 7. ドキュメント上の限界

- 本ディレクトリは **20260828_153335 Run の Freeze** — 再実行・数値更新は Phase 2 以降
- 調査メモ（candidate_research/fetch.md）の SPECIFICATION は Run 前情報 — OBSERVED と混同しない（[SAFETY_COMPARISON.md](./SAFETY_COMPARISON.md) 参照）
