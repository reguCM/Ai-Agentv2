"""Experiment-only Decision Adoption Gate.

Local first_recommendation is not a final/locked decision.
Does not import production runtime. Does not send Strong/Cursor adopted
answers to the model. Hidden eval adopted text must never be placed in
retry payloads.
"""
from __future__ import annotations

import re
from typing import Any

HIGH_UNCERTAINTY = 50  # Local self-eval signal only. Not a Gate 2 route by itself.

# Retired as a routing allowlist. Gate 2 must not key off decision_id / Q-number.
IMPORTANT_DECISIONS = frozenset()

REQUIRED_FIELDS = [
    "decision_id",
    "first_recommendation",
    "reason",
    "rejected_alternatives",
    "known_issues",
    "concrete_failure_scenarios",
    "need_human",
    "uncertainty_score",
    "uncertainty_reason",
    "needs_deep_review",
]

NEGATION_BEFORE = re.compile(
    r"(?i)(do\s+not|don't|dont|never|stop|avoid|skip|without|forbid|"
    r"reject|rejected|"
    r"禁止|しない|使わない|止め|廃止|外す|残さない|戻さない|拒否|"
    r"not\s+use|not\s+allow|not\s+select|not\s+rank|not\s+merge|"
    r"strictly\s+separated|keep\s+.{0,40}separated|分離)"
)

