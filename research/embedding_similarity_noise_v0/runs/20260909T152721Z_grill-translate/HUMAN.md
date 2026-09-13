# Grill後 翻訳層 v0

- run_id: `20260909T152721Z_grill-translate`
- 翻訳モデル: `qwen3:14b`
- Embedding（補助）: `qwen3-embedding:0.6b`
- Production / Grill 接続: なし
- 主評価: 既存 `match_clarification_to_candidate_paths` が unique gold になるか
- cosine は補助。SELECTED 規則ではない

## シナリオ（仮置き）

人間が『文書を確認して』と依頼し、残候補が実ファイル3件。Grill がどれかを聞いている。人間がノイズ付き日本語で答える。同一検索クエリで3件が同時ヒットした事実ではない。Grill後に残った候補集合としての仮置き。

## ノイズ文の照合

- 生データ unique gold: **12 / 30**
- 翻訳後 unique gold: **22 / 30**
- 近づいた / 同じ / 遠ざかった: **12 / 18 / 0**
- 生で誤読（unique_wrong）: 0
- 翻訳後の誤読: 0
- 補助 cosine（gold）平均差: 0.076137

## ノイズ種別

| 種別 | 生 unique gold | 訳 unique gold | closer | same | farther |
|---|---:|---:|---:|---:|---:|
| clean | 3 / 3 | 2 / 3 | 0 | 2 | 1 |
| typo | 0 / 3 | 3 / 3 | 3 | 0 | 0 |
| conversion | 0 / 3 | 1 / 3 | 1 | 2 | 0 |
| missing_char | 3 / 3 | 3 / 3 | 0 | 3 | 0 |
| particle_drop | 3 / 3 | 3 / 3 | 0 | 3 | 0 |
| colloquial | 1 / 3 | 2 / 3 | 2 | 1 | 0 |
| filler | 3 / 3 | 3 / 3 | 0 | 3 | 0 |
| restatement | 0 / 3 | 3 / 3 | 3 | 0 | 0 |
| asr_like | 0 / 3 | 1 / 3 | 2 | 1 | 0 |
| demonstrative | 2 / 3 | 2 / 3 | 0 | 3 | 0 |
| compound | 0 / 3 | 1 / 3 | 1 | 2 | 0 |

## 一覧

