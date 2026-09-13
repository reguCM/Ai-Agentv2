# v0 Stage 3 Human Review Dataset

**実装変更なし。** `human_web_need` は人間レビュー用スキャフォールドであり、Agent採点の自動正解ではない。
`classification_candidates` は草案タグ。`misjudgment_final` はすべて null。

## 列の意味

| 列 | 意味 |
|----|------|
| human_web_need | 人間レビュー用のWeb必要性（needs_web/no_web/ambiguous/reviewer_uncertain） |
| heuristic_judgment | capability_route 観測の judged_appropriate |
| llm_called_search_web | Toolループで search_web が実行されたか |
| search_primary_outcome | hits/error/…（検索経路。判断正誤ではない） |
| answer_surface_proxy | Stage2表面プロキシ（真偽ではない） |
| classification_candidates | Stage3草案タグ（C/D/F/G/Eファミリ） |

## 50件一覧

| case | human_web_need | heuristic | llm_called | search | answer | classification (primary) | reason (short) |
|------|----------------|-----------|------------|--------|--------|--------------------------|----------------|
| A01 | needs_web | True | True | error | inconclusive | `D_search_path_error_candidate` | 検索実行後 outcome=error（判断正誤とは別）; related空で uncertain に落ちた構造; 検索 |
| A02 | needs_web | True | True | error | inconclusive | `D_search_path_error_candidate` | 検索実行後 outcome=error（判断正誤とは別）; related空で uncertain に落ちた構造; 検索 |
| A03 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| A04 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| A05 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| A06 | needs_web | False | True | error | success_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| B01 | no_web | False | False | None | success_candidate | `F_related_continue_not_sufficiency_candidate` | relatedありで continue（達成保証ではない）; 人間レビュー上no_webでローカルTool実行あり |
| B02 | no_web | False | False | None | success_candidate | `F_related_continue_not_sufficiency_candidate` | relatedありで continue（達成保証ではない）; 人間レビュー上no_webでローカルTool実行あり |
| B03 | no_web | False | False | None | success_candidate | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造; 人間レビュー上no_webでローカルTool実行あり |
| B04 | no_web | False | False | None | success_candidate | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造; 人間レビュー上no_webでローカルTool実行あり |
| B05 | no_web | False | False | None | success_candidate | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造 |
| B06 | no_web | False | False | None | inconclusive | `F_related_continue_not_sufficiency_candidate` | relatedありで continue（達成保証ではない）; 人間レビュー上no_webでローカルTool実行あり |
| C01 | ambiguous | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| C02 | ambiguous | False | True | hits | success_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索で hits あり（利用可否 |
| C03 | ambiguous | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| C04 | ambiguous | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| C05 | ambiguous | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| D01 | no_web | True | False | None | success_candidate | `C_layer_mismatch_overflag_candidate` | heuristic judged_yes だが search_web 未実行; relatedありで continue（ |
| D02 | no_web | True | False | None | failure_candidate | `C_layer_mismatch_overflag_candidate` | heuristic judged_yes だが search_web 未実行; needs_new_tool 発火（D0 |
| D03 | no_web | True | False | None | inconclusive | `C_layer_mismatch_overflag_candidate` | heuristic judged_yes だが search_web 未実行; related空で uncertain  |
| D04 | no_web | True | False | None | inconclusive | `C_layer_mismatch_overflag_candidate` | heuristic judged_yes だが search_web 未実行; relatedありで continue（ |
| D05 | no_web | True | False | None | success_candidate | `C_layer_mismatch_overflag_candidate` | heuristic judged_yes だが search_web 未実行; relatedありで continue（ |
| E01 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| E02 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| E03 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| E04 | ambiguous | False | True | error | success_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| E05 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| F01 | needs_web | False | True | error | success_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| F02 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| F03 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| F04 | needs_web | False | True | error | failure_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| F05 | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| G01 | no_web | False | False | None | inconclusive | `F_related_continue_not_sufficiency_candidate` | relatedありで continue（達成保証ではない）; 人間レビュー上no_webでローカルTool実行あり |
| G02 | no_web | False | False | None | success_candidate | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造; 人間レビュー上no_webでローカルTool実行あり |
| G03 | no_web | False | False | None | success_candidate | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造; 人間レビュー上no_webでローカルTool実行あり |
| G04 | no_web | False | False | None | inconclusive | `F_related_continue_not_sufficiency_candidate` | relatedありで continue（達成保証ではない）; 人間レビュー上no_webでローカルTool実行あり |
| G05 | no_web | False | False | None | success_candidate | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造; 人間レビュー上no_webでローカルTool実行あり |
| G06 | reviewer_uncertain | False | True | error | success_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| G07 | reviewer_uncertain | False | True | error | success_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| G08 | reviewer_uncertain | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| G09 | reviewer_uncertain | False | False | None | inconclusive | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造 |
| G10 | reviewer_uncertain | False | True | error | success_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| H01 | ambiguous | False | True | error | failure_candidate | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| H02 | ambiguous | True | True | error | inconclusive | `D_search_path_error_candidate` | 検索実行後 outcome=error（判断正誤とは別）; relatedありで continue（達成保証ではない）; |
| H03 | ambiguous | False | False | None | success_candidate | `F_route_uncertain_saturated_candidate` | related空で uncertain に落ちた構造 |
| P01a | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| P01b | needs_web | False | True | hits | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索で hits あり（利用可否 |
| P01c | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| P02a | ambiguous | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |
| P02b | needs_web | False | True | error | inconclusive | `C_layer_mismatch_underflag_candidate` | heuristic judged_no だが LLM が search_web 実行; 検索実行後 outcome=er |

