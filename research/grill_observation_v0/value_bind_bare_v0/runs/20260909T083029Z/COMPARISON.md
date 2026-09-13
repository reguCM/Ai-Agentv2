# value_bind_bare_v0 A/B/C/D 比較

D: `20260909T083029Z` Runtimeなし 純粋な値束縛
A/B/C は既存 Run（read-only）。

| 項目 | A Slotなし | B Slot役割 | C Task≠Action | D 純粋束縛 |
|---|---|---|---|---|
| status | UNRESOLVED | UNRESOLVED | UNRESOLVED | PROPOSED |
| value | null | null | null | grid |
| validator | UNRESOLVED | UNRESOLVED | UNRESOLVED | EXTRACTABLE |
| verdict | PARTIAL | PARTIAL | PARTIAL | PASS |
| reason | gridの構造と内容が確認されていない | 確認済み情報に検索対象の具体的内容や構造の記述がない | 検索対象を表す文字列の具体的な情報が確認済み情報にない | 検索対象として明示的に記述されている |

判定 D: **PASS**

確認済み文章から指定役割に対応する値を抽出し、Validator が literal 確認できた。

モデルは値束縛能力を持つが、これまでのRuntime / Grill Contextではその能力をうまく使えていない可能性

