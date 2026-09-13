# FILE-TOOLS-CONTEXT-16384-VERIFY-P2-8 作業 REPORT

**TASK_ID:** `FILE-TOOLS-CONTEXT-16384-VERIFY-P2-8`  
**担当:** Cursor  
**状態:** `P2-8_VERIFY_COMPLETE`  
**日付:** 2026-09-02

---

## 1. 実施内容

P2-7 で 32768 が VRAM 逼迫・timeout 多発だったことを受け、**16384** を RTX 3060 12GB 環境で実測した。

変更は `config/llm_models.yaml` の `qwen3_14b.context_limit` のみ。  
各 LLM 実行の **実行前・実行後** に `get_gpu_status` / `get_gpu_processes` で GPU 状態を記録した。

**16384 の正式採用は今回決定しない。** 測定データの取得が目的。

---

## 2. 変更内容

| 項目 | 変更前（P2-7） | 変更後 |
|------|---------------|--------|
| `qwen3_14b.context_limit` | 32768 | **16384** |

---

## 3. GPU 環境

| 項目 | 値 |
|------|-----|
| GPU | **NVIDIA GeForce RTX 3060** |
| VRAM 総量 | **12288 MiB** |
| Ollama | 0.33.2 |
| モデル | qwen3:14b (Q4_K_M) |
| API | POST /api/chat |
| Thinking | 未指定（None） |
| timeout | **90 秒**（変更なし） |

### 実行前 GPU（検証開始時・モデル未ロード）

| 項目 | 値 |
|------|-----|
| VRAM 使用 | 1924 MiB |
| VRAM 空き | **10364 MiB** |
| GPU 使用率 | 26% |
| GPU 温度 | 59°C |

### モデルロード後（典型値）

| 項目 | 値 |
|------|-----|
| VRAM 使用 | **~11735–11869 MiB** |
| VRAM 空き | **~340–570 MiB** |
| llama-server.exe | Ollama プロセス確認 |

### 主な GPU 使用プロセス（実行前）

Windows シェル/UI 系プロセス多数（explorer, SearchHost, Edge WebView2, NVIDIA Share 等）。  
多くは `vram_used: unknown`（権限不足）。**Stable Diffusion / ComfyUI は未確認。**

---

## 4. テスト条件

P2-7 と同一構成。検索 payload: **50 match / 10345B / truncated=true**

| テスト | 回数 |
|--------|-----:|
| A. instrumented search → read | 5 |
| B. 固定 50 match payload → read | 3 |
| C. list_files → read_file | 2 |
| D. multi read | 2 |

診断スクリプト: `ai_tool/agent_integration/file_tools_context_16384_verify_p28.py`  
一次資料: `runs/ai_tool/20260902T075445Z_file_tools_context_16384_verify_p28/verify.json`

---

## 5. テスト結果サマリー

### A. search → read_file（instrumented）× 5

| 指標 | 結果 |
|------|------|
| Native read_file 生成 | **5/5** |
| read_file 実行 | **5/5** |
| search → read 連鎖 | **5/5** |
| Type 3 | **0/5** |
| Type 4 | **0/5** |
| **timeout（round 2）** | **5/5** |
| 平均実行時間 | **~150 秒/run** |
| 実行前 VRAM 空き（平均） | 2377 MiB※ |

※1 回目は 10364 MiB（冷スタート）、2 回目以降は **~340–480 MiB**（モデル常駐）

### B. 固定 50 match payload × 3

| Run | Native read_file | Type 3 | Type 4 | timeout | 時間 | 実行前 VRAM 空き |
|-----|------------------|--------|--------|---------|-----:|-----------------:|
| 1 | **Yes** | No | No | No | 36s | 419 MiB |
| 2 | **Yes** | No | No | No | 13s | 426 MiB |
| 3 | **Yes** | No | No | No | 11s | 417 MiB |

**3/3 成功。timeout なし。平均 ~20 秒。**

### C. list_files → read_file × 2

| 指標 | 結果 |
|------|------|
| Native read_file | **2/2** |
| timeout | **0/2** |
| Type 3/4 | **0/2** |
| 実行前 VRAM 空き（平均） | ~438 MiB |

### D. multi read × 2

| 指標 | 結果 |
|------|------|
| Native read_file | **0/2** |
| Type 4 | **2/2** |
| timeout | **0/2** |
| tool_sequence | search_files のみ |

---

## 6. Native Tool Calling / Type 3 / Type 4

| 分類 | 観測 |
|------|------|
| 正常（Native TC → 実行） | fixed **3/3**、list **2/2**、main TC 生成 **5/5** |
| **Type 3**（捏造） | **0 回**（全テスト） |
| **Type 4**（thinking `<tool_call>` のみ） | **multi 2/2** のみ |

---

## 7. VRAM・速度

