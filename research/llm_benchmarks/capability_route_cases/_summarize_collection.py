import json
from pathlib import Path

roots = [
    Path("research/llm_benchmarks/capability_route_obs/collect_20260821_155753"),
    Path("research/llm_benchmarks/capability_route_obs/collect_batch_remaining"),
]
for root in roots:
    if not root.exists():
        continue
    print("===", root.name)
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        log = d / "capability_route.jsonl"
        if not log.is_file():
            continue
        rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        s1 = next((r for r in rows if r.get("kind") == "capability_route_observation"), {})
        s2 = next((r for r in rows if r.get("kind") == "capability_outcome_compare"), {})
        route = (s1.get("capability_route") or {}).get("route")
        webj = (s1.get("web_search") or {}).get("judgment") or {}
        webe = (s1.get("web_search") or {}).get("execution") or {}
        pattern = (s2.get("compare_summary") or {}).get("web_pattern")
        answer = ((s2.get("chain") or {}).get("final_answer") or {}).get("outcome_proxy")
        print(
            f"{d.name}: route={route} judged_web={webj.get('judged_appropriate')} "
            f"called={webe.get('called')} outcomes={webe.get('outcomes')} "
            f"pattern={pattern} answer={answer}"
        )
