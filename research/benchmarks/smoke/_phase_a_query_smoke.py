"""
Phase A: 5ケースの検索クエリ生成スモーク（Web検索は実行しない）。
"""
import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT

ROOT = REPO_ROOT
HERE = Path(__file__).resolve().parent

import json
import os
from pathlib import Path

os.environ.setdefault("AI_AGENT_SEARCH_INTENT_LLM", "0")

from tools.system.tool_builder.research.query_intent import (
    build_exploration_queries,
    build_followup_queries,
    extract_search_intent,
    normalize_query,
)
from tools.system.tool_builder.research.web import build_search_queries

CASES = [
    "WindowsのCPU温度を取得するToolを作ってください。",
    "Windowsのディスク使用率を取得するToolを作ってください。",
    "GPUの使用率を取得するToolを作ってください。",
    "GPU VRAMの使用量をMB単位で取得するToolを作ってください。",
    "Windowsのメモリ使用率を取得するToolを作ってください。",
]


def main():
    rows = []
    for request in CASES:
        intent = extract_search_intent(request, prefer_llm=False)
        exploration = build_exploration_queries(intent, max_queries=3)
        via_build = build_search_queries(
            {"kind": "output", "question": "output 'status' の取得方法"},
            subject={"subcategory": intent.get("target") if intent.get("target") != "unspecified" else ""},
            user_request=request,
            search_intent=intent,
            allow_legacy_fallback=False,
        )
        followup = build_followup_queries(
            intent,
            ["output 'status' の取得方法"],
            searched=exploration,
            max_queries=2,
        )
        row = {
            "request": request,
            "intent": intent,
            "exploration_queries": exploration,
            "build_search_queries": via_build,
            "followup_queries": followup,
            "checks": {
                "no_single_token_disk": all(
                    normalize_query(q) != "disk" for q in exploration + via_build
                ),
                "no_get_volume_hardcode": all(
                    "get-volume" not in q.lower() for q in exploration + via_build
                ),
                "no_disk_disk": all(
                    "disk disk" not in normalize_query(q)
                    for q in exploration + via_build + followup
                ),
            },
        }
        rows.append(row)
        print("=" * 60)
        print(request)
        print("intent:", json.dumps(intent, ensure_ascii=False))
        print("exploration:", exploration)
        print("followup:", followup)
        print("checks:", row["checks"])

    out = ROOT / "research" / "llm_benchmarks" / "phase_a_query_smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
