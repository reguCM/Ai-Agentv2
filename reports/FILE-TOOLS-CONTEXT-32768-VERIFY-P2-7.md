# FILE-TOOLS-CONTEXT-32768-VERIFY-P2-7 作業 REPORT

**TASK_ID:** `FILE-TOOLS-CONTEXT-32768-VERIFY-P2-7`  
**担当:** Cursor  
**状態:** `P2-7_VERIFY_COMPLETE`  
**日付:** 2026-09-02

---

## 1. 目的

Qwen3:14b の Ollama `num_ctx=32768` が、**現在の AI-Agent 本番経路**（`POST /api/chat` + Native Tool Calling）で**実用上問題なく使えるか**を検証する。

32768 を Agent 標準 Context Size の候補として採用できるかを、RTX 3060 12GB の実環境で確認する。

---

## 2. 変更内容

| 項目 | 変更前（P2-6 適用後） | 変更後 |
|------|----------------------|--------|
| `qwen3_14b.context_limit` | **8192** | **32768** |

※ 指示書の「4096 → 32768」に対し、実際の変更前状態は P2-6 適用済みの **8192**。

| ファイル | 変更 |
|----------|------|
| `config/llm_models.yaml` | `qwen3_14b.context_limit: 32768` のみ |

**変更しなかったもの:** Agent、Tool、Registry、Prompt、Thinking、timeout、その他プロファイル。

---

## 3. 環境

| 項目 | 値 |
|------|-----|
| Ollama | **0.33.2** |
| モデル | **qwen3:14b**（14.8B, Q4_K_M, max context 40960） |
| API | **POST /api/chat**（`tools.system.llm.chat`） |
| Thinking | **未指定（None）** |
| GPU | **NVIDIA GeForce RTX 3060 12GB** |
| Python | 3.10.11 / Windows 10 |
| 診断スクリプト | `ai_tool/agent_integration/file_tools_context_32768_verify_p27.py` |
| 一次資料 | `runs/ai_tool/20260902T071425Z_file_tools_context_32768_verify_p27/verify.json` |

### VRAM 初期 vs 負荷後

| タイミング | used | free | 備考 |
|------------|-----:|-----:|------|
| 検証開始前 | 1948 MiB | 10166 MiB | モデル未ロード |
| 1回目 search 後 | **11815 MiB** | **299 MiB** | 32768 ctx でモデルロード |
| 検証終了時 | **11948 MiB** | **166 MiB** | **VRAM ほぼ上限** |

---

## 4. テスト条件

| テスト | 回数 | 内容 |
|--------|-----:|------|
| **main** | 5 | 本番 instrumented chain、広い search プロンプト（P2-6 同等） |
| **fixed_payload** | 3 | P2-5F 相当：50 match 固定 payload + 本番 `ollama_chat` |
| **list_then_read** | 2 | `list_files → read_file`（P2-4 B） |
| **multi_read** | 2 | `search_files → read_file → read_file` 試行 |

検索 payload（今回）: **50 match / 10286B / truncated=true**

---

## 5. 各 Run 結果サマリー

### 5.1 main（instrumented search → read）× 5

| Run | search_files | Native read_file | read_file 実行 | Type 3 | Type 4 | エラー | 時間 |
|-----|-------------|------------------|----------------|--------|--------|--------|-----:|
| 1 | Yes (50 match) | **Yes** | **Yes** | No | No | round2 **timeout** | 208s |
| 2 | Yes | **Yes** | **Yes** | No | No | round2 **timeout** | ~200s |
| 3 | Yes | **Yes** | **Yes** | No | No | round2 **timeout** | ~200s |
| 4 | Yes | **Yes** | **Yes** | No | No | round2 **timeout** | ~200s |
| 5 | Yes | **Yes** | **Yes** | No | No | round2 **timeout** | ~200s |

- **5/5** で `search_files → read_file` Native Tool Call + 実実行に成功
- **5/5** で round 2（`registry/tools.json` 読取後の最終回答生成）が **90 秒 timeout**
- read_file 対象例: `registry/tools.json`（payload ~49KB）

### 5.2 fixed_payload（50 match 固定）× 3

| Run | Native read_file | Type 3 | Type 4 | 結果 | 時間 |
|-----|------------------|--------|--------|------|-----:|
| 1 | No | — | — | **LLMTimeoutError 90s** | 90s |
| 2 | **Yes** | No | No | PASS | 52s |
| 3 | **Yes** | No | No | PASS | 44s |

### 5.3 list_files → read_file × 2

| Run | list_files | Native read_file | 実行 | Type 3/4 | エラー |
|-----|------------|------------------|------|----------|--------|
| 1 | Yes | **Yes** | **Yes** | No | なし |
| 2 | Yes | **Yes** | **Yes** | No | なし |

### 5.4 multi read（search → read → read）× 2

| Run | 結果 |
|-----|------|
| 1 | round0 **LLMTimeoutError 90s** |
| 2 | round0 **LLMTimeoutError 90s** |

---

## 6. Native Tool Calling 結果

