# value_provenance_action_param_v0 3段階比較

A: `20260909T081235Z` Slotなし
B: `20260909T081755Z` Slot役割のみ
C: `20260909T082518Z` Slot役割 + Task/Action入力の区別

Production 未変更。`_search_query` 未使用。Tool 未実行。Validator / Grounding 文面は未変更。

| 項目 | A Slotなし | B Slot役割 | C Task≠Action入力 |
|---|---|---|---|
| status | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| value | null | null | null |
| source_type | NONE | NONE | NONE |
| source_text | null | null | null |
| reason | gridの構造と内容が確認されていない | 確認済み情報に検索対象の具体的内容や構造の記述がない | 検索対象を表す文字列の具体的な情報が確認済み情報にない |
| grounding_violation | False | False | False |
| validator | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| verdict | PARTIAL | PARTIAL | PARTIAL |
| Task/Action区別の形跡 | taskish=True actionish=False | taskish=True actionish=True | taskish=False actionish=True proposed=False |

判定 C: **PARTIAL**

AI は安全に UNRESOLVED を返した。

