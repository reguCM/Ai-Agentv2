# Validator

モデル非依存。LLM の出力癖を直すために分岐を増やさない。  
「このモデルは表を残しやすい」は `docs/llm/` に書き、Validator コードには書かない。

## 役割

`validate_tool_result` は Tool の実行結果を見て、次に何をするかを決める材料を返す。

返すもの:

- `result`: OK / NG
- `status`: pass / warning / fail / blocked
- `disposition.repairable` / `blocked` / `acceptable`
- `research_request`（情報が足りないとき）

分岐そのものは `first_pipeline_step` が行う。詳細は `docs/repair_types.md`。

## 機械が決めること

- 戻り値が dict か
- キーが `proposal.output` と一致するか
- 値が生テーブルか、見出し・区切り・空か
- 既知の表形式なら `evidence.parsed_table`（header / separator / value）に分解する
- `'未実装'` スタブか
- 実行例外か（IndexError など）
- subprocess の returncode / stdout の扱いが誤っていないか
- コマンドが調査結果と食い違っていないか

PowerShell のような既知の表は、パース方法を LLM に考えさせない。  
Validator が表を構造化し、LLM は「どのキーに value を入れるか」に集中する。

将来は Tool 側で JSON/CSV を取る標準に寄せ、この種の repair 自体を減らす。

LLM に環境を推測させない。検証済み情報は Python が注入する。

## 値として認めないもの

`meaningless_output` は次を値としない。

- 空文字
- 表の見出し行
- 区切り線（`---` など）

「このモデルは `load` や `error` を返しやすい」は `docs/llm/` に書く。  
`status` が数値かどうかで repair に回す、といったモデル対策は Validator に入れない。

## ファイル

- `tools/system/tool_builder/validate/result.py`
- `tools/system/tool_builder/validate/implementation.py`
- `tools/system/tool_builder/validate/spec.py`
- `tools/system/tool_builder/validate/warning_actions.py`

テスト: `tests/test_pipeline_routing.py`（LLM を呼ばない）  
Repair 家族: `tests/test_repair_family.py`。家族単位の LLM ベンチは `AI_AGENT_REPAIR_FAMILY=R1`。
