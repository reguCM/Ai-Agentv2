# FILE-TOOLS-THINKING-CONTEXT-DIAG-P2-5F 作業 REPORT

**TASK_ID:** `FILE-TOOLS-THINKING-CONTEXT-DIAG-P2-5F`  
**担当:** Cursor  
**状態:** `P2-5F_INVESTIGATION_COMPLETE`  
**日付:** 2026-09-02

---

## 1. 結論

### 総合判定: **B — Context Size を増やすと Native Tool Call が安定する**

| 条件 | thinking | num_ctx | Native read_file (3回) | 主な失敗形態 |
|------|----------|--------:|------------------------:|-------------|
| **A** | ON (`think=True`) | **4096**（現行） | **0/3** | Type 3 捏造回答 |
| **B** | OFF (`think=False`) | **4096** | **0/3** | Type 3 捏造回答（search スニペット要約） |
| **C** | ON | **8192** | **3/3** | なし |
| **D** | ON | **16384** | **3/3** | なし |
| REF | 未指定（本番経路） | **4096** | **0/3** | Type 3 捏造回答 |

**Thinking OFF 単独（判定 A）は支持されない。** `think=False` + `num_ctx=4096` でも Native `read_file` は **0/3**。  
**Context Size 8192 以上（判定 B）は明確に支持。** `think=True` のまま `num_ctx≥8192` で **6/6 成功**。

副判定: **D に近いが Context 側が支配的** — Thinking ON + 大 Context（C/D）で改善。Thinking OFF + 現行 Context（B）では改善せず。

---

## 2. 実行環境

| 項目 | 値 |
|------|-----|
| Ollama version | `0.33.2` |
| モデル | `qwen3:14b`（14.8B, Q4_K_M） |
| モデル context length（Ollama show） | **40960** |
| Capabilities | completion, **tools**, **thinking** |
| 本番 profile `context_limit` | **4096** |
| 本番 profile `num_predict` | 2048 |
| 本番 profile `temperature` | 0 |
| 本番 API | **`POST /api/chat`**（`ollama.Client.chat`） |
| OpenAI `/v1/chat/completions` | **使用していない** |
| 本番 `think` 指定 | **未指定（None）** — `tools/system/llm.py` に `think` 引数なし |
| 診断 endpoint | 本番と同じ `ollama.Client`（default host） |

### 本番 LLM 経路（コード確認）

```32:45:tools/system/llm.py
def chat(**kwargs):
    profile = _profile()
    kwargs.setdefault("model", profile["model"])
    options = dict(kwargs.get("options") or {})
    options.setdefault("num_predict", int(profile.get("num_predict") or 2048))
    options.setdefault("temperature", float(profile.get("temperature") or 0))
    if profile.get("context_limit"):
        options.setdefault("num_ctx", int(profile.get("context_limit")))
    kwargs["options"] = options
    ...
    return get_client().chat(**kwargs)
```

---

## 3. 実験条件

| 項目 | 値 |
|------|-----|
| 再現ベース | P2-5E Case F 相当（広い search 結果を LLM へ） |
| 検索条件 | `search_files(path=".", query="read_file")` |
| 実 payload（今回 run 時点） | **50 match / 10137B / truncated=true** |
| user prompt | P2-5E と同一（system prompt 含め変更なし） |
| messages 構造 | P2-5A `post_search_llm_only` 相当 |
| 各条件実行回数 | **3 回** |
| 変更したパラメータ | **`think` と `options.num_ctx` のみ** |

### P2-5E からの payload  drift（記録）

| 項目 | P2-5E Case F | P2-5F 今回 |
|------|-------------|-----------|
| match_count | 39 | **50**（診断ファイル追加で増加） |
| payload_bytes | 7811 | **10137** |
| truncated | true（files_scanned 200 上限） | true（**match 50 上限**） |

件数は P2-5E より多いが、**現行 Context 4096 では失敗・8192 では成功**という切り分け結果は一貫。

---

## 4. 結果表

### 4.1 主条件（A〜D + 本番参照）

| Condition | thinking | ctx | matches | payload | Native read_file | thinking `<tool_call>` | 捏造 (Type 3) |
|-----------|----------|----:|--------:|--------:|-----------------:|-----------------------:|--------------:|
| A | ON | 4096 | 50 | 10137B | **0/3** | 0/3 | 2/3 |
| B | OFF | 4096 | 50 | 10137B | **0/3** | 0/3 | **3/3** |
| C | ON | 8192 | 50 | 10137B | **3/3** | 0/3 | 0/3 |
| D | ON | 16384 | 50 | 10137B | **3/3** | 0/3 | 0/3 |
| REF | None（本番） | 4096 | 50 | 10137B | **0/3** | 0/3 | 2/3 |

### 4.2 prompt token 使用量（参考）

| Condition | prompt_eval_count（例） | 解釈 |
|-----------|------------------------:|------|
| A / B / REF | ~2050 | 4096 ctx 内で prompt が context の ~50% を占有 |
| C / D | ~4559 | 8192 ctx では prompt が ~56%。余裕確保後 Native TC 成功 |

---

## 5. 各条件の詳細

### Condition A — Thinking ON + ctx=4096（現行相当）

- **0/3** Native `read_file`
- 失敗形態: **Type 3**（自然言語 + 捏造）
- `assistant.thinking` **あり**（~3000 文字）。thinking 内で read_file 使用を検討するが Native TC 未生成
- thinking 内 `<tool_call>` タグ: **0/3**