# Per-decision known-wrong / invariant rules. `adopted` from hidden_eval is
# intentionally absent: retry may cite these strings, never the adopted answer.
GATE_RULES: list[dict[str, Any]] = [
    {
        "id": "Q9_merge_file_registry_keywords",
        "decision_ids": ("Q9",),
        "kind": "known_wrong",
        "forbidden": (
            "Merging generic-file / workspace_file_read keywords with "
            "registry_read keywords into one vocabulary."
        ),
        "contract": (
            "registry_read and workspace_file_read are not the same meaning "
            "even if both may use read_file."
        ),
        "locked_priors": [],
        "adopt_res": [
            r"merge\s+(generic\s+)?file.{0,160}(registry_read|registry)",
            r"merge\s+(the\s+)?(two\s+)?(keywords|capabilities)",
            r"keyword[s]?.{0,40}merge",
            r"両方を.{0,20}keyword",
            r"keyword.{0,20}でマージ",
        ],
        "reject_res": [
            r"do\s+not\s+merge",
            r"don't\s+merge",
            r"not\s+merge",
            r"マージしない",
            r"strictly\s+separated",
            r"keep\s+.{0,80}separated",
            r"分離",
        ],
    },
    {
        "id": "Q25_restore_look_first0_silent_read",
        "decision_ids": ("Q25",),
        "kind": "known_wrong",
        "forbidden": (
            "Keeping or restoring look_first[0] silent/default read for "
            "pathless file-read next_action."
        ),
        "contract": (
            "Current look_first[0] silent read is a defect, not the spec. "
            "Pathless file-read must not auto-read registry/tools.json."
        ),
        "locked_priors": [],
        "adopt_res": [
            r"keep\s+silent\s+read",
            r"maintain\s+silent",
            r"restore\s+look_first\[0\]",
            r"黙読を維持",
            r"look_first\[0\].{0,40}(戻|維持)",
            r"default(?:ing)?\s+to\s+look_first\[0\]",
            r"allow\s+pathless\s+read",
        ],
        "reject_res": [
            r"stop\s+silent",
            r"stop\s+defaulting",
            r"abolish",
            r"require\s+path",
            r"path\s+根拠",
            r"黙読.{0,8}(止|廃)",
            r"look_first\[0\].{0,20}廃止",
        ],
    },
    {
        "id": "Q29_text_slice_as_search_query",
        "decision_ids": ("Q29",),
        "kind": "known_wrong",
        "forbidden": "Using text[:80] (or a long-text slice) as search_files query.",
        "contract": (
            "Long text as a search query produces irrelevant hits. If a query "
            "cannot be extracted mechanically, do not inject search next_action."
        ),
        "locked_priors": [],
        "adopt_res": [
            r"use\s+text\[:80\]",
            r"text\[:80\]\s+as\s+(query|search)",
            r"長文を\s*query",
            r"slice.{0,20}as\s+query",
        ],
        "reject_res": [
            r"do\s+not\s+use\s+text\[:80\]",
            r"don't\s+use\s+text\[:80\]",
            r"text\[:80\].{0,12}禁止",
            r"skip\s+next_action",
            r"next_action\s+なし",
            r"no\s+query.{0,40}skip",
        ],
    },
    {
        "id": "Q14_15_rank_by_index",
        "decision_ids": ("Q14-15",),
        "kind": "known_wrong",
        "forbidden": (
            "Selecting among 2+ Help-confirmed candidates by list index [0] "
            "and marking RESOLVED."
        ),
        "contract": "Do not treat ranking among 2+ candidate tools as H4 Core.",
        "locked_priors": [],
        "adopt_res": [
            r"select\s+first\s+candidate",
            r"candidate_tools\s*\[\s*0\s*\]",
            r"\(\[0\]\)",
            r"mark(?:ed)?\s+as\s+resolved.{0,40}2\+",
            r"\[0\].{0,40}resolved",
        ],
        "reject_res": [
            r"do\s+not\s+rank",
            r"not\s+\[0\]",
            r"candidates_available",
            r"2\+\s*なら.{0,20}選ばない",
            r"exactly\s+1",
        ],
    },
    {
        "id": "Q30_silent_list_dot_close",
        "decision_ids": ("Q30",),
        "kind": "known_wrong",
        "forbidden": (
            "Silently applying the pathless file-read rule to list_files so "
            "that '.' is forbidden during Core."
        ),
        "contract": (
            "Do not silently close list '.' the same way as pathless read "
            "during H4 Core."
        ),
        "locked_priors": [
            "Q25 path-required read next_action is for file-read, not a silent rewrite of list_files '.'."
        ],
        "adopt_res": [
            r"require\s+path\s+for\s+list",
            r"do\s+not\s+allow\s+pathless\s+['\"]?\.['\"]?",
            r"forbid.{0,20}list.{0,20}\.",
            r"pathless\s+['\"]?\['\"]?\s*forbidden",
        ],
        "reject_res": [
            r"allow\s+['\"]?\.",
            r"residual",
            r"do\s+not\s+silently",
            r"selected\s+時",
            r"keep\s+['\"]?\.",
        ],
    },
    {
        "id": "Q7_fold_plural_to_first",
        "decision_ids": ("Q7",),
        "kind": "known_wrong",
        "forbidden": "Folding 2+ capabilities/results into first, or deleting the singular API.",
        "contract": "Do not delete singular APIs. Do not always fold 2+ into first.",
        "locked_priors": [],
        "adopt_res": [
            r"fold\s+2\s*\+?\s*into\s+first",
            r"fold\s+2\+",
            r"常に first に折",
            r"delete\s+singular",
            r"単数.{0,12}削除",
        ],
        "reject_res": [
            r"do\s+not\s+fold",
            r"not\s+fold",
            r"do\s+not\s+delete\s+singular",
            r"0/1/2\+\s*error",
        ],
    },
    {
        "id": "Q47_delete_leftovers_as_done",
        "decision_ids": ("Q47",),
        "kind": "known_wrong",
        "forbidden": "Deleting leftovers to declare Core complete.",
        "contract": "Deleting leftover code is not completion.",
        "locked_priors": [],
        "adopt_res": [
            r"delete\s+leftovers",
            r"掃除して完成",
            r"leftover.{0,20}削除して完成",
        ],
        "reject_res": [
            r"do\s+not\s+delete\s+leftovers",
            r"keep\s+residuals",
            r"削除しない",
        ],
    },
    {
        "id": "cardinality_index_or_head_select",
        "decision_ids": None,
        "kind": "known_wrong",
        "forbidden": (
            "Selecting, injecting, or resolving among 2+ candidates by list index "
            "[0], first, or head without a unique non-index reason."
        ),
        "contract": (
            "Among 2+ candidates, do not adopt first/[0]/head as the chosen item. "
            "Mentioning the forbidden pattern as a rejected example is not a violation."
        ),
        "locked_priors": [],
        "adopt_res": [
            r"inject only\s*\[\s*0\s*\]",
            r"inject\s+first(?:\s+(?:of\s+)?(?:multiple|2\+))?",
            r"inject.{0,24}\[\s*0\s*\]",
            r"select first candidate",
            r"select(?:ing)? .{0,60}by (?:list )?index",
            r"take the first\s+(?:candidate|next_action|item)",
            r"head of (?:the )?(?:list|candidates)",
            r"candidate_tools\s*\[\s*0\s*\]",
            r"next_action.{0,24}\[\s*0\s*\]",
            r"\[\s*0\s*\]\s*だけ\s*(inject|選|確定)",
            r"先頭候補.{0,12}(選|inject|確定)",
        ],
        "reject_res": [
            r"inject none",
            r"do not inject",
            r"don't inject",
            r"reject selecting.{0,80}\[\s*0\s*\]",
            r"do not rank",
            r"not\s*\[\s*0\s*\]",
            r"2\+\s*なら.{0,24}(なし|選ばない|inject なし)",
            r"どれも inject しない",
            r"stop silent.{0,24}look_first\[\s*0\s*\]",
        ],
    },
    {
        "id": "shared_keyword_family_prefer",
        "decision_ids": None,
        "kind": "known_wrong",
        "forbidden": (
            "Confirming or preferring one capability family from a shared / "
            "cross-cutting keyword alone (for example 検索 → web_search)."
        ),
        "contract": (
            "Shared keywords that sit on multiple families do not uniquely "
            "confirm a family. Do not add web from 検索 alone when a file "
            "target is present. Do not prefer one family from that shared token."
        ),
        "locked_priors": [],
        "adopt_res": [
            r"prefer adding to web_search",
            r"prefer .{0,24}to web_search",
            r"片方へ prefer",
            r"検索.{0,24}web を足",
            r"confirm web from .{0,12}(search|検索)",
        ],
        "reject_res": [
            r"avoid shared keywords",
            r"横断共有だけでは確定しない",
            r"検索だけで web を足さない",
            r"do not (confirm|prefer|add).{0,40}(shared|検索)",
            r"file対象.{0,20}web を足さない",
        ],
    },
]


