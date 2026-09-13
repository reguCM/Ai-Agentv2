# Cursor vs AI-Agent

**監査日:** 2026-08-28

本プロジェクト監査における**必須の役割分離**。

---

## 定義

| 主体 | 役割 |
|------|------|
| **Cursor** | 外部 IDE / AI 開発支援環境。人間と協調してコード・テスト・ドキュメント・実験ランナーを**作成・実行**する。 |
| **AI-Agent** | 本リポジトリが開発している**ローカル LLM Agent**（`agent.py` + Ollama + Registry Tool）。 |

---

## 何が Cursor 作業か

以下は **「Tool Creation 工程を Cursor（人間支援付き）で実装した」** 例であり、  
**「AI-Agent が自律的に Tool を作った」** ではない。

| 成果 | 実際の作成主体 | AI-Agent 自律? |
|------|---------------|----------------|
| `ai_tool/experimental/scoped_read/` | Cursor + 人間指示 | **No** |
| `ai_tool/experimental/read_url/` | Cursor + 人間指示 | **No** |
| Tool Creation Validator | Cursor + 人間指示 | **No** |
| Context Builder Phase 1–2 | Cursor + 人間指示 | **No** |
| MCP 比較 harness / ドキュメント | Cursor + 人間指示 | **No** |
| `docs/ai_tool/*` 監査・Freeze 文書 | Cursor + 人間指示 | **No** |

---

## 何が AI-Agent 自身のコードか

| コンポーネント | 説明 |
|---------------|------|
| `agent.py` | Agent 本体（LLM ループ） |
| `tools/*` | Agent が import して実行する Tool |
| `registry/tools.json` | Agent が読む Tool 定義 |
| `tools/system/agent_tool_gate.py` | Agent 実行時の認可 |
| Pipeline Tools | Agent **コードベース内**の Tool Builder フロー（LLM 公開外） |

Agent は **既存 Registry Tool を選択・実行** できる。  
新規 Tool の **Specification → Implementation → Registry** 自動パイプラインは **未統合**。

---

## Tool Builder Pipeline との関係

Registry には `create_tool_proposal`, `register_tool` 等 **pipeline Tool** がある。  
これらは AI-Agent **コードベース内**の研究 / Tool Builder 経路用。

ただし:

- Agent の通常 LLM ループ（`visibility: agent`）からは **見えない**
- Tool Creation Layer（`docs/ai_tool/tool_creation/`）とは **別系統**（自動マージなし）
- 「Agent が自律的に Tool を生成した」とは **現状言えない**

---

## External Help / Context Builder

| 機能 | Cursor への自動送信 | Agent 自律 |
|------|-------------------|------------|
| Context Builder | **No** — ファイル生成のみ | **No** |
| External Help Package | **No** — パッケージ出力のみ | **No** |
| Diagnostic FW NH14 Shadow | **No** — 研究記録 | **No** |

---

## 記載ルール（以降の文書）

| 誤り | 正しい表現 |
|------|-----------|
| AI-Agent が read_url を実装した | Cursor 支援下で experimental Tool として実装した |
| AI-Agent が MCP 比較を実施した | 開発者/Cursor が実験ランナーを実行した |
| Context Builder が LLM に自動投入 | Context Builder が manifest を**生成**（投入は未実装） |

---

## 監査への含意

- **COMPLETED_CAPABILITIES** は「リポジトリとして動作確認済み」を列挙
- **Agent 自律能力** と **開発環境で構築した experimental 資産** は分けて記録する