### Condition B — Thinking OFF + ctx=4096

- **0/3** Native `read_file` — **判定 A（Thinking OFF で改善）は否定**
- `assistant.thinking` **空**（thinking 無効化は確認）
- 失敗形態: search 結果スニペットを **長文 Markdown で要約**（read_file 未実行）。**3/3 捏造疑い**
- 探索的 1 回 probe（実装前）では `think=False` → Native read_file **1/1 成功**だったが、**正式 3 回では再現せず**（モデル揺らぎ）

### Condition C — Thinking ON + ctx=8192

- **3/3** Native `read_file`
- 例: `read_file({"path": "ai_tool/agent_integration/file_tools_integration_verify.py", "limit": 20})`
- thinking あり + Native TC **共存**（thinking と tool_calls は両立可能）

### Condition D — Thinking ON + ctx=16384

- **3/3** Native `read_file`
- C と同等に安定。8192 で足りる可能性が高い

### REF — 本番 `tools/system.llm.chat`（think 未指定, ctx=4096）

- **0/3** Native `read_file` — A と同型の失敗
- 本番経路は `think=None` → qwen3 デフォルトで **thinking 有効**と推定（thinking 出力あり）

---

## 6. 異常分類（§6）

| 分類 | A | B | C | D | REF |
|------|---|---|---|---|-----|
| 正常（Native read_file） | 0 | 0 | 3 | 3 | 0 |
| 異常1（thinking 内 TC 文字列） | 0 | 0 | 0 | 0 | 0 |
| 異常2（content 内 TC 文字列） | 0 | 0 | 0 | 0 | 0 |
| 異常3（Tool 未実行 + 捏造） | 2 | **3** | 0 | 0 | 2 |

**今回の 39〜50 件条件では、P2-5A の Type 4（thinking `<tool_call>`）は 0 回。** 失敗は **Type 3 捏造** が主。

---

## 7. P2-5 / P2-5A / P2-5E との関係

| 過去調査 | 今回との関係 |
|----------|-------------|
| P2-5: Agent Loop は正常 | 変更なし。ctx 8192 では Native TC 正常生成を再確認 |
| P2-5A: messages 構造では説明不可 | 今回も messages 同一。`num_ctx` のみ変更で結果が変化 → **Context Size が決定因子** |
| P2-5E: 39 件で Native 0/3 | 50 件でも ctx=4096 なら 0/3。**ctx=8192 なら 3/3** で説明が進む |

---

## 8. 判定（§9）

| 判定 | 該当 | 根拠 |
|------|------|------|
| **A** Thinking OFF で明確改善 | **否** | B: 0/3（probe 1 回のみ成功、3 回では再現せず） |
| **B** Context Size 増で改善 | **是** | C/D: 3/3 vs A: 0/3 |
| **C** どちらでも改善しない | **否** | C/D で改善 |
| **D** 両方で改善 | **部分** | Context 増（C/D）で改善。Thinking OFF（B）では改善せず |

**最終判定: B（Context Size が有力）**

---

## 9. 修正方法の確度（§10 準備・今回は Registry 登録なし）

### 最も有力（実験で支持）

| ID | 内容 | 確度 | 根拠 |
|----|------|------|------|
| `increase_context` | `num_ctx` を **8192 以上**に増やす | **高** | C/D: 6/6 Native read_file。4096 では 0/9 |

### まだ確証がない

| ID | 内容 | 確度 | 根拠 |
|----|------|------|------|
| `disable_thinking` | `think=False` | **低** | B: 0/3。probe 1/1 のみ成功（揺らぎ） |
| `increase_context_min_16384` | 16384 必須 | **低** | D は 3/3 だが C も 3/3。8192 で十分な可能性 |

**今回の実験結果をもとに本番設定変更は行っていない。**

---

## 10. 次に試すべき方向（実装は別タスク）

1. **`config/llm_models.yaml` の `qwen3_14b.context_limit` を 8192 に引き上げ** — 最有力。VRAM/ latency 確認要
2. **`think=False` の追加検証** — `think=False` + `num_ctx=8192` の交叉条件（今回未実施）
3. **prompt token 監視** — `prompt_eval_count` を Agent 観測に追加し、4096 接近時のアラート
4. P2-5E 継続項（search 結果 UX）— Context 増加と併用検討

---

## 11. 成果物

| ファイル | 内容 |
|----------|------|
| `ai_tool/agent_integration/file_tools_thinking_context_diag_p25f.py` | **新規** 診断スクリプト |
| `runs/ai_tool/20260902T064810Z_file_tools_thinking_context_diag_p25f/diag.json` | 一次資料 |
| `reports/FILE-TOOLS-THINKING-CONTEXT-DIAG-P2-5F.md` | 本報告書 |

**禁止事項への変更: なし**（Agent / Registry / Tool 実装 / prompt / 救済処理）

---

## 12. テスト

```text
179 passed, 3 skipped
```

---

## 13. 再現コマンド

```bash
python -m ai_tool.agent_integration.file_tools_thinking_context_diag_p25f
```

---

## 14. 完了確認

| 項目 | 状態 |
|------|------|
| 環境情報取得 | PASS |
| Thinking ON/OFF 比較 | PASS |
| Context Size 比較 | PASS |
| 各 3 回実行 | PASS |
| Native TC / thinking TC / 捏造 記録 | PASS |
| 判定 A〜D | PASS（**B**） |
| コード修正なし | PASS |
| 報告書作成 | PASS |

**本番設定変更・P2-6 には進まない。**