def _as_text(row: dict[str, Any]) -> str:
    rec = str(row.get("first_recommendation") or "")
    reason = str(row.get("reason") or "")
    return rec


def _rejected_blob(row: dict[str, Any]) -> str:
    val = row.get("rejected_alternatives") or []
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return " ".join(str(x) for x in val)
    return str(val)


def _search_any(patterns: list[str], text: str) -> re.Match[str] | None:
    for pat in patterns:
        m = re.search(pat, text, flags=re.I | re.S)
        if m:
            return m
    return None


def _search_all(patterns: list[str], text: str) -> list[re.Match[str]]:
    found: list[re.Match[str]] = []
    for pat in patterns:
        found.extend(re.finditer(pat, text, flags=re.I | re.S))
    found.sort(key=lambda m: m.start())
    return found


def _clause_prefix(text: str, start: int, window: int = 72) -> str:
    """Prefix used for negation. A previous sentence's Avoid/Do-not does not
    negate a later unnegated adopt clause.
    """
    prefix = text[max(0, start - window) : start]
    last = -1
    cut_len = 0
    for sep in (". ", "。", "! ", "? ", "; ", ".\n", "!\n", "?\n"):
        idx = prefix.rfind(sep)
        if idx > last:
            last = idx
            cut_len = len(sep)
    if last >= 0:
        return prefix[last + cut_len :]
    return prefix


def _negated_at(text: str, start: int, window: int = 72) -> bool:
    return bool(NEGATION_BEFORE.search(_clause_prefix(text, start, window)))


def stance_on_rule(row: dict[str, Any], rule: dict[str, Any]) -> str:
    """Return adopt | reject | absent | unclear for one known-wrong rule.

    An unnegated adopt is a violation even if the rec also states the
    correct constraint. Mentioning the forbidden pattern only under
    reject/negation is not a violation.
    """
    rec = str(row.get("first_recommendation") or "")
    if not rec.strip():
        return "absent"
    adopt_hits = _search_all(list(rule["adopt_res"]), rec)
    reject_hits = _search_all(list(rule["reject_res"]), rec)
    unneg_adopt = [m for m in adopt_hits if not _negated_at(rec, m.start())]
    if unneg_adopt:
        return "adopt"
    if reject_hits or (adopt_hits and not unneg_adopt):
        return "reject"
    rejected = _rejected_blob(row)
    if _search_any(list(rule["adopt_res"]), rejected):
        return "reject"
    return "absent"


