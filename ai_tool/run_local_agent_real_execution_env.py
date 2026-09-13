#!/usr/bin/env python3
"""Ollama 環境の読取のみ。実LLM / Tool / Search は呼ばない。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.chat_interface.ollama_env import describe_ollama_env
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow


def main() -> int:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_local_agent_real_execution"
    run_dir = _REPO / "runs" / "ai_tool" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    env = describe_ollama_env()
    wf = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )
    stopped = not env.get("configured_in_ollama_list")
    payload = {
        "run_id": run_id,
        "judgment": "STOPPED_FOR_USER_CONFIRM",
        "judgment_ja": (
            "設定モデルはディスク上にあるが、起動中の ollama list には無い。"
            "pull / 切替 / pipeline.yaml 変更はしていない。実LLMテストは未実施。"
        ),
        "production_changes": 0,
        "pipeline_yaml_changed": False,
        "ollama_pull": False,
        "model_switched": False,
        "live_llm_tests": False,
        "web_search_tests": False,
        "standard_workflow_default_discovery": wf.facet_discovery,
        "ollama": env,
        "tests": {
            "A": "未実施（実LLM停止）",
            "B": "未実施（実LLM停止）",
            "C": "未実施（実LLM停止）",
            "Web": "未実施（GPU実測が先）",
        },
        "stopped_for_user_confirm": stopped,
        "ask_user": (
            "起動中の Ollama に D:\\ollama\\models を見せて再起動してよいか。"
            "これは別モデルへの切替ではなく、設定モデル deepseek-coder-v2:16b を list に出すための確認。"
        ),
    }
    (run_dir / "observations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "judgment": payload["judgment"],
                "configured_model": env.get("configured_model"),
                "ollama_list": env.get("ollama_list"),
                "disk_manifests": env.get("disk_manifests"),
                "live_llm_tests": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({
        "judgment": payload["judgment"],
        "configured_model": env.get("configured_model"),
        "ollama_list": env.get("ollama_list"),
        "disk_manifests": env.get("disk_manifests"),
        "ask_user": payload["ask_user"],
    }, ensure_ascii=False, indent=2))
    print(f"wrote {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
