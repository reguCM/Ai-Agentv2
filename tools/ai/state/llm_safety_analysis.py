"""
Phase C: 機械 Safety が unknown のときだけ、設定済み LLM で構造分析する。

- 安全証明ではない（not_a_safety_proof）
- machine_assessed を書き換えない
- Web ページ本文は渡さない
- tools.system.llm.chat + get_llm_profile を使用（GPT 専用にしない）
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from tools.ai.state.safety_assessment import (
    READONLY_CMDLETS,
    SIDE_FS_DELETE,
    SIDE_FS_WRITE,
    SIDE_NET,
    SIDE_PRIV,
    SIDE_PROCESS,
    SIDE_READ,
    SIDE_SERVICE,
    SIDE_STATE,
    SIDE_UNKNOWN,
)

# cannot_rule_out に含まれたら ExperimentCandidate 不可
CRITICAL_CANNOT_RULE_OUT = frozenset(
    {
        SIDE_NET,
        "network_egress",
        SIDE_FS_WRITE,
        "filesystem_write",
        SIDE_FS_DELETE,
        "filesystem_delete",
        SIDE_PROCESS,
        "process_control",
        SIDE_SERVICE,
        "service_control",
        SIDE_PRIV,
        "privilege_escalation",
        "dynamic_code",
        SIDE_STATE,  # 動的/状態変更の否定不能も含め安全側
    }
)

LLM_ANALYSIS_KEYS = (
    "operation_summary_ja",
    "read_only_likely",
    "side_effects",
    "cannot_rule_out",
    "similar_known_ops",
    "obfuscation_or_dynamic",
    "confidence",
    "rationale_ja",
    "not_a_safety_proof",
)


def known_readonly_operation_names() -> list[str]:
    """内部管理の比較対象（Web 文言ではない）。"""
    return sorted({name for name in READONLY_CMDLETS if name.startswith("get-")})


def build_llm_safety_materials(candidate: dict, machine_rationale_codes: list | None) -> dict:
    command = str((candidate or {}).get("command") or "").strip()
    args = list((candidate or {}).get("args") or [])
    return {
        "command": command,
        "args": args,
        "machine_rationale_codes": list(machine_rationale_codes or []),
        "known_readonly_operations": known_readonly_operation_names(),
        "instructions_ja": (
            "これは安全性の証明依頼ではありません。"
            "コマンドの構造・想定副作用・既知の読取操作との類似性だけを分析してください。"
            "Webページの『安全』『危険』という説明は根拠にしないでください（渡されていません）。"
            "実行を許可する権限はありません。"
            "確信度が低い場合や否定できない副作用がある場合は cannot_rule_out に列挙してください。"
        ),
        "required_json_keys": list(LLM_ANALYSIS_KEYS),
        "critical_side_effects_to_consider": sorted(CRITICAL_CANNOT_RULE_OUT),
    }


def build_llm_safety_messages(materials: dict) -> list[dict]:
    system = (
        "あなたはコマンド構造の分析アシスタントです。"
        "安全性を証明してはいけません。Execution Gate を変更する権限はありません。"
        "必ず JSON オブジェクトのみを返してください。"
        "フィールド: operation_summary_ja (string), read_only_likely (bool), "
        "side_effects (string[]), cannot_rule_out (string[]), "
        "similar_known_ops (string[]), obfuscation_or_dynamic (bool), "
        "confidence (low|medium|high), rationale_ja (string[]), "
        "not_a_safety_proof (true 必須)."
    )
    user = (
        "分析対象（command/args と機械 rationale のみ）:\n"
        + json.dumps(materials, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def extract_json_object(text: str) -> dict | None:
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


def normalize_llm_safety_payload(payload: dict | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    # 「安全です」だけ等、必須構造が欠ける場合は無効
    required_presence = ("operation_summary_ja", "read_only_likely", "cannot_rule_out")
    if any(k not in payload for k in required_presence):
        return None

    def _list(value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        return []

    read_only = payload.get("read_only_likely")
    if isinstance(read_only, str):
        read_only = read_only.strip().lower() in ("true", "1", "yes")
    else:
        read_only = bool(read_only)

    obfuscation = payload.get("obfuscation_or_dynamic")
    if isinstance(obfuscation, str):
        obfuscation = obfuscation.strip().lower() in ("true", "1", "yes")
    else:
        obfuscation = bool(obfuscation)

    confidence = str(payload.get("confidence") or "low").strip().lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "low"

    summary = str(payload.get("operation_summary_ja") or "").strip()
    rationale = _list(payload.get("rationale_ja"))
    # 断定口調だけの回答は構造不足として落とす
    if not summary or re.fullmatch(r"安全です[。．!]?", summary):
        return None
    if rationale and all(re.fullmatch(r"安全です[。．!]?", r) for r in rationale):
        if len(summary) < 12:
            return None

    return {
        "operation_summary_ja": summary,
        "read_only_likely": read_only,
        "side_effects": _list(payload.get("side_effects")),
        "cannot_rule_out": _list(payload.get("cannot_rule_out")),
        "similar_known_ops": _list(payload.get("similar_known_ops")),
        "obfuscation_or_dynamic": obfuscation,
        "confidence": confidence,
        "rationale_ja": rationale,
        "not_a_safety_proof": True,
    }


def run_llm_structural_safety_analysis(
    candidate: dict,
    machine_rationale_codes: list | None = None,
    *,
    chat_fn: Callable | None = None,
) -> dict[str, Any]:
    """
    戻り値は常に監査用 dict。
    ok=False のときは Gate 側で ExperimentCandidate 不可。
    """
    from tools.system.config import get_llm_profile
    from tools.system.llm import LLMTimeoutError

    profile = get_llm_profile()
    model_id = str(profile.get("id") or profile.get("model") or "unknown")
    materials = build_llm_safety_materials(candidate, machine_rationale_codes)
    messages = build_llm_safety_messages(materials)

    # 監査: Web「安全」文言が入力に無いこと
    joined = json.dumps(materials, ensure_ascii=False) + json.dumps(
        messages, ensure_ascii=False
    )
    assert "ウイルスではない" not in joined
    # 意図的に「このコマンドは安全」のような Web 説明を materials に入れない

    result = {
        "ok": False,
        "phase": "kss-phase-c",
        "model_profile_id": model_id,
        "model": str(profile.get("model") or ""),
        "error": None,
        "raw_text": None,
        "analysis": None,
        "materials_keys": sorted(materials.keys()),
        "web_content_included": False,
        "not_a_safety_proof": True,
    }

    try:
        if chat_fn is None:
            from tools.system.llm import chat as chat_fn

        response = chat_fn(
            messages=messages,
            options={"num_predict": 512, "temperature": 0},
        )
        text = getattr(getattr(response, "message", None), "content", None)
        if callable(getattr(response, "get", None)):
            # dict-like mock
            text = response.get("message", {}).get("content") or text
        result["raw_text"] = text
        payload = extract_json_object(text or "")
        normalized = normalize_llm_safety_payload(payload)
        if not normalized:
            result["error"] = "invalid_or_incomplete_json"
            return result
        result["analysis"] = normalized
        result["ok"] = True
        return result
    except LLMTimeoutError as exc:
        result["error"] = f"timeout:{exc}"
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
        return result


def llm_permits_experiment_candidate(llm_bundle: dict | None) -> tuple[bool, list[str]]:
    """
    LLM 出力を機械条件で評価する。Gate を LLM に渡さない。
    許可されても Execute にはしない。ExperimentCandidate 提示の可否のみ。
    cannot_rule_out=[] は安全証明ではない。
    """
    codes = []
    if not isinstance(llm_bundle, dict) or not llm_bundle.get("ok"):
        codes.append("llm_analysis_unavailable")
        return False, codes
    analysis = llm_bundle.get("analysis") or {}
    if not analysis:
        codes.append("llm_analysis_empty")
        return False, codes

    if not analysis.get("read_only_likely"):
        codes.append("llm_not_read_only_likely")
        return False, codes

    if analysis.get("obfuscation_or_dynamic"):
        codes.append("llm_obfuscation_or_dynamic")
        return False, codes

    # 「安全です」だけの根拠は不可
    rationale = [str(x).strip() for x in (analysis.get("rationale_ja") or [])]
    summary = str(analysis.get("operation_summary_ja") or "").strip()
    if _is_safe_only_claim(summary) or (
        rationale and all(_is_safe_only_claim(r) for r in rationale)
    ):
        codes.append("llm_safe_only_claim_rejected")
        return False, codes

    cannot_list = analysis.get("cannot_rule_out")
    if cannot_list is None:
        codes.append("llm_cannot_rule_out_missing")
        return False, codes
    cannot = {str(x).strip().lower() for x in (cannot_list or []) if str(x).strip()}
    # 空配列は「全部否定できた証明」ではない。提示条件の一部に過ぎない。
    codes.append("cannot_rule_out_empty_is_not_safety_proof")

    critical_hit = sorted(
        c for c in cannot if c in {x.lower() for x in CRITICAL_CANNOT_RULE_OUT}
    )
    if critical_hit:
        codes.append("llm_cannot_rule_out:" + ",".join(critical_hit))
        return False, codes

    effects = [str(x).strip().lower() for x in (analysis.get("side_effects") or [])]
    if not effects:
        codes.append("llm_side_effects_empty")
        return False, codes
    if any(e != SIDE_READ and e != "read_query" for e in effects):
        codes.append("llm_side_effects_not_readonly_only")
        return False, codes

    similar = [str(x).strip() for x in (analysis.get("similar_known_ops") or []) if str(x).strip()]
    if not similar:
        codes.append("llm_similar_known_ops_required")
        return False, codes

    confidence = str(analysis.get("confidence") or "low").lower()
    if confidence not in ("medium", "high"):
        codes.append("llm_confidence_too_low_for_experiment_candidate")
        return False, codes

    if len(summary) < 12:
        codes.append("llm_operation_summary_too_thin")
        return False, codes

    codes.append("llm_mechanical_experiment_candidate_presentation_ok")
    return True, codes


def _is_safe_only_claim(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return True
    return bool(
        re.fullmatch(
            r"(安全です|問題ありません|危険ではありません|safe)[。．!！]?",
            t,
            flags=re.I,
        )
    )