def missing_required_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if row.get("_parse_missing"):
        return list(REQUIRED_FIELDS)
    for key in REQUIRED_FIELDS:
        if key not in row or row.get(key) in (None, ""):
            if key == "first_recommendation" or key not in ("need_human", "needs_deep_review"):
                if row.get(key) in (None, "") or key not in row:
                    missing.append(key)
    rec = row.get("first_recommendation")
    if not str(rec or "").strip():
        if "first_recommendation" not in missing:
            missing.append("first_recommendation")
    score = row.get("uncertainty_score")
    if score is not None and not isinstance(score, int):
        missing.append("uncertainty_score")
    return missing


def local_self_eval_signals(row: dict[str, Any]) -> list[str]:
    """Record Local self-eval. Never a Gate 1 fail and never a Gate 2 route by itself."""
    reasons: list[str] = []
    if row.get("need_human") is True:
        reasons.append("need_human")
    score = row.get("uncertainty_score")
    if isinstance(score, int) and score >= HIGH_UNCERTAINTY:
        reasons.append("high_uncertainty")
    if row.get("needs_deep_review") is True:
        reasons.append("needs_deep_review")
    return reasons


def escalation_reasons(row: dict[str, Any], decision_id: str) -> list[str]:
    """Backward-compatible alias. decision_id is ignored on purpose (no Q-id routing)."""
    del decision_id
    return local_self_eval_signals(row)


def evaluate_adoption_gate(
    *,
    row: dict[str, Any],
    decision_id: str,
    heuristic_dangerous: list[str],
    prior_contradictions: list[str],
) -> dict[str, Any]:
    """Deterministic gate. heuristic_dangerous is recorded, never FAIL-only cause."""
    missing = missing_required_fields(row)
    semantic: list[dict[str, str]] = []
    unclear: list[str] = []
    retry_known_wrong: list[str] = []
    retry_contracts: list[str] = []
    retry_priors: list[str] = []
    why: list[str] = []

    for rule in GATE_RULES:
        ids = rule.get("decision_ids")
        if ids is not None and decision_id not in ids:
            continue
        stance = stance_on_rule(row, rule)
        if stance == "adopt":
            semantic.append({"rule_id": rule["id"], "kind": rule["kind"], "forbidden": rule["forbidden"]})
            retry_known_wrong.append(rule["forbidden"])
            retry_contracts.append(rule["contract"])
            retry_priors.extend(list(rule.get("locked_priors") or []))
            why.append(f"first_recommendation adopts forbidden action: {rule['id']}")
        elif stance == "unclear":
            unclear.append(rule["id"])

    semantic_ids = [s["rule_id"] for s in semantic]
    heuristic_only = [
        h for h in (heuristic_dangerous or []) if not _heuristic_explained_by_semantic(h, semantic_ids, decision_id)
    ]

    if missing and "first_recommendation" in missing:
        result = "FAIL"
        why.append("required first_recommendation is empty or missing")
        retry_contracts.append("Output must include a non-empty first_recommendation and the other required fields.")
    elif missing:
        result = "UNKNOWN"
        why.append("required structured fields incomplete: " + ",".join(missing))
    elif semantic:
        result = "FAIL"
    elif unclear:
        result = "UNKNOWN"
        why.append("stance on known-wrong is unclear: " + ",".join(unclear))
    elif prior_contradictions:
        result = "FAIL"
        why.append("locked prior contradiction: " + ",".join(prior_contradictions))
        retry_priors.extend(prior_contradictions)
    else:
        result = "PASS"

    semantic_result = result
    esc = local_self_eval_signals(row) if result == "PASS" else []

    return {
        "result": result,
        "semantic_gate_result": semantic_result,
        "local_signals": esc,
        "escalation_reasons": esc,
        "heuristic_dangerous": list(heuristic_dangerous or []),
        "heuristic_only_dangerous": heuristic_only,
        "semantic_dangerous": semantic,
        "prior_contradictions": list(prior_contradictions or []),
        "missing_fields": missing,
        "reasons": why,
        "violated_prior_or_known_wrong": retry_priors + retry_known_wrong,
        "retry_payload": None
        if semantic_result != "FAIL"
        else {
            "violated_locked_priors": retry_priors,
            "known_wrong": retry_known_wrong,
            "related_contracts": retry_contracts,
            "why_not_adoptable": " ".join(
                x for x in why if not str(x).startswith("escalate:")
            ),
        },
    }


