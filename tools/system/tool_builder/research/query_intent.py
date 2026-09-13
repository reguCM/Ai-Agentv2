"""
Phase A: ユーザー要求から SearchIntent を抽出し、探索用検索クエリを生成する。

- API / コマンド名の決め打ちはしない
- implementation_context は質問に明示があるときだけ設定する
- SEARCH_HINTS に依存しない主経路（失敗時のみ呼び出し側で fallback）
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

UNSPECIFIED = "unspecified"

INTENT_KEYS = (
    "platform",
    "target",
    "metric",
    "unit",
    "desired_operation",
    "implementation_context",
    "purpose",
)

# 質問に明示されたときだけ許可する実装文脈（推測禁止）
_EXPLICIT_IMPL_PATTERNS = (
    (re.compile(r"powershell", re.I), "PowerShell"),
    (re.compile(r"\bpython\b|パイソン", re.I), "Python"),
    (re.compile(r"\bwmi\b", re.I), "WMI"),
    (re.compile(r"\bcim\b|ciminstance", re.I), "CIM"),
    (re.compile(r"nvidia-?smi", re.I), "nvidia-smi"),
    (re.compile(r"win32api|windows api", re.I), "Windows API"),
    (re.compile(r"performance\s*counter|パフォーマンス\s*カウンタ", re.I), "Performance Counter"),
)

_GAP_FILLER = (
    "is still unconfirmed",
    "still unconfirmed",
    "is unconfirmed",
    "unconfirmed",
    "が未確認",
    "は未確認",
    "未確認",
    "を取得する方法",
    "の取得方法",
    "を確認する必要があります",
    "を確認する",
    "investigate",
    "how to obtain",
)

_TECH_PATTERNS = (
    re.compile(r"\bGet-[A-Za-z][A-Za-z0-9]*\b"),
    re.compile(r"\bWin32_[A-Za-z][A-Za-z0-9]*\b"),
    re.compile(r"\bnvidia-smi\b", re.I),
    re.compile(r"\bGet-CimInstance\b", re.I),
    re.compile(r"\bGet-WmiObject\b", re.I),
    re.compile(r"\bGet-Counter\b", re.I),
    re.compile(r"\bGet-Volume\b", re.I),
    re.compile(r"\bwmic\b", re.I),
)

_TECH_PHRASES = (
    ("performance counter", "Performance Counter"),
    ("wmi class", "WMI"),
    ("cim class", "CIM"),
    ("powershell", "PowerShell"),
)


def empty_intent(*, source: str = "empty") -> dict[str, Any]:
    return {key: UNSPECIFIED for key in INTENT_KEYS} | {"source": source}


def normalize_query(query: str | None) -> str:
    text = str(query or "").strip().lower()
    text = text.replace("％", "%").replace("°ｃ", "°c")
    text = re.sub(r"[\"'`]", " ", text)
    text = re.sub(r"[，、。；;:：]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # 連続重複トークン（disk disk）を畳む
    tokens = text.split()
    deduped = []
    for token in tokens:
        if not deduped or deduped[-1] != token:
            deduped.append(token)
    return " ".join(deduped)


def query_already_searched(query: str, searched: list[str] | set[str] | None) -> bool:
    key = normalize_query(query)
    if not key:
        return True
    seen = {normalize_query(item) for item in (searched or [])}
    return key in seen


def dedupe_queries(queries, *, searched=None, limit=None) -> list[str]:
    out = []
    seen = {normalize_query(item) for item in (searched or []) if normalize_query(item)}
    for query in queries or []:
        cleaned = re.sub(r"\s+", " ", str(query or "")).strip()
        key = normalize_query(cleaned)
        if not key or key in seen:
            continue
        # 単語1つだけのクエリは探索として弱すぎるので除外（fallback 以外）
        if len(key.split()) < 2 and key not in {"nvidia-smi"}:
            continue
        seen.add(key)
        out.append(cleaned)
        if limit is not None and len(out) >= limit:
            break
    return out


def _text_blob(*parts) -> str:
    return " ".join(str(p or "") for p in parts)


def explicit_implementation_context(request_text: str) -> str:
    text = str(request_text or "")
    for pattern, label in _EXPLICIT_IMPL_PATTERNS:
        if pattern.search(text):
            return label
    return UNSPECIFIED


def sanitize_intent(intent: dict | None, request_text: str = "") -> dict[str, Any]:
    out = empty_intent(source=(intent or {}).get("source") or "sanitized")
    if isinstance(intent, dict):
        for key in INTENT_KEYS:
            value = intent.get(key)
            if value is None or str(value).strip() == "":
                continue
            out[key] = str(value).strip()
        if intent.get("source"):
            out["source"] = str(intent.get("source"))
    # 明示がなければ決め打ち禁止
    explicit = explicit_implementation_context(request_text)
    if explicit == UNSPECIFIED:
        out["implementation_context"] = UNSPECIFIED
    else:
        # LLM が別物を入れても、明示値のみ採用
        out["implementation_context"] = explicit
    return out


def _has_token(text: str, *tokens: str) -> bool:
    """ラテン語トークンを日本語隣接でも検出（\\b はCJKで効かない）。"""
    lowered = str(text or "")
    for token in tokens:
        if not token:
            continue
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", lowered, re.I):
            return True
    return False


def fallback_intent_from_text(
    request_text: str,
    *,
    subject=None,
    state=None,
    proposal=None,
) -> dict[str, Any]:
    """LLM 失敗時・オフ時の機械 Intent。実装文脈は明示時のみ。"""
    subject = subject or {}
    proposal = proposal or {}
    text = _text_blob(
        request_text,
        getattr(state, "task", None) if state is not None else None,
        (state or {}).get("task") if isinstance(state, dict) else None,
    )
    intent = empty_intent(source="fallback_rules")

    if re.search(r"windows|ウィンドウズ", text, re.I):
        intent["platform"] = "Windows"
    elif _has_token(text, "linux") or re.search(r"リナックス", text, re.I):
        intent["platform"] = "Linux"
    elif re.search(r"macos|mac\s*os", text, re.I) or _has_token(text, "mac"):
        intent["platform"] = "macOS"

    sub = str(subject.get("subcategory") or proposal.get("subcategory") or "").lower()
    if (
        _has_token(text, "vram")
        or re.search(r"ビデオメモリ|显存", text, re.I)
        or sub == "vram"
    ):
        intent["target"] = "gpu"
        intent["metric"] = "vram_usage"
    elif _has_token(text, "gpu") or re.search(r"ジーピーユー", text, re.I) or sub == "gpu":
        intent["target"] = "gpu"
    elif (
        re.search(r"ディスク", text, re.I)
        or _has_token(text, "disk")
        or re.search(r"drive\s*usage", text, re.I)
        or sub == "disk"
    ):
        intent["target"] = "disk"
    elif (
        re.search(r"メモリ", text, re.I)
        or _has_token(text, "memory", "ram")
        or sub == "memory"
    ):
        intent["target"] = "memory"
    elif (
        _has_token(text, "cpu")
        or re.search(r"プロセッサ|processor", text, re.I)
        or sub == "cpu"
    ):
        intent["target"] = "cpu"

    if intent["metric"] == UNSPECIFIED:
        if re.search(r"温度|temperature|°\s*c|℃", text, re.I):
            intent["metric"] = "temperature"
        elif re.search(r"使用量|capacity|amount", text, re.I):
            intent["metric"] = "usage_amount"
        elif re.search(r"使用率|利用率|utilization|usage", text, re.I):
            intent["metric"] = "usage"

    if _has_token(text, "mb") or re.search(r"メガバイト", text, re.I):
        intent["unit"] = "MB"
    elif re.search(r"%|％|パーセント|percent", text, re.I):
        intent["unit"] = "%"
    elif re.search(r"°\s*c|℃|度", text, re.I) or intent["metric"] == "temperature":
        intent["unit"] = "°C"
    elif intent["metric"] == "usage":
        intent["unit"] = "%"

    if re.search(r"監視|monitor", text, re.I):
        intent["desired_operation"] = "monitor"
    elif re.search(r"一覧|list", text, re.I):
        intent["desired_operation"] = "list"
    elif re.search(r"取得|get|measure|測", text, re.I):
        intent["desired_operation"] = "get"

    if re.search(r"tool|ツール", text, re.I):
        intent["purpose"] = "tool_output"

    intent["implementation_context"] = explicit_implementation_context(text)
    return sanitize_intent(intent, text)


def _extract_json_object(text: str):
    stripped = str(text or "").strip()
    if not stripped:
        return None
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(stripped[start : end + 1])
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def _llm_intent_enabled() -> bool:
    """既定はオフ（機械 fallback 主）。明示 ON のときだけ LLM 抽出を試す。"""
    raw = os.environ.get("AI_AGENT_SEARCH_INTENT_LLM")
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def extract_search_intent_llm(request_text: str, *, state=None, proposal=None) -> dict | None:
    if not _llm_intent_enabled():
        return None
    text = str(request_text or "").strip()
    if not text:
        return None
    decisions = []
    if state is not None:
        raw = getattr(state, "decisions", None)
        if raw is None and isinstance(state, dict):
            raw = state.get("decisions")
        for item in raw or []:
            if isinstance(item, dict):
                decisions.append(
                    {
                        "key": item.get("key"),
                        "value": item.get("value"),
                    }
                )
    schema_hint = {
        "platform": "Windows|Linux|macOS|unspecified",
        "target": "cpu|gpu|memory|disk|unspecified",
        "metric": "usage|temperature|vram_usage|usage_amount|unspecified",
        "unit": "%|MB|°C|unspecified",
        "desired_operation": "get|monitor|list|unspecified",
        "implementation_context": (
            "unspecified unless the user explicitly named PowerShell/Python/WMI/CIM/etc."
        ),
        "purpose": "tool_output|unspecified",
    }
    prompt = (
        "Extract a SearchIntent JSON object from the user request.\n"
        "Do NOT invent an implementation technology. "
        "If PowerShell/Python/WMI/etc. is not explicitly requested, "
        "set implementation_context to \"unspecified\".\n"
        "Do NOT put specific API or command names (Get-Volume, nvidia-smi, Win32_*) "
        "into any field.\n"
        f"Schema: {json.dumps(schema_hint, ensure_ascii=False)}\n"
        f"User request: {text}\n"
        f"Known decisions (optional): {json.dumps(decisions[:8], ensure_ascii=False)}\n"
        "Return JSON only."
    )
    try:
        from tools.system.llm import chat

        response = chat(
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 256, "temperature": 0},
        )
        content = getattr(getattr(response, "message", None), "content", None)
        payload = _extract_json_object(content or "")
        if not isinstance(payload, dict):
            return None
        payload["source"] = "llm"
        return sanitize_intent(payload, text)
    except Exception:
        return None


def extract_search_intent(
    request_text: str,
    *,
    subject=None,
    state=None,
    proposal=None,
    prefer_llm: bool | None = None,
) -> dict[str, Any]:
    text = str(request_text or "").strip()
    if not text and state is not None:
        text = str(getattr(state, "task", None) or "").strip()
        if not text and isinstance(state, dict):
            text = str(state.get("task") or "").strip()
    use_llm = _llm_intent_enabled() if prefer_llm is None else bool(prefer_llm)
    if use_llm:
        llm_intent = extract_search_intent_llm(
            text, state=state, proposal=proposal
        )
        if llm_intent and any(
            llm_intent.get(k) not in (None, "", UNSPECIFIED)
            for k in ("platform", "target", "metric")
        ):
            return llm_intent
    return fallback_intent_from_text(
        text, subject=subject, state=state, proposal=proposal
    )


def _metric_phrases(metric: str) -> list[str]:
    metric = str(metric or "").lower()
    if metric == "temperature":
        return ["temperature"]
    if metric == "vram_usage":
        return ["VRAM usage"]
    if metric == "usage_amount":
        return ["usage"]
    if metric == "usage":
        return ["usage", "utilization"]
    return []


def _unit_phrase(unit: str) -> str:
    unit = str(unit or "")
    if unit in (UNSPECIFIED, ""):
        return ""
    if unit == "%":
        return "percentage"
    return unit


def intent_base_terms(intent: dict | None) -> list[str]:
    intent = intent or empty_intent()
    terms = []
    for key in ("platform", "target"):
        value = intent.get(key)
        if value and value != UNSPECIFIED:
            terms.append(str(value))
    metric = intent.get("metric")
    if metric and metric != UNSPECIFIED:
        phrases = _metric_phrases(metric)
        if phrases:
            terms.append(phrases[0])
        else:
            terms.append(str(metric).replace("_", " "))
    unit = _unit_phrase(intent.get("unit") or "")
    if unit:
        terms.append(unit)
    return terms


def intent_filter_keywords(intent: dict | None) -> list[str]:
    terms = intent_base_terms(intent)
    intent = intent or {}
    for phrase in _metric_phrases(intent.get("metric") or ""):
        if phrase not in terms:
            terms.append(phrase)
    ctx = intent.get("implementation_context")
    if ctx and ctx != UNSPECIFIED:
        terms.append(str(ctx))
    return [t for t in terms if t]


def build_exploration_queries(intent: dict | None, *, max_queries: int = 3) -> list[str]:
    intent = sanitize_intent(intent or empty_intent())
    base = intent_base_terms(intent)
    if len(base) < 2:
        # 最低限 target+metric が無いと探索不能 → 空（呼び出し側 fallback）
        return []

    candidates = []
    core = " ".join(base)
    candidates.append(core)

    op = intent.get("desired_operation")
    if op == "monitor":
        candidates.append(f"{core} monitoring")
    else:
        candidates.append(f"{' '.join(intent_base_terms(intent))} command")

    # 別角度: utilization / how to measure（API名なし）
    metric = intent.get("metric")
    platform = intent.get("platform")
    target = intent.get("target")
    alt_parts = []
    if platform and platform != UNSPECIFIED:
        alt_parts.append(str(platform))
    if target and target != UNSPECIFIED:
        alt_parts.append(str(target))
    if metric == "usage":
        alt_parts.append("utilization")
    elif metric == "temperature":
        alt_parts.append("temperature sensor")
    elif metric == "vram_usage":
        alt_parts.append("VRAM memory used")
    else:
        alt_parts.append("measurement")
    candidates.append(" ".join(alt_parts))

    ctx = intent.get("implementation_context")
    if ctx and ctx != UNSPECIFIED:
        # 明示されたときだけ技術文脈クエリを差し替え（決め打ち追加ではない）
        candidates[1] = f"{core} {ctx}"

    return dedupe_queries(candidates, limit=max_queries)


def clean_missing_gap(text: str) -> str:
    cleaned = str(text or "").strip()
    for filler in _GAP_FILLER:
        cleaned = re.sub(re.escape(filler), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\"'`]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;/-")
    # output 'status' → status をギャップ語として残す程度に簡略化
    cleaned = re.sub(r"^\s*output\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def build_followup_queries(
    intent: dict | None,
    missing=None,
    *,
    discovered=None,
    searched=None,
    max_queries: int = 2,
) -> list[str]:
    """
    missing / discovered を単純連結しない。
    Intent を保ち、ギャップ語だけを足す。
    """
    intent = sanitize_intent(intent or empty_intent())
    base_terms = intent_base_terms(intent)
    base = " ".join(base_terms)
    candidates = []

    gaps = []
    for item in missing or []:
        gap = clean_missing_gap(item)
        if gap and normalize_query(gap) not in {normalize_query(base), ""}:
            gaps.append(gap)
    if gaps and base:
        gap0 = gaps[0]
        # ギャップが Intent と別メトリクスへ大きく逸脱していても、
        # Intent を捨てて gap だけにはしない
        if normalize_query(gap0) not in normalize_query(base):
            candidates.append(f"{base} {gap0}")
        else:
            candidates.append(base)
    elif base:
        candidates.append(f"{base} method")

    # discovered は追撃用に別関数。ここではヒント程度に1本まで
    for tech in discovered or []:
        tech = str(tech or "").strip()
        if not tech or not base:
            continue
        candidates.append(f"{tech} {base}")
        break

    return dedupe_queries(candidates, searched=searched, limit=max_queries)


def build_pursuit_query(
    technique: str,
    intent: dict | None,
    *,
    searched=None,
) -> str | None:
    tech = str(technique or "").strip()
    if not tech:
        return None
    base = " ".join(intent_base_terms(intent))
    query = f"{tech} {base}".strip() if base else tech
    queries = dedupe_queries([query], searched=searched, limit=1)
    return queries[0] if queries else None


def extract_discovered_techniques(hits, *, limit: int = 5) -> list[str]:
    found = []
    seen = set()
    blob_parts = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        blob_parts.append(
            " ".join(
                str(hit.get(k) or "")
                for k in ("title", "snippet", "url")
            )
        )
    blob = "\n".join(blob_parts)
    for pattern in _TECH_PATTERNS:
        for match in pattern.findall(blob):
            key = normalize_query(match)
            if not key or key in seen:
                continue
            seen.add(key)
            found.append(match if not match.lower().startswith("get-") else match)
            if len(found) >= limit:
                return found
    lowered = blob.lower()
    for needle, label in _TECH_PHRASES:
        if needle in lowered:
            key = normalize_query(label)
            if key and key not in seen:
                seen.add(key)
                found.append(label)
                if len(found) >= limit:
                    break
    return found


def resolve_user_request(user_request=None, state=None, item=None) -> str:
    if str(user_request or "").strip():
        return str(user_request).strip()
    if state is not None:
        task = getattr(state, "task", None)
        if task:
            return str(task).strip()
        if isinstance(state, dict) and state.get("task"):
            return str(state.get("task")).strip()
    if isinstance(item, dict) and item.get("question") and not item.get("followup"):
        # 初回 item.question は output 'status' のことが多いので使わない
        return ""
    return ""
