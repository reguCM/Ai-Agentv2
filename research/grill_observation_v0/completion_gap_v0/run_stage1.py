"""Completion Gap Grill v0 — Stage 1: one Gap Grill cycle, no implementation.

Technical Specification is loaded from the natural-exit run. Not invented here.
Current State is measured from the experiment workspace, not from chat history.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
WORKSPACE = HERE / "workspace"
SOURCE = ROOT / "research" / "grill_observation_v0" / "natural_exit_v0" / "runs" / "20260909T012036Z"

# Same assembled spec as grill_to_code_v0, taken from SOURCE files. No added meaning.
TECHNICAL_SPEC = """Goal:
簡単なテトリスを作る。

仕様:
- Pythonで作る
- Pygameを使う
- ゲームの基本機能の範囲: 初期実装では「テトロミノの落下・移動・回転」「行の削除」「ゲームオーバー判定」を実装し、後でスコアやレベルアップを追加する。
- ゲーム画面のサイズとグリッドの設定: 標準的なテトリスのグリッド（10×20）を採用し、1ブロックを30×30ピクセルに設定。画面サイズは300×600ピクセル。
- ゲームループの構造:
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    # ゲーム状態の更新
    # 画面の描画
    pygame.display.flip()
  この構造をベースに、処理を細分化する。
- テトロミノの形状と初期配置: 各テトロミノを2次元配列で定義し、回転時に行列の転置と反転を用いて処理。
- 衝突判定の実装方法: 移動後のテトロミノの各ブロックの座標を計算し、グリッドの範囲外または既存ブロックと重なっている場合に衝突と判定。
- 行の削除（ラインクリア）のロジック: 各行をチェックし、すべてのセルが埋まっている場合に削除。上にある行を下にシフトし、スコアを加算。
- ゲームオーバーの判定条件: 新しいテトロミノを生成し、初期位置（グリッドの上部）に配置できない場合にゲームオーバーと判定。
- ゲームの速度（落下速度）の調整: pygame.time.get_ticks()を用いて、一定時間（例: 500ms）ごとにテトロミノを下に移動。
"""

SYSTEM = """確定仕様と現在地点を比較する。
完成までにまだ不足しているものの中から、今、次に解消すべきものを1つだけ選ぶ。
一度に複数の作業へ進まない。
実装上必要なことが決まっていない場合だけ質問を1つする。
コードベースや環境を調べれば判断できることは人間へ聞かない。
確定仕様を満たしており、追加で必要なものが無ければ、完成可能な状態であることを回答する。
Development Plan全体や全Work一覧は出さない。
"""

USER_QUESTION = """確定仕様と現在地点を比較してください。

完成までにまだ不足しているものの中から、
今、次に解消すべきものを1つだけ選んでください。

一度に複数の作業へ進まないでください。

実装上必要なことが決まっていない場合だけ
質問を1つしてください。

コードベースや環境を調べれば判断できることは
人間へ聞かないでください。