def _heuristic_explained_by_semantic(flag: str, semantic_ids: list[str], decision_id: str) -> bool:
    mapping = {
        "merge_push": "Q9_merge_file_registry_keywords",
        "look_first0_default": "Q25_restore_look_first0_silent_read",
        "search_text_slice": "Q29_text_slice_as_search_query",
        "ranking_by_index": "Q14_15_rank_by_index",
    }
    sid = mapping.get(flag)
    return bool(sid and sid in semantic_ids)


def build_gate_retry_user(
    *,
    base_isolated_user: str,
    decision_id: str,
    previous_recommendation: str,
    payload: dict[str, Any],
) -> str:
    """Constraints-only retry. Must not include Strong/Cursor adopted answers."""
    priors = payload.get("violated_locked_priors") or []
    wrong = payload.get("known_wrong") or []
    contracts = payload.get("related_contracts") or []
    why = str(payload.get("why_not_adoptable") or "")
    block = {
        "gate": "FAIL",
        "decision_id": decision_id,
        "previous_first_recommendation_not_adopted": previous_recommendation,
        "violated_locked_priors": priors,
        "known_wrong_forbidden_actions": wrong,
        "related_existing_contracts": contracts,
        "why_current_proposal_is_not_adoptable": why,
        "instruction": (
            "Reconsider your first recommendation so it satisfies these constraints. "
            "Do not copy a hidden Strong/Cursor answer; none is provided. "
            "Return JSON {\"decisions\":[{...only this decision_id...}]} with all required fields."
        ),
    }
    import json

    return (
        base_isolated_user
        + "\n\n# Adoption Gate FAIL — constraints only, not an answer key\n"
        + json.dumps(block, ensure_ascii=False, indent=2)
    )


def final_adoption_status(gate_result: str) -> str:
    """Gate 1 status only. Gate 2 uses final_route_status."""
    if gate_result == "PASS":
        return "adoption_candidate"
    if gate_result == "UNKNOWN":
        return "escalate_strong_or_human"
    return "rejected"


def final_route_status(route: str) -> str:
    if route == "AUTO":
        return "adoption_candidate"
    if route == "REVIEW":
        return "review_strong_or_critic"
    if route == "HUMAN":
        return "needs_human"
    return "rejected"


def topic_attributes(question: str, context: str, recommendation: str, reason: str) -> list[str]:
    """Topic tags from text. Informational only; not a standalone Gate 2 route."""
    blob = f"{question}\n{context}\n{recommendation}\n{reason}".lower()
    attrs: list[str] = []
    if re.search(
        r"silent read|黙読|auto-execut|tools\.json|sandbox|pathless read|自動実行|fail closed|fail-closed",
        blob,
    ):
        attrs.append("safety")
    if re.search(
        r"leftover|掃除して完成|delete leftover|削除して完成|delete singular|singular api.{0,24}delete|irreversible|破壊",
        blob,
    ):
        attrs.append("destructive")
        attrs.append("irreversible")
    if re.search(
        r"out-of-tree|snapshot|caller|compat|ranking|candidate_tools|keyword.{0,30}merge|マージ|api\b|allowlist|除外",
        blob,
    ):
        attrs.append("compatibility")
    return sorted(set(attrs))


def _reason_blob(uncertainty_reason: str, reason: str, known_issues: Any, rec: str) -> str:
    issues = known_issues
    if isinstance(issues, list):
        issues = " ".join(str(x) for x in issues)
    return f"{uncertainty_reason}\n{reason}\n{issues}\n{rec}"


