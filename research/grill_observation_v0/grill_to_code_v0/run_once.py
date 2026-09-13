"""One-shot: grill-me on natural-exit spec. Does not modify prior runs."""
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
SOURCE = (
    ROOT
    / "research"
    / "grill_observation_v0"
    / "natural_exit_v0"
    / "runs"
    / "20260909T012036Z"
)

# grill-me principles only. No extra steering.
SYSTEM = """共通理解に達するまで、計画のあらゆる面を質問する。
質問は1つずつ行い、各質問には推奨回答を付ける。
コードベースや環境から分かることはユーザーに聞かず、自分で調べる。
"""

# Spec taken from natural-exit T1 items + initial completed. No added tetris facts.
USER = """Goal:
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

この仕様を見てコードに移したいです。
何から始めたらいいですか？
"""


def main() -> int:
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    call = call_freeform(
        model=provider,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label="grill_to_code_T1",
    )
    record = {
        "experiment": "grill_to_code_v0",
        "run_id": run_id,
        "source_run": str(SOURCE),
        "model": provider,
        "system": SYSTEM,
        "user": USER,
        "raw_response": call.get("raw_text") or "",
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "note": "One shot. Prior runs not modified. No human answer. No T2.",
    }
    (run_dir / "SYSTEM.txt").write_text(SYSTEM, encoding="utf-8")
    (run_dir / "USER.txt").write_text(USER, encoding="utf-8")
    (run_dir / "raw.txt").write_text(str(call.get("raw_text") or ""), encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(call.get("raw_text") or "", flush=True)
    print(f"RUN {run_dir}", flush=True)
    return 1 if call.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
