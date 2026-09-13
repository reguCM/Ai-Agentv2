"""Summarize a capability_route dataset results run for human review.

同一 observation_id で揃える観点:
- pre_web_answer_candidate（Webなしならどう答えたか）
- web_search called / outcomes（実際に検索したか・結果）
- final_answer（最終回答の表面）
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def _clip(text: object, n: int = 240) -> str | None:
    if text is None:
        return None
    s = str(text).replace("\r\n", "\n").replace("\n", " ").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def load_case_logs(run_dir: Path) -> list[dict]:
    rows = []
    for d in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        log = d / "capability_route.jsonl"
        if not log.is_file():
            continue
        entries = [
            json.loads(line)
            for line in log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        pre = next(
            (e for e in entries if e.get("kind") == "pre_web_answer_candidate"),
            {},
        )
        s1 = next(
            (e for e in entries if e.get("kind") == "capability_route_observation"),
            {},
        )
        s2 = next(
            (e for e in entries if e.get("kind") == "capability_outcome_compare"),
            {},
        )
        obs_ids = {
            e.get("observation_id")
            for e in (pre, s1, s2)
            if e.get("observation_id")
        }
        webj = (s1.get("web_search") or {}).get("judgment") or {}
        webe = (s1.get("web_search") or {}).get("execution") or {}
        chain = s2.get("chain") or {}
        answer = chain.get("final_answer") or {}
        pre_block = pre.get("pre_web_answer_candidate") or chain.get(
            "pre_web_answer_candidate"
        ) or {}
        web_results = chain.get("web_search_results") or {}
        if not web_results and webe:
            web_results = {
                "called": webe.get("called"),
                "call_count": webe.get("call_count"),
                "outcomes": webe.get("outcomes"),
            }

        rows.append(
            {
                "case_id": d.name,
                "observation_id": s1.get("observation_id")
                or pre.get("observation_id")
                or s2.get("observation_id"),
                "observation_id_aligned": len(obs_ids) <= 1,
                "category": (s1.get("extra") or {}).get("collection_category")
                or (pre.get("extra") or {}).get("collection_category"),
                "group_id": (s1.get("extra") or {}).get("collection_group_id"),
                "request": s1.get("request") or pre.get("request"),
                "route": (s1.get("capability_route") or {}).get("route"),
                "route_reason": (s1.get("capability_route") or {}).get("reason"),
                "judged_web": webj.get("judged_appropriate"),
                "web_called": webe.get("called"),
                "web_outcomes": webe.get("outcomes"),
                "web_primary_outcome": (chain.get("web_execution") or {}).get(
                    "primary_outcome"
                )
                or (
                    (webe.get("outcomes") or [None])[0]
                    if webe.get("outcomes")
                    else None
                ),
                "web_hit_digest_preview": [
                    {
                        "title": (h or {}).get("title"),
                        "url": (h or {}).get("url"),
                    }
                    for call in (web_results.get("calls") or [])
                    for h in (call.get("hit_digest") or [])[:3]
                ][:5],
                "tools_tried": [
                    t.get("tool_name") for t in (s1.get("agent_tools_tried") or [])
                ],
                "web_pattern": (s2.get("compare_summary") or {}).get("web_pattern"),
                "pre_web_surface": (pre_block.get("surface") or {}).get("status"),
                "pre_web_proxy": (pre_block.get("surface") or {}).get("outcome_proxy"),
                "pre_web_char_count": pre_block.get("char_count"),
                "pre_web_preview": _clip(pre_block.get("content"), 280),
                "pre_web_generation_error": pre_block.get("generation_error"),
                "answer_surface": answer.get("status"),
                "answer_proxy": answer.get("outcome_proxy"),
                "answer_char_count": answer.get("char_count"),
                "has_pre_web_event": bool(pre),
                "kinds_present": [e.get("kind") for e in entries if e.get("kind")],
                "misjudgment_classification": s2.get("misjudgment_classification"),
            }
        )
    return rows


def write_compare_csv(rows: list[dict], path: Path) -> None:
    fields = [
        "case_id",
        "observation_id",
        "observation_id_aligned",
        "category",
        "request",
        "pre_web_preview",
        "pre_web_surface",
        "pre_web_proxy",
        "web_called",
        "web_primary_outcome",
        "web_outcomes",
        "answer_surface",
        "answer_proxy",
        "web_pattern",
        "route",
        "judged_web",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["web_outcomes"] = json.dumps(
                row.get("web_outcomes") or [], ensure_ascii=False
            )
            writer.writerow(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--write", type=Path, default=None)
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    rows = load_case_logs(args.run_dir)

    judged_call = Counter()
    for r in rows:
        key = (
            "judged_yes" if r["judged_web"] else "judged_no",
            "called" if r["web_called"] else "not_called",
        )
        judged_call[key] += 1

    routes = Counter(r["route"] for r in rows)
    patterns = Counter(r["web_pattern"] for r in rows)
    pre_web_n = sum(1 for r in rows if r.get("has_pre_web_event"))
    aligned_n = sum(1 for r in rows if r.get("observation_id_aligned"))

    paraphrase = defaultdict(list)
    for r in rows:
        if r.get("group_id"):
            paraphrase[r["group_id"]].append(
                {
                    "case_id": r["case_id"],
                    "route": r["route"],
                    "judged_web": r["judged_web"],
                    "web_called": r["web_called"],
                    "web_pattern": r["web_pattern"],
                    "pre_web_surface": r.get("pre_web_surface"),
                    "answer_proxy": r.get("answer_proxy"),
                }
            )

    report = {
        "run_dir": str(args.run_dir),
        "case_count": len(rows),
        "pre_web_event_count": pre_web_n,
        "observation_id_aligned_count": aligned_n,
        "route_counts": dict(routes),
        "web_judge_vs_call": {
            f"{a}|{b}": n for (a, b), n in sorted(judged_call.items())
        },
        "web_pattern_counts": dict(patterns.most_common()),
        "paraphrase_groups": dict(paraphrase),
        "cases": rows,
        "notes": [
            "No Stage3 misjudgment labels.",
            "success_candidate is surface proxy only.",
            "Do not treat heuristic routes as ground truth.",
            "pre_web vs final_answer is for human comparison; web usefulness is not auto-judged.",
        ],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    out = args.write or (args.run_dir / "human_summary.json")
    out.write_text(text, encoding="utf-8")
    csv_path = args.csv or (args.run_dir / "pre_web_compare.csv")
    write_compare_csv(rows, csv_path)
    print(f"wrote {out}")
    print(f"wrote {csv_path}")
    print("cases", len(rows))
    print("pre_web_events", pre_web_n)
    print("observation_id_aligned", aligned_n)
    print("routes", dict(routes))
    print("judge_vs_call", report["web_judge_vs_call"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