def _negated_recommendation(recommendation: str) -> bool:
    return bool(re.search(r"(?i)(do not|don't|しない|禁止|keep residual)", recommendation))


MISSING_ARTIFACT = re.compile(
    r"(?i)("
    r"no existing .{0,80}(vocabulary|registry|path pattern|disambiguation)|"
    r"no explicit .{0,80}vocabulary|"
    r"does not handle .{0,80}(matching|registry)|"
    r"no registry-based|"
    r"requires new .{0,40}(vocabulary|tool\.json|disambiguation)|"
    r"unless .{0,100}(exists|exist)|"
    r"may need adjustment|"
    r"without changing .{0,40}(singular )?api"
    r")"
)

SAFETY_BEHAVIOR_CHANGE = re.compile(
    r"(?i)("
    r"stop silent|"
    r"require path for file-read|"
    r"require path for .{0,24}read|"
    r"abolish .{0,24}(silent|look_first)|"
    r"黙読.{0,8}(止|廃)|"
    r"look_first\[0\].{0,20}廃止"
    r")"
)

RESIDUAL_CORE_SETTLED = re.compile(
    r"(?i)(as residual|residual as|during h4 core|out-of-core|"
    r"do not enforce path|keep residuals|do not delete leftovers)"
)

SINGULAR_CANONICAL = re.compile(
    r"(?i)(keep single api|single api per capability|keep singular|"
    r"正本.{0,16}単数)"
)

PLURAL_API_FORK = re.compile(
    r"(?i)(複数形|複数 capability|plural|正本 API を複数|単数 API を|"
    r"0/1/2\+|fold 2\+|2\+ を first)"
)

KEEP_CODE_TABLE_AS_CORE = re.compile(
    r"(?i)(keep .{0,80}(in capability core|as capability canonical|in the capability core)|"
    r"capability core.{0,40}(keep|remain)|"
    r"正本に残)"
)

REMOVE_FROM_CORE = re.compile(
    r"(?i)(remove .{0,80}(from capability core|from the capability canonical)|"
    r"正本から外|capability core.{0,20}(remove|外))"
)

CANONICAL_KEEP_OR_REMOVE_QUESTION = re.compile(
    r"(?i)(正本に残すか外す|capability 正本|capability core|"
    r"正本から外すか)"
)


def _pole_asserted(text: str, patterns: tuple[str, ...]) -> re.Match[str] | None:
    for pat in patterns:
        m = re.search(pat, text, flags=re.I | re.S)
        if m and not _negated_at(text, m.start()):
            return m
    return None


POLARITY_PAIRS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (r"\badd\b", r"足す"),
        (r"do not add", r"don't add", r"keywords only", r"足さない", r"idを足さない"),
    ),
    (
        (r"\bkeep\b", r"残す"),
        (r"\bremove\b", r"外す", r"(?<!not )delete", r"削除"),
    ),
    (
        (r"\badopt\b", r"採用"),
        (r"\breject\b", r"不採用", r"採用しない"),
    ),
    (
        (r"\binclude\b", r"含める"),
        (r"exclude", r"含めない", r"do not include", r"don't include"),
    ),
)


def polarity_fork_unclosed(question: str, recommendation: str) -> bool:
    """True when the question offers both poles and the rec asserts both as adopted."""
    q = str(question or "")
    rec = str(recommendation or "")
    if not q.strip() or not rec.strip():
        return False
    for pos_pats, neg_pats in POLARITY_PAIRS:
        q_pos = any(re.search(p, q, flags=re.I) for p in pos_pats)
        q_neg = any(re.search(p, q, flags=re.I) for p in neg_pats)
        if not (q_pos and q_neg):
            continue
        rec_pos = _pole_asserted(rec, pos_pats)
        rec_neg = _pole_asserted(rec, neg_pats)
        if rec_pos and rec_neg:
            return True
    return False


