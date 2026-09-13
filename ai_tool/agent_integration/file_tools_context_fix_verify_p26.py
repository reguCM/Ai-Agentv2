"""P2-6: context_limit=8192 修正後の本番経路検証（検証専用）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.agent_integration.file_tools_chain_diag_p25 import run_instrumented_chain
from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile

_REPO = Path(__file__).resolve().parents[2]

_USER_REQUEST = (
    "Tool Registryで read_file がどこで定義または参照されているか探して、"
    "重要なファイルを1つ選んで内容を確認してください。"
)
_RUNS = 3


def _is_type3_fabrication(trace: dict[str, Any]) -> bool:
    """search 後に read_file 未実行で最終回答がある = Type 3 疑い。"""
    if trace.get("read_file_after_search"):
        return False
    seq = trace.get("tool_sequence") or []
    if "search_files" not in seq:
        return False
    final = str(trace.get("final_answer") or "")
    if not final.strip():
        return True
    fabricated_hints = (
        "仮想" in final
        or "```python" in final
        or "読み取り結果" in final
        or ("def " in final and "read_file" in final.lower())
    )
    return fabricated_hints or len(final) > 200


def _run_verification() -> dict[str, Any]:
    profile = get_llm_profile()
    wide = search_files("read_file", path=".")
    payload_bytes = len(json.dumps(wide, ensure_ascii=False, indent=2).encode("utf-8"))

    out: dict[str, Any] = {
        "task_id": "FILE-TOOLS-CONTEXT-SIZE-FIX-P2-6",
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "llm_profile": profile,
        "search_inspection": {
            "match_count": wide.get("match_count"),
            "payload_bytes": payload_bytes,
            "truncated": wide.get("truncated"),
            "error": wide.get("error"),
        },
        "user_request": _USER_REQUEST,
        "path": "production tools.system.llm.chat + execute_registry_tool (instrumented_chain)",
        "p25f_reference": {
            "condition": "REF production + ctx=4096 → 0/3 native read_file",
            "fix_condition": "ctx=8192 → expected 3/3",
        },
        "runs": [],
    }

    for i in range(1, _RUNS + 1):
        trace = run_instrumented_chain(
            _USER_REQUEST,
            scenario_id=f"p26_verify_run{i}",
        )
        native_read_file = False
        read_file_executed = False
        for rnd in trace.get("rounds") or []:
            if rnd.get("llm_tool_names") and "read_file" in rnd["llm_tool_names"]:
                native_read_file = True
            if rnd.get("executed_tool") == "read_file":
                read_file_executed = True

        type3 = _is_type3_fabrication(trace)
        out["runs"].append(
            {
                "run_number": i,
                "native_read_file_generated": native_read_file,
                "read_file_executed": read_file_executed,
                "read_file_after_search": trace.get("read_file_after_search"),
                "type3_fabrication_suspected": type3,
                "tool_sequence": trace.get("tool_sequence"),
                "final_answer_preview": str(trace.get("final_answer") or "")[:400],
                "rounds_summary": [
                    {
                        "round_index": r.get("round_index"),
                        "llm_tool_names": r.get("llm_tool_names"),
                        "executed_tool": r.get("executed_tool"),
                        "match_count": r.get("match_count"),
                        "payload_bytes": r.get("payload_bytes"),
                    }
                    for r in (trace.get("rounds") or [])
                ],
            }
        )

    ok_runs = [
        r
        for r in out["runs"]
        if r["native_read_file_generated"]
        and r["read_file_executed"]
        and r["read_file_after_search"]
        and not r["type3_fabrication_suspected"]
    ]
    out["summary"] = {
        "runs_total": _RUNS,
        "pass_runs": len(ok_runs),
        "native_read_file_count": sum(1 for r in out["runs"] if r["native_read_file_generated"]),
        "read_file_executed_count": sum(1 for r in out["runs"] if r["read_file_executed"]),
        "type3_count": sum(1 for r in out["runs"] if r["type3_fabrication_suspected"]),
        "verdict": "PASS" if len(ok_runs) == _RUNS else ("PARTIAL" if ok_runs else "FAIL"),
    }
    return out


def main() -> Path:
    out = _run_verification()
    ts = out["timestamp"]
    run_dir = _REPO / "runs" / "ai_tool" / f"{ts}_file_tools_context_fix_verify_p26"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "verify.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Saved:", path)
    print("context_limit:", out["llm_profile"].get("context_limit"))
    print("verdict:", out["summary"]["verdict"])
    for r in out["runs"]:
        print(
            f"  run{r['run_number']}: native_rf={r['native_read_file_generated']} "
            f"executed={r['read_file_executed']} type3={r['type3_fabrication_suspected']} "
            f"seq={r['tool_sequence']}"
        )
    return path


if __name__ == "__main__":
    main()
