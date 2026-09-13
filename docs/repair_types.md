# Repair 種類

モデル非依存。種類の増減は Validator の仕様変更であり、LLM 最適化ではない。

## 測定用の5分類（R1〜R5）

Validator の code は残す。ベンチでは家族単位でも測る。

| 家族 | 意味 | 既存 code / 信号 | 分岐 |
|---|---|---|---|
| R1 Syntax / Format | JSON破損、空 code、戻り値の形 | `return_value_not_dict` `wrong_output_key` `unparsed_output` `meaningless_output` `no_json` `no_code` | repair |
| R2 Runtime | IndexError / KeyError / TypeError / subprocess | `runtime_exception` `subprocess_result_handling` | repair |
| R3 Semantic | 動くが要求と違う種類の値 | `semantic_mismatch` | repair |
| R4 Finding | 間違った finding を、確認済みの正しい finding へ | `wrong_command`（調査済み） | research_repair |
| R5 Research | finding 不足。調査してから実装 | `stub_value`（未調査） | research → 新finding → implementation |

R4 は「持っている正しい finding に戻す」。R5 は「finding が足りないので調査に戻る」。混ぜて測らない。

実装: `tools/system/tool_builder/repair_family.py`  
テスト: `tests/test_repair_family.py`（LLM を呼ばない）

---

## 一覧

| 種類 | code | 直後の分岐 | 直し方 |
|---|---|---|---|
| ① 生出力 | `unparsed_output` | repair | `evidence.parsed_table.value` を戻り値にする。表のパースは再発明しない |
| ② キー間違い | `wrong_output_key` | repair | `proposal.output` のキーに合わせる |
| ③ dict ではない | `return_value_not_dict` | repair | dict にする |
| ④ subprocess 処理ミス | `subprocess_result_handling` | repair | returncode を見て stdout を使う |
| ⑤ 未実装スタブ | `stub_value` | research → research_repair | `usable_findings` の command/sample で実装 |
| ⑥ 間違ったコマンド | `wrong_command` | research → research_repair | 確認済みコマンドへ置き換える |

追加（ベース）:

| code | 分岐 | 意味 |
|---|---|---|
| `meaningless_output` | repair | 見出し・区切り・空文字 |
| `runtime_exception` | repair | 実行時例外。調査せずコードを直す |
| `semantic_mismatch` | repair | 形は通るが、要求した種類の値ではない |

## 分岐規則

`first_pipeline_step`:

1. 完了なら `pass`
2. 修理対象があり、調査が必要なら  
   - 調査済み → `research_repair`  
   - 未調査 → `research`
3. 修理対象があり、調査が不要なら `repair`
4. 情報不足だけなら `research`

repair と research が同時にあるときは repair を先にする。

## 調査済みの定義

`research_has_verified_method`: `usable_findings` の要素に `evidence.command` と `evidence.sample` がある。

confidence=medium の `reference_findings` は実装根拠にしない。

## 空 code

repair 案に `code` が無ければ適用しない。  
`apply_repair` は `code がない repair 案は適用しない` を返す。

## LLM ベンチマークとの関係

種類ごとの成功率は `research/llm_benchmarks/repair_results.json` に記録する。  
家族（R1〜R5）でも集計する。成功率の低さを理由に、この表の分岐をモデル別に変えない。