## コンテンツトピック別集計

```json
{
  "composite": {
    "n": 3,
    "human_web_need": {
      "ambiguous": 3
    },
    "heuristic_yes": 1,
    "llm_called": 2,
    "search_primary": {
      "error": 2,
      "null": 1
    },
    "layer_underflag": 1,
    "layer_overflag": 0,
    "search_error": 2
  },
  "current_info": {
    "n": 7,
    "human_web_need": {
      "needs_web": 6,
      "ambiguous": 1
    },
    "heuristic_yes": 1,
    "llm_called": 7,
    "search_primary": {
      "error": 7
    },
    "layer_underflag": 6,
    "layer_overflag": 0,
    "search_error": 7
  },
  "file_ops": {
    "n": 11,
    "human_web_need": {
      "no_web": 11
    },
    "heuristic_yes": 5,
    "llm_called": 0,
    "search_primary": {
      "null": 11
    },
    "layer_underflag": 0,
    "layer_overflag": 5,
    "search_error": 0
  },
  "general_knowledge": {
    "n": 2,
    "human_web_need": {
      "no_web": 1,
      "ambiguous": 1
    },
    "heuristic_yes": 0,
    "llm_called": 1,
    "search_primary": {
      "null": 1,
      "error": 1
    },
    "layer_underflag": 1,
    "layer_overflag": 0,
    "search_error": 1
  },
  "local_observation": {
    "n": 4,
    "human_web_need": {
      "no_web": 4
    },
    "heuristic_yes": 0,
    "llm_called": 0,
    "search_primary": {
      "null": 4
    },
    "layer_underflag": 0,
    "layer_overflag": 0,
    "search_error": 0
  },
  "news": {
    "n": 1,
    "human_web_need": {
      "needs_web": 1
    },
    "heuristic_yes": 1,
    "llm_called": 1,
    "search_primary": {
      "error": 1
    },
    "layer_underflag": 0,
    "layer_overflag": 0,
    "search_error": 1
  },
  "niche_or_fictional": {
    "n": 4,
    "human_web_need": {
      "needs_web": 4
    },
    "heuristic_yes": 0,
    "llm_called": 4,
    "search_primary": {
      "error": 4
    },
    "layer_underflag": 4,
    "layer_overflag": 0,
    "search_error": 4
  },
  "product_external": {
    "n": 3,
    "human_web_need": {
      "ambiguous": 2,
      "needs_web": 1
    },
    "heuristic_yes": 0,
    "llm_called": 3,
    "search_primary": {
      "hits": 1,
      "error": 2
    },
    "layer_underflag": 3,
    "layer_overflag": 0,
    "search_error": 2
  },
  "time_dependent": {
    "n": 6,
    "human_web_need": {
      "needs_web": 3,
      "ambiguous": 3
    },
    "heuristic_yes": 0,
    "llm_called": 6,
    "search_primary": {
      "error": 6
    },
    "layer_underflag": 6,
    "layer_overflag": 0,
    "search_error": 6
  },
  "tool_gap": {
    "n": 5,
    "human_web_need": {
      "reviewer_uncertain": 5
    },
    "heuristic_yes": 0,
    "llm_called": 4,
    "search_primary": {
      "error": 4,
      "null": 1
    },
    "layer_underflag": 4,
    "layer_overflag": 0,
    "search_error": 4
  },
  "weather": {
    "n": 4,
    "human_web_need": {
      "needs_web": 4
    },
    "heuristic_yes": 0,
    "llm_called": 4,
    "search_primary": {
      "error": 3,
      "hits": 1
    },
    "layer_underflag": 4,
    "layer_overflag": 0,
    "search_error": 3
  }
}
```

