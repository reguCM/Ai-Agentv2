"""Web Evidence → Live LLM Context Format Shootout.

Same fixed Evidence, four packaging formats, real LLM (qwen3:8b when available).
Does NOT modify Production, Agent, Registry, or SYSTEM_PROMPT.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.experimental.evidence_context.packager import (
    EvidenceBundle,
    build_context,
    build_hybrid_context,
    build_production_raw_context,
    fact_coverage_in_context,
)
from ai_tool.web_evidence_llm_context_investigation import investigation_cases
from ai_tool.web_tool_extraction_normalization_production import run_production_golden
from ai_tool.web_tool_success_class_accuracy_evaluation import (
    AnswerClass,
    classify_answer,
)

RepoRoot = Path(__file__).resolve().parents[1]

ShootoutFormat = Literal["A_RAW", "B_PASSAGE", "C_GROUPED", "D_HYBRID"]
FormatClassification = Literal["C0", "C1", "C2", "C3", "C4"]
ShootoutDecision = Literal[
    "STOP_NO_CHANGE",
    "RECORD",
    "INVESTIGATE",
    "EXPERIMENTAL_CAPABILITY",
    "HUMAN_REVIEW_REQUIRED",
]

SHOOTOUT_FORMATS: list[ShootoutFormat] = ["A_RAW", "B_PASSAGE", "C_GROUPED", "D_HYBRID"]

SIGNIFICANT_ACCURACY_GAP = 0.05  # 5pp — below this = no practical difference

UNCERTAINTY_RE = re.compile(
    r"未確認|不明|わから|確認でき(?:ない|ません)|特定でき(?:ない|ません)|"
    r"cannot confirm|unknown|unclear|not (?:able to )?confirm",
    re.I,
)

ChatFn = Callable[..., Any]


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def shootout_system_prompt() -> str:
    """Eval-only minimal prompt — NOT Production SYSTEM_PROMPT."""
    return """
あなたはWeb Evidenceに基づいてユーザーの質問に答えるアシスタントです。評価実行中です。

