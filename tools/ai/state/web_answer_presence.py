"""
KSS-1.4: Web hit 答え存在性監査（observation-only / 主に offline）。

Research 実行時の行動は変更しない。
llm_self_confidence とは別物: web_answer_presence_judge / heuristic。

ラベル: direct | core | lead | related | none | unknown
unknown を none にしない。routing には使わない。
"""

from __future__ import annotations

import os
import re
from collections import Counter

MISSING = "missing"

ANSWER_PRESENCE_LABELS = (
    "direct",
    "core",
    "lead",
    "related",
    "none",
    "unknown",
)

# ケース別の「答えに近い」手がかり（機械ヒューリスティック用・推定で埋めない）
CASE_CORE_HINTS = {
    "memory_usage": (
        "freephysicalmemory",
        "totalvisiblememory",
        "win32_operatingsystem",
        "memory usage",
        "available memory",
    ),
    "cpu_temperature": (
        "msacpi_thermalzone",
        "thermalzone",
        "temperature",
        "get-ciminstance",
        "thermal",
        "cpu temp",
    ),
    "disk_usage": (
        "get-psdrive",
        "get-volume",
        "win32_logicaldisk",
        "freespace",
        "disk usage",
        "drive",
    ),
    "gpu_usage": (
        "nvidia-smi",
        "utilization.gpu",
        "gpu utilization",
        "cuda",
    ),
    "gpu_vram_usage": (
        "nvidia-smi",
        "memory.used",
        "memory.total",
        "vram",
        "framebuffer",
    ),
}

_LEAD_RE = re.compile(
    r"Win32_\w+|MSAcpi_\w+|Get-\w+|nvidia-smi|wmic\s+\w+|CIM_\w+",
    re.I,
)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{2,}")


def kss14_answer_audit_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KSS14_OBS")
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get("AI_AGENT_KSS13_OBS") or os.environ.get(
            "AI_AGENT_KSS11_OBS"
        )
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def llm_answer_judge_enabled() -> bool:
    """オフライン LLM Judge。既定 OFF。routing には使わない。"""
    raw = os.environ.get("AI_AGENT_KSS14_ANSWER_JUDGE")
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _missing():
    return MISSING


def _hit_text(hit):
    if not isinstance(hit, dict):
        return ""
    return " ".join(
        str(x or "") for x in (hit.get("title"), hit.get("snippet"), hit.get("url"))
    ).lower()


def _compact_hit(hit, *, dropped=False, discard_reason=None):
    if not isinstance(hit, dict):
        return None
    item = {
        "title": hit.get("title"),
        "snippet": (hit.get("snippet") or "")[:400],
        "url": hit.get("url"),
        "backend": hit.get("backend"),
        "score": hit.get("score", _missing()),
        "dropped": bool(dropped),
        "discard_reason": discard_reason
        if discard_reason is not None
        else (_missing() if dropped else "kept"),
    }
    return item


def collect_hit_partition_from_web_exec(web_exec, *, max_each=12):
    """
    web_exec.results[].hits / evidence.dropped_hits から分離。
    無い場合は missing（空リストで埋めない）。
    """
    if not isinstance(web_exec, dict):
        return {
            "all_hits": _missing(),
            "kept_hits": _missing(),
            "dropped_hits": _missing(),
            "kept_count": _missing(),
            "dropped_count": _missing(),
            "all_count": _missing(),
            "source": "missing_web_exec",
        }

    kept = []
    dropped = []
    dropped_count_sum = 0
    found_dropped_field = False
    for item in web_exec.get("results") or []:
        if not isinstance(item, dict):
            continue
        for hit in item.get("hits") or []:
            c = _compact_hit(hit, dropped=False)
            if c:
                kept.append(c)
        ev = item.get("evidence") or {}
        if "dropped_hits" in ev or "dropped_count" in ev:
            found_dropped_field = True
        for hit in ev.get("dropped_hits") or []:
            reason = _infer_discard_reason(hit)
            c = _compact_hit(hit, dropped=True, discard_reason=reason)
            if c:
                dropped.append(c)
        if ev.get("dropped_count") is not None:
            dropped_count_sum += int(ev.get("dropped_count") or 0)

    # all = kept + dropped（観測用・重複 URL はそのまま）
    all_hits = kept + dropped
    return {
        "all_hits": all_hits[: max_each * 2],
        "kept_hits": kept[:max_each],
        "dropped_hits": dropped[:max_each]
        if found_dropped_field
        else _missing(),
        "kept_count": len(kept),
        "dropped_count": dropped_count_sum
        if found_dropped_field
        else (_missing() if not dropped else len(dropped)),
        "all_count": len(kept)
        + (
            dropped_count_sum
            if found_dropped_field
            else (len(dropped) if dropped else 0)
        ),
        "source": "web_exec",
        "note": (
            "dropped_hits truncated in executor to [:5] per item; "
            "not a behavior change"
        ),
    }