| id | 種別 | 生入力 | 翻訳 | 生の照合 | 訳後の照合 | gold | 生判定 | 訳判定 | 近づいたか | 生 cosine | 訳 cosine | Δcosine |
|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|
| current_clean | clean | CURRENTの文書を読んで | CURRENT_DEVELOPMENT_STATE.mdを読んで | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | unique_gold | unique_gold | same | 0.465149 | 0.574041 | 0.108892 |
| current_typo | typo | CURRETの文書を読んで | CURRENT_DEVELOPMENT_STATE.mdの文書を読んで | （なし） | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | empty | unique_gold | closer | 0.419867 | 0.571201 | 0.151334 |
| current_conversion | conversion | 過連との文書を読んで | 過連との文書を読んで | （なし） | （なし） | `docs/CURRENT_DEVELOPMENT_STATE.md` | empty | empty | same | 0.339875 | 0.343015 | 0.00314 |
| current_missing_char | missing_char | CURRENTの文書を読 | CURRENT_DEVELOPMENT_STATE.mdを読 | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | unique_gold | unique_gold | same | 0.47933 | 0.578032 | 0.098702 |
| current_particle | particle_drop | CURRENT文書読んで | CURRENT_DEVELOPMENT_STATE.md文書読んで | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | unique_gold | unique_gold | same | 0.398364 | 0.536024 | 0.13766 |
| current_colloquial | colloquial | 今の開発状態のやつ | 今の開発状態のやつ | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | unique_gold | unique_gold | same | 0.565171 | 0.564834 | -0.000337 |
| current_filler | filler | えっとCURRENTの文書を読んでください | CURRENT_DEVELOPMENT_STATE.mdを読んでください | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | unique_gold | unique_gold | same | 0.487682 | 0.570116 | 0.082434 |
| current_restatement | restatement | GrillじゃなくてCURRENTの文書 | CURRENT_DEVELOPMENT_STATE.md | `docs/GRILL_V0.md`, `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | ambiguous_includes_gold | unique_gold | closer | 0.459905 | 0.524375 | 0.06447 |
| current_asr | asr_like | カレントの文書を呼んで | カレントの文書を呼んで | （なし） | （なし） | `docs/CURRENT_DEVELOPMENT_STATE.md` | empty | empty | same | 0.407848 | 0.408038 | 0.00019 |
| current_demonstrative | demonstrative | そっちのCURRENT | そっちのCURRENT_DEVELOPMENT_STATE.md | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/CURRENT_DEVELOPMENT_STATE.md` | unique_gold | unique_gold | same | 0.503467 | 0.604392 | 0.100925 |
| current_compound | compound | えっと過連とのやつ読んで | 過連とのやつ読んで | （なし） | （なし） | `docs/CURRENT_DEVELOPMENT_STATE.md` | empty | empty | same | 0.325216 | 0.357343 | 0.032127 |
| grill_clean | clean | Grillの原則の文書 | Grill v0 — 人間向け質問原則と出口 / 人間の意図が必要なものを優先する / T... | `docs/GRILL_V0.md` | `docs/GRILL_V0.md`, `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/GRILL_V0.md` | unique_gold | ambiguous_includes_gold | farther | 0.705311 | 0.949909 | 0.244598 |
| grill_typo | typo | Grrillの文書 | Grill v0 の文書 | （なし） | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | empty | unique_gold | closer | 0.511842 | 0.67776 | 0.165918 |
| grill_conversion | conversion | 具入るのやつ | 具入るのやつ | （なし） | （なし） | `docs/GRILL_V0.md` | empty | empty | same | 0.340464 | 0.340668 | 0.000204 |
| grill_missing_char | missing_char | Grillの原 | Grillの原稿はGRILL_V0.mdですか？ | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | unique_gold | unique_gold | same | 0.597941 | 0.600143 | 0.002202 |
| grill_particle | particle_drop | Grill原則の文書 | Grill原則の文書 | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | unique_gold | unique_gold | same | 0.67747 | 0.677537 | 6.7e-05 |
| grill_colloquial | colloquial | グリルのやつ | Grill v0 — 人間向け質問原則と出口 / 人間の意図が必要なものを優先する / T... | （なし） | `docs/GRILL_V0.md`, `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/GRILL_V0.md` | empty | ambiguous_includes_gold | closer | 0.485049 | 0.953034 | 0.467985 |
| grill_filler | filler | あのーGrillの原則なんですけど | Grillの原則なんですけど | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | unique_gold | unique_gold | same | 0.600517 | 0.622963 | 0.022446 |
| grill_restatement | restatement | CURRENTじゃなくてGrillの原則 | Grillの原則 | `docs/CURRENT_DEVELOPMENT_STATE.md`, `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | ambiguous_includes_gold | unique_gold | closer | 0.645179 | 0.716075 | 0.070896 |
| grill_asr | asr_like | グリルの文書を呼んで | Grill v0 — 人間向け質問原則と出口 / 人間の意図が必要なものを優先する / T... | （なし） | `docs/GRILL_V0.md`, `docs/CURRENT_DEVELOPMENT_STATE.md` | `docs/GRILL_V0.md` | empty | ambiguous_includes_gold | closer | 0.500111 | 0.953034 | 0.452923 |
| grill_demonstrative | demonstrative | 原則のほう | 原則のほう | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | `docs/GRILL_V0.md` | unique_gold | unique_gold | same | 0.435038 | 0.435038 | 0.0 |
| grill_compound | compound | まあ具入るのやつ | まあ具入るのやつ | （なし） | （なし） | `docs/GRILL_V0.md` | empty | empty | same | 0.332605 | 0.333561 | 0.000956 |
| agents_clean | clean | AGENTSの方針 | AGENTS.mdの方針 | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` | unique_gold | unique_gold | same | 0.604137 | 0.56887 | -0.035267 |
| agents_typo | typo | AGNETSの方針 | AGENTSの方針 | （なし） | `AGENTS.md` | `AGENTS.md` | empty | unique_gold | closer | 0.571547 | 0.60485 | 0.033303 |
| agents_conversion | conversion | 揚げんつの方針 | AGENTS.mdの方針 | （なし） | `AGENTS.md` | `AGENTS.md` | empty | unique_gold | closer | 0.545203 | 0.567355 | 0.022152 |
| agents_missing_char | missing_char | AGENTSの方 | AGENTS.mdの方 | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` | unique_gold | unique_gold | same | 0.562943 | 0.563113 | 0.00017 |
| agents_particle | particle_drop | AGENTS方針 | AGENTS.md方針 | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` | unique_gold | unique_gold | same | 0.54269 | 0.55619 | 0.0135 |
| agents_colloquial | colloquial | エージェントのやつ | AGENTS.md | （なし） | `AGENTS.md` | `AGENTS.md` | empty | unique_gold | closer | 0.536874 | 0.581625 | 0.044751 |
| agents_filler | filler | まあAGENTSの方針かな | AGENTSの方針かな | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` | unique_gold | unique_gold | same | 0.475656 | 0.529 | 0.053344 |
| agents_restatement | restatement | CURRENTじゃなくてAGENTSの方針 | AGENTSの方針 | `docs/CURRENT_DEVELOPMENT_STATE.md`, `AGENTS.md` | `AGENTS.md` | `AGENTS.md` | ambiguous_includes_gold | unique_gold | closer | 0.522785 | 0.604137 | 0.081352 |
| agents_asr | asr_like | エージェンツの方針 | AGENTS.mdの方針 | （なし） | `AGENTS.md` | `AGENTS.md` | empty | unique_gold | closer | 0.596483 | 0.567355 | -0.029128 |
| agents_demonstrative | demonstrative | ポリシーのほう | ポリシーのほう | （なし） | （なし） | `AGENTS.md` | empty | empty | same | 0.591311 | 0.589241 | -0.00207 |
| agents_compound | compound | まあえーじぇんつのやつ | AGENTS.md のやつ | （なし） | `AGENTS.md` | `AGENTS.md` | empty | unique_gold | closer | 0.380921 | 0.593404 | 0.212483 |

## 資源

- baseline: VRAM 3908 / 12288 MiB, RAM used 38798 / 65277 MB
- after_translate: VRAM 10899 / 12288 MiB, RAM used 39170 / 65277 MB
- after_embed: VRAM 11909 / 12288 MiB, RAM used 41165 / 65277 MB
