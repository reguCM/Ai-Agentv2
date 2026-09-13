"""NH7 observation parse + mechanical fingerprint mapping (experimental)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

NH6_SCHEMA = (
    Path(__file__).resolve().parents[1] / "nh6" / "feature_schema.json"
)

ALLOWED_FEATURES = list(
    json.loads(NH6_SCHEMA.read_text(encoding="utf-8"))["features"].keys()
)

FEATURE_NAME_RE = re.compile(
    r"\b(state_change_requested|reopen_requested|has_runtime_logs|"
    r"needs_path_integration|evidence_suspicious|near_exact_reactivation|"
    r"similar_but_new_goal|small_llm_output_suspicious|llm_disagreement|"
    r"code_available|path_unknown_or_untrusted)\b"
)

NONE_TOKENS = {"なし", "none", "n/a", "na", "無", "not present", "no log", "コード診断は今回不要"}


def extract_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _as_list(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _text_of(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for k in ("quote", "text", "fact", "evidence", "action", "kind", "summary"):
            if item.get(k):
                return str(item.get(k))
        return json.dumps(item, ensure_ascii=False)
    return str(item)


def _quote_of(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("quote") or item.get("text") or "")
    return str(item or "")


def _join_texts(items: list[Any]) -> str:
    parts: list[str] = []
    for x in items:
        if isinstance(x, dict):
            parts.append(str(x.get("quote") or x.get("text") or ""))
            parts.extend(str(t) for t in _as_list(x.get("texts")))
            parts.append(str(x.get("action") or ""))
            parts.append(str(x.get("kind") or ""))
        else:
            parts.append(_text_of(x))
    return " ".join(p for p in parts if p).lower()


def _reopen_positive(text: str) -> bool:
    t = (text or "").lower()
    stripped = re.sub(
        r"reopen\s*ではなく[^\n。]*|reopenではない[^\n。]*|not\s+a?\s*reopen[^\n。]*",
        " ",
        t,
        flags=re.I,
    )
    return "reopen" in stripped


def _is_none_text(s: str) -> bool:
    t = (s or "").strip().lower()
    if not t:
        return True
    compact = re.sub(r"\s+", "", t)
    if compact in NONE_TOKENS or t in NONE_TOKENS:
        return True
    if compact.startswith("なし"):
        return True
    if "不要" in t and "コード" in t:
        return True
    return False


def _boolish(val: Any) -> bool | None:
    if val is True or val is False:
        return val
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"true", "yes", "present"}:
        return True
    if s in {"false", "no", "absent", "none", "なし"}:
        return False
    return None


def normalize_observation(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    evid = raw.get("explicit_evidence_information")
    if isinstance(evid, dict):
        evid_list = [evid]
    else:
        evid_list = _as_list(evid)

    runtime = raw.get("explicit_runtime_symptoms")
    if isinstance(runtime, dict):
        runtime_list = [runtime]
    else:
        runtime_list = _as_list(runtime)

    code = raw.get("explicit_code_scope")
    if isinstance(code, dict):
        code_list = [code]
    else:
        code_list = _as_list(code)

    return {
        "explicit_requests": _as_list(raw.get("explicit_requests")),
        "explicit_state_changes": _as_list(raw.get("explicit_state_changes")),
        "explicit_runtime_symptoms": runtime_list,
        "explicit_evidence_information": evid_list,
        "explicit_code_scope": code_list,
        "surface_text_relation": raw.get("surface_text_relation") or {},
        "prior_analysis_notes": _as_list(raw.get("prior_analysis_notes")),
        "unknowns": [str(x) for x in _as_list(raw.get("unknowns"))],
        "inferences_not_facts": [str(x) for x in _as_list(raw.get("inferences_not_facts"))],
        "evidence_classes": raw.get("evidence_classes") or raw.get("evidence_classification") or {},
        "raw": raw,
        "hallucinated_feature_keys": sorted(
            {m.group(0) for m in FEATURE_NAME_RE.finditer(json.dumps(raw, ensure_ascii=False))}
        ),
    }


def observation_slots(obs: dict[str, Any]) -> dict[str, bool]:
    """Boolean slots used to evaluate observation extraction (not Selector features)."""
    req = _join_texts(obs.get("explicit_requests") or [])
    st = _join_texts(obs.get("explicit_state_changes") or [])
    rt_items = obs.get("explicit_runtime_symptoms") or []
    rt = _join_texts(rt_items)
    evid_items = obs.get("explicit_evidence_information") or []
    evid = _join_texts(evid_items)
    code_items = obs.get("explicit_code_scope") or []
    code = _join_texts(code_items)
    prior = _join_texts(obs.get("prior_analysis_notes") or [])
    rel = obs.get("surface_text_relation") or {}
    rel_s = json.dumps(rel, ensure_ascii=False).lower() if rel else ""

    runtime_present = False
    for item in rt_items:
        if isinstance(item, dict) and _boolish(item.get("present")) is False:
            continue
        if isinstance(item, dict) and _boolish(item.get("present")) is True:
            runtime_present = True
        txt = _text_of(item)
        if txt and not _is_none_text(txt) and (
            "[observed]" in txt.lower() or "latency" in txt.lower() or "count=" in txt.lower()
        ):
            runtime_present = True
        if isinstance(item, dict):
            for t in _as_list(item.get("texts") or item.get("quotes")):
                if t and not _is_none_text(str(t)):
                    runtime_present = True

    files: list[str] = []
    excerpt = False
    excerpt_false = False
    multi = False
    caller_unknown = False
    for item in code_items:
        if isinstance(item, dict):
            files.extend([str(x) for x in _as_list(item.get("files") or item.get("files_mentioned")) if x])
            ep = _boolish(item.get("excerpt_present"))
            if ep is True:
                excerpt = True
            elif ep is False:
                excerpt_false = True
            if _boolish(item.get("multi_file") or item.get("multi_file_stated")) is True:
                multi = True
            if _boolish(item.get("caller_unknown") or item.get("caller_unknown_stated")) is True:
                caller_unknown = True
        t = _quote_of(item)
        if "caller" in t.lower() and ("不明" in t or "unknown" in t.lower()):
            caller_unknown = True
        if "ファイル" in t or ".py" in t:
            excerpt = True
        if any(n in t for n in ["3ファイル", "複数", "跨"]):
            multi = True
        if t and not _is_none_text(t) and "不要" not in t and not excerpt_false:
            excerpt = True

    if len({f.lower() for f in files if f}) >= 2:
        multi = True
        excerpt = True
    elif files and not excerpt_false:
        excerpt = True
    if excerpt_false and not files:
        excerpt = False

    evid_id = False
    evid_exists = False
    mismatch = False
    for item in evid_items:
        t = _text_of(item)
        if re.search(r"e-\d+|evidence_id|evidence id", t, re.I):
            evid_id = True
        if isinstance(item, dict):
            if item.get("id") or item.get("evidence_id"):
                evid_id = True
            if _boolish(item.get("exists") or item.get("exists_stated")) is True:
                evid_exists = True
            if _boolish(item.get("content_mismatch") or item.get("content_mismatch_stated")) is True:
                mismatch = True
        if "exists=true" in t.lower() or "exists: true" in t.lower():
            evid_exists = True
        if "一致しない" in t or "mismatch" in t.lower() or "unrelated" in t.lower():
            mismatch = True
        if re.search(r"e-\d+", t, re.I):
            evid_id = True

    reopen = _reopen_positive(req + " " + st) or _reopen_positive(evid)
    state_upd = any(
        k in (req + st)
        for k in ["change request", "更新", "active", "goal", "claim", "hypothesis", "reopen"]
    ) and not _no_state(req + st)

    rel_kind = str(rel.get("relation") or rel.get("kind") or "").lower()
    near = rel_kind in {
        "near_exact",
        "punctuation",
        "case",
        "unicode",
        "case_unicode",
    } or any(k in rel_s + st + req for k in ["句読点", "punctuation", "unicode 正規化", "case 差"])
    similar_new = rel_kind in {"similar_new", "new_meaning"} or any(
        k in rel_s + st + req for k in ["対象機能が異なる", "新しい意味"]
    )

    return {
        "state_update_present": bool(state_upd) and not _no_state(req + st),
        "reopen_present": reopen,
        "runtime_log_present": runtime_present and "なし" not in rt,
        "no_runtime_stated": ("なし" in rt) or any(
            isinstance(x, dict) and _boolish(x.get("present")) is False for x in rt_items
        ),
        "no_state_change_stated": _no_state(req + st),
        "code_excerpt_present": excerpt and "不要" not in code and not (
            _is_none_text(code) and not files
        ),
        "multi_file": multi,
        "caller_unknown": caller_unknown,
        "evidence_id_present": evid_id,
        "evidence_exists_true": evid_exists,
        "content_mismatch_stated": mismatch,
        "near_exact_surface": near,
        "similar_new_meaning": similar_new,
        "small_llm_unverified": (
            ("小型" in prior or "small llm" in prior)
            and any(k in prior for k in ["未検証", "断定"])
        ),
        "llm_disagreement": (
            any(k in prior for k in ["一致しない", "不一致", "disagreement"])
            and ("大型" in prior or "large llm" in prior)
        ),
        "handoff_mismatch": ("stdout" in (req + prior + rt) and "messages" in (req + prior + rt)),
        "ranking_filter_confusion": "混同" in (req + prior + rt)
        or ("ranking" in (req + prior) and "filter" in (req + prior) and "混同" in (req + prior)),
        "off_path_causes": any(k in (req + prior) for k in ["経路外", "off-path", "off_path", "本文get", "retry"]),
    }


def _no_state(text: str) -> bool:
    t = text.lower()
    return any(
        p in t
        for p in [
            "変更要求はない",
            "変更なし",
            "state 変更なし",
            "state変更なし",
            "action\": \"none",
            "action: none",
        ]
    )


def map_observations_to_features(
    obs: dict[str, Any],
    *,
    observed_only: bool = False,
) -> dict[str, Any]:
    """Mechanical mapping. Does not call LLM. INFERENCE cannot set unsafe features true."""
    obs = normalize_observation(obs if "explicit_requests" in (obs or {}) or obs else obs)
    slots = observation_slots(obs)
    features: dict[str, bool] = {}
    mapping_trace: list[str] = []
    unknowns = list(obs.get("unknowns") or [])

    if observed_only:
        classes = obs.get("evidence_classes") or {}
        inf = " ".join(str(x) for x in (classes.get("inference") or [])).lower()
        # Drop slot trues that appear only in inference lists, not in explicit fields.
        # Mapping still uses structured explicit_* fields; observed_only blocks inference-only extras.
        if inf and not (obs.get("explicit_evidence_information") or []):
            slots["content_mismatch_stated"] = False
            slots["evidence_exists_true"] = False

    if slots["state_update_present"] or slots["reopen_present"]:
        features["state_change_requested"] = True
        mapping_trace.append("explicit state/reopen request → state_change_requested=true")
    elif slots["no_state_change_stated"]:
        features["state_change_requested"] = False
        mapping_trace.append("explicit no-state-change → state_change_requested=false")

    if slots["reopen_present"]:
        features["reopen_requested"] = True
        mapping_trace.append("REOPEN mentioned → reopen_requested=true")
    elif slots["no_state_change_stated"] or slots["state_update_present"]:
        features["reopen_requested"] = False
        mapping_trace.append("no REOPEN / ordinary update → reopen_requested=false")

    if slots["runtime_log_present"]:
        features["has_runtime_logs"] = True
        mapping_trace.append("runtime log text present → has_runtime_logs=true")
    elif slots["no_runtime_stated"]:
        features["has_runtime_logs"] = False
        mapping_trace.append("runtime なし → has_runtime_logs=false")

    if slots["code_excerpt_present"]:
        features["code_available"] = True
        mapping_trace.append("code excerpt/files → code_available=true")
    else:
        features["code_available"] = False
        mapping_trace.append("no code excerpt → code_available=false")

    if slots["multi_file"]:
        features["needs_path_integration"] = True
        features["needs_local_analysis"] = True
        mapping_trace.append("multi-file → needs_path_integration=true")
    elif features.get("code_available") is True and slots["caller_unknown"]:
        features["needs_local_analysis"] = True
        features["needs_path_integration"] = False
        mapping_trace.append("single excerpt + caller unknown → local yes, integration false")
    elif features.get("code_available") is True:
        features["needs_local_analysis"] = True

    if slots["caller_unknown"] or (
        features.get("code_available") and features.get("needs_path_integration")
    ):
        features["path_unknown_or_untrusted"] = True
        mapping_trace.append("caller unknown or multi-file path → path_unknown_or_untrusted=true")

    if slots["near_exact_surface"]:
        features["near_exact_reactivation"] = True
        mapping_trace.append("explicit punct/case/unicode diff → near_exact_reactivation=true")

    if slots["similar_new_meaning"]:
        features["similar_but_new_goal"] = True
        mapping_trace.append("explicit new meaning → similar_but_new_goal=true")

    if slots["evidence_id_present"]:
        features["evidence_present"] = True
        mapping_trace.append("evidence id → evidence_present=true")
    if slots["evidence_exists_true"]:
        features["evidence_exists"] = True
        mapping_trace.append("exists=true stated → evidence_exists=true")
    if slots["content_mismatch_stated"]:
        features["evidence_content_mismatch"] = True
        features["evidence_suspicious"] = True
        mapping_trace.append("explicit content mismatch → evidence_suspicious=true")

    if slots["small_llm_unverified"]:
        features["small_llm_output_suspicious"] = True
        mapping_trace.append("unverified small-LLM diagnosis → small_llm_output_suspicious=true")
    if slots["llm_disagreement"]:
        features["llm_disagreement"] = True
        mapping_trace.append("explicit disagreement → llm_disagreement=true")

    # Ranking/filter / handoff / off-path: only if explicit confusion/off-path language
    prior = _join_texts(obs.get("prior_analysis_notes") or [])
    blob = prior + " " + _join_texts(obs.get("explicit_requests") or [])
    if "混同" in blob or ("handoff 境界" in blob):
        if "ranking" in blob.lower() and "filter" in blob.lower():
            features["suspect_ranking_vs_filter"] = True
            mapping_trace.append("explicit ranking/filter confusion → suspect_ranking_vs_filter=true")
    if slots["handoff_mismatch"] and "一致しない" in blob:
        features["suspect_stdout_vs_llm_handoff"] = True
        mapping_trace.append("explicit stdout/messages mismatch → suspect_stdout_vs_llm_handoff=true")
    if slots["off_path_causes"]:
        features["suspect_off_path_causes"] = True
        mapping_trace.append("explicit off-path cause mention → suspect_off_path_causes=true")

    if features.get("code_available"):
        features.setdefault("suspect_ranking_vs_filter", False)
        features.setdefault("suspect_stdout_vs_llm_handoff", False)
        features.setdefault("suspect_off_path_causes", False)

    # Do not set evidence_timestamp_unknown from 「可能性」 inferences
    inf = _join_texts(obs.get("inferences_not_facts") or [])
    if "timestamp" in inf or "古い可能性" in inf:
        mapping_trace.append("timestamp staleness kept as inference; feature not set")
        if "evidence_timestamp_unknown" not in unknowns:
            unknowns.append("evidence_timestamp_unknown_not_set_from_inference")

    extra = [k for k in features if k not in ALLOWED_FEATURES]
    for k in extra:
        features.pop(k, None)

    return {
        "features": features,
        "uncertainties": unknowns,
        "mapping_trace": mapping_trace,
        "slots": slots,
        "hallucinated_feature_keys": obs.get("hallucinated_feature_keys") or [],
    }


def evaluate_observation(gold_slots: dict[str, bool], pred_slots: dict[str, bool], case_id: str) -> dict[str, Any]:
    keys = sorted(set(gold_slots) | set(pred_slots))
    results = []
    correct = 0
    extra_true = 0
    miss_true = 0
    for k in keys:
        g = bool(gold_slots.get(k))
        p = bool(pred_slots.get(k))
        status = "correct" if g == p else "error"
        if g == p:
            correct += 1
        elif p and not g:
            extra_true += 1
        else:
            miss_true += 1
        results.append({"slot": k, "gold": g, "pred": p, "status": status})
    n = len(keys) or 1
    return {
        "case_id": case_id,
        "slot_accuracy": round(correct / n, 4),
        "correct": correct,
        "extra_true": extra_true,
        "miss_true": miss_true,
        "slot_results": results,
    }