def collect_hit_partition_from_saved(round_item=None, researched=None):
    """
    保存済み round から。dropped が無ければ dropped_hits=missing。
    """
    researched = researched or {}
    round_item = round_item or {}
    part = researched.get("web_hit_partition") or round_item.get("web_hit_partition")
    if isinstance(part, dict) and part.get("kept_hits") is not None:
        return part

    kept_raw = researched.get("web_hits") or round_item.get("web_hits") or []
    kept = [_compact_hit(h, dropped=False) for h in kept_raw]
    kept = [h for h in kept if h]
    return {
        "all_hits": _missing(),
        "kept_hits": kept,
        "dropped_hits": _missing(),
        "kept_count": len(kept),
        "dropped_count": _missing(),
        "all_count": _missing(),
        "source": "saved_web_hits_only",
        "note": "historical runs omit dropped_hits; do not invent",
    }


def _infer_discard_reason(hit):
    """既存 filter 規則に沿った観測用理由（再判定）。行動変更なし。"""
    try:
        from tools.system.tool_builder.research.web import (
            IRRELEVANT_HIT_TOKENS,
            hit_is_relevant,
            hit_score,
        )
    except Exception:
        return _missing()
    text = _hit_text(hit)
    if not text.strip():
        return "empty_text"
    for tok in IRRELEVANT_HIT_TOKENS:
        if tok in text:
            return f"irrelevant_token:{tok}"
    if hit_score(hit) <= 0 and not hit_is_relevant(hit):
        return "not_relevant_low_score"
    if not hit_is_relevant(hit):
        return "hit_is_relevant_false"
    return "dropped_by_filter_or_limit"


def heuristic_answer_presence(hit, *, request_text="", case_id=None):
    """
    機械ヒューリスティック。LLM 自己申告ではない。
    ページ全文が無い場合は snippet のみ → しばしば unknown/related。
    """
    if not isinstance(hit, dict):
        return {
            "answer_presence": "unknown",
            "method": "web_answer_presence_heuristic",
            "reasons": ["invalid_hit"],
            "not_for_decision": True,
        }
    text = _hit_text(hit)
    title = str(hit.get("title") or "")
    snippet = str(hit.get("snippet") or "")
    if not text.strip():
        return {
            "answer_presence": "unknown",
            "method": "web_answer_presence_heuristic",
            "reasons": ["empty_text"],
            "not_for_decision": True,
        }
    if len(snippet.strip()) < 20 and not title.strip():
        return {
            "answer_presence": "unknown",
            "method": "web_answer_presence_heuristic",
            "reasons": ["insufficient_snippet"],
            "not_for_decision": True,
        }

    reasons = []
    core_hints = CASE_CORE_HINTS.get(str(case_id or ""), ())
    core_hits = [h for h in core_hints if h in text]
    lead_ids = _LEAD_RE.findall(text)

    req = str(request_text or "").lower()
    req_tokens = {t.lower() for t in _TOKEN_RE.findall(req) if len(t) >= 4}
    hit_tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    overlap = req_tokens & hit_tokens if req_tokens else set()

    # none: clearly off-topic irrelevant
    try:
        from tools.system.tool_builder.research.web import IRRELEVANT_HIT_TOKENS

        if any(tok in text for tok in IRRELEVANT_HIT_TOKENS) and not core_hits:
            return {
                "answer_presence": "none",
                "method": "web_answer_presence_heuristic",
                "reasons": ["irrelevant_token"],
                "not_for_decision": True,
            }
    except Exception:
        pass

    # direct: multiple core hints + measurement verbs
    measureish = any(
        x in text
        for x in (
            "select-object",
            "get-",
            "property",
            "percent",
            "usage",
            "temperature",
            "freespace",
            "memory.used",
        )
    )
    if len(core_hits) >= 2 and measureish:
        reasons.extend([f"core_hint:{h}" for h in core_hits[:3]])
        reasons.append("measure_context")
        return {
            "answer_presence": "direct",
            "method": "web_answer_presence_heuristic",
            "reasons": reasons,
            "not_for_decision": True,
        }

    if core_hits:
        reasons.extend([f"core_hint:{h}" for h in core_hits[:3]])
        return {
            "answer_presence": "core",
            "method": "web_answer_presence_heuristic",
            "reasons": reasons,
            "not_for_decision": True,
        }

    if lead_ids:
        reasons.append(f"lead_identifiers:{lead_ids[:4]}")
        return {
            "answer_presence": "lead",
            "method": "web_answer_presence_heuristic",
            "reasons": reasons,
            "not_for_decision": True,
            "exploratory_useful_candidate": True,
        }

    if len(overlap) >= 3:
        reasons.append(f"request_token_overlap:{sorted(overlap)[:6]}")
        return {
            "answer_presence": "related",
            "method": "web_answer_presence_heuristic",
            "reasons": reasons,
            "not_for_decision": True,
        }

    if overlap:
        reasons.append(f"weak_overlap:{sorted(overlap)[:4]}")
        return {
            "answer_presence": "related",
            "method": "web_answer_presence_heuristic",
            "reasons": reasons,
            "not_for_decision": True,
        }

    # 日本語リクエストで英語ドキュメントのみ等 → unknown 寄り
    if req and not overlap and not core_hits:
        return {
            "answer_presence": "unknown",
            "method": "web_answer_presence_heuristic",
            "reasons": ["no_token_overlap_with_request"],
            "not_for_decision": True,
        }

    return {
        "answer_presence": "none",
        "method": "web_answer_presence_heuristic",
        "reasons": ["no_core_lead_or_overlap"],
        "not_for_decision": True,
    }