def need_human_is_value_judgment(blob: str) -> bool:
    """True only if the stated reason needs user purpose/preference, not contract recheck."""
    low = blob.lower()
    human_cues = (
        r"\bpreference\b",
        r"\btaste\b",
        r"好み",
        r"ユーザーの目的",
        r"product vision",
        r"should we ship",
        r"価値判断",
        r"which product goal",
    )
    review_cues = (
        r"constraint",
        r"locked",
        r"prior",
        r"api contract",
        r"registry",
        r"tools\.json",
        r"vocabulary",
        r"snapshot",
        r"caller",
        r"residual",
        r"out-of-core",
        r"disambiguation",
        r"exclusion",
        r"path pattern",
        r"look_first",
    )
    has_human = any(re.search(p, low) for p in human_cues)
    has_review = any(re.search(p, low) for p in review_cues)
    if has_human and not has_review:
        return True
    return False


def route_final(
    *,
    semantic_gate_result: str,
    semantic_dangerous: list[Any] | None,
    need_human: bool,
    needs_deep_review: bool,
    uncertainty_score: int | None,
    uncertainty_reason: str = "",
    reason: str = "",
    known_issues: Any = None,
    question: str = "",
    context: str = "",
    recommendation: str = "",
) -> dict[str, Any]:
    """Gate 2: AUTO / REVIEW / HUMAN from meaning, not Local self-eval flags.

    need_human / uncertainty / needs_deep_review are recorded as signals only.
    decision_id must not be passed in; Q-numbers are not routing features.
    """
    attrs = topic_attributes(question, context, recommendation, reason)
    blob = _reason_blob(uncertainty_reason, reason, known_issues, recommendation)
    rec = str(recommendation or "")
    value_judgment = need_human_is_value_judgment(blob)
    notes: list[str] = []
    signals = {
        "need_human": bool(need_human),
        "needs_deep_review": bool(needs_deep_review),
        "high_uncertainty": isinstance(uncertainty_score, int) and uncertainty_score >= HIGH_UNCERTAINTY,
    }

    def packed(route: str, extra_notes: list[str], why_human: str | None = None) -> dict[str, Any]:
        return {
            "route": route,
            "attributes": attrs,
            "value_judgment": value_judgment if route == "HUMAN" else False,
            "notes": extra_notes,
            "why_human": why_human,
            "local_signals": signals,
        }

    if semantic_gate_result == "FAIL" or semantic_dangerous:
        if value_judgment:
            return packed(
                "HUMAN",
                ["semantic_fail_and_value_judgment"],
                "Retry still adopts a forbidden action and the remaining choice is a user value judgment, "
                "not a contract recheck.",
            )
        return packed("REVIEW", ["semantic_fail_contract_recheck"])

    if value_judgment:
        return packed(
            "HUMAN",
            ["reason_is_value_judgment"],
            "Existing contract/code does not uniquely determine the choice; "
            "the stated reason is user purpose/preference.",
        )

    if re.search(r"(?i)(delete leftover|掃除して完成|delete singular|削除して完成)", rec) and not _negated_recommendation(rec):
        return packed(
            "HUMAN",
            ["destructive_without_existing_forbidding_stance"],
            "The recommendation adopts a destructive/irreversible action without an existing "
            "approval or forbidding contract in the packet.",
        )

    if SAFETY_BEHAVIOR_CHANGE.search(rec) and not RESIDUAL_CORE_SETTLED.search(rec):
        notes.append("safety_behavior_change_unverified")
        return packed("REVIEW", notes)

    if PLURAL_API_FORK.search(question) and SINGULAR_CANONICAL.search(rec):
        notes.append("api_cardinality_not_uniquely_settled")
        return packed("REVIEW", notes)

    if (
        CANONICAL_KEEP_OR_REMOVE_QUESTION.search(question)
        and KEEP_CODE_TABLE_AS_CORE.search(rec)
        and not REMOVE_FROM_CORE.search(rec)
    ):
        notes.append("canonical_code_table_keep_not_uniquely_settled")
        return packed("REVIEW", notes)

    residual_settled = bool(RESIDUAL_CORE_SETTLED.search(rec))
    if MISSING_ARTIFACT.search(blob) and not residual_settled:
        notes.append("unresolved_artifact_or_api_adjustment")
        return packed("REVIEW", notes)

    if polarity_fork_unclosed(question, rec):
        notes.append("decision_polarity_not_closed")
        return packed("REVIEW", notes)

    return packed("AUTO", ["semantic_pass_uniquely_settled"])
