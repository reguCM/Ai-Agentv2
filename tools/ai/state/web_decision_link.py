"""
KSS-1.2: Web evidence ↔ decision 紐付け（観測のみ）。

既存 hit_score / hits / candidates を使い、候補がどの hit と語彙的に重なるかを記録する。
候補の採否・実行・routing は変更しない。

欠落は missing（推定で埋めない）。
"""

from __future__ import annotations

import os
import re

from tools.system.tool_builder.research.web import hit_score


def kss12_obs_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KSS12_OBS")
    if raw is None or str(raw).strip() == "":
        # KSS-1.1 と同時 ON でも可
        raw = os.environ.get("AI_AGENT_KSS11_OBS")
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{2,}|Win32_\w+|Get-\w+", re.I)


def _tokens(*parts):
    text = " ".join(str(p or "") for p in parts).lower()
    return {t.lower() for t in _TOKEN_RE.findall(text)}


def annotate_hits_with_scores(hits):
    """既存 hit_score を付与したコピー。入力は変更しない。"""
    out = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        item = dict(hit)
        if "score" not in item or item.get("score") is None:
            item["score"] = hit_score(hit)
        out.append(item)
    return out


def link_candidates_to_hits(candidates, hits):
    """
    候補ごとに、語彙 overlap が最大の hit を記録する。
    overlap=0 なら linked=False / best_hit=missing。
    """
    scored_hits = annotate_hits_with_scores(hits)
    links = []
    for idx, cand in enumerate(candidates or []):
        if not isinstance(cand, dict):
            continue
        c_tokens = _tokens(
            cand.get("command"),
            " ".join(str(a) for a in (cand.get("args") or [])),
            cand.get("question"),
            cand.get("route"),
        )
        best = None
        best_overlap = 0
        best_score = None
        for h_i, hit in enumerate(scored_hits):
            h_tokens = _tokens(hit.get("title"), hit.get("snippet"), hit.get("url"))
            overlap = len(c_tokens & h_tokens) if c_tokens and h_tokens else 0
            if overlap > best_overlap:
                best_overlap = overlap
                best = h_i
                best_score = hit.get("score")
        linked = best is not None and best_overlap > 0
        links.append(
            {
                "candidate_index": idx,
                "command": cand.get("command"),
                "args": list(cand.get("args") or []),
                "linked": linked,
                "best_hit_index": best if linked else "missing",
                "token_overlap": best_overlap if linked else 0,
                "best_hit_score": best_score if linked else "missing",
                "best_hit_url": (
                    (scored_hits[best].get("url") if linked else None) or "missing"
                )
                if linked
                else "missing",
                "candidate_token_count": len(c_tokens),
                "link_method": "token_overlap_with_existing_hit_score",
                "not_for_decision": True,
            }
        )
    n = len(links)
    linked_n = sum(1 for x in links if x.get("linked"))
    return {
        "enabled": True,
        "phase": "kss-1.2",
        "not_for_decision": True,
        "behavior_changed": False,
        "hits_scored": [
            {
                "title": h.get("title"),
                "url": h.get("url"),
                "backend": h.get("backend"),
                "score": h.get("score"),
            }
            for h in scored_hits[:12]
        ],
        "candidate_hit_links": links,
        "link_coverage": round(linked_n / n, 3) if n else None,
        "candidates_total": n,
        "candidates_linked": linked_n,
        "candidates_unlinked": n - linked_n,
        "hits_total": len(scored_hits),
        "audit_gaps": _audit_gaps(scored_hits, links),
    }


def _audit_gaps(scored_hits, links):
    gaps = []
    if not scored_hits:
        gaps.append("no_web_hits_in_round")
    if scored_hits and all(
        (h.get("score") is None or h.get("score") == "missing") for h in scored_hits
    ):
        gaps.append("hit_score_missing_on_all_hits")
    if links and all(not x.get("linked") for x in links):
        gaps.append("zero_candidate_hit_token_overlap")
    if not gaps:
        gaps.append("none")
    return gaps


def maybe_link_web_to_decisions(candidates, hits):
    if not kss12_obs_enabled():
        return {"enabled": False, "phase": "kss-1.2"}
    return link_candidates_to_hits(candidates, hits)
