"""One-shot: Local LLM semantic-need selection. Observation only.

Does not modify Production Runtime, Help, Registry, or Capability Resolution.
Does not call tools. Does not send expected answers or Registry tool names.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

from research.grill_observation_v0.natural_exit_v0.run import call_freeform

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

# Prompt text is the observation case only. No expected example. No Tool / Help names.
USER = """Goal:

gridを検索して、その内容を要約してほしい。

Current State:

まだ何も調査していない。

質問:

このGoalを満たすために、
今の時点で次に満たす必要があることを1つだけ答えてください。

具体的なTool名、関数名、Capability ID、実装方法ではなく、
「何を知る・確認する・行う必要があるか」
という意味レベルで答えてください。

一度に1つだけ答えてください。
"""


def main() -> int:
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "user", "content": USER}]
    (run_dir / "USER.txt").write_text(USER, encoding="utf-8")
    (run_dir / "prompt.json").write_text(
        json.dumps(
            {
                "messages": messages,
                "note": "No system message. No expected example. No Registry/Help/Tool names.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    call = call_freeform(
        model=provider,
        messages=messages,
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label="semantic_need_T1",
    )
    raw = str(call.get("raw_text") or "")
    (run_dir / "qwen_raw.txt").write_text(raw, encoding="utf-8")
    record = {
        "experiment": "semantic_need_v0",
        "run_id": run_id,
        "model_id": model_id,
        "model": provider,
        "profile": {
            "context_limit": profile.get("context_limit"),
            "num_predict": profile.get("num_predict"),
            "temperature": profile.get("temperature"),
            "hard_timeout_seconds": profile.get("hard_timeout_seconds"),
        },
        "messages": messages,
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "verdict": None,
        "verdict_reason": "Observer fills after reading qwen_raw.txt. Not computed by harness.",
        "note": "One case. No tools. No Help. Production unchanged. Stop after save.",
    }
    (run_dir / "run.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(raw, flush=True)
    print(f"RUN {run_dir}", flush=True)
    return 1 if call.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
