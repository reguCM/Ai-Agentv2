"""Retry TEST_B/C/E for DeepSeek with shortened materials (same question schemas)."""

from __future__ import annotations

import json
from pathlib import Path

from ollama import Client

from tools.system.config import get_llm_profile

from run_code_reading_experiment import build_code_pack as build_code_pack_cre, load_evidence_text
from run_n2_execution_path_gate_experiment import N2_GATE_PROMPT
from run_spec_experiment import estimate_tokens, extract_json

OUT = Path(__file__).resolve().parent / "runs" / "20260824_234729" / "model_comparison_deepseek"
QWEN_CODE = Path(__file__).resolve().parent / "runs" / "20260824_082857" / "code_reading_experiment"
N2 = Path(__file__).resolve().parent / "runs" / "20260824_212236" / "n2_execution_path_gate"


def split_su(text: str) -> tuple[str, str]:
    text = text.replace("\r\n", "\n")
    after = text.split("[SYSTEM]", 1)[1]
    system, user = after.split("[USER]", 1)
    return system.strip(), user.strip()


def instr_before_code(user: str) -> str:
    for marker in ["注: Agent 公開", "## FILE"]:
        i = user.find(marker)
        if i != -1:
            return user[:i]
    return user[:5000]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prompts_deepseek").mkdir(exist_ok=True)

    code, _ = build_code_pack_cre()
    parts = load_evidence_text().split("===== CASE SEPARATOR =====")
    short_logs = "\n\n===== CASE SEPARATOR =====\n\n".join(parts[:4])
    cands = json.loads((N2 / "results" / "SHARED_GENERATE.json").read_text(encoding="utf-8"))

    profile = get_llm_profile("deepseek_coder_v2_16b")
    model = profile["model"]
    client = Client(timeout=1800)
    num_ctx = 16384
    num_predict = 4096

    sys_b, user_b_orig = split_su((QWEN_CODE / "actual_llm_prompt_TEST_B.txt").read_text(encoding="utf-8"))
    user_b = (
        instr_before_code(user_b_orig)
        + "\n\n【注意】DeepSeek 利用可能 ctx 不足のため、ログは12件中先頭4件のみ。"
        "設問スキーマは Qwen 実行時と同一。\n\n"
        + code
        + "\n\n--- 実測ログ（短縮） ---\n"
        + short_logs
    )

    sys_c, user_c_orig = split_su((QWEN_CODE / "actual_llm_prompt_TEST_C.txt").read_text(encoding="utf-8"))
    user_c = (
        instr_before_code(user_c_orig)
        + "\n\n【注意】DeepSeek 利用可能 ctx 不足のため、ログは先頭4件のみ。"
        "設問スキーマは同一。\n\n"
        + code
        + "\n\n--- 実測ログ（短縮） ---\n"
        + short_logs
    )

    sys_e = (
        "あなたは Tool 診断の補助をする。本番コードは修正しない。\n"
        "「コード上に関数がある」ことと「公開 search_web 実行経路で呼ばれる」ことを混同するな。\n"
        "一般知識で処理を補完するな。確認できなければ UNKNOWN。JSONのみ。日本語可。"
    )
    user_e = (
        N2_GATE_PROMPT
        + "\n--- 原因候補（自由生成・未フィルタ） ---\n"
        + json.dumps(cands.get("candidates") or cands, ensure_ascii=False, indent=2)
        + "\n\n【注意】DeepSeek ctx 制約のため実測ログ全文は省略。"
        "存在判定はコード根拠のみ。execution_observed は UNKNOWN としてよい。\n\n"
        "--- コード ---\n"
        + code
    )

    mapping = {
        "TEST_B": (sys_b, user_b, "TEST_B_CODE_LOG_DEEPSEEK.md"),
        "TEST_C": (sys_c, user_c, "TEST_C_CAUSE_DEEPSEEK.md"),
        "TEST_E": (sys_e, user_e, "TEST_E_GATE_DEEPSEEK.md"),
    }
    meta = []
    for name, (system, user, md_name) in mapping.items():
        est = estimate_tokens(system + user)
        print(name, "est", est, "chars", len(system) + len(user), flush=True)
        (OUT / "prompts_deepseek" / f"{name}_CTX_ADAPTED.txt").write_text(
            f"[SYSTEM]\n{system}\n\n[USER]\n{user}", encoding="utf-8"
        )
        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict},
            keep_alive="10m",
        )
        raw = str(getattr(getattr(resp, "message", None), "content", None) or "")
        parsed = extract_json(raw)
        (OUT / f"{name}_raw_ctx_adapted.txt").write_text(raw, encoding="utf-8")
        body = (
            f"# {name} DeepSeek-Coder-V2 16B（ctx適応版）\n\n"
            f"- model: `{model}`\n"
            f"- num_ctx_used: {num_ctx}\n"
            f"- prompt_tokens_est: {est}\n"
            "- **全文プロンプトは Ollama 利用可能 ctx 超過で失敗。"
            "設問スキーマは同一、ログ/材料を短縮。**\n"
            "- Qwen 比較時はこの制約を必ず併記すること。\n\n"
            "```json\n"
            + json.dumps(parsed or {"_raw": raw[:30000]}, ensure_ascii=False, indent=2)
            + "\n```\n"
        )
        (OUT / md_name).write_text(body, encoding="utf-8")
        meta.append({"name": name, "est": est, "parsed": bool(parsed), "out": len(raw)})
        print(name, "done", meta[-1], flush=True)

    (OUT / "ctx_adapted_retry.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("ALL DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
