"""Bridge。既存 judgment_action_bridge_experiment は import しない。"""

from __future__ import annotations

from research.llm_benchmarks.judgment_layer_llm_connection_experiment.execute import run_scripted
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.parse import parse_actions
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.select import select_actions
from research.llm_benchmarks.judgment_layer_llm_connection_experiment.validate import validate_actions


def parse_judgment(text, known_files):
    actions, fences, clauses = parse_actions(text, known_files)
    validated = validate_actions(actions, known_files)
    selected, mapping_status = select_actions(validated)
    return {
        "input_text": text,
        "judgment_received": bool(text and str(text).strip()),
        "clauses": clauses,
        "fences": fences,
        "action_candidates": validated,
        "selected_actions": selected,
        "mapping_status": mapping_status,
        "action_extracted": any(item.get("intent") not in (None, "unresolved") for item in validated),
        "action_validated": any(item.get("validated") for item in validated),
        "tool_selected": bool(selected),
    }
