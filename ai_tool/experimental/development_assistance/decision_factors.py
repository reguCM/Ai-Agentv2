"""Decision factors from existing Candidate metadata — no Decision Matrix Core."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai_tool.experimental.development_assistance.version_facts import version_facts_from_candidate

FactorStatus = Literal["match", "partial", "unknown", "conflict", "not_applicable"]


@dataclass
class DecisionFactor:
    factor: str
    status: FactorStatus
    detail: str
    candidate_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UserConstraints:
    os: str = ""
    python: str = ""
    gpu: str = ""
    cuda: str = ""
    license_preference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}


def _python_compatible(stated: str, required: str) -> FactorStatus:
    if not required or not stated or stated == "UNKNOWN":
        return "unknown"
    req = required.replace("Python ", "").strip()
    st = stated.replace("python", "").replace("Python ", "").strip()
    if req in st or st.startswith(req[:3]):
        return "match"
    if st and req:
        return "partial"
    return "unknown"


def compute_decision_factors(
    candidate: dict[str, Any],
    *,
    user_constraints: dict[str, str] | None = None,
) -> list[DecisionFactor]:
    """Derive decision factors — explains material, does not pick winner."""
    cid = str(candidate.get("candidate_id") or "")
    env = candidate.get("environment") or {}
    factors: list[DecisionFactor] = []

    vf = version_facts_from_candidate(candidate)
    if vf.version != "UNKNOWN":
        factors.append(
            DecisionFactor(
                "version",
                "match",
                f"Version {vf.version} ({vf.provenance})",
                cid,
            )
        )
    else:
        factors.append(DecisionFactor("version", "unknown", "Version not found in source", cid))

    py = env.get("python") or "UNKNOWN"
    req_py = (user_constraints or {}).get("python", "")
    factors.append(
        DecisionFactor(
            "python_compatibility",
            _python_compatible(py, req_py) if req_py else ("match" if py != "UNKNOWN" else "unknown"),
            f"Documented: {py}" + (f"; required: {req_py}" if req_py else ""),
            cid,
        )
    )

    lic = str(candidate.get("license") or "UNKNOWN")
    pref = (user_constraints or {}).get("license_preference", "")
    if lic == "UNKNOWN":
        lic_status: FactorStatus = "unknown"
    elif pref and pref.lower() in lic.lower():
        lic_status = "match"
    elif "GPL" in lic and pref and "MIT" in pref:
        lic_status = "conflict"
    else:
        lic_status = "match" if lic != "UNKNOWN" else "unknown"
    factors.append(
        DecisionFactor("license", lic_status, f"License: {lic}", cid)
    )

    scat = candidate.get("source_category") or "Other"
    factors.append(
        DecisionFactor(
            "official_source",
            "match" if "Official" in scat else "partial",
            f"Source type: {scat}",
            cid,
        )
    )

    if env.get("cuda") or env.get("gpu"):
        req_cuda = (user_constraints or {}).get("cuda", "")
        cuda_val = env.get("cuda") or env.get("gpu") or "UNKNOWN"
        if req_cuda and req_cuda.lower() in str(cuda_val).lower():
            c_st: FactorStatus = "match"
        elif req_cuda:
            c_st = "partial"
        else:
            c_st = "match"
        factors.append(
            DecisionFactor("cuda_compatibility", c_st, f"Documented: {cuda_val}", cid)
        )

    unknowns = candidate.get("unknowns") or []
    if unknowns:
        factors.append(
            DecisionFactor(
                "unknown_count",
                "partial",
                f"Unknown fields: {', '.join(unknowns)}",
                cid,
            )
        )

    conflicts = candidate.get("conflicts") or []
    if conflicts:
        factors.append(
            DecisionFactor(
                "conflict",
                "conflict",
                f"{len(conflicts)} conflict(s) observed — not auto-resolved",
                cid,
            )
        )

    return factors


def compare_candidates_for_decision(
    candidates: list[dict[str, Any]],
    *,
    user_constraints: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Summarize decision material across candidates — not a mechanical ranking."""
    per_cand: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        if c.get("type") == "Custom Build":
            continue
        cid = str(c.get("candidate_id") or "")
        per_cand[cid] = [f.to_dict() for f in compute_decision_factors(c, user_constraints=user_constraints)]

    # Narrative hints (not scores)
    hints: list[str] = []
    for c in candidates:
        if c.get("type") == "Custom Build":
            continue
        cid = c.get("candidate_id")
        factors = per_cand.get(str(cid), [])
        matches = sum(1 for f in factors if f.get("status") == "match")
        unknowns = sum(1 for f in factors if f.get("status") == "unknown")
        hints.append(
            f"{c.get('name')} ({cid}): {matches} matching factors, {unknowns} unknown(s), "
            f"license={c.get('license')}, source={c.get('source_category')}"
        )

    return {
        "factors_by_candidate": per_cand,
        "comparison_hints": hints,
        "recommendation_style": "material_explanation_not_mechanical_winner",
    }


def infer_deciding_factors(
    selected_id: str | None,
    candidates: list[dict[str, Any]],
    *,
    user_message: str = "",
) -> list[str]:
    """Record what likely drove selection — observed post-hoc, not predetermined."""
    if not selected_id:
        return []
    cand = next((c for c in candidates if c.get("candidate_id") == selected_id), None)
    if not cand:
        return ["user_preference"]

    factors: list[str] = []
    msg = user_message.lower()
    if "license" in msg or "gpl" in msg or "mit" in msg:
        factors.append("license")
    if "python" in msg or "バージョン" in msg:
        factors.append("python_compatibility")
    if "cuda" in msg or "gpu" in msg:
        factors.append("cuda_compatibility")
    if "公式" in msg or "official" in msg:
        factors.append("official_source")
    if "b" in msg or "a" in msg:
        factors.append("user_candidate_preference")

    env = cand.get("environment") or {}
    if env.get("python") != "UNKNOWN" and "python_compatibility" not in factors:
        factors.append("python_compatibility")
    if cand.get("license") not in (None, "UNKNOWN") and "license" not in factors:
        factors.append("license")
    if cand.get("source_category") == "Official Documentation":
        factors.append("official_source_availability")
    if not factors:
        factors.append("documentation_quality")
    return list(dict.fromkeys(factors))