def annotate_hits_answer_presence(hits, *, request_text="", case_id=None, dropped=False):
    if hits == MISSING or hits is None:
        return _missing()
    out = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        item = dict(hit)
        item["dropped"] = bool(dropped or hit.get("dropped"))
        judged = heuristic_answer_presence(
            item, request_text=request_text, case_id=case_id
        )
        item["answer_presence"] = judged["answer_presence"]
        item["answer_presence_method"] = judged["method"]
        item["answer_presence_reasons"] = judged.get("reasons") or []
        item["exploratory_useful_candidate"] = bool(
            judged.get("exploratory_useful_candidate")
            or judged["answer_presence"] == "lead"
        )
        # LLM judge slot（未実行時 missing）
        item["web_answer_presence_judge"] = _missing()
        out.append(item)
    return out


def summarize_answer_presence(kept_annotated, dropped_annotated):
    def _count(items, label):
        if items == MISSING or items is None:
            return _missing()
        return sum(1 for h in items if h.get("answer_presence") == label)

    def _any_valuable(items):
        if items == MISSING or items is None:
            return _missing()
        return any(
            h.get("answer_presence") in ("direct", "core", "lead") for h in items
        )

    kept_ok = kept_annotated not in (None, MISSING)
    drop_ok = dropped_annotated not in (None, MISSING)

    valuable = ("direct", "core", "lead")
    answer_in_kept = (
        any(h.get("answer_presence") in valuable for h in (kept_annotated or []))
        if kept_ok
        else _missing()
    )
    answer_in_dropped = (
        any(h.get("answer_presence") in valuable for h in (dropped_annotated or []))
        if drop_ok
        else _missing()
    )
    if answer_in_kept is True or answer_in_dropped is True:
        answer_in_any = True
    elif kept_ok and drop_ok:
        answer_in_any = False
    elif kept_ok and answer_in_kept is False and not drop_ok:
        # dropped 未観測 → 全体の「答え無し」は断定できない
        answer_in_any = _missing()
    else:
        answer_in_any = _missing()

    unknown_n = 0
    unknown_known = False
    for bucket in (kept_annotated, dropped_annotated):
        if bucket in (None, MISSING):
            continue
        unknown_known = True
        unknown_n += sum(1 for h in bucket if h.get("answer_presence") == "unknown")

    discard_x_presence = Counter()
    if drop_ok:
        for h in dropped_annotated or []:
            key = (
                str(h.get("discard_reason") or MISSING),
                str(h.get("answer_presence") or MISSING),
            )
            discard_x_presence[key] += 1

    return {
        "total_web_hits": (
            (len(kept_annotated or []) if kept_ok else 0)
            + (len(dropped_annotated or []) if drop_ok else 0)
        )
        if kept_ok or drop_ok
        else _missing(),
        "kept_hits": len(kept_annotated or []) if kept_ok else _missing(),
        "dropped_hits": len(dropped_annotated or []) if drop_ok else _missing(),
        "direct_in_kept": _count(kept_annotated, "direct"),
        "core_in_kept": _count(kept_annotated, "core"),
        "lead_in_kept": _count(kept_annotated, "lead"),
        "related_in_kept": _count(kept_annotated, "related"),
        "none_in_kept": _count(kept_annotated, "none"),
        "unknown_in_kept": _count(kept_annotated, "unknown"),
        "direct_in_dropped": _count(dropped_annotated, "direct"),
        "core_in_dropped": _count(dropped_annotated, "core"),
        "lead_in_dropped": _count(dropped_annotated, "lead"),
        "related_in_dropped": _count(dropped_annotated, "related"),
        "none_in_dropped": _count(dropped_annotated, "none"),
        "unknown_in_dropped": _count(dropped_annotated, "unknown"),
        "unknown_count": unknown_n if unknown_known else _missing(),
        "answer_in_any_hit": answer_in_any
        if answer_in_kept is not MISSING or answer_in_dropped is not MISSING
        else _missing(),
        "answer_in_kept_hit": answer_in_kept,
        "answer_in_dropped_hit": answer_in_dropped,
        "answer_presence_unknown": (
            unknown_n > 0 if unknown_known else _missing()
        ),
        "valuable_dropped_not_kept": (
            answer_in_dropped is True and answer_in_kept is False
        )
        if drop_ok and kept_ok
        else _missing(),
        "discard_reason_x_answer_presence": {
            f"{a}|{b}": n for (a, b), n in discard_x_presence.items()
        },
        "method": "web_answer_presence_heuristic",
        "llm_judge_used": False,
        "not_llm_self_confidence": True,
        "not_for_decision": True,
    }


