# PROTOCOL_GAP — プロトコル v1 と現行実装

一次資料: `harness.py` / `catalog.py` / `dispatch.py` / `adapters.py` / 結果 JSON。  
判定: ○ 一致 / △ 部分一致 / × 不一致 / ? 未確認

---

## 適合表

| Phase | プロトコル | 現行実装 | 判定 | 根拠 | 影響 |
| --- | --- | --- | --- | --- | --- |
| Failure | 最小情報 | 第1 user は tool_name/status/error_type/error。source/traceback/validation は第1文に無い。ただし `get_current_failure` が一括で渡す | △ | harness 126–136, adapters 36–52 | 「最小で始めた」と「調査単位を選んだ」が分離できない |
| Tool提示 | 選択可能 | 13名を system テキストで提示。native `tools=` なし。required/return schema なし | △ | harness 33–45, catalog 180–186, llm.py 32–45 | 名前は見える。用途理解と native 選択は別 |
| Tool選択 | LLM自身 | 固定1 Tool ループではない。JSON の name を dispatch。許可は catalog 13 | △ | harness 156–159, dispatch 8–13 | 選択主体は LLM。一括 Failure Tool が選択実験を歪める |
| Tool実行 | Dispatcher | name → handler(**args)。未知は error dict | ○ | dispatch.py 8–20 | 実行経路はプロトコルどおり |
| Tool結果 | LLMへ返す | 次 user に JSON 文字列。3500 超は切断。結果 JSON には本文なし | △ | harness 163–167 | 再判断はメモリ上可能。後追い不能。一括ペイロード |
| 再判断 | LLM再実行 | Tool 後は loop 継続で `_ask`。final 後は break で LLM なし | △ | harness 137–177 | Tool 後の再判断は可。Test 後は不可 |
| 修正 | 修正案 | final.patch_source。本番 apply_repair なし | △ | harness 168–176 | 案の提出はある。確定適用はサンドボックス Test のみ |
| Test | Sandbox | 一時ファイル subprocess。本番 cpu_status.py は Failure 生成後に復元済み | △ | adapters 133–186, harness 108–112 | 隔離実行はある。validation/期待値なし |
| Test判定 | 実行成功≠解決 | 例外なし → status=pass, ok=true | × | adapters 159–161 | 解決と pass が同一ラベル |
| Test再投入 | LLMへ返す | final 後 break。test_of_patch は JSON 保存のみ | × | harness 168–177 | 解決/再調査/HELP の Test 後分岐が無い |
| 再調査 | Tool再利用 | Test 前の loop 内なら可。Test 後は不可 | △ / × | MAX_TURNS loop vs break | Test 失敗後の再調査は不成立 |
| HELP | 判断を記録 | request_human_help と final.help。状態機械なし | △ | adapters 73–80, harness 161–162, 171 | 呼べばフラグは立つ。Schema 未確定 |
| Logging | 全過程追跡 | turns.raw/parsed、tools_called、test_of_patch。messages/SYSTEM/Tool本文なし | × | harness 140–147, 204–207 | 結果 JSON だけでは LLM 入力を再構成できない |
| Parser | （付随） | JSON only 要求。混在は unparsed → 短い再指示 | △ | harness 38–42, 52–77, 151–153 | 失敗で実験条件（user 文）が変わる |

提示方式の確定: **A-1**（system テキスト + JSON name）。A-2 / A-3 ではない。

---

## 結果 JSON だけで追えるか

IndexError 記録 (`results/20260831T183219Z/index_error.json`) でできること:

- Turn の LLM **出力** raw
- parsed の有無
- tools_called 名の列
- 最終 patch と test_of_patch

できないこと:

- Turn の LLM **入力**（system、第1 user、Tool result 本文）
- Tool に渡した arguments の保存（parsed にあれば出力側のみ）
- Test を LLM が見たかどうか（見ていない）

したがって「ログがある」≠「過程を再構成できる」。

---

## Parser が条件を変えるか

unparsed 時、次の user が形式再指示だけになる（153）。当初の SYSTEM は残るが、直前 user が Tool 結果ではなく再指示に置き換わる。混在応答のあと、モデルは「JSON only」再指示を見てから final を出した（実測 step 2→3）。プロトコルの「Tool 結果を見て再判断」とは、そのターンでは一致しない。
