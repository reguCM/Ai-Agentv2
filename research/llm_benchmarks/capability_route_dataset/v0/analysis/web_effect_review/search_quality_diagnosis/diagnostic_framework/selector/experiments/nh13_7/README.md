# NH13-7 Mechanical Glossary Selection

NH13 follow-up: mechanical term selection from problem materials + `selection_rules.json`.

## Files

- `glossary_selector.py` — `select_terms(materials, mode=relevant|minimal)`
- `selection_rules.json` — hint/keyword/dependency rules (from glossary.json metadata)
- `cases/gold_selection.json` — human gold (NH13 CASE_RELEVANT_TERMS)
- `evaluation/selection_eval.py` — Stage 1 precision/recall
- `evaluation/failure_classify.py` — F1–F7 tags

## Run

```bash
python run_nh13_7_mechanical_glossary_selection.py
```

Results: `runs/<run_id>/nh13_7_mechanical_glossary_selection/`

## Conditions

| Cond | Source |
|------|--------|
| A | NH13 A reuse (no glossary) |
| B | NH13 B reuse (full) |
| C | NH13 D reuse (human relevant) |
| D | Mechanical relevant (this module) |
| E | Mechanical minimal |
| F | LLM term selection control |

Production code unchanged.
