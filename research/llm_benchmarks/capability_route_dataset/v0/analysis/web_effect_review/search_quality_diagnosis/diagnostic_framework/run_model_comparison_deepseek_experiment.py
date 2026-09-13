"""
Qwen3:8b vs DeepSeek-Coder-V2 16B 診断モデル比較。
本番 Tool は変更しない。既存実験は上書きしない。
Qwen は再実行せず既存成果物を参照コピーする。
DeepSeek には既存実験の実プロンプトを可能な限りそのまま送る。
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama import Client

from tools.system.config import get_llm_profile

from run_spec_experiment import THIS_DIR, estimate_tokens, extract_json, chat

RUNS_DIR = THIS_DIR / "runs"

# 既存 Qwen 実験（再実行しない）
QWEN_CODE = RUNS_DIR / "20260824_082857" / "code_reading_experiment"
QWEN_ROUTE = RUNS_DIR / "20260824_195842" / "route_decomposition_experiment"
QWEN_N2 = RUNS_DIR / "20260824_212236" / "n2_execution_path_gate"


def split_system_user(prompt_text: str) -> tuple[str, str]:
    text = prompt_text.replace("\r\n", "\n")
    if "[SYSTEM]" in text and "[USER]" in text:
        after_sys = text.split("[SYSTEM]", 1)[1]
        system, user = after_sys.split("[USER]", 1)
        return system.strip(), user.strip()
    return "", text.strip()


def extract_phase(prompt_md: str, phase_header: str) -> str:
    text = prompt_md.replace("\r\n", "\n")
    marker = f"===== {phase_header} ====="
    if marker not in text:
        return text
    rest = text.split(marker, 1)[1]
    nxt = rest.find("\n===== ")
    if nxt != -1:
        rest = rest[:nxt]
    return rest.strip()


def write_md(path: Path, title: str, parsed: dict | None, raw: str, extra: str = "") -> None:
    body = [f"# {title}", ""]
    if extra:
        body.extend([extra, ""])
    if parsed:
        body.append("```json")
        body.append(json.dumps(parsed, ensure_ascii=False, indent=2))
        body.append("```")
    else:
        body.append("（JSON 解析失敗。原文は raw）")
        body.append("")
        body.append("```")
        body.append((raw or "")[:40000])
        body.append("```")
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def copy_qwen(src: Path, dst: Path) -> None:
    dst.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")


def try_chat(
    client: Client,
    model: str,
    system: str,
    user: str,
    num_ctx: int,
    num_predict: int,
) -> tuple[str, dict | None, int, str | None]:
    """Returns raw, parsed, used_ctx, error."""
    try:
        raw = chat(client, model, system, user, num_ctx, num_predict)
        return raw, extract_json(raw), num_ctx, None
    except Exception as exc:  # noqa: BLE001 — record Ollama/ctx failures
        return "", None, num_ctx, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="deepseek_coder_v2_16b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--fallback-num-ctx", type=int, default=16384)
    ap.add_argument("--num-predict", type=int, default=4096)
    args = ap.parse_args()

    profile = get_llm_profile(args.model_id)
    model = profile["model"]
    client = Client(timeout=600)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / run_id / "model_comparison_deepseek"
    out.mkdir(parents=True, exist_ok=True)
    prompts_dir = out / "prompts_deepseek"
    prompts_dir.mkdir(exist_ok=True)

    # --- Qwen artifacts (copy, do not re-run) ---
    copy_qwen(QWEN_CODE / "TEST_A_CODE_READING.md", out / "TEST_A_CODE_READING_QWEN.md")
    copy_qwen(QWEN_CODE / "TEST_B_CODE_LOG_ANALYSIS.md", out / "TEST_B_CODE_LOG_QWEN.md")
    copy_qwen(QWEN_CODE / "TEST_C_CAUSE_DIAGNOSIS.md", out / "TEST_C_CAUSE_QWEN.md")
    copy_qwen(QWEN_ROUTE / "TEST_A_phase2_connections.md", out / "TEST_D_ROUTE_QWEN.md")
    copy_qwen(QWEN_N2 / "TEST_B_GATE_raw.txt", out / "TEST_E_GATE_QWEN.md")
    # keep a readable json wrapper for E qwen
    qwen_e = (QWEN_N2 / "results" / "TEST_B.json").read_text(encoding="utf-8")
    (out / "TEST_E_GATE_QWEN.md").write_text(
        "# TEST-E N2 ゲート（Qwen3:8b 既存結果・再実行なし）\n\n"
        "出典: `runs/20260824_212236/n2_execution_path_gate/results/TEST_B.json`\n\n"
        "```json\n" + qwen_e + "\n```\n",
        encoding="utf-8",
    )

    tests = [
        {
            "id": "TEST_A",
            "out_md": "TEST_A_CODE_READING_DEEPSEEK.md",
            "prompt_src": QWEN_CODE / "actual_llm_prompt_TEST_A.txt",
            "phase": None,
        },
        {
            "id": "TEST_B",
            "out_md": "TEST_B_CODE_LOG_DEEPSEEK.md",
            "prompt_src": QWEN_CODE / "actual_llm_prompt_TEST_B.txt",
            "phase": None,
        },
        {
            "id": "TEST_C",
            "out_md": "TEST_C_CAUSE_DEEPSEEK.md",
            "prompt_src": QWEN_CODE / "actual_llm_prompt_TEST_C.txt",
            "phase": None,
        },
        {
            "id": "TEST_D",
            "out_md": "TEST_D_ROUTE_DEEPSEEK.md",
            "prompt_src": QWEN_ROUTE / "actual_llm_prompt_TEST_A.md",
            "phase": "phase2_connections",
        },
        {
            "id": "TEST_E",
            "out_md": "TEST_E_GATE_DEEPSEEK.md",
            "prompt_src": QWEN_N2 / "prompts" / "TEST_B.txt",
            "phase": None,
        },
    ]

    results: dict[str, Any] = {}
    measurements = []
    ctx_notes: list[str] = []

    for t in tests:
        src_text = t["prompt_src"].read_text(encoding="utf-8", errors="replace")
        if t["phase"]:
            src_text = extract_phase(src_text, t["phase"])
        system, user = split_system_user(src_text)
        (prompts_dir / f"{t['id']}.txt").write_text(
            f"[SYSTEM]\n{system}\n\n[USER]\n{user}", encoding="utf-8"
        )
        est = estimate_tokens(system + user)
        print(t["id"], "tokens_est", est, "chars", len(system) + len(user), flush=True)

        used_ctx = args.num_ctx
        raw, parsed, used_ctx, err = try_chat(
            client, model, system, user, args.num_ctx, args.num_predict
        )
        if err or (not raw and not parsed):
            print("  retry fallback ctx", args.fallback_num_ctx, "err", err, flush=True)
            ctx_notes.append(
                f"{t['id']}: num_ctx={args.num_ctx} failed ({err}); retry {args.fallback_num_ctx}"
            )
            raw, parsed, used_ctx, err2 = try_chat(
                client, model, system, user, args.fallback_num_ctx, args.num_predict
            )
            if err2:
                ctx_notes.append(f"{t['id']}: fallback also failed ({err2})")
                raw = raw or f"ERROR: {err2}"

        extra = (
            f"- model: `{model}` (`{args.model_id}`)\n"
            f"- num_ctx_used: {used_ctx}\n"
            f"- prompt_tokens_est: {est}\n"
            f"- source_prompt: `{t['prompt_src'].as_posix()}`"
            + (f" phase={t['phase']}" if t["phase"] else "")
            + "\n"
            f"- Qwen 再実行なし。同一保存プロンプトを DeepSeek へ送信。"
        )
        write_md(out / t["out_md"], t["id"] + " DeepSeek-Coder-V2 16B", parsed, raw, extra)
        (out / f"{t['id']}_raw.txt").write_text(raw or "", encoding="utf-8")
        meas = {
            "test": t["id"],
            "prompt_chars": len(system) + len(user),
            "prompt_tokens_est": est,
            "output_chars": len(raw or ""),
            "parsed": bool(parsed),
            "num_ctx_used": used_ctx,
            "error": err,
        }
        measurements.append(meas)
        results[t["id"]] = {
            "parsed": parsed,
            "num_ctx_used": used_ctx,
            "source_prompt": str(t["prompt_src"]),
            "qwen_not_rerun": True,
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deepseek_model": model,
        "deepseek_model_id": args.model_id,
        "qwen_model": "qwen3:8b",
        "requested_num_ctx": args.num_ctx,
        "fallback_num_ctx": args.fallback_num_ctx,
        "num_predict": args.num_predict,
        "temperature": 0,
        "qwen_sources": {
            "TEST_A_B_C": str(QWEN_CODE),
            "TEST_D": str(QWEN_ROUTE / "TEST_A_phase2_connections.md"),
            "TEST_E": str(QWEN_N2 / "results" / "TEST_B.json"),
        },
        "ctx_notes": ctx_notes,
        "profile_yaml_context_limit": profile.get("context_limit"),
        "measurements": measurements,
        "tests": results,
        "implementation_changed": False,
        "note": "人間比較は COMPARISON_REPORT.md。Qwen は既存結果。DeepSeek のみ新規実行。",
    }
    (out / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with (out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "test",
                "prompt_tokens_est",
                "output_chars",
                "parsed",
                "num_ctx_used",
                "error",
            ]
        )
        for m in measurements:
            w.writerow(
                [
                    m["test"],
                    m["prompt_tokens_est"],
                    m["output_chars"],
                    m["parsed"],
                    m["num_ctx_used"],
                    m.get("error") or "",
                ]
            )

    (out / "README.md").write_text(
        "\n".join(
            [
                "# model_comparison_deepseek",
                "",
                "Qwen3:8b（既存結果）vs DeepSeek-Coder-V2 16B（新規実行）。",
                "本番 search_web / Agent / ranking は未変更。",
                "Qwen は再実行していない。DeepSeek には既存の実プロンプトを送信。",
                "",
                f"DeepSeek model={model} requested_num_ctx={args.num_ctx} temperature=0",
                "profile yaml context_limit は 4096 だが実験は 32768 を試行（失敗時 16384）。",
                "",
                "評価は COMPARISON_REPORT.md。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("done", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