確定仕様を満たしており、
追加で必要なものが無ければ、
完成可能な状態であることを回答してください。
"""


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_source_files() -> dict[str, str]:
    return {
        "SYSTEM.txt": (SOURCE / "SYSTEM.txt").read_text(encoding="utf-8"),
        "completed_before_T1.json": (SOURCE / "snapshots" / "completed_before_T1.json").read_text(encoding="utf-8"),
        "turn_1_raw.txt": (SOURCE / "turn_1_raw.txt").read_text(encoding="utf-8"),
    }


def measure_current_state() -> dict[str, Any]:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    files = sorted(
        str(p.relative_to(WORKSPACE)).replace("\\", "/")
        for p in WORKSPACE.rglob("*")
        if p.is_file()
    )
    env = dict(os.environ)
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    py = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    pg = subprocess.run(
        [sys.executable, "-c", "import pygame; print(pygame.version.ver)"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    pygame_ok = pg.returncode == 0
    return {
        "kind": "observed_facts",
        "experiment_workspace": str(WORKSPACE),
        "files_in_workspace": files,
        "implemented_content": "NOT OBSERVED: no game source files in experiment workspace",
        "python": (py.stdout or "").strip() if py.returncode == 0 else None,
        "pygame_import_ok": pygame_ok,
        "pygame_version": (pg.stdout or "").strip() if pygame_ok else None,
        "pygame_import_error": (pg.stderr or "").strip() if not pygame_ok else None,
        "tests": {
            "ran": False,
            "result": "NOT OBSERVED: no tetris tests have been run in this experiment",
        },
        "errors": [],
        "last_completed_gap": None,
        "note": "Facts only. No inferred game features.",
    }


def build_user(spec: str, state: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# 確定Technical Specification",
            spec.strip(),
            "",
            "# 実際のCurrent State",
            json.dumps(state, ensure_ascii=False, indent=2),
            "",
            USER_QUESTION,
        ]
    )


def classify(raw: str) -> dict[str, Any]:
    """Observer-only. Does not edit raw."""
    text = str(raw or "")
    complete = bool(
        re.search(r"完成可能な状態", text)
        or re.search(r"追加で必要なもの(は|が)無", text)
        or re.search(r"確定仕様を満たして(いる|おり)", text)
        or re.search(r"Gap(が|は)無", text, flags=re.I)
    )
    question = bool(
        re.search(r"(質問|聞かせて|教えてください|どちらにしますか)", text)
        and re.search(r"[？?]", text)
    )
    if complete and not re.search(r"次に(解消|実装|作る)", text):
        kind = "COMPLETE"
    elif question and not re.search(r"次に解消すべき", text):
        kind = "QUESTION"
    else:
        kind = "NEXT"
    gap = ""
    m = re.search(r"(?:次に(?:解消|着手|実装)すべき(?:もの|Gap|ギャップ)?[:：]?\s*)(.+)", text)
    if m:
        gap = m.group(1).strip().split("\n")[0]
    elif kind == "NEXT":
        m2 = re.search(r"^#+\s+(.+)$", text, flags=re.M)
        if m2:
            gap = m2.group(1).strip()
    return {
        "classification": kind,
        "selected_gap": gap,
        "note": "Observer classification. Raw response is stored separately and not rewritten.",
    }


def main() -> int:
    sources = load_source_files()
    state = measure_current_state()
    user = build_user(TECHNICAL_SPEC, state)
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = _utc()
    run_dir = RUNS / run_id
    cycle_dir = run_dir / "cycle_1"
    cycle_dir.mkdir(parents=True, exist_ok=True)

    call = call_freeform(
        model=provider,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label="gap_c1",
    )
    raw = str(call.get("raw_text") or "")
    judged = classify(raw)
    record = {
        "experiment": "completion_gap_v0",
        "stage": 1,
        "run_id": run_id,
        "cycle": 1,
        "model": provider,
        "source_spec_run": str(SOURCE),
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "classification": judged["classification"],
        "selected_gap": judged["selected_gap"],
        "implementation": None,
        "tests": None,
        "stopped": "stage1_after_gap_grill",
        "note": "Stage 1 only. No implementation. Prior runs not modified.",
    }
    (cycle_dir / "technical_specification.txt").write_text(TECHNICAL_SPEC, encoding="utf-8")
    _dump(cycle_dir / "current_state.json", state)
    (cycle_dir / "gap_grill_system.txt").write_text(SYSTEM, encoding="utf-8")
    (cycle_dir / "gap_grill_user.txt").write_text(user, encoding="utf-8")
    (cycle_dir / "qwen_raw.txt").write_text(raw, encoding="utf-8")
    _dump(cycle_dir / "classification.json", judged)
    _dump(cycle_dir / "source_files.json", {k: "loaded" for k in sources})
    (cycle_dir / "source_SYSTEM.txt").write_text(sources["SYSTEM.txt"], encoding="utf-8")
    (cycle_dir / "source_completed_before_T1.json").write_text(
        sources["completed_before_T1.json"], encoding="utf-8"
    )
    (cycle_dir / "source_turn_1_raw.txt").write_text(sources["turn_1_raw.txt"], encoding="utf-8")
    _dump(run_dir / "run.json", record)
    print(raw, flush=True)
    print(f"CLASSIFICATION {judged['classification']}", flush=True)
    print(f"SELECTED_GAP {judged['selected_gap']}", flush=True)
    print(f"RUN {run_dir}", flush=True)
    print("STOPPED Stage 1. No implementation.", flush=True)
    return 1 if call.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
