"""
KSS-1.5: Live web hit partition（kept/dropped 実測）+ 人手監査データセット。

observation-only。filter / candidate / verifier / judge の挙動は変更しない。
過去データから dropped を再構築しない。
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from tools.ai.state.web_answer_presence import (
    ANSWER_PRESENCE_LABELS,
    MISSING,
    annotate_hits_answer_presence,
    heuristic_answer_presence,
)


def kss15_obs_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KSS15_OBS")
    if raw is None or str(raw).strip() == "":
        raw = os.environ.get("AI_AGENT_KSS14_OBS")
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _missing():
    return MISSING


def _host(url):
    try:
        return (urlparse(str(url or "")).hostname or "").lower() or _missing()
    except Exception:
        return _missing()


def _hit_id(hit, *, search_id, rank):
    raw = f"{search_id}|{rank}|{hit.get('url') or ''}|{hit.get('title') or ''}"
    return "hit_" + hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _infer_drop_reason(hit, *, subject=None, keywords=None):
    try:
        from tools.system.tool_builder.research.web import (
            IRRELEVANT_HIT_TOKENS,
            hit_is_relevant,
            hit_score,
        )
    except Exception:
        return _missing()
    text = " ".join(
        str(x or "") for x in (hit.get("title"), hit.get("snippet"), hit.get("url"))
    ).lower()
    if not text.strip():
        return "empty_text"
    for tok in IRRELEVANT_HIT_TOKENS:
        if tok in text:
            return f"irrelevant_token:{tok}"
    if not hit_is_relevant(hit, keywords=keywords, subject=subject):
        if hit_score(hit) <= 0:
            return "not_relevant_low_score"
        return "hit_is_relevant_false"
    return "not_relevant"


def build_search_partition(
    *,
    ranked_hits,
    kept_hits,
    dropped_irrelevant,
    query,
    keywords=None,
    subject=None,
    search_id=None,
    round_id=None,
    item_id=None,
    max_store=40,
):
    """
    同一検索結果集合内で kept/dropped を区別して記録。
    filter 結果は変更しない（呼び出し側が渡したリストを写す）。
    """
    search_id = search_id or f"search_{uuid.uuid4().hex[:10]}"
    kept_urls = {
        str(h.get("url") or "") for h in (kept_hits or []) if isinstance(h, dict)
    }
    kept_list = list(kept_hits or [])
    # limit で落ちた「関連だが truncate」
    truncated = []
    try:
        from tools.system.tool_builder.research.web import hit_is_relevant

        for h in ranked_hits or []:
            if not isinstance(h, dict):
                continue
            url = str(h.get("url") or "")
            if url in kept_urls:
                continue
            if hit_is_relevant(h, keywords=keywords, subject=subject):
                truncated.append(h)
    except Exception:
        truncated = []

    records = []
    # kept first with ranks from ranked order if possible
    rank_by_url = {}
    for i, h in enumerate(ranked_hits or [], start=1):
        if isinstance(h, dict) and h.get("url"):
            rank_by_url[str(h.get("url"))] = i

    def _score(hit):
        if isinstance(hit, dict) and hit.get("score") is not None:
            return hit.get("score")
        try:
            from tools.system.tool_builder.research.web import hit_score

            return hit_score(hit)
        except Exception:
            return _missing()

    for hit in kept_list:
        if not isinstance(hit, dict):
            continue
        url = str(hit.get("url") or "")
        rank = rank_by_url.get(url, _missing())
        hid = _hit_id(hit, search_id=search_id, rank=rank if rank != MISSING else 0)
        records.append(
            {
                "search_id": search_id,
                "round_id": round_id if round_id is not None else _missing(),
                "item_id": item_id if item_id is not None else _missing(),
                "query": query if query is not None else _missing(),
                "hit_id": hid,
                "url": hit.get("url"),
                "title": hit.get("title"),
                "snippet": (hit.get("snippet") or "")[:500],
                "source": hit.get("backend") or _missing(),
                "domain": _host(hit.get("url")),
                "kept": True,
                "drop_reason": "kept",
                "position_rank": rank,
                "existing_hit_score": _score(hit),
                "candidate_link": _missing(),  # filled later
            }
        )

    for hit in dropped_irrelevant or []:
        if not isinstance(hit, dict):
            continue
        url = str(hit.get("url") or "")
        if url in kept_urls:
            continue
        rank = rank_by_url.get(url, _missing())
        hid = _hit_id(hit, search_id=search_id, rank=rank if rank != MISSING else 0)
        records.append(
            {
                "search_id": search_id,
                "round_id": round_id if round_id is not None else _missing(),
                "item_id": item_id if item_id is not None else _missing(),
                "query": query if query is not None else _missing(),
                "hit_id": hid,
                "url": hit.get("url"),
                "title": hit.get("title"),
                "snippet": (hit.get("snippet") or "")[:500],
                "source": hit.get("backend") or _missing(),
                "domain": _host(hit.get("url")),
                "kept": False,
                "drop_reason": _infer_drop_reason(
                    hit, subject=subject, keywords=keywords
                ),
                "position_rank": rank,
                "existing_hit_score": _score(hit),
                "candidate_link": _missing(),
            }
        )

    for hit in truncated:
        if not isinstance(hit, dict):
            continue
        url = str(hit.get("url") or "")
        if url in kept_urls:
            continue
        rank = rank_by_url.get(url, _missing())
        hid = _hit_id(hit, search_id=search_id, rank=rank if rank != MISSING else 0)
        records.append(
            {
                "search_id": search_id,
                "round_id": round_id if round_id is not None else _missing(),
                "item_id": item_id if item_id is not None else _missing(),
                "query": query if query is not None else _missing(),
                "hit_id": hid,
                "url": hit.get("url"),
                "title": hit.get("title"),
                "snippet": (hit.get("snippet") or "")[:500],
                "source": hit.get("backend") or _missing(),
                "domain": _host(hit.get("url")),
                "kept": False,
                "drop_reason": "kept_limit_truncation",
                "position_rank": rank,
                "existing_hit_score": _score(hit),
                "candidate_link": _missing(),
            }
        )

    # store cap (obs only; does not change which hits were used for candidates)
    records = records[:max_store]
    kept_n = sum(1 for r in records if r.get("kept") is True)
    drop_n = sum(1 for r in records if r.get("kept") is False)
    return {
        "search_id": search_id,
        "query": query if query is not None else _missing(),
        "round_id": round_id if round_id is not None else _missing(),
        "records": records,
        "kept_count": kept_n,
        "dropped_count": drop_n,
        "ranked_input_count": len(ranked_hits or []),
        "filter_kept_count": len(kept_list),
        "filter_dropped_irrelevant_count": len(dropped_irrelevant or []),
        "filter_truncated_relevant_count": len(truncated),
        "behavior_changed": False,
        "not_for_decision": True,
        "phase": "kss-1.5",
    }


def merge_web_exec_partitions(web_exec, *, round_id=None, max_store=80):
    """web_exec.results 内の obs_partition / evidence から統合。"""
    if not isinstance(web_exec, dict):
        return {
            "enabled": False,
            "records": _missing(),
            "kept_hits": _missing(),
            "dropped_hits": _missing(),
            "source": "missing_web_exec",
            "note": "no live web_exec; do not invent dropped from history",
        }

    all_records = []
    searches = []
    for item in web_exec.get("results") or []:
        if not isinstance(item, dict):
            continue
        part = (item.get("evidence") or {}).get("obs_hit_partition")
        if isinstance(part, dict) and part.get("records"):
            searches.append(part)
            all_records.extend(part.get("records") or [])
            continue
        # fallback: reconstruct from evidence kept/dropped (may be truncated)
        ev = item.get("evidence") or {}
        kept = item.get("hits") or ev.get("hits") or []
        dropped = ev.get("dropped_hits") or []
        if not kept and not dropped:
            continue
        part = build_search_partition(
            ranked_hits=list(kept) + list(dropped),
            kept_hits=kept,
            dropped_irrelevant=dropped,
            query=ev.get("query") or item.get("search_query"),
            keywords=ev.get("keywords"),
            subject=None,
            round_id=round_id,
            item_id=item.get("id"),
            max_store=40,
        )
        part["note"] = "fallback_from_evidence_truncated_dropped"
        searches.append(part)
        all_records.extend(part.get("records") or [])

    all_records = all_records[:max_store]
    kept = [r for r in all_records if r.get("kept") is True]
    dropped = [r for r in all_records if r.get("kept") is False]
    return {
        "enabled": True,
        "phase": "kss-1.5",
        "not_for_decision": True,
        "behavior_changed": False,
        "round_id": round_id if round_id is not None else _missing(),
        "searches": searches,
        "records": all_records,
        "kept_hits": kept,
        "dropped_hits": dropped,
        "kept_count": len(kept),
        "dropped_count": len(dropped),
        "total_hits": len(all_records),
        "total_searches": len(searches),
        "source": "live_web_exec",
    }


def attach_candidate_links(partition, candidates=None, web_decision_link=None):
    """KSS-1.2 link 情報を hit に後付け（行動変更なし）。"""
    if not isinstance(partition, dict) or partition.get("records") == MISSING:
        return partition
    records = list(partition.get("records") or [])
    url_to_linked = {}
    if isinstance(web_decision_link, dict) and web_decision_link.get("enabled"):
        scored = web_decision_link.get("hits_scored") or []
        for link in web_decision_link.get("candidate_hit_links") or []:
            if not link.get("linked"):
                continue
            idx = link.get("best_hit_index")
            if isinstance(idx, int) and 0 <= idx < len(scored):
                url = scored[idx].get("url")
                if url:
                    url_to_linked[str(url)] = {
                        "linked": True,
                        "candidate_index": link.get("candidate_index"),
                        "token_overlap": link.get("token_overlap"),
                        "command": link.get("command"),
                    }
    for rec in records:
        url = str(rec.get("url") or "")
        if url in url_to_linked:
            rec["candidate_link"] = url_to_linked[url]
        elif rec.get("candidate_link") in (None, MISSING):
            rec["candidate_link"] = {"linked": False} if candidates is not None else _missing()
    partition["records"] = records
    partition["kept_hits"] = [r for r in records if r.get("kept") is True]
    partition["dropped_hits"] = [r for r in records if r.get("kept") is False]
    return partition


def enrich_partition_with_heuristic(partition, *, request_text="", case_id=None):
    """人手監査前の heuristic ラベル（正解扱いしない）。"""
    if not isinstance(partition, dict):
        return partition
    records = []
    for rec in partition.get("records") or []:
        item = dict(rec)
        judged = heuristic_answer_presence(
            item, request_text=request_text, case_id=case_id
        )
        item["heuristic_answer_presence"] = judged["answer_presence"]
        item["heuristic_reasons"] = judged.get("reasons") or []
        item["human_answer_presence"] = _missing()
        item["human_rationale"] = _missing()
        item["llm_answer_presence"] = _missing()
        item["llm_human_agreement"] = _missing()
        records.append(item)
    partition = dict(partition)
    partition["records"] = records
    partition["kept_hits"] = [r for r in records if r.get("kept") is True]
    partition["dropped_hits"] = [r for r in records if r.get("kept") is False]
    return partition


VALUABLE = ("direct", "core", "lead")


def label_of(rec, *, prefer_human=True):
    if prefer_human:
        h = rec.get("human_answer_presence")
        if h not in (None, MISSING, "missing", ""):
            return h
    return rec.get("heuristic_answer_presence") or MISSING


def build_human_audit_dataset(
    case_records,
    *,
    prefer_human=True,
    max_per_bucket=30,
):
    """
    人手監査用エントリ。
    buckets: failed_dropped, success_dropped, success_kept, failed_kept
    """
    entries = []
    bucket_counts = Counter()

    for case in case_records or []:
        case_id = case.get("case")
        request = case.get("request") or ""
        final_pass = case.get("pass")
        fail_stage = case.get("fail_stage")
        stop_reason = case.get("stop_reason")
        for rnd in case.get("rounds") or []:
            round_id = rnd.get("round")
            part = rnd.get("web_hit_partition") or {}
            records = part.get("records")
            if records in (None, MISSING) or not isinstance(records, list):
                continue
            for rec in records:
                kept = rec.get("kept") is True
                lab = label_of(rec, prefer_human=prefer_human)
                valuable = lab in VALUABLE
                if final_pass is True and not kept:
                    bucket = "B_success_dropped"
                elif final_pass is False and not kept:
                    bucket = "A_failed_dropped"
                elif final_pass is True and kept and valuable:
                    bucket = "C_success_kept_answerish"
                elif final_pass is False and kept and valuable:
                    bucket = "D_failed_kept_answerish"
                elif kept:
                    bucket = "kept_other"
                else:
                    bucket = "dropped_other"

                if bucket_counts[bucket] >= max_per_bucket and bucket in (
                    "kept_other",
                    "dropped_other",
                ):
                    continue
                if bucket_counts[bucket] >= max_per_bucket:
                    continue
                bucket_counts[bucket] += 1

                entries.append(
                    {
                        "audit_id": f"aud_{uuid.uuid4().hex[:10]}",
                        "bucket": bucket,
                        "case": case_id,
                        "round": round_id,
                        "original_question": request,
                        "query": rec.get("query"),
                        "kept": kept,
                        "drop_reason": rec.get("drop_reason"),
                        "url": rec.get("url"),
                        "domain": rec.get("domain"),
                        "title": rec.get("title"),
                        "snippet": rec.get("snippet"),
                        "source": rec.get("source"),
                        "position_rank": rec.get("position_rank"),
                        "existing_hit_score": rec.get("existing_hit_score"),
                        "candidate_link": rec.get("candidate_link"),
                        "search_id": rec.get("search_id"),
                        "hit_id": rec.get("hit_id"),
                        "final_pass": final_pass,
                        "fail_stage": fail_stage,
                        "stop_reason": stop_reason,
                        "heuristic_answer_presence": rec.get(
                            "heuristic_answer_presence"
                        ),
                        "human_answer_presence": rec.get(
                            "human_answer_presence", _missing()
                        ),
                        "human_rationale": rec.get("human_rationale", _missing()),
                        "llm_answer_presence": rec.get(
                            "llm_answer_presence", _missing()
                        ),
                        "allowed_labels": list(ANSWER_PRESENCE_LABELS),
                        "label_guide": {
                            "direct": "元の質問にほぼ直接回答できる",
                            "core": "回答の核心事実がある",
                            "lead": "次の検索・推論に使える重要な手掛かり",
                            "related": "関連だが重要とは言えない",
                            "none": "実質情報なし",
                            "unknown": "判断不能（noneと同一視しない）",
                        },
                    }
                )

    return {
        "phase": "kss-1.5",
        "not_for_decision": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bucket_counts": dict(bucket_counts),
        "entries": entries,
        "instructions": (
            "Fill human_answer_presence and human_rationale (1 line). "
            "Do not treat heuristic as ground truth. "
            "LLM Judge only after enough human labels."
        ),
    }


def write_human_audit_markdown(dataset, out_path: Path):
    lines = [
        "# KSS-1.5 Human Audit Worksheet",
        "",
        dataset.get("instructions") or "",
        "",
        f"entries: {len(dataset.get('entries') or [])}",
        f"buckets: `{json.dumps(dataset.get('bucket_counts') or {}, ensure_ascii=False)}`",
        "",
    ]
    for i, e in enumerate(dataset.get("entries") or [], 1):
        lines.extend(
            [
                f"## {i}. {e.get('audit_id')} — {e.get('bucket')}",
                "",
                f"- Case: `{e.get('case')}` Round: `{e.get('round')}`",
                f"- Final: pass={e.get('final_pass')} fail_stage={e.get('fail_stage')} stop={e.get('stop_reason')}",
                f"- Original question: {e.get('original_question')}",
                f"- Query: {e.get('query')}",
                f"- Kept/Dropped: **{'KEPT' if e.get('kept') else 'DROPPED'}**",
                f"- Drop reason: `{e.get('drop_reason')}`",
                f"- Domain/URL: `{e.get('domain')}` / {e.get('url')}",
                f"- Title: {e.get('title')}",
                f"- Snippet: {e.get('snippet')}",
                f"- Rank/score: {e.get('position_rank')} / {e.get('existing_hit_score')}",
                f"- Heuristic (not truth): `{e.get('heuristic_answer_presence')}`",
                f"- Human label: `{e.get('human_answer_presence')}` ← fill direct|core|lead|related|none|unknown",
                f"- Human rationale: `{e.get('human_rationale')}` ← 1 line why",
                "",
            ]
        )
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")


def track_lead_trajectories(case_records, *, prefer_human=True):
    """lead hit の後続 trajectory を追跡（因果断定なし）。"""
    tracks = []
    for case in case_records or []:
        rounds = case.get("rounds") or []
        lead_rounds = []
        for rnd in rounds:
            part = rnd.get("web_hit_partition") or {}
            for rec in part.get("records") or []:
                if label_of(rec, prefer_human=prefer_human) == "lead":
                    lead_rounds.append(rnd.get("round"))
                    break
        if not lead_rounds:
            continue
        first_lead = min(lead_rounds)
        later = [r for r in rounds if (r.get("round") or 0) > first_lead]
        later_core = False
        later_no_gain_streak = 0
        max_ng = 0
        for r in later:
            part = r.get("web_hit_partition") or {}
            for rec in part.get("records") or []:
                if label_of(rec, prefer_human=prefer_human) in ("direct", "core"):
                    later_core = True
            k13 = r.get("exploration_value_observation") or {}
            if k13.get("no_gain_existing") is True:
                later_no_gain_streak += 1
                max_ng = max(max_ng, later_no_gain_streak)
            else:
                later_no_gain_streak = 0
        tracks.append(
            {
                "case": case.get("case"),
                "final_pass": case.get("pass"),
                "first_lead_round": first_lead,
                "later_core_or_direct": later_core,
                "later_no_gain_max_streak": max_ng,
                "pattern": (
                    "lead_then_coreish"
                    if later_core
                    else (
                        "lead_then_no_gain"
                        if max_ng >= 2
                        else "lead_then_other"
                    )
                ),
                "note": "observational pathway only; not causal",
            }
        )
    return tracks


def compute_kss15_metrics(case_records, *, prefer_human=True):
    """レポート必須指標。人間ラベル優先、無ければ heuristic（明示）。"""
    label_source = "human" if prefer_human else "heuristic"
    human_n = 0
    for case in case_records or []:
        for rnd in case.get("rounds") or []:
            for rec in (rnd.get("web_hit_partition") or {}).get("records") or []:
                if rec.get("human_answer_presence") not in (
                    None,
                    MISSING,
                    "missing",
                    "",
                ):
                    human_n += 1
    if prefer_human and human_n == 0:
        label_source = "heuristic_pending_human_audit"

    totals = Counter()
    drop_x = Counter()
    failed = 0
    success = 0
    fail_ans_dropped = 0
    fail_ans_kept = 0
    fail_no_ans = 0
    searches = 0

    group = Counter()  # kept/dropped × answer/noanswer

    for case in case_records or []:
        is_pass = case.get("pass") is True
        if is_pass:
            success += 1
        elif case.get("pass") is False:
            failed += 1

        case_has_ans_kept = False
        case_has_ans_dropped = False
        case_has_any_hit = False
        dropped_observed = False

        for rnd in case.get("rounds") or []:
            part = rnd.get("web_hit_partition") or {}
            if part.get("source") == "live_web_exec" or isinstance(
                part.get("dropped_hits"), list
            ):
                if part.get("dropped_hits") not in (None, MISSING):
                    dropped_observed = True
            searches += int(part.get("total_searches") or 0) or len(
                part.get("searches") or []
            )
            records = part.get("records")
            if not isinstance(records, list):
                continue
            for rec in records:
                case_has_any_hit = True
                totals["total_hits"] += 1
                kept = rec.get("kept") is True
                if kept:
                    totals["kept_hits"] += 1
                else:
                    totals["dropped_hits"] += 1
                lab = label_of(rec, prefer_human=(label_source == "human"))
                if label_source != "human":
                    lab = rec.get("heuristic_answer_presence") or MISSING
                else:
                    # human preferred with heuristic fallback for coverage stats? 
                    # Spec: human audit - for metrics before human, use heuristic clearly
                    lab = label_of(rec, prefer_human=True)
                    if lab == MISSING:
                        lab = rec.get("heuristic_answer_presence") or MISSING

                valuable = lab in VALUABLE
                if kept and lab == "direct":
                    totals["kept_with_direct"] += 1
                if kept and lab == "core":
                    totals["kept_with_core"] += 1
                if kept and lab == "lead":
                    totals["kept_with_lead"] += 1
                if (not kept) and lab == "direct":
                    totals["dropped_with_direct"] += 1
                if (not kept) and lab == "core":
                    totals["dropped_with_core"] += 1
                if (not kept) and lab == "lead":
                    totals["dropped_with_lead"] += 1
                if lab == "unknown":
                    totals["dropped_answer_presence_unknown" if not kept else "kept_unknown"] += 1

                if kept:
                    group["kept_answer" if valuable else "kept_no_answer"] += 1
                else:
                    group["dropped_answer" if valuable else "dropped_no_answer"] += 1
                    drop_x[f"{rec.get('drop_reason')}|{lab}"] += 1

                if valuable and kept:
                    case_has_ans_kept = True
                if valuable and not kept:
                    case_has_ans_dropped = True

        if case.get("pass") is False:
            if case_has_ans_dropped:
                fail_ans_dropped += 1
            if case_has_ans_kept:
                fail_ans_kept += 1
            if (
                not case_has_ans_kept
                and not case_has_ans_dropped
                and dropped_observed
            ):
                fail_no_ans += 1
            elif not case_has_ans_kept and not dropped_observed:
                # cannot claim no answer in dropped
                pass

    dropped_n = totals.get("dropped_hits") or 0
    dropped_valuable = (
        totals.get("dropped_with_direct", 0)
        + totals.get("dropped_with_core", 0)
        + totals.get("dropped_with_lead", 0)
    )
    dropped_answer_rate = (
        round(dropped_valuable / dropped_n, 3) if dropped_n else _missing()
    )

    leads = track_lead_trajectories(
        case_records, prefer_human=(label_source == "human")
    )
    lead_success = sum(1 for t in leads if t.get("final_pass") is True)
    lead_fail = sum(1 for t in leads if t.get("final_pass") is False)
    no_lead_success = sum(
        1
        for c in case_records or []
        if c.get("pass") is True
        and not any(t.get("case") == c.get("case") for t in leads)
    )
    no_lead_fail = sum(
        1
        for c in case_records or []
        if c.get("pass") is False
        and not any(t.get("case") == c.get("case") for t in leads)
    )

    return {
        "label_source": label_source,
        "human_labels_filled": human_n,
        "total_searches": searches or _missing(),
        "total_hits": totals.get("total_hits", 0),
        "kept_hits": totals.get("kept_hits", 0),
        "dropped_hits": totals.get("dropped_hits", 0)
        if totals.get("dropped_hits")
        else (0 if any(
            isinstance((r.get("web_hit_partition") or {}).get("dropped_hits"), list)
            for c in case_records or []
            for r in c.get("rounds") or []
        ) else _missing()),
        "failed_runs": failed,
        "successful_runs": success,
        "kept_with_direct": totals.get("kept_with_direct", 0),
        "kept_with_core": totals.get("kept_with_core", 0),
        "kept_with_lead": totals.get("kept_with_lead", 0),
        "dropped_with_direct": totals.get("dropped_with_direct", 0),
        "dropped_with_core": totals.get("dropped_with_core", 0),
        "dropped_with_lead": totals.get("dropped_with_lead", 0),
        "dropped_answer_presence_unknown": totals.get(
            "dropped_answer_presence_unknown", 0
        ),
        "failed_runs_with_answer_in_dropped": fail_ans_dropped,
        "failed_runs_with_answer_in_kept": fail_ans_kept,
        "failed_runs_with_no_answer_found": fail_no_ans,
        "four_group_counts": dict(group),
        "drop_reason_x_answer_presence": dict(drop_x),
        "dropped_answer_rate": dropped_answer_rate,
        "failed_runs_with_recoverable_dropped_info": fail_ans_dropped,
        "lead_continuation": {
            "cases_with_lead": len(leads),
            "lead_then_success": lead_success,
            "lead_then_fail": lead_fail,
            "no_lead_success": no_lead_success,
            "no_lead_fail": no_lead_fail,
            "tracks": leads,
            "note": "counts only; do not claim causation",
        },
        "llm_judge_agreement": {
            "status": "deferred_until_human_labels",
            "agreement_rate": _missing(),
        },
    }
