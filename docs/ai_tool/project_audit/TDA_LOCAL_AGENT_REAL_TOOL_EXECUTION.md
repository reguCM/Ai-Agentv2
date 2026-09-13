# Local Agent 実経路（Chat → LLM → Tool）

**日付:** 2026-08-30  
**Run:** `runs/ai_tool/20260830_203335_local_agent_real_execution`  
**判定:** `STOPPED_FOR_USER_CONFIRM`（ユーザー確認で停止）  
**Production 変更:** 0  
**pipeline.yaml:** 未変更  
**ollama pull / モデル切替 / 環境変数変更:** していない

実LLMによる Test A / B / C は **未実施**。未実施のものを PASS にしていない。

---

## モデル環境（読取のみ）

| 項目 | 値 |
|------|-----|
| 設定モデル | `deepseek-coder-v2:16b`（`pipeline.yaml` の `deepseek_coder_v2_16b`） |
| Ollama 応答 | `ollama show` / 前回 Chat で **404** |
| `ollama list`（起動中 serve） | **空** |
| シェル `OLLAMA_MODELS` | `D:\ollama\models` |
| ディスク上の manifest | `deepseek-coder-v2:16b`, `qwen3:8b`, `qwen3:14b`, `qwen2.5-coder:7b`, `gemma3:12b` |

設定モデルは **ディスクにある**。起動中の `ollama serve` がそれを list していない。  
別モデルへ切り替えていない。pull していない。

### 確認してほしいこと

別モデルへの変更ではなく、次のどちらかを指定してください。

1. **推奨:** 起動中 Ollama に `D:\ollama\models` を見せて再起動する（設定どおり `deepseek-coder-v2:16b` を使う）  
2. Chat だけ別モデル（例: `qwen3:8b`）を使う（その場合は対象と影響を書いてから変更する）

承認があるまで実LLMテストは再開しない。

---

## 観測表（Test A/B/C）

| 項目 | Test A | Test B | Test C | Web |
|------|--------|--------|--------|-----|
| Chat入力 | 未実施 | 未実施 | 未実施 | 未実施（Bが先） |
| LLM呼び出し | 未実施 | 未実施 | 未実施 | — |
| 使用モデル | deepseek-coder-v2:16b（404） | 同左 | 同左 | — |
| LLMによるTool選択 | 未実施 | 未実施 | 未実施 | — |
| Tool名 | — | 期待: get_gpu_status | 期待: get_gpu_processes | search_web |
| Tool実行 | — | 未実施 | 未実施 | — |
| Tool実結果 | — | 未実施 | 未実施 | — |
| Tool結果のLLM帰還 | — | 未実施 | 未実施 | — |
| 最終回答 | — | 未実施 | 未実施 | — |
| Web Search | なし | なし | なし | 未実施 |
| Cursor関与 | 調査・文書・Event文言 | 同左 | 同左 | — |
| Session | 経路は既存 | 同左 | 同左 | — |

モック LLM の単体テストでは、**モックが `get_gpu_status` を選んだあと** Dispatcher が実 Tool を実行する経路は通る。それは Test B の成功条件（実LLMが選ぶ）ではない。

---

## 報告 14 項

1. **変更したファイル**  
   - `ai_tool/chat_interface/events.py`（ユーザー向け status 行）  
   - `ai_tool/chat_interface/agent_turn.py`（`llm_send` / `tool_select` Event）  
   - `ai_tool/chat_interface/static/app.js`（処理を見る）  
   - `ai_tool/chat_interface/server.py`（health に環境読取）  
   - `ai_tool/chat_interface/ollama_env.py`（list / ディスク読取。chat しない）  
   - テストと本報告書・Run  
   `agent.py` / Registry / `pipeline.yaml` / Research は未変更。

2. **変更理由**  
   処理イベントを指定の日本語に近づける。モデル環境を実行せず記録する。

3. **Chat → Agent**  
   既存 `run_chat_ui.py` → `run_chat_turn`。agent.py は import しない。

4. **Agent → LLM**  
   `tools.system.llm.chat`。設定モデルは 404 のため実呼出しテストは停止。

5. **LLM → Tool選択**  
   構造あり（Ollama `tool_calls`）。実LLMでは未確認。

6. **Agent → Tool実行**  
   Registry の importlib 実行（Chat 側 `_execute_agent_tool`）。新しい Dispatcher Core は作っていない。

7. **Tool → LLM帰還**  
   `role=tool` で messages に戻す構造あり。実LLMでは未確認。

8. **Chatへの回答**  
   構造あり。実LLMでは未確認。

9. **Event表示**  
   「処理を見る」に受信 / LLM / Tool選択 / 実行 / 検索有無 / Session / Cursor 未接続を出すよう更新。実画面での LLM 成功は未確認。

10. **Cursorが関与した部分**  
    コード読取、Event 文言、環境調査、文書。Tool 結果の作文はしていない。

11. **Local Agent自身が実行した部分**  
    今回の実LLMターンは無し。モックテスト内の Dispatcher 実行のみ（実LLM選択ではない）。

12. **未実装**  
    Research / Memory / Discovery / Cursor API / スマホ / Tool作成本接続 / Web Search 実測 / agent.py とのループ一本化。

13. **モデル404**  
    継続。原因候補は serve が `D:\ollama\models` を見ていないこと。ディスクには設定モデルがある。

14. **次に実装可能な範囲**  
    ユーザーが Ollama のモデル可視性を直したあと、同じ Chat 経路で Test A → B（実LLMが get_gpu_status を選ぶ）→ 成功後に Search。GPU 成功前に Search を同時実装しない。

---

## 四者の分離

| 主体 | 今回したこと |
|------|----------------|
| Cursor | 調査・Event・文書。回答の代行なし |
| Local Agent | 実LLMターンなし |
| LLM | 未呼び出し（404 回避のため停止） |
| Tool | 実LLM経路では未実行 |

Web Search は Test B 成功後。今回は進めていない。
