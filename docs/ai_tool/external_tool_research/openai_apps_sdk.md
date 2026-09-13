# OpenAI Apps SDK (Research Notes)

調査日: 2026-08-28

## 位置づけ

2025 年以降、OpenAI は ChatGPT 内アプリ向けに **Apps SDK** を提供。基盤は **Model Context Protocol (MCP)**。旧「ChatGPT Plugin」方式の後継として、MCP を中心に据えている。

## 構成要素

1. **MCP Server（必須）** — Tool と（任意で）Resource を公開
2. **Web UI（任意）** — iframe 内コンポーネント。MCP Apps bridge（JSON-RPC over postMessage）
3. **ChatGPT ホスト** — Developer Mode で `/mcp` URL を登録

## AI-Agent との関係

| Apps SDK 機能 | AI-Agent Phase 1 |
|---------------|------------------|
| MCP tools/list, tools/call | 参考にし `MCPToolProvider` 実装 |
| MCP Resources | 未実装 |
| ChatGPT UI / iframe | 対象外（ローカル Agent） |
| Plugin ディレクトリ公開 | 対象外 |

AI-Agent は Ollama + ローカル Python Agent のため、**MCP クライアント層の設計のみ借用**する。

## MCP Apps 互換

Apps SDK UI は MCP Apps 標準に準拠。ChatGPT 固有拡張として `window.openai` があるが、ベースライン互換は MCP Apps bridge。

## セキュリティ・運用

- 組織検証・ガイドライン準拠が公開前提（ChatGPT 側）
- ローカル Agent では同等の allowlist / trust ポリシーを自前実装する必要あり

## リンク

- [Introducing apps in ChatGPT and the Apps SDK](https://openai.com/index/introducing-apps-in-chatgpt/)
- [Apps SDK Quickstart](https://developers.openai.com/apps-sdk/quickstart)
- [MCP Apps compatibility in ChatGPT](https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt)

## 結論（Phase 1）

**EXPERIMENTAL 参照のみ。** 実装は MCP プロトコル層に限定。Apps SDK 固有の UI / 公開フローは NEXT_STEPS で必要になった時点で再評価。
