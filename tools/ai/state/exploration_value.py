"""
KSS-1.3: 探索価値・情報利得の観測基盤（完全 observation-only）。

目的: 各 research round について
  - 新しい情報 / 探索手掛かりが出たか
  - 過去 round の繰り返しではないか
  - 既存 information_gain / no_gain との関係
  - その後の成功・失敗との照合
を後から分析できるデータを残す。

禁止: routing / confidence 閾値 / Web 強制 / 固定検索回数 /
      HELP / 上位 LLM routing / Phase 5.1 正式化 /
      MAX_RESEARCH_ROUNDS・MAX_STAGNATION 緩和 /
      no_gain 意味変更 / hit 採否・judge・verifier 変更 /
      exploration_value 単一スコア

存在しない値は missing（0 埋めしない）。
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from tools.ai.state.web_decision_link import (
    _TOKEN_RE,
    annotate_hits_with_scores,
    link_candidates_to_hits,
)


MISSING = "missing"

# 取得不能（推定禁止）— 明示用
ALWAYS_MISSING_FIELDS = (
    "new_entity_count",  # NER 無し
    "exploration_value_score",  # 単一スコア禁止
    "semantic_novelty",
    "embedding_similarity",
)


def kss13_obs_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KSS13_OBS")
    if raw is None or str(raw).strip() == "":
        # 1.1/1.2 と同時に観測する運用を許容
        raw = os.environ.get("AI_AGENT_KSS12_OBS") or os.environ.get(
            "AI_AGENT_KSS11_OBS"
        )
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _missing():
    return MISSING


def _is_missing(v):
    return v is None or v == MISSING


def empty_prior_sets():
    return {
        "urls": set(),
        "hosts": set(),
        "tokens": set(),
        "command_keys": set(),
        "reference_fingerprints": set(),
    }


def _host(url):
    try:
        host = (urlparse(str(url or "")).hostname or "").lower()
        return host or None
    except Exception:
        return None


def _tokens_from(*parts):
    text = " ".join(str(p or "") for p in parts).lower()
    return {t.lower() for t in _TOKEN_RE.findall(text)}


def _command_key(command, args=None):
    cmd = str(command or "").strip().lower()
    arg_s = " ".join(str(a) for a in (args or [])).strip().lower()
    if not cmd and not arg_s:
        return None
    return f"{cmd}|{arg_s}"[:240]


def extract_round_sets(researched=None, round_item=None):
    """1 round から機械的に url/host/token/command 集合を抽出。"""
    researched = researched or {}
    round_item = round_item or {}
    hits = researched.get("web_hits") or round_item.get("web_hits") or []
    cands = researched.get("candidates") or []
    if not cands:
        for run in round_item.get("verified_runs") or []:
            if isinstance(run, dict):
                cands.append(
                    {"command": run.get("command"), "args": run.get("args") or []}
                )

    urls, hosts, tokens, cmds = set(), set(), set(), set()
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        url = hit.get("url")
        if url:
            urls.add(str(url))
            h = _host(url)
            if h:
                hosts.add(h)
        tokens |= _tokens_from(hit.get("title"), hit.get("snippet"), hit.get("url"))

    for cand in cands:
        if not isinstance(cand, dict):
            continue
        tokens |= _tokens_from(
            cand.get("command"),
            " ".join(str(a) for a in (cand.get("args") or [])),
            cand.get("question"),
        )
        ck = _command_key(cand.get("command"), cand.get("args"))
        if ck:
            cmds.add(ck)

    for key in round_item.get("candidate_keys") or []:
        if key:
            cmds.add(str(key).lower()[:240])
            tokens |= _tokens_from(key)

    refs = set()
    research = researched.get("research") or {}
    for item in research.get("reference_findings") or []:
        if not isinstance(item, dict):
            continue
        fp = str(
            item.get("finding")
            or item.get("id")
            or (item.get("evidence") or {}).get("command")
            or ""
        )[:200]
        if fp:
            refs.add(fp.lower())

    return {
        "urls": urls,
        "hosts": hosts,
        "tokens": tokens,
        "command_keys": cmds,
        "reference_fingerprints": refs,
    }


def _jaccard(a, b):
    if not a and not b:
        return _missing()
    union = a | b
    if not union:
        return _missing()
    return round(len(a & b) / len(union), 3)


def collect_web_search_stats(web_exec=None, web_hits=None, web_decision_link=None):
    """
    search_result_count = kept + dropped（web_exec に dropped_count がある場合のみ）。
    web_exec が無ければ search_result_count / dropped は missing。
    """
    kept_from_hits = len(web_hits or [])
    if web_decision_link and isinstance(web_decision_link.get("hits_total"), int):
        # link obs は truncate 前の hits を見ない場合あり → hits_total 優先しない
        pass

    dropped = None
    kept_from_exec = None
    if isinstance(web_exec, dict):
        total_dropped = 0
        total_kept = 0
        found_dropped = False
        for item in web_exec.get("results") or []:
            if not isinstance(item, dict):
                continue
            total_kept += len(item.get("hits") or [])
            ev = item.get("evidence") or {}
            if ev.get("dropped_count") is not None:
                total_dropped += int(ev.get("dropped_count") or 0)
                found_dropped = True
        kept_from_exec = total_kept
        if found_dropped:
            dropped = total_dropped

    kept = kept_from_exec if kept_from_exec is not None else kept_from_hits
    if dropped is not None:
        search_result_count = kept + dropped
    else:
        search_result_count = _missing()

    return {
        "search_result_count": search_result_count,
        "kept_hit_count": kept,
        "dropped_hit_count": dropped if dropped is not None else _missing(),
        "web_hits_saved_count": kept_from_hits,
    }


def _extract_existing_gain(researched, decision_evidence=None):
    """既存 KSS-0 / KSS-1.1 の information_gain / no_gain を写す（再発明しない）。"""
    kss0 = researched.get("knowledge_source_observation") or {}
    de = decision_evidence or researched.get("decision_evidence_observation") or {}
    evd = de.get("evidence") or {} if isinstance(de, dict) else {}

    no_gain = evd.get("no_gain")
    info = None
    for cov_key in ("known_coverage_after", "known_coverage"):
        cov = kss0.get(cov_key) if isinstance(kss0, dict) else None
        if not isinstance(cov, dict):
            continue
        if no_gain is None or no_gain == _missing():
            if "no_gain" in cov:
                no_gain = cov.get("no_gain")
        nested = cov.get("information_gain")
        if isinstance(nested, dict):
            info = nested
            break
        if cov.get("has_gain") is not None or cov.get("no_gain") is not None:
            info = {
                "has_gain": cov.get("has_gain"),
                "no_gain": cov.get("no_gain"),
            }
            break

    if info is None and isinstance(kss0.get("information_gain"), dict):
        info = kss0.get("information_gain")

    if no_gain is None:
        no_gain = _missing()
    if info is None:
        info = _missing()

    return info, no_gain


def _link_metrics(researched, round_item=None):
    wlink = researched.get("web_decision_link")
    if not (isinstance(wlink, dict) and wlink.get("enabled")):
        wlink = (round_item or {}).get("web_decision_link")
    if isinstance(wlink, dict) and wlink.get("enabled"):
        return {
            "candidate_count": wlink.get("candidates_total"),
            "linked_candidate_count": wlink.get("candidates_linked"),
            "candidate_to_hit_link_count": wlink.get("candidates_linked"),
            "zero_overlap_count": wlink.get("candidates_unlinked"),
            "link_coverage": wlink.get("link_coverage"),
            "hits_total": wlink.get("hits_total"),
            "source": "web_decision_link",
        }
    # 再計算（オフライン / obs OFF 時）— 行動変更なし
    hits = researched.get("web_hits") or (round_item or {}).get("web_hits") or []
    cands = list(researched.get("candidates") or [])
    if not cands:
        for run in (round_item or {}).get("verified_runs") or []:
            if isinstance(run, dict):
                cands.append(
                    {"command": run.get("command"), "args": run.get("args") or []}
                )
    if not hits and not cands:
        return {
            "candidate_count": (round_item or {}).get("candidate_count", 0),
            "linked_candidate_count": _missing(),
            "candidate_to_hit_link_count": _missing(),
            "zero_overlap_count": _missing(),
            "link_coverage": _missing(),
            "hits_total": len(hits),
            "source": "missing_inputs",
        }
    linked = link_candidates_to_hits(cands, hits)
    return {
        "candidate_count": linked.get("candidates_total"),
        "linked_candidate_count": linked.get("candidates_linked"),
        "candidate_to_hit_link_count": linked.get("candidates_linked"),
        "zero_overlap_count": linked.get("candidates_unlinked"),
        "link_coverage": linked.get("link_coverage"),
        "hits_total": linked.get("hits_total"),
        "source": "retro_token_overlap",
    }


def observe_exploration_round(
    *,
    round_num,
    researched=None,
    progress_decision=None,
    prior_sets=None,
    decision_evidence=None,
    web_exec=None,
    case_id=None,
    research_run_id=None,
    round_item=None,
):
    """
    1 research round の探索価値観測バンドル。
    prior_sets は呼び出し側が保持し、戻り値の prior_sets_after で更新する。
    """
    researched = researched or {}
    progress_decision = progress_decision or {}
    prior = prior_sets if prior_sets is not None else empty_prior_sets()
    for k in empty_prior_sets():
        prior.setdefault(k, set())

    current = extract_round_sets(researched, round_item)
    new_urls = current["urls"] - prior["urls"]
    new_hosts = current["hosts"] - prior["hosts"]
    new_tokens = current["tokens"] - prior["tokens"]
    new_cmds = current["command_keys"] - prior["command_keys"]
    new_refs = current["reference_fingerprints"] - prior["reference_fingerprints"]

    rep_urls = current["urls"] & prior["urls"]
    rep_tokens = current["tokens"] & prior["tokens"] if prior["tokens"] else set()

    web_stats = None
    pre = researched.get("web_exec_stats")
    if isinstance(pre, dict) and (
        "kept_hit_count" in pre or "search_result_count" in pre
    ):
        web_stats = {
            "search_result_count": pre.get("search_result_count", _missing()),
            "kept_hit_count": pre.get(
                "kept_hit_count",
                len(
                    researched.get("web_hits")
                    or (round_item or {}).get("web_hits")
                    or []
                ),
            ),
            "dropped_hit_count": pre.get("dropped_hit_count", _missing()),
            "web_hits_saved_count": pre.get(
                "web_hits_saved_count",
                len(
                    researched.get("web_hits")
                    or (round_item or {}).get("web_hits")
                    or []
                ),
            ),
        }
    else:
        web_stats = collect_web_search_stats(
            web_exec=web_exec,
            web_hits=researched.get("web_hits") or (round_item or {}).get("web_hits"),
            web_decision_link=researched.get("web_decision_link"),
        )
    link = _link_metrics(researched, round_item)
    info_gain, no_gain = _extract_existing_gain(researched, decision_evidence)

    de = decision_evidence or researched.get("decision_evidence_observation") or {}
    evd = de.get("evidence") or {} if isinstance(de, dict) else {}
    evidence_level = evd.get("evidence_level")
    if evidence_level is None:
        evidence_level = _missing()

    # new_information_count: progress の新 finding keys（意味的新規性ではない）
    has_new = progress_decision.get("has_new_finding")
    new_info_count = _missing()
    if has_new is True:
        # キー集合が無ければ boolean のみ → count は missing、flag で記録
        keys = progress_decision.get("new_finding_keys")
        if isinstance(keys, (list, set, tuple)):
            new_info_count = len(keys)
        else:
            new_info_count = _missing()
    elif has_new is False:
        new_info_count = 0

    cand_count = link.get("candidate_count")
    if cand_count is None or _is_missing(cand_count):
        filt = researched.get("candidate_filter_stats") or {}
        if filt.get("after") is not None:
            cand_count = filt.get("after")
        elif (round_item or {}).get("candidate_count") is not None:
            cand_count = (round_item or {}).get("candidate_count")
        else:
            cand_count = len(researched.get("candidates") or [])

    # hit scores
    hit_scores = []
    score_missing_n = 0
    for hit in annotate_hits_with_scores(
        researched.get("web_hits") or (round_item or {}).get("web_hits") or []
    ):
        sc = hit.get("score")
        if sc is None:
            score_missing_n += 1
            hit_scores.append(_missing())
        else:
            hit_scores.append(sc)

    token_j = _jaccard(current["tokens"], prior["tokens"]) if prior["tokens"] else (
        0.0 if current["tokens"] else _missing()
    )
    url_j = _jaccard(current["urls"], prior["urls"]) if prior["urls"] else (
        0.0 if current["urls"] else _missing()
    )

    exploration_signal = {
        "has_new_url": bool(new_urls),
        "has_new_source": bool(new_hosts),
        "has_new_term": bool(new_tokens),
        "has_new_command_key": bool(new_cmds),
        "has_linked_candidate": (
            bool(link.get("linked_candidate_count"))
            if not _is_missing(link.get("linked_candidate_count"))
            else _missing()
        ),
        "has_information_gain_existing": (
            bool(info_gain.get("has_gain"))
            if isinstance(info_gain, dict) and "has_gain" in info_gain
            else _missing()
        ),
        "progress_has_new_finding": has_new if has_new is not None else _missing(),
        "composite_score": _missing(),  # 単一スコアは作らない
    }

    missing_fields = list(ALWAYS_MISSING_FIELDS)
    if _is_missing(web_stats["search_result_count"]):
        missing_fields.append("search_result_count")
    if _is_missing(web_stats["dropped_hit_count"]):
        missing_fields.append("dropped_hit_count")
    if _is_missing(new_info_count) and has_new is not False:
        missing_fields.append("new_information_count")
    if evidence_level == _missing():
        missing_fields.append("evidence_level")
    if info_gain == _missing():
        missing_fields.append("information_gain_existing_detail")
    if no_gain == _missing():
        missing_fields.append("no_gain_existing")

    present = 0
    total_tracked = 0
    tracked_vals = [
        web_stats["kept_hit_count"],
        cand_count,
        link.get("link_coverage"),
        len(new_urls),
        len(new_hosts),
        len(new_tokens),
        no_gain,
        evidence_level,
    ]
    for v in tracked_vals:
        total_tracked += 1
        if not _is_missing(v):
            present += 1

    bundle = {
        "enabled": True,
        "phase": "kss-1.3",
        "not_for_decision": True,
        "behavior_changed": False,
        "round_index": round_num,
        "search_volume": {
            "search_result_count": web_stats["search_result_count"],
            "kept_hit_count": web_stats["kept_hit_count"],
            "dropped_hit_count": web_stats["dropped_hit_count"],
            "web_hits_saved_count": web_stats["web_hits_saved_count"],
        },
        "information_novelty": {
            "new_url_count": len(new_urls),
            "new_source_count": len(new_hosts),
            "new_term_count": len(new_tokens),
            "new_reference_count": len(new_refs),
            "new_command_key_count": len(new_cmds),
            "new_entity_count": _missing(),
            "new_information_count": new_info_count,
            "new_information_flag": has_new if has_new is not None else _missing(),
        },
        "exploration_leads": {
            "candidate_count": cand_count,
            "linked_candidate_count": link.get("linked_candidate_count"),
            "candidate_to_hit_link_count": link.get("candidate_to_hit_link_count"),
            "zero_overlap_count": link.get("zero_overlap_count"),
            "link_coverage": link.get("link_coverage"),
            "link_metric_source": link.get("source"),
        },
        "evidence_strength": {
            "evidence_level": evidence_level,
            "verify_high_count": evd.get("verify_high_count", _missing()),
            "verify_low_count": evd.get("verify_low_count", _missing()),
            "usable_count": evd.get("usable_count", _missing()),
            "hit_scores": hit_scores[:12],
            "hit_score_missing_count": score_missing_n,
        },
        "information_gain_existing": info_gain,
        "no_gain_existing": no_gain,
        "duplicate_or_repeated": {
            "progress_duplicate_only": (
                progress_decision.get("duplicate_only")
                if "duplicate_only" in progress_decision
                else _missing()
            ),
            "repeated_url_count": len(rep_urls),
            "repeated_term_count": len(rep_tokens) if prior["tokens"] else (
                0 if not current["tokens"] else _missing()
            ),
            "duplicate_or_repeated_count": (
                len(rep_urls)
                if prior["urls"] or prior["tokens"]
                else (0 if round_num == 1 else _missing())
            ),
        },
        "previous_round_similarity": {
            "token_jaccard": token_j,
            "url_jaccard": url_j,
            "method": "set_jaccard_mechanical",
            "note": "not semantic similarity",
        },
        "exploration_signal": exploration_signal,
        "observation_quality": {
            "fields_present": present,
            "fields_tracked": total_tracked,
            "coverage": round(present / total_tracked, 3) if total_tracked else None,
            "missing_fields": missing_fields,
        },
        "progress_action": progress_decision.get("action", _missing()),
        "progress_reason": progress_decision.get("reason", _missing()),
        "progress_stagnation": progress_decision.get("stagnation", _missing()),
        "run_linkage": {
            "case_id": case_id if case_id is not None else _missing(),
            "research_run_id": research_run_id
            if research_run_id is not None
            else _missing(),
            "round_index": round_num,
            # 以下は run 終了後に analyzer が埋める
            "final_pass": _missing(),
            "fail_stage": _missing(),
            "fail_reason": _missing(),
            "total_rounds": _missing(),
            "next_round_exists": _missing(),
            "next_round_gain": _missing(),
            "eventually_succeeded": _missing(),
        },
        "missing_fields_policy": "missing_not_zero",
        "available_vs_missing_note": {
            "AVAILABLE": [
                "kept_hit_count",
                "candidate_count",
                "new_url/source/term counts (set-diff)",
                "link_coverage (KSS-1.2)",
                "information_gain_existing / no_gain_existing",
                "token/url jaccard",
                "evidence_level (KSS-1.1)",
            ],
            "MISSING_unless_web_exec": ["search_result_count", "dropped_hit_count"],
            "ALWAYS_MISSING": list(ALWAYS_MISSING_FIELDS),
        },
    }

    # prior 更新用コピー
    after = {
        "urls": set(prior["urls"]) | current["urls"],
        "hosts": set(prior["hosts"]) | current["hosts"],
        "tokens": set(prior["tokens"]) | current["tokens"],
        "command_keys": set(prior["command_keys"]) | current["command_keys"],
        "reference_fingerprints": set(prior["reference_fingerprints"])
        | current["reference_fingerprints"],
    }
    return bundle, after


def maybe_observe_exploration_round(**kwargs):
    if not kss13_obs_enabled():
        return {"enabled": False, "phase": "kss-1.3"}, kwargs.get(
            "prior_sets"
        ) or empty_prior_sets()
    return observe_exploration_round(**kwargs)


def attach_run_outcomes(bundles, *, final_pass, fail_stage=None, fail_reason=None):
    """run 終了後に各 round へ最終結果・次 round 利得を付与（分析用・判断変更なし）。"""
    out = []
    n = len(bundles or [])
    for i, b in enumerate(bundles or []):
        if not isinstance(b, dict):
            continue
        item = dict(b)
        link = dict(item.get("run_linkage") or {})
        link["final_pass"] = final_pass
        link["fail_stage"] = fail_stage if fail_stage is not None else _missing()
        link["fail_reason"] = fail_reason if fail_reason is not None else _missing()
        link["total_rounds"] = n
        link["eventually_succeeded"] = bool(final_pass) if final_pass is not None else _missing()
        next_exists = i + 1 < n
        link["next_round_exists"] = next_exists
        if next_exists:
            nxt = bundles[i + 1] if isinstance(bundles[i + 1], dict) else {}
            ng = nxt.get("no_gain_existing")
            ig = nxt.get("information_gain_existing")
            if isinstance(ig, dict) and "has_gain" in ig:
                link["next_round_gain"] = bool(ig.get("has_gain"))
            elif ng is not None and ng != _missing():
                link["next_round_gain"] = not bool(ng)
            else:
                # novelty proxy
                nov = nxt.get("information_novelty") or {}
                link["next_round_gain"] = bool(
                    (nov.get("new_url_count") or 0) > 0
                    or (nov.get("new_term_count") or 0) > 0
                    or (nov.get("new_source_count") or 0) > 0
                )
        else:
            link["next_round_gain"] = _missing()
        item["run_linkage"] = link
        out.append(item)
    return out


def rebuild_from_round_details(round_details, progress_log=None, **run_meta):
    """保存済み research_rounds_detail から観測を再構築（無いものは missing）。"""
    progress_by_round = {}
    for p in progress_log or []:
        if isinstance(p, dict) and p.get("round") is not None:
            progress_by_round[p["round"]] = p

    prior = empty_prior_sets()
    bundles = []
    for item in round_details or []:
        if not isinstance(item, dict):
            continue
        rnd = item.get("round")
        prog = progress_by_round.get(rnd) or {}
        # progress flags may only live in decision_evidence
        de = item.get("decision_evidence_observation") or {}
        if not prog and de.get("enabled"):
            for ev in de.get("decision_events") or []:
                if ev.get("decision_type") == "research_progress":
                    prog = {
                        "action": ev.get("progress_action"),
                        "reason": ev.get("progress_reason"),
                        "stagnation": ev.get("progress_stagnation"),
                        "has_new_finding": ev.get("progress_has_new_finding"),
                        "duplicate_only": ev.get("progress_duplicate_only"),
                        "missing_same": ev.get("progress_missing_same"),
                    }
                    break
        researched = {
            "web_hits": item.get("web_hits") or [],
            "web_decision_link": item.get("web_decision_link"),
            "knowledge_source_observation": item.get(
                "knowledge_source_observation"
            ),
            "decision_evidence_observation": de,
            "candidates": [],
            "candidate_filter_stats": {
                "after": item.get("candidate_count"),
            },
            "research": {},
        }
        bundle, prior = observe_exploration_round(
            round_num=rnd,
            researched=researched,
            progress_decision=prog,
            prior_sets=prior,
            decision_evidence=de,
            web_exec=None,  # 過去データに無し → search_result_count missing
            case_id=run_meta.get("case_id"),
            research_run_id=run_meta.get("research_run_id"),
            round_item=item,
        )
        bundles.append(bundle)

    return attach_run_outcomes(
        bundles,
        final_pass=run_meta.get("final_pass"),
        fail_stage=run_meta.get("fail_stage"),
        fail_reason=run_meta.get("fail_reason"),
    )


# silence unused import warning for re if any
_ = re
