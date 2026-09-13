"""最小 DevelopmentSpec。最終判定（安全 / 確実 / 実行可能）は含めない。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VERDICT_KEYS = ("feasible", "safe", "correct", "executable", "build", "確実に動く")


def development_spec_from_materials(materials: dict[str, Any]) -> dict[str, Any]:
    """選択済み材料だけから Spec を作る。LLM スタンドイン。記憶検索はしない。"""
    py = (materials.get("version") or {}).get("python") or ""
    env = materials.get("environment") or {}
    spec = {
        "target": materials.get("target") or "",
        "requirement": materials.get("requirement") or "",
        "environment": {
            "os": env.get("os") or "",
            "cuda": env.get("cuda") or "",
        },
        "version": {
            "python": {
                "current": py,
                "status": (materials.get("version") or {}).get("python_status"),
            }
        },
        "evidence": list(materials.get("evidence") or []),
        "unknown": list(materials.get("unknown") or []),
        "conflict": list(materials.get("conflict") or []),
        "reuse": list(materials.get("reused_facets") or []),
        "research_required": list(materials.get("research_required_facets") or []),
        "runtime": f"Python {py}" if py else "",
        "copied_from_old_python": False,
        "provenance_note": "Draft from selected Facets — not a safety/feasibility verdict",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verdicts_absent": True,
    }
    for k in VERDICT_KEYS:
        spec.pop(k, None)
        assert k not in spec
    return spec


def spec_has_verdict(spec: dict[str, Any]) -> bool:
    blob = str(spec)
    return any(k in spec or k in blob for k in ("feasible", "safe", "correct") if k in spec)