ルール:
- 提示されたEvidence（main_text / passages / sources）に書かれた事実のみを根拠に答える。
- Evidenceにない具体的数値・固有名詞を捏造しない。
- 複数ソースで年度や定義が異なる場合は、混同せず区別して述べる。
- Evidenceが不足している場合は「未確認」と述べる。
- HTML構造の説明は不要。簡潔に答える。
""".strip()


def build_shootout_context(fmt: ShootoutFormat, bundle: EvidenceBundle) -> str:
    if fmt == "A_RAW":
        return build_production_raw_context(bundle)
    if fmt == "B_PASSAGE":
        return build_context("A2_PASSAGE", bundle)
    if fmt == "C_GROUPED":
        return build_context("A3_SOURCE_GROUPED", bundle)
    if fmt == "D_HYBRID":
        return build_hybrid_context(bundle, include_verification=False)
    raise ValueError(f"unknown shootout format: {fmt}")


def normalize_response(text: str | None) -> str:
    if not text:
        return ""
    s = str(text).strip()
    for tag in ("think", "redacted_reasoning"):
        s = re.sub(rf"<{tag}>.*?</{tag}>", "", s, flags=re.DOTALL | re.I).strip()
    return re.sub(r"\s+", " ", s).strip()


def _verbosity_ratio(answer: str, evidence: str) -> float:
    if not evidence:
        return 0.0
    return round(len(answer) / max(len(evidence), 1), 3)


def analyze_conflict_answer(answer: str) -> dict[str, Any]:
    """Deterministic conflict observation for IC-F01-style cases."""
    a = answer or ""
    mentions_2024 = bool(re.search(r"2024|275\s*万|2[,，]?750[,，]?000", a))
    mentions_2020 = bool(re.search(r"2020|2752[,，]?412|国勢調査", a))
    both_numbers = bool(re.search(r"275[,，]?000|275\s*万", a)) and bool(re.search(r"2752", a))
    suspected_merge = bool(re.search(r"999|1900\s*万|単一の人口は", a)) and not (mentions_2024 and mentions_2020)
    unsupported_extra = bool(re.search(r"[0-9]{7,}", a)) and not both_numbers
    return {
        "distinguishes_years": mentions_2024 and mentions_2020,
        "mentions_2024": mentions_2024,
        "mentions_2020": mentions_2020,
        "both_numeric_values_present": both_numbers,
        "suspected_merge": suspected_merge,
        "unsupported_extra_numeric": unsupported_extra,
    }


@dataclass
class ShootoutArmResult:
    case_id: str
    category: str
    format: ShootoutFormat
    context_size: int
    raw_evidence_size: int
    fact_coverage_in_context: str
    raw_response: str
    normalized_response: str
    answer_class: AnswerClass | Literal["SKIPPED", "UNKNOWN"]
    expected_correct: bool | None
    fact_met: dict[str, bool] = field(default_factory=dict)
    unsupported_claims: int = 0
    contradiction: bool = False
    numeric_error: bool = False
    entity_error: bool = False
    temporal_error: bool = False
    scope_error: bool = False
    evidence_mismatch: bool = False
    refusal_or_uncertainty: bool = False
    verbosity_ratio: float = 0.0
    latency_ms: float | None = None
    llm_skipped: bool = False
    conflict_analysis: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _failure_flags(answer_class: AnswerClass | str) -> dict[str, bool]:
    return {
        "contradiction": answer_class == "Contradiction",
        "numeric_error": answer_class == "Numeric Error",
        "entity_error": answer_class == "Entity Error",
        "temporal_error": answer_class == "Temporal Error",
        "scope_error": answer_class == "Scope Error",
        "evidence_mismatch": answer_class in ("Source Misuse", "Unsupported Addition"),
    }


def call_live_llm(
    *,
    context: str,
    user_request: str,
    chat_fn: ChatFn,
    model: str,
) -> tuple[str, float]:
    messages = [
        {"role": "system", "content": shootout_system_prompt()},
        {"role": "user", "content": f"{context}\n\n上記Evidenceのみに基づき、次の質問に答えてください:\n{user_request}"},
    ]
    started = time.perf_counter()
    response = chat_fn(messages=messages, model=model)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    raw = getattr(getattr(response, "message", None), "content", None) or ""
    return raw, latency_ms


def evaluate_shootout_arm(
    bundle: EvidenceBundle,
    fmt: ShootoutFormat,
    *,
    chat_fn: ChatFn | None,
    model: str,
    llm_enabled: bool,
) -> ShootoutArmResult:
    ctx = build_shootout_context(fmt, bundle)
    cov_met, cov_total = fact_coverage_in_context(ctx, bundle.expected_facts)
    raw_evidence = bundle.raw_combined

    if not llm_enabled or chat_fn is None:
        return ShootoutArmResult(
            case_id=bundle.case_id,
            category=bundle.category,
            format=fmt,
            context_size=len(ctx),
            raw_evidence_size=len(raw_evidence),
            fact_coverage_in_context=f"{cov_met}/{cov_total}",
            raw_response="",
            normalized_response="",
            answer_class="SKIPPED",
            expected_correct=None,
            llm_skipped=True,
        )

    raw_response, latency_ms = call_live_llm(
        context=ctx,
        user_request=bundle.user_request,
        chat_fn=chat_fn,
        model=model,
    )
    normalized = normalize_response(raw_response)

    if not normalized:
        return ShootoutArmResult(
            case_id=bundle.case_id,
            category=bundle.category,
            format=fmt,
            context_size=len(ctx),
            raw_evidence_size=len(raw_evidence),
            fact_coverage_in_context=f"{cov_met}/{cov_total}",
            raw_response=raw_response[:2000],
            normalized_response="",
            answer_class="UNKNOWN",
            expected_correct=None,
            latency_ms=latency_ms,
        )

    ans_class, claims, fact_met, _ = classify_answer(normalized, raw_evidence, bundle.expected_facts)
    unsupported = sum(1 for c in claims if c.support == "unsupported")
    flags = _failure_flags(ans_class)

    conflict = analyze_conflict_answer(normalized) if bundle.category == "conflict" else None

    return ShootoutArmResult(
        case_id=bundle.case_id,
        category=bundle.category,
        format=fmt,
        context_size=len(ctx),
        raw_evidence_size=len(raw_evidence),
        fact_coverage_in_context=f"{cov_met}/{cov_total}",
        raw_response=raw_response[:2000],
        normalized_response=normalized[:2000],
        answer_class=ans_class,
        expected_correct=ans_class == "Correct",
        fact_met=fact_met,
        unsupported_claims=unsupported,
        **flags,
        refusal_or_uncertainty=bool(UNCERTAINTY_RE.search(normalized)),
        verbosity_ratio=_verbosity_ratio(normalized, raw_evidence),
        latency_ms=latency_ms,
        conflict_analysis=conflict,
    )


def aggregate_by_format(rows: list[ShootoutArmResult]) -> dict[str, Any]:
    agg: dict[str, dict[str, Any]] = {}
    for fmt in SHOOTOUT_FORMATS:
        sub = [r for r in rows if r.format == fmt and not r.llm_skipped]
        if not sub:
            agg[fmt] = {"cases": 0, "skipped": True}
            continue
        correct = sum(1 for r in sub if r.expected_correct)
        n = len(sub)
        agg[fmt] = {
            "cases": n,
            "expected_correct_count": correct,
            "accuracy": round(correct / n, 3),
            "avg_context_size": int(sum(r.context_size for r in sub) / n),
            "avg_latency_ms": round(sum(r.latency_ms or 0 for r in sub) / n, 1),
            "avg_verbosity_ratio": round(sum(r.verbosity_ratio for r in sub) / n, 3),
            "unsupported_rate": round(sum(r.unsupported_claims for r in sub) / n, 3),
            "numeric_error_rate": round(sum(1 for r in sub if r.numeric_error) / n, 3),
            "contradiction_rate": round(sum(1 for r in sub if r.contradiction) / n, 3),
            "refusal_rate": round(sum(1 for r in sub if r.refusal_or_uncertainty) / n, 3),
            "skipped": False,
        }
    return agg


def aggregate_by_category(rows: list[ShootoutArmResult]) -> dict[str, Any]:
    cats = sorted({r.category for r in rows})
    out: dict[str, Any] = {}
    for cat in cats:
        out[cat] = {}
        for fmt in SHOOTOUT_FORMATS:
            sub = [r for r in rows if r.category == cat and r.format == fmt and not r.llm_skipped]
            if not sub:
                continue
            correct = sum(1 for r in sub if r.expected_correct)
            out[cat][fmt] = {
                "accuracy": round(correct / len(sub), 3),
                "cases": len(sub),
            }
    return out


def format_cost_benefit(agg: dict[str, Any]) -> list[dict[str, Any]]:
    raw = agg.get("A_RAW") or {}
    raw_acc = raw.get("accuracy") or 0
    rows: list[dict[str, Any]] = []
    impl_cost = {"A_RAW": "NONE", "B_PASSAGE": "LOW", "C_GROUPED": "LOW", "D_HYBRID": "MEDIUM"}
    for fmt in SHOOTOUT_FORMATS:
        a = agg.get(fmt) or {}
        if a.get("skipped"):
            continue
        acc = a.get("accuracy") or 0
        ctx = a.get("avg_context_size") or 0
        raw_ctx = raw.get("avg_context_size") or ctx or 1
        rows.append(
            {
                "format": fmt,
                "accuracy_benefit": round(acc - raw_acc, 3),
                "grounding_benefit": "NONE" if acc <= raw_acc else "MARGINAL",
                "context_size": ctx,
                "context_size_vs_raw": round(ctx / max(raw_ctx, 1), 3),
                "latency_ms": a.get("avg_latency_ms"),
                "implementation_cost": impl_cost.get(fmt, "UNKNOWN"),
                "maintenance_cost": impl_cost.get(fmt, "UNKNOWN"),
                "reuse_value": "HIGH" if fmt in ("B_PASSAGE", "C_GROUPED") else "MEDIUM",
                "defensive_value": "LOW" if acc <= raw_acc else "MEDIUM",
                "production_risk": "NONE",
            }
        )
    return rows


def classify_shootout_formats(agg: dict[str, Any], *, category_agg: dict[str, Any]) -> dict[str, FormatClassification]:
    raw_acc = (agg.get("A_RAW") or {}).get("accuracy") or 0
    classifications: dict[str, FormatClassification] = {}

    for fmt in SHOOTOUT_FORMATS:
        a = agg.get(fmt) or {}
        if a.get("skipped"):
            classifications[fmt] = "C0"
            continue
        acc = a.get("accuracy") or 0
        gap = acc - raw_acc

        # Consistent category wins (>=2 categories, >=10pp over raw)
        cat_wins = 0
        for _cat, fmts in category_agg.items():
            if fmt not in fmts or "A_RAW" not in fmts:
                continue
            if (fmts[fmt].get("accuracy") or 0) - (fmts["A_RAW"].get("accuracy") or 0) >= 0.1:
                cat_wins += 1

        if gap >= SIGNIFICANT_ACCURACY_GAP and cat_wins >= 2:
            classifications[fmt] = "C2"
        elif gap >= SIGNIFICANT_ACCURACY_GAP:
            classifications[fmt] = "C1"
        elif gap <= -SIGNIFICANT_ACCURACY_GAP:
            classifications[fmt] = "C0"
        else:
            classifications[fmt] = "C0"

    return classifications


def discover_core_candidates(
    agg: dict[str, Any],
    format_classifications: dict[str, FormatClassification],
    conflict_rows: list[ShootoutArmResult],
) -> list[dict[str, Any]]:
    cands: list[dict[str, Any]] = []
    best_fmt = max(
        ((f, (agg.get(f) or {}).get("accuracy") or 0) for f in SHOOTOUT_FORMATS),
        key=lambda x: x[1],
        default=("A_RAW", 0),
    )[0]
    raw_acc = (agg.get("A_RAW") or {}).get("accuracy") or 0
    best_acc = (agg.get(best_fmt) or {}).get("accuracy") or 0

    cands.append(
        {
            "id": "CTX-PASSAGE",
            "classification": format_classifications.get("B_PASSAGE", "C0"),
            "note": "Live LLM shootout — see format_classifications",
        }
    )
    cands.append(
        {
            "id": "CTX-CONFLICT",
            "classification": "C2"
            if any((r.conflict_analysis or {}).get("suspected_merge") for r in conflict_rows)
            else "C1",
            "note": "Conflict case — packaging alone may not resolve year/definition distinction",
        }
    )
    cands.append(
        {
            "id": "CTX-BUILDER",
            "classification": "C0" if best_acc <= raw_acc + SIGNIFICANT_ACCURACY_GAP else "C1",
            "note": "No standalone builder unless C2 validated across categories",
        }
    )

    meaningful = best_acc - raw_acc >= SIGNIFICANT_ACCURACY_GAP
    cands.append(
        {
            "id": "SHOOTOUT-VERDICT",
            "classification": "C2" if meaningful else "C0",
            "best_format": best_fmt,
            "accuracy_gap_vs_raw": round(best_acc - raw_acc, 3),
        }
    )
    return cands


def determine_decision(
    agg: dict[str, Any],
    format_classifications: dict[str, FormatClassification],
    *,
    llm_enabled: bool,
    golden_pass: bool,
) -> ShootoutDecision:
    if not llm_enabled:
        return "RECORD"

    raw_acc = (agg.get("A_RAW") or {}).get("accuracy") or 0
    accs = [(agg.get(f) or {}).get("accuracy") or 0 for f in SHOOTOUT_FORMATS if not (agg.get(f) or {}).get("skipped")]
    if not accs:
        return "RECORD"

    best = max(accs)
    spread = best - min(accs)
    raw_is_best_tier = raw_acc >= best - 0.01

    if spread < SIGNIFICANT_ACCURACY_GAP and raw_is_best_tier:
        return "STOP_NO_CHANGE" if golden_pass else "RECORD"

    c2_count = sum(1 for c in format_classifications.values() if c == "C2")
    if c2_count >= 1:
        return "INVESTIGATE"

    return "RECORD"


def run_web_evidence_live_llm_context_shootout(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
    fetch_live_baseline: bool = False,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    head = _git_head()
    golden = run_production_golden(fetch_live=fetch_live_baseline)
    golden_pass = golden.get("overall") == "PASS"

    cases = investigation_cases()
    if case_ids:
        allowed = set(case_ids)
        cases = [c for c in cases if c.case_id in allowed]

    rows: list[ShootoutArmResult] = []
    for case in cases:
        for fmt in SHOOTOUT_FORMATS:
            rows.append(
                evaluate_shootout_arm(
                    case,
                    fmt,
                    chat_fn=chat_fn,
                    model=model,
                    llm_enabled=llm_enabled,
                )
            )

    agg = aggregate_by_format(rows)
    cat_agg = aggregate_by_category(rows)
    cost_benefit = format_cost_benefit(agg)
    fmt_class = classify_shootout_formats(agg, category_agg=cat_agg)

    conflict_rows = [r for r in rows if r.category == "conflict" and not r.llm_skipped]
    core_cands = discover_core_candidates(agg, fmt_class, conflict_rows)

    decision = determine_decision(agg, fmt_class, llm_enabled=llm_enabled, golden_pass=golden_pass)

    rejected: list[dict[str, str]] = []
    raw_acc = (agg.get("A_RAW") or {}).get("accuracy") or 0
    for fmt in SHOOTOUT_FORMATS:
        a = agg.get(fmt) or {}
        if a.get("skipped"):
            continue
        acc = a.get("accuracy") or 0
        if fmt != "A_RAW" and acc <= raw_acc:
            rejected.append({"format": fmt, "reason": "No accuracy gain vs A_RAW"})
        if fmt == "D_HYBRID" and (a.get("avg_context_size") or 0) > (agg.get("A_RAW") or {}).get("avg_context_size", 0) * 2:
            rejected.append({"format": fmt, "reason": "Large context without proportional benefit"})

    spread = 0.0
    accs = [(agg.get(f) or {}).get("accuracy") or 0 for f in SHOOTOUT_FORMATS if not (agg.get(f) or {}).get("skipped")]
    if accs:
        spread = round(max(accs) - min(accs), 3)

    context_effect_confirmed = spread >= SIGNIFICANT_ACCURACY_GAP

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": head,
        "final_head": head,
        "overall": "PASS" if golden_pass else "PARTIAL",
        "production_changes": [],
        "llm_enabled": llm_enabled,
        "model": model or "none",
        "phase_start_baseline": {
            "head": head,
            "golden": golden,
            "golden_pass": golden_pass,
            "prior_proxy_phase": "WEB_EVIDENCE_LLM_CONTEXT_INVESTIGATION — A1/A2/A3/A6 tied at 54.5% proxy",
        },
        "shootout_formats": SHOOTOUT_FORMATS,
        "cases_run": len(cases),
        "arms_total": len(rows),
        "results": [r.to_dict() for r in rows],
        "aggregate_by_format": agg,
        "aggregate_by_category": cat_agg,
        "cost_benefit": cost_benefit,
        "format_classifications": fmt_class,
        "context_format_effect_confirmed": context_effect_confirmed,
        "accuracy_spread": spread,
        "conflict_observations": [r.to_dict() for r in conflict_rows],
        "core_capability_discovery": core_cands,
        "rejected_alternatives": rejected,
        "decision_log": {
            "question": "Context formatによる実LLM品質差はあるか",
            "evidence": {"aggregate_by_format": agg, "aggregate_by_category": cat_agg},
            "decision": decision,
            "production": "変更なし",
            "core": core_cands,
            "rejected_alternatives": rejected,
        },
        "human_review_required": False,
        "next_phase_candidates": [
            "C2 conflict-aware context prototype if conflict failures persist on live LLM",
            "Search improvement remains E2E priority per prior benchmark",
        ]
        if decision != "STOP_NO_CHANGE"
        else [],
        "deterministic_scope": "classify_answer + ExpectedFact — no LLM Judge",
        "remaining_unknowns": [] if llm_enabled else ["Live LLM arms skipped — ollama unavailable"],
    }


def make_mock_shootout_chat_fn() -> ChatFn:
    """Deterministic mock for unit tests (not LLM Judge)."""

    def _chat(**kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        blob = " ".join(str(m.get("content") or "") for m in messages if isinstance(m, dict))

        answer = "未確認です。"
        if re.search(r"275|2[,，]?750", blob) and "面積" in blob and "225" in blob:
            answer = "人口は約275万人、面積は225.21平方キロメートルです。"
        elif re.search(r"275|2[,，]?750", blob):
            answer = "大阪市の人口は約275万人（2,750,000人）です。"
        elif "東京" in blob and ("首都" in blob or "capital" in blob.lower()):
            answer = "日本の首都は東京（東京都）です。"
        elif "377" in blob and "面積" in blob:
            answer = "日本の国土面積は約377,975平方キロメートルです。"
        elif "2020" in blob and "272" in blob:
            answer = "2020年国勢調査による大阪市の人口は2,752,412人でした。"
        elif "横浜" in blob and ("最多" in blob or "comparison" in blob.lower()):
            answer = "日本で人口が最多の政令指定都市は横浜市です。"
        elif "375" in blob or "3,774" in blob:
            answer = "横浜市の人口は約377万4,256人です。"
        elif "2.75 million" in blob.lower() or "million" in blob.lower():
            answer = "Osaka has a population of approximately 2.75 million people."
        elif "1,234,567" in blob or "1234567" in blob:
            answer = "Registered population is 1,234,567."
        elif "2024" in blob and "2020" in blob and "275" in blob:
            answer = "2024年推計では約275万人、2020年国勢調査では2,752,412人です。"

        class _Msg:
            content = answer

        class _Resp:
            message = _Msg()

        return _Resp()

    return _chat
