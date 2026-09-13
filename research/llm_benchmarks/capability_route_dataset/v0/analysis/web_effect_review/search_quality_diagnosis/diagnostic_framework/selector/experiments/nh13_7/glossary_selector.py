"""Mechanical glossary term selection — NH13-7. No LLM in selection path."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parents[2]
GLOSSARY_JSON = FRAMEWORK / "knowledge_base" / "glossary" / "glossary.json"
RULES_PATH = HERE / "selection_rules.json"

NH8 = FRAMEWORK / "selector" / "experiments" / "nh8"
if str(NH8) not in sys.path:
    sys.path.insert(0, str(NH8))
from uncertainty_gate import material_hints  # noqa: E402


def load_rules() -> dict[str, Any]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def load_glossary() -> dict[str, Any]:
    return json.loads(GLOSSARY_JSON.read_text(encoding="utf-8"))


def valid_terms(glossary: dict[str, Any] | None = None) -> set[str]:
    glossary = glossary or load_glossary()
    return {t["term"] for t in glossary.get("terms", [])}


def _blob(materials: dict[str, Any]) -> str:
    return json.dumps(materials or {}, ensure_ascii=False).lower()


def keyword_hits(materials: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    b = _blob(materials)
    fired: list[str] = []
    for kw, terms in (rules.get("keyword_to_terms") or {}).items():
        if kw in b:
            fired.extend(terms)
    return fired


def expand_dependencies(
    selected: set[str],
    rules: dict[str, Any],
    valid: set[str],
) -> tuple[set[str], list[str]]:
    reasons: list[str] = []
    expanded = set(selected)
    deps = rules.get("dependency_expansion") or {}
    changed = True
    while changed:
        changed = False
        for term in list(expanded):
            for dep in deps.get(term, []):
                if dep in valid and dep not in expanded:
                    expanded.add(dep)
                    reasons.append(f"dependency:{term}->{dep}")
                    changed = True
    return expanded, reasons


def select_terms(
    materials: dict[str, Any],
    *,
    mode: str = "relevant",
    rules: dict[str, Any] | None = None,
    glossary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """mode: relevant | minimal"""
    rules = rules or load_rules()
    glossary = glossary or load_glossary()
    valid = valid_terms(glossary)
    selected: set[str] = set()
    rule_hits: list[str] = []
    excluded: list[str] = []

    for t in rules.get("always_include") or []:
        if t in valid:
            selected.add(t)
            rule_hits.append(f"always:{t}")

    hints = material_hints(materials)
    for hint, active in hints.items():
        if not active:
            continue
        for term in (rules.get("hint_to_terms") or {}).get(hint, []):
            if term in valid:
                selected.add(term)
                rule_hits.append(f"hint:{hint}->{term}")

    for term in keyword_hits(materials, rules):
        if term in valid:
            selected.add(term)
            rule_hits.append(f"keyword:{term}")

    if mode == "relevant":
        selected, dep_reasons = expand_dependencies(selected, rules, valid)
        rule_hits.extend(dep_reasons)
    else:
        # minimal: direct hits only + required deps for REOPEN/Evidence
        minimal_seed = set(selected)
        for term in list(minimal_seed):
            if term in ("REOPEN", "Evidence", "State"):
                deps, dr = expand_dependencies({term}, rules, valid)
                selected |= deps
                rule_hits.extend(dr)
        for ex in rules.get("minimal_exclude") or []:
            if ex in selected:
                selected.discard(ex)
                excluded.append(ex)
        cap = int(rules.get("minimal_max_terms") or 6)
        if len(selected) > cap:
            priority = list(rules.get("always_include") or []) + [
                "REOPEN", "Evidence", "State", "Validator", "Gate", "Ranking", "Filter",
                "stdout", "LLM handoff", "Small LLM", "Safety", "Fingerprint",
            ]
            kept: set[str] = set()
            for p in priority:
                if p in selected:
                    kept.add(p)
                if len(kept) >= cap:
                    break
            for t in sorted(selected):
                if len(kept) >= cap:
                    break
                kept.add(t)
            excluded.extend(sorted(selected - kept))
            selected = kept

    selected_sorted = sorted(selected)
    text = _render_glossary_block(selected_sorted, glossary)
    return {
        "selected_terms": selected_sorted,
        "selection_reasons": rule_hits,
        "selection_rules": ["selection_rules.json", f"mode={mode}"],
        "excluded_terms": sorted(set(excluded)),
        "token_count": max(1, len(text) // 4),
        "char_count": len(text),
        "glossary_text": text,
        "hints": hints,
    }


def _render_glossary_block(terms: list[str], glossary: dict[str, Any]) -> str:
    by_name = {t["term"]: t for t in glossary.get("terms", [])}
    lines = ["## Project glossary (mechanically selected)\n"]
    for name in terms:
        t = by_name.get(name)
        if not t:
            continue
        ja = (t.get("aliases") or [""])[0]
        lines.append(f"### {t['term']} ({ja})")
        lines.append(t.get("human_definition", ""))
        if t.get("llm_definition"):
            lines.append(f"DO NOT: {t['llm_definition'].split('。')[0]}。")
        lines.append("")
    return "\n".join(lines)


def appendix_from_selection(sel: dict[str, Any]) -> str:
    if not sel.get("glossary_text"):
        return ""
    return f"\n\n---\n# Glossary context (mechanical)\n\n{sel['glossary_text']}"