| Context | VRAM 使用（ロード後） | VRAM 空き | fixed 50match 平均 | main 平均 |
|--------:|----------------------:|----------:|-------------------:|----------:|
| **16384（今回）** | ~11800 MiB | **~400–550 MiB** | **~20s、3/3** | **~150s、timeout 5/5** |
| 32768（P2-7） | ~11948 MiB | **~166 MiB** | ~62s、2/3 | ~200s、timeout 5/5 |
| 8192（P2-5F/6） | NOT_OBSERVED 詳細 | NOT_OBSERVED | 3/3（P2-5F） | PARTIAL 2/3（P2-6） |

**16384 は 32768 より VRAM 空き・速度とも改善。**  
ただし **instrumented 全連鎖完走は 32768 と同様に timeout 5/5**。

### Context + VRAM 空き + 結果（観測できた相関）

| 条件 | VRAM 空き（実行前） | 結果 | 時間 |
|------|-------------------:|------|-----:|
| 16384、冷スタート | 10364 MiB | search OK | ~29s |
| 16384、モデル常駐 | ~400–550 MiB | fixed → Native read_file | 11–36s |
| 16384、モデル常駐 | ~340–480 MiB | search→read TC 成功 → **round2 timeout** | ~150s |

**判断:** timeout は **VRAM 空きだけでは説明できない**。`registry/tools.json` 読取後（~49KB payload）の **round 2 最終回答**で 90s 超過が主因。  
**他プロセス VRAM 圧迫の定量評価は不可**（多数プロセスで vram_used unknown）。

---

## 8. 回帰テスト

```text
179 passed, 3 skipped
```

---

## 9. P2-5F / P2-6 / P2-7 との比較

| Context | 出典 | Tool Calling（fixed 50match） | Tool Calling（instrumented search→read） | timeout | VRAM 空き（ロード後） | 実行時間 |
|--------:|------|------------------------------|----------------------------------------|---------|---------------------|---------|
| 4096 | P2-5F | 0/3 | NOT_OBSERVED 同一条件 | — | — | — |
| 8192 | P2-5F/6 | **3/3** | 2/3（P2-6） | P2-6: 1/3 | NOT_OBSERVED | NOT_OBSERVED |
| **16384** | **P2-8** | **3/3** | TC **5/5**、完走 **0/5** | **5/5** round2 | **~400–550 MiB** | fixed ~20s / main ~150s |
| 32768 | P2-7 | 2/3 | TC **5/5**、完走 **0/5** | **5/5** + fixed 1/3 | **~166 MiB** | fixed ~62s / main ~200s |

---

## 10. GPU との関係（判断できる範囲）

| 要因 | 判断 |
|------|------|
| Context Size 16384 vs 32768 | 16384 の方が **VRAM 余裕・速度・fixed 成功率** で優位 |
| Context Size 16384 vs 8192 | 8192 の VRAM/速度詳細は **NOT_OBSERVED**。fixed 成功率は同等（3/3） |
| GPU 空き容量 | モデルロード後 **~400–550 MiB** — 32768 よりマシだが **実用marginal** |
| 他プロセス | UI 系多数。**VRAM 寄与の定量分離は NOT_DETERMINED** |
| timeout | **90s 設定 + 大きな Tool 結果後の round 2** が主因。**Context だけでは解消せず** |

---

## 11. 判定

### **PARTIAL**

| 観点 | 評価 |
|------|------|
| Tool Calling（fixed / list） | **良好**（3/3、2/2） |
| Tool Calling（instrumented 完走） | **不良**（timeout 5/5） |
| Type 3 | **なし** |
| Type 4 | multi のみ 2/2 |
| 安定性 | fixed は安定、instrumented 完走は不安定 |
| 性能 | 32768 より改善、ただし main ~150s |
| GPU | 32768 より空き増（~400–550 MiB）だが **ギリギリ** |

**16384 は 32768 より実用候補として優位だが、RTX 3060 12GB で Agent 標準として即採用できる安定性には未達。**

8192 との直接比較（VRAM・instrumented 完走率）は **今回未実施のため NOT_DETERMINED**。

---

## 12. 次フェーズへの推奨（今回は実装しない）

1. **8192 vs 16384 の同条件再測定**（GPU スナップショット付き）— 標準候補の絞り込み
2. **timeout 延長は別タスク・人間判断**（今回変更禁止）
3. **Context Manager 設計** — PC 上限・GPU 空き・過去実測の参照（P2-8 以降）
4. **instrumented 完走失敗** — `registry/tools.json` 大 payload 後の round 2 がボトルネック（Tool Result UX は別フェーズ）

---

## 13. 現在の設定状態

`qwen3_14b.context_limit` は検証のため **16384 のまま**。

---

## 14. 再現コマンド

```bash
python -c "from tools.system.config import get_llm_profile; print(get_llm_profile()['context_limit'])"
python -m ai_tool.agent_integration.file_tools_context_16384_verify_p28
```

---

**P2-8 完了**  
**判定: PARTIAL**