| 指標 | 結果 |
|------|------|
| main: search → Native read_file | **5/5** |
| main: read_file 実実行 | **5/5** |
| fixed_payload: Native read_file | **2/3** |
| list → read: Native read_file | **2/2** |
| multi read: 2回 read_file | **0/2** |
| Type 3（捏造回答） | **0 回**（全テスト） |
| Type 4（thinking `<tool_call>` のみ） | **0 回**（全テスト） |

**Tool Calling 自体は、応答が完了すれば Native `read_file` を生成できる。**  
ただし **32768 + 大きな Tool 結果** では **90 秒 timeout** が頻発。

---

## 7. Type 3 / Type 4

| 分類 | 発生 |
|------|------|
| 正常（Native tool_calls → 実行） | main 5/5、fixed 2/3、list 2/2 で確認 |
| **Type 3**（捏造回答） | **0 回** |
| **Type 4**（thinking 内 `<tool_call>` のみ） | **0 回** |

32768 でも Type 3/4 は今回の条件では **観測されず**。主な問題は **timeout** と **VRAM 逼迫**。

---

## 8. VRAM・速度

| 観点 | 所見 |
|------|------|
| VRAM | 32768 ctx ロード後 **~11.9GB / 12GB**（空き **~166–300 MiB**） |
| VRAM 不足クラッシュ | **なし**（Ollama は動作継続） |
| 速度 | round 1（50 match 後 read_file）: **~44–75 秒** |
| timeout | **90 秒** 設定で round 2 または大 payload 1 回目が **頻繁に超過** |
| avg main elapsed | **~200 秒/run**（timeout 含む） |
| GPU util | ピーク **100%** 観測 |

**RTX 3060 12GB では 32768 は VRAM 的にギリギリ。** 実用上、他プロセス余地がほぼない。

---

## 9. 回帰テスト

```text
179 passed, 3 skipped
```

P2-6 同等テスト群。**新規失敗なし。**

---

## 10. P2-5F / P2-6 との比較

| Context | 条件 | Native read_file | 主な問題 |
|--------:|------|------------------|----------|
| 4096 | P2-5F post_search 50 match | 0/3 | Type 3 捏造 |
| 8192 | P2-5F post_search 50 match | 3/3 | — |
| 8192 | P2-6 instrumented | 2/3 | 1 run 失敗 |
| **32768** | P2-7 post_search 50 match | **2/3** | 1 timeout |
| **32768** | P2-7 instrumented search→read | **5/5** TC 成功 | **5/5** round2 timeout |

32768 は **8192 より Tool Calling 安定性が劣るわけではない**（むしろ TC 生成は良好）。  
一方 **VRAM 使用量増・推論遅延・90s timeout 超過** が RTX 3060 12GB では顕著。

---

## 11. 判定

### **PARTIAL**

| PASS 条件 | 状態 |
|-----------|------|
| Native Tool Calling 安定 | **TC 生成は良好**（main 5/5）だが **timeout で連鎖完走不可** |
| search → read 安定 | TC/実行 **5/5**、最終回答 **0/5**（timeout） |
| Type 3 なし | **PASS** |
| Type 4 実用問題なし | **PASS** |
| VRAM 不足なし | **VRAM 逼迫**（空き ~166 MiB）— 実用上懸念 |
| 性能問題なし | **FAIL**（90s timeout 頻発、~200s/run） |
| 回帰テスト | **PASS** |

**32768 を RTX 3060 12GB の Agent 標準 Context Size として即採用することは推奨できない。**

理由:
1. VRAM 余裕がほぼない（~11.9/12 GB）
2. 本番 timeout 90 秒では大きな Tool 結果後の応答が **頻繁に失敗**
3. 8192 では P2-5F で 3/3 成功していた点に対し、32768 は速度面で劣後

---

## 12. 次フェーズへの推奨

| 優先 | 推奨 | 根拠 |
|------|------|------|
| 1 | **8192 を標準候補として維持** | P2-5F/P2-6 で TC 改善確認。32768 より VRAM/速度に余裕 |
| 2 | 32768 採用検討時は **GPU メモリ増設またはモデル量化見直し** | 12GB では実用marginal |
| 3 | timeout 延長は **別タスクで人間判断**（今回変更禁止） | 32768 で round2 完走に >90s 必要 |
| 4 | Context Manager / Tool 結果 UX | P2-5E 系の根本対策（今回未着手） |

**今回実施しなかったこと:** 16384 試行、Thinking 変更、timeout 変更、Tool/Prompt 変更、救済処理。

---

## 13. 現在の設定状態

`config/llm_models.yaml` の `qwen3_14b.context_limit` は検証のため **32768 のまま**。

標準採用を確定する前に、**8192 への戻し**を人間判断で検討すること。

---

## 14. 再現コマンド

```bash
python -c "from tools.system.config import get_llm_profile; print(get_llm_profile()['context_limit'])"
python -m ai_tool.agent_integration.file_tools_context_32768_verify_p27
```

---

**P2-7 完了**  
**判定: PARTIAL**
