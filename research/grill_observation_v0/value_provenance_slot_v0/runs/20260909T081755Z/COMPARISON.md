# value_provenance_slot_v0 比較

this_run: `20260909T081755Z`
baseline: `20260909T081235Z`
Production 未変更。`_search_query` 未使用。Tool 未実行。

| 項目 | Baseline（Slotなし） | 今回（Slot役割のみ） | 変化 |
|---|---|---|---|
| status | UNRESOLVED | UNRESOLVED | no |
| value | null | null | no |
| source_type | NONE | NONE | no |
| source_text | null | null | no |
| reason | gridの構造と内容が確認されていない | 確認済み情報に検索対象の具体的内容や構造の記述がない | yes |
| grounding_violation | False | False | no |
| validator | UNRESOLVED | UNRESOLVED | no |
| verdict | PARTIAL | PARTIAL | no |

判定: **PARTIAL**

AI は安全に UNRESOLVED を返した。

