# Local Agent Chat Interface（R3.5-B）

**日付:** 2026-08-30  
**起動:** `python ai_tool/run_chat_ui.py` → http://127.0.0.1:8765/  
**Run:** `runs/ai_tool/20260830_201044_r3_5b_chat_interface`  
**Production 変更:** 0（`agent.py` 未変更、Registry 未変更）  
**新規 C3:** 0  
**既定 Workflow:** `facet_discovery="off"`  
**Cursor 接続:** なし  
**判定:** `PARTIAL_PASS`（一部成立）

---

## 判定

```text
R3.5-B
判定: PARTIAL_PASS

実装: Chat UI / Event / Session / Tool作成分岐 あり
Production: 変更なし（agent.py を破壊していない）
既存Workflow: 既定 off のまま
Cursor接続: なし
実LLM: Ollama は呼んだ。モデル deepseek-coder-v2:16b は未導入（404）
Tool: mock 経路と get_gpu_status 直接実行は確認。LLM 経由の Tool 選択はモデル不足で未達
Web Search: 経路は実装。実検索は LLM 未達のため未実行
Memory: dump_all なし。全記憶 0 Facet を LLM に渡していない
Research: ResearchRecord 保存なし（正確に表示）
Session: JSON Session あり（新 Core ではない）
Chat: ブラウザから送受信できる
```

無理に PASS にしない。窓口は動く。設定モデルがこのマシンに無い。

---

## 実際の経路（実装後）

```text
User
 ↓
ブラウザ Chat UI（127.0.0.1:8765）
 ↓
run_chat_turn
 ↓
分岐
  ├─ 通常 → Ollama（tools.system.llm.chat）+ visibility=agent Tool
  └─ Tool作成 → create_tool_proposal（Registry 書き込みなし）
 ↓
Experimental bind/diff/select は表示のみ
 ↓
Event Log + Session JSON
 ↓
「処理を見る」
```

`agent.py` は import しない（起動ループが走るため）。  
使う実行主体は Local Agent の Ollama と Registry Tool であり、Cursor API ではない。

CLI `python agent.py` は従来どおり残している。

---

## 成功条件

| # | 条件 | 結果 |
|---|------|------|
| 1 | ブラウザからチャットできる | 成立（http://127.0.0.1:8765/） |
| 2 | Ollama を呼べる | 呼び出しはした。モデル 404 |
| 3 | Tool 使用の有無 | Event で表示。実LLMでは未選択 |
| 4 | Tool 結果 | mock + `get_gpu_status` 直接実行で確認 |
| 5 | Web Search 有無 | 表示あり。実検索は未達 |
| 6 | Research / Memory 参照有無 | 保存なし / 0 Facet と表示 |
| 7 | LLM 材料の選択 | dump_all なし。Case E は 0→選択表示のみ |
| 8 | Tool作成を区別 | Case D `route=tool_creation`、Registry 未変更 |
| 9 | Session | `cs-...` JSON |
| 10 | Cursor が実行主体ではない | UI と Event で未接続 |
| 11 | 既存テスト | R1 / R2 / R3 / P / R3.5-A / Chat テスト緑 |
| 12 | Production Workflow | 未変更 |

---

## Case A–E（Local Agent 経路）

同一 Session で `run_chat_turn` を実行した。Cursor が回答を書いていない。

### Case A「こんにちは」

- route: chat
- Tool: 使用なし
- Search: なし
- 実LLM: モデル 404
- ブラウザでも同じエラーと「処理を見る」を確認

### Case B「GPUの状態を教えて」

- LLM 経由の Tool 選択: モデル不足で未達
- Tool 単体（Local Agent）: `get_gpu_status` 成功  
  GPU: NVIDIA GeForce RTX 3060 / 温度 59 / VRAM 2465/12288  
  これは Cursor の編集ではなく、既存 Tool の実測

### Case C「RTX 3060について最新情報を調べて」

- Web Search: LLM が Tool を選べず未実行
- ResearchRecord: **保存なし**（仕様どおり）

### Case D「CPU温度を取得するToolを作って」

- Tool作成要求として分岐
- `create_tool_proposal` まで。Registry **書き込みなし**
- 仕様文の LLM 生成はモデル 404 で失敗。登録はしていない
- 状態: ユーザー確認待ち

### Case E「前に調べたAをPython 3.13で使えるか調べて」

- bind: `UNRESOLVED`（Session に ResearchRecord が無い。技術名を推測していない）
- python_version: 3.13 を差分として記録。3.12 Evidence のコピーは **false**
- 全記憶 0 Facet。dump_all を LLM に渡していない
- Agent 経路では Record が無いので、R3 の 19→4 は **この窓口では再現しない**（未接続を隠していない）

---

## Local Agent 自身で確認できた能力

- ブラウザ Chat と Session
- Ollama への実際の呼び出し（失敗内容も Event に残る）
- Tool 使用なし / Tool作成 / Research 保存なし の区別
- `get_gpu_status` の実測
- Experimental pointer の UNRESOLVED 表示
- Cursor 未接続の明示

## Cursor が補助していた部分

- 本 Chat UI のコード作成
- pytest / 監査文書
- R1〜R3 harness（この窓口には未接続）

## まだ Cursor に依存している部分

- 設定モデルの導入（`ollama pull`）は人間 / Cursor 作業
- ファイル作成・pytest・コード修正は従来どおり Cursor
- bind が成立する ResearchRecord 蓄積は Agent Chat にまだ無い

## 次に実装すべき部分

1. 利用可能な Ollama モデルを入れる（pipeline.yaml は勝手に変えない）
2. モデルがある状態で Case B / C を再実行（Tool / Web Search の LLM 選択）
3. Prompt と Registry のファイル Tool 不一致（R3.5-A の未修正問題）
4. Research 可視化の本接続は、保存が始まってから（今出すと誤解する）

---

## 起動

```text
python ai_tool/run_chat_ui.py
```

ブラウザ: http://127.0.0.1:8765/

Avatar / 音声 / スマホ / Cursor API / 自動 Registry 登録 / 全 Memory の LLM 投入は作っていない。
