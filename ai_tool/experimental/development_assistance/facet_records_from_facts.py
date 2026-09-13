"""実Research の環境・Version・License から Facet を機械的に切り出す。Core ではない。

build_research_record は run に facet_records が無いと空のままになる。
ここでは既存フィールドから導出するだけ。新しい記憶 Core は作らない。
"""
from __future__ import annotations

import re
from typing import Any

from ai_tool.experimental.development_assistance.research_record import ResearchRecord

_PY = re.compile(r"3\.\d+")
_CUDA = re.compile(r"12(?:\.\d+)?|11(?:\.\d+)?")
_PY_NAMED = re.compile(r"Python\s+3\.\d+", re.I)


def enrich_environment_from_candidates(rec: ResearchRecord) -> dict[str, str]:
    """TDA の Python 正規表現が 'Python library' を先に取ると Version が落ちる。既存抽出を壊さず補う。"""
    env = dict(rec.environment_facts or {})
    py = str(env.get("python") or "")
    if not _PY.search(py):
        repaired = ""
        for c in rec.technology_candidates:
            blob = " ".join(
                [
                    str(c.get("description") or ""),
                    str(c.get("name") or ""),
                    str(c.get("claim") or ""),
                    " ".join(str(v) for v in ((c.get("metadata") or {}).get("all_versions") or [])),
                ]
            )
            named = _PY_NAMED.search(blob)
            if named:
                repaired = named.group(0)
                break
            vers = [str(v) for v in ((c.get("metadata") or {}).get("all_versions") or []) if str(v).startswith("3.")]
            if vers:
                repaired = f"Python {vers[0]}"
                break
        if repaired:
            env["python"] = repaired
    rec.environment_facts = env
    return env


def derive_facet_records(rec: ResearchRecord) -> list[dict[str, Any]]:
    """environment_facts / version_facts / license_facts から Facet を足す。既存は残す。"""
    existing = list(rec.facet_records or [])
    have = {str(f.get("facet_id") or "") for f in existing}
    env = rec.environment_facts or {}
    added: list[dict[str, Any]] = []

    def _add(fid: str, family: str, aliases: list[str], evidence: list[str]) -> None:
        if fid in have or not evidence:
            return
        added.append(
            {
                "facet_id": fid,
                "family": family,
                "aliases": aliases,
                "evidence": evidence,
                "unknown": [],
                "conflicts": [],
            }
        )
        have.add(fid)

    py = str(env.get("python") or "")
    pm = _PY.search(py)
    if pm:
        _add("python_version", "environment", ["python", pm.group(0)], [py])
    os_name = str(env.get("os") or "")
    if os_name:
        _add("os", "environment", [os_name.lower()], [os_name])
    cuda = str(env.get("cuda") or "")
    cm = _CUDA.search(cuda)
    if cm:
        _add("cuda", "dependency", ["cuda", cm.group(0)], [cuda])
    if env.get("docker"):
        _add("docker", "container", ["docker"], [str(env["docker"])])
    if rec.license_facts:
        lic = str(rec.license_facts[0])
        _add("license", "license", ["license", lic.lower()], [lic])
    blob = " ".join(
        [
            rec.topic,
            rec.requirement,
            str(env),
            " ".join(str(c.get("name") or "") + " " + str(c.get("description") or "") for c in rec.technology_candidates),
        ]
    ).lower()
    if "ursim" in blob:
        _add("ursim", "runtime", ["ursim"], ["URSim"])
    if "ros" in blob:
        _add("ros", "middleware", ["ros"], ["ROS"])
    if "node.js" in blob or "nodejs" in blob:
        _add("nodejs", "runtime", ["nodejs", "node.js"], ["Node.js"])
    if "parse_a_payload" in blob or str(env.get("label") or "").upper() == "A":
        _add("product_api", "api", ["parse_a_payload", "liba"], ["parse_a_payload"])

    rec.facet_records = existing + added
    return added