def audit_round_answer_presence(
    *,
    request_text="",
    case_id=None,
    web_hit_partition=None,
    round_item=None,
    researched=None,
):
    part = web_hit_partition or collect_hit_partition_from_saved(
        round_item, researched
    )
    kept = part.get("kept_hits")
    dropped = part.get("dropped_hits")
    kept_ann = annotate_hits_answer_presence(
        kept if kept != MISSING else [],
        request_text=request_text,
        case_id=case_id,
        dropped=False,
    )
    if kept == MISSING:
        kept_ann = _missing()
    if dropped == MISSING or dropped is None:
        dropped_ann = _missing()
    else:
        dropped_ann = annotate_hits_answer_presence(
            dropped,
            request_text=request_text,
            case_id=case_id,
            dropped=True,
        )

    summary = summarize_answer_presence(kept_ann, dropped_ann)
    lead_in_round = False
    for bucket in (kept_ann, dropped_ann):
        if bucket in (None, MISSING):
            continue
        if any(h.get("answer_presence") == "lead" for h in bucket):
            lead_in_round = True
            break

    return {
        "enabled": True,
        "phase": "kss-1.4",
        "not_for_decision": True,
        "behavior_changed": False,
        "judge_family": "web_answer_presence",
        "not_llm_self_confidence": True,
        "partition_source": part.get("source"),
        "partition_note": part.get("note"),
        "kept_answer_presence": kept_ann,
        "dropped_answer_presence": dropped_ann,
        "aggregates": summary,
        "lead_present": lead_in_round
        if kept_ann != MISSING or dropped_ann != MISSING
        else _missing(),
        "exploratory_useful_round_candidate": lead_in_round,
        "routing_hint": _missing(),
        "human_audit_samples": build_human_audit_samples(
            kept_ann, dropped_ann, case_id=case_id, limit=4
        ),
    }


def build_human_audit_samples(kept_ann, dropped_ann, *, case_id=None, limit=4):
    """人間が判定可能な抜粋（LLM Judge を信頼する前の対照用）。"""
    samples = []
    for label, bucket, dropped_flag in (
        ("kept", kept_ann, False),
        ("dropped", dropped_ann, True),
    ):
        if bucket in (None, MISSING):
            samples.append(
                {
                    "bucket": label,
                    "status": "missing",
                    "note": "no hits available for human audit",
                }
            )
            continue
        for hit in (bucket or [])[:limit]:
            samples.append(
                {
                    "case_id": case_id,
                    "bucket": label,
                    "dropped": dropped_flag,
                    "title": hit.get("title"),
                    "snippet": (hit.get("snippet") or "")[:240],
                    "url": hit.get("url"),
                    "discard_reason": hit.get("discard_reason"),
                    "heuristic_answer_presence": hit.get("answer_presence"),
                    "human_answer_presence": _missing(),  # 人手記入欄
                    "llm_judge_answer_presence": hit.get(
                        "web_answer_presence_judge", _missing()
                    ),
                }
            )
    return samples