## 言い換えgroup

```json
{
  "para_osaka_weather": [
    {
      "case_id": "P01a",
      "human_web_need": "needs_web",
      "heuristic_judgment": false,
      "llm_called": true,
      "search_primary_outcome": "error",
      "answer_surface_proxy": "inconclusive",
      "heuristic_route": "uncertain",
      "classification_candidates": [
        "C_layer_mismatch_underflag_candidate",
        "D_search_path_error_candidate",
        "F_route_uncertain_saturated_candidate",
        "E_insufficient_search_evidence_candidate"
      ]
    },
    {
      "case_id": "P01b",
      "human_web_need": "needs_web",
      "heuristic_judgment": false,
      "llm_called": true,
      "search_primary_outcome": "hits",
      "answer_surface_proxy": "inconclusive",
      "heuristic_route": "uncertain",
      "classification_candidates": [
        "C_layer_mismatch_underflag_candidate",
        "D_search_path_hits_candidate",
        "F_route_uncertain_saturated_candidate",
        "E_hits_use_unverified_candidate"
      ]
    },
    {
      "case_id": "P01c",
      "human_web_need": "needs_web",
      "heuristic_judgment": false,
      "llm_called": true,
      "search_primary_outcome": "error",
      "answer_surface_proxy": "inconclusive",
      "heuristic_route": "uncertain",
      "classification_candidates": [
        "C_layer_mismatch_underflag_candidate",
        "D_search_path_error_candidate",
        "F_route_uncertain_saturated_candidate",
        "E_insufficient_search_evidence_candidate"
      ]
    }
  ],
  "para_rtx3060": [
    {
      "case_id": "P02a",
      "human_web_need": "ambiguous",
      "heuristic_judgment": false,
      "llm_called": true,
      "search_primary_outcome": "error",
      "answer_surface_proxy": "inconclusive",
      "heuristic_route": "uncertain",
      "classification_candidates": [
        "C_layer_mismatch_underflag_candidate",
        "D_search_path_error_candidate",
        "F_route_uncertain_saturated_candidate",
        "E_insufficient_search_evidence_candidate"
      ]
    },
    {
      "case_id": "P02b",
      "human_web_need": "needs_web",
      "heuristic_judgment": false,
      "llm_called": true,
      "search_primary_outcome": "error",
      "answer_surface_proxy": "inconclusive",
      "heuristic_route": "uncertain",
      "classification_candidates": [
        "C_layer_mismatch_underflag_candidate",
        "D_search_path_error_candidate",
        "F_route_uncertain_saturated_candidate",
        "E_insufficient_search_evidence_candidate"
      ]
    }
  ]
}
```

## C/D/F/G/E 候補件数

- **C_layer_mismatch**: 34 tags assigned across cases
- **D_search_path**: 32 tags assigned across cases
- **F_route_related**: 50 tags assigned across cases
- **G_tool_capability**: 17 tags assigned across cases
- **E_evidence_answer**: 32 tags assigned across cases

## 追加収集提案（不足カテゴリのみ）

- (6-8) heuristic語ギャップの再現（最近/明日/天気 vs 最新/現在/ニュース） — focus: time_dependent / weather / news contrast
- (4-6) search hits成功連鎖の観測が不足（D_search_path_hits が稀） — focus: stable English / evergreen topics
- (2-3) new_tool ヒント衝突の確認（F_new_tool / registryに 型） — focus: short substring collisions
- (3-4) human no_web なのに LLM検索（G_no_web_human_but_llm_searched）がほぼ無い／逆にD系overflagの再現 — focus: web_word_but_unneeded paraphrases

## 限界

- n=50 では一般化できない。
- 判断層のずれと Web検索機能失敗（D_*）を混同しない。
- heuristic 修正案は本成果物では実装しない。

