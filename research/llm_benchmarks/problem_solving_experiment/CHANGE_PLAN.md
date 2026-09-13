# CHANGE_PLAN — 実装する場合に触る箇所

**今回は実装しない。** 本番 Registry / execute_tool / Repair / FA は対象外。

実験基盤に限る。採用方式（A-1/A-2/A-3, F-*, T-*）が決まってから着手する。

---

## 変更が必要になりうるファイル

| ファイル | 何のため |
| --- | --- |
| `research/llm_benchmarks/problem_solving_experiment/harness.py` | messages 保存、Test 結果の再投入、parser、SYSTEM、chat 引数 |
| `catalog.py` | LLM 向け説明 / schema テキストまたは Ollama tools 配列 |
| `dispatch.py` | 引数検証、未知 Tool、結果のメタ（truncated） |
| `adapters.py` | `get_current_failure` の返す範囲、`experiment_test_source` の多軸結果 |
| 結果出力先 `results/` | 保存フィールド追加（実行時） |
| `smoke.py` | ラッパの戻り形が変わった場合の確認 |

触らなくてよい（この実験の目的では）:

- `registry/tools.json`
- `agent.py` の `execute_tool`（参照のみ。A-2 でも実験は独自 dispatch で足りる）
- Repair Loop / MATERIALS / `first_pipeline_step`
- `validate/result.py` の Schema（呼ぶだけなら変更不要）

参照してよい既存:

- `tools/system/llm.py` の `chat`（kwargs 透過。`tools=` を足すならハーネス側）
- `tools/system/llm_tool_capability.py` の `probe_tool_calling`（A-2 前の確認）
- `tools/system/tool_builder/validate/result.py` の `validate_tool_result`（パッチ後に実験が呼ぶ候補）

---

## 変更ブロック（順序の候補。採用後）

1. **ログ** — `chat` 直前の messages コピーと raw response を JSON に書く。これだけで「何を渡したか」が検証可能になる  
2. **Failure 分離** — `get_current_failure` または初期 user の中身（F-*）  
3. **Test 多軸 + LLM へ戻す** — `experiment_test_source` の意味を変え、T-*  
4. **Tool 提示** — A-1 説明強化 / A-2 tools= / A-3 schema テキスト  
5. **Parser** — P-* 。ログが先なら parser 失敗も残せる  

1 は他の採用判断より先にできる。2–5 は人間判断が要る。

---

## 触ってはいけないもの（再掲）

FA、本番 Registry、本番 execute_tool、Repair Loop、MATERIALS、first_pipeline_step、Research / Environment 本番経路、Test Result Schema の本番変更。
