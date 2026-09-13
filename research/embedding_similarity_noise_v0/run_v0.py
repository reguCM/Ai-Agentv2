"""Independent Japanese input-noise embedding experiment. Not connected to Production / Grill."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

V0_RUN = ROOT / "research" / "embedding_similarity_v0" / "run_v0.py"
_SPEC = importlib.util.spec_from_file_location("embedding_similarity_v0_run", V0_RUN)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load helper module: {V0_RUN}")
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)

from ollama import Client

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "cases.json"
_SLOT_SPEC = importlib.util.spec_from_file_location("embedding_slot_metrics", HERE / "slot_metrics.py")
if _SLOT_SPEC is None or _SLOT_SPEC.loader is None:
    raise RuntimeError(f"cannot load slot_metrics: {HERE / 'slot_metrics.py'}")
slot_metrics = importlib.util.module_from_spec(_SLOT_SPEC)
_SLOT_SPEC.loader.exec_module(slot_metrics)
DEFAULT_GEN_MODEL = "qwen3:14b"
DEFAULT_EMBED_MODEL = "qwen3-embedding:0.6b"
NOISE_ORDER = [
    "clean",
    "typo",
    "conversion",
    "missing_char",
    "particle_drop",
    "colloquial",
    "filler",
    "restatement",
    "asr_like",
    "demonstrative",
    "compound",
]


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None or value != value:
        return None
    return round(value, digits)


def evaluate_query(
    query: dict[str, Any],
    ranked: list[dict[str, Any]],
    clean_eval: dict[str, Any] | None,
) -> dict[str, Any]:
    gold_id = str(query["gold_id"])
    gold_row = next((row for row in ranked if row["candidate_id"] == gold_id), None)
    top = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    gold_rank = gold_row["rank"] if gold_row else None
    gold_cosine = gold_row["cosine"] if gold_row else None
    top_id = top["candidate_id"] if top else None
    top_cosine = top["cosine"] if top else None
    second_id = second["candidate_id"] if second else None
    second_cosine = second["cosine"] if second else None
    gold_is_top = gold_rank == 1
    if gold_is_top and gold_cosine is not None and second_cosine is not None:
        gap_vs_second = _round(gold_cosine - second_cosine)
    elif gold_cosine is not None and top_cosine is not None:
        gap_vs_second = _round(gold_cosine - top_cosine)
    else:
        gap_vs_second = None
    clean_gold_cosine = (clean_eval or {}).get("gold_cosine")
    clean_gold_rank = (clean_eval or {}).get("gold_rank")
    delta_vs_clean = None
    if gold_cosine is not None and clean_gold_cosine is not None:
        delta_vs_clean = _round(gold_cosine - clean_gold_cosine)
    wrong_above_gold = []
    if gold_rank is not None:
        wrong_above_gold = [
            {
                "candidate_id": row["candidate_id"],
                "text": row["text"],
                "kind": row.get("kind"),
                "rank": row["rank"],
                "cosine": row["cosine"],
            }
            for row in ranked
            if row["candidate_id"] != gold_id and row["rank"] < gold_rank
        ]
    return {
        "query_id": query["id"],
        "anchor_id": query["anchor_id"],
        "noise_type": query["noise_type"],
        "query_text": query["text"],
        "note": query.get("note"),
        "gold_id": gold_id,
        "gold_rank": gold_rank,
        "gold_cosine": gold_cosine,
        "gold_is_top": gold_is_top,
        "top_id": top_id,
        "top_cosine": top_cosine,
        "second_id": second_id,
        "second_cosine": second_cosine,
        "gap_vs_second": gap_vs_second,
        "clean_gold_rank": clean_gold_rank,
        "clean_gold_cosine": clean_gold_cosine,
        "delta_vs_clean": delta_vs_clean,
        "wrong_above_gold": wrong_above_gold,
        "experimental_outcome": "gold_top" if gold_is_top else "gold_not_top",
    }


def summarize(evals: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evals:
        by_type[str(item["noise_type"])].append(item)
        by_anchor[str(item["anchor_id"])].append(item)

    def pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
        noisy = [row for row in rows if row["noise_type"] != "clean"]
        target = noisy if noisy else rows
        gold_top = [row for row in target if row.get("gold_is_top")]
        failed = [row for row in target if not row.get("gold_is_top")]
        ranks = [row["gold_rank"] for row in target if row.get("gold_rank") is not None]
        gaps = [row["gap_vs_second"] for row in target if row.get("gap_vs_second") is not None]
        deltas = [row["delta_vs_clean"] for row in target if row.get("delta_vs_clean") is not None]
        return {
            "n": len(target),
            "gold_top_n": len(gold_top),
            "gold_not_top_n": len(failed),
            "gold_top_rate": _round(len(gold_top) / len(target), 4) if target else None,
            "mean_gold_rank": _round(sum(ranks) / len(ranks), 3) if ranks else None,
            "mean_gap_vs_second": _round(sum(gaps) / len(gaps), 6) if gaps else None,
            "mean_delta_vs_clean": _round(sum(deltas) / len(deltas), 6) if deltas else None,
            "failed_query_ids": [row["query_id"] for row in failed],
        }

    type_rows = {key: pack(by_type[key]) for key in NOISE_ORDER if key in by_type}
    failed_types = [
        key
        for key, row in type_rows.items()
        if key != "clean" and row.get("gold_not_top_n")
    ]
    noisy = [row for row in evals if row["noise_type"] != "clean"]
    return {
        "all_noisy": pack(noisy),
        "by_noise_type": type_rows,
        "by_anchor": {key: pack(by_anchor[key]) for key in sorted(by_anchor)},
        "noise_types_with_gold_not_top": failed_types,
        "failed_queries": [
            {
                "query_id": row["query_id"],
                "noise_type": row["noise_type"],
                "anchor_id": row["anchor_id"],
                "query_text": row["query_text"],
                "gold_rank": row["gold_rank"],
                "gold_cosine": row["gold_cosine"],
                "top_id": row["top_id"],
                "top_cosine": row["top_cosine"],
                "gap_vs_second": row["gap_vs_second"],
                "delta_vs_clean": row["delta_vs_clean"],
                "wrong_above_gold": row["wrong_above_gold"],
            }
            for row in evals
            if row["noise_type"] != "clean" and not row.get("gold_is_top")
        ],
    }


def write_human_review(path: Path, record: dict[str, Any]) -> None:
    summary = record.get("summary") or {}
    lines = [
        "# Embedding similarity Japanese input noise v0",
        "",
        f"- run_id: `{record.get('run_id')}`",
        f"- embed_model: `{record.get('embed_model')}`",
        f"- backend: `{record.get('backend')}`",
        f"- device: `{record.get('device')}`",
        f"- embedding_method: `{record.get('embedding_method')}`",
        f"- gen_model: `{record.get('gen_model')}`",
        f"- with_gen: `{record.get('with_gen')}`",
        "- Production / Grill 接続: なし",
        "- 閾値正本化: なし",
        "- SELECTED規則: なし",
        "",
        "`gold_is_top` はこの候補集合で意図候補が1位だった観測。SELECTED規則ではない。",
        "",
        "## 資源",
        "",
    ]
    for snap in record.get("snapshots") or []:
        gpu = snap.get("gpu") or {}
        ram = snap.get("ram") or {}
        lines.append(
            f"- {snap.get('label')}: VRAM {gpu.get('vram_used')} / {gpu.get('vram_total')} MiB, "
            f"RAM used {ram.get('used_mb')} / {ram.get('total_mb')} MB"
        )
    slot_summary = ((record.get("slot_metrics") or {}).get("summary") or {})
    if slot_summary:
        lines.extend(
            [
                "",
                "## Agent slot（Goal / Meaning / Focus / Target Role）",
                "",
                "仮対応。Production スキーマではない。",
                "",
                f"- intended_slot_top: {slot_summary.get('intended_slot_top_n')}/{slot_summary.get('n')} "
                f"({slot_summary.get('intended_slot_top_rate')})",
                f"- correct_object_top: {slot_summary.get('correct_object_top_n')}/{slot_summary.get('n')} "
                f"({slot_summary.get('correct_object_top_rate')})",
                f"- confusion: {slot_summary.get('confusion_counts')}",
                f"- top_slot_type: {slot_summary.get('top_slot_type_counts')}",
                f"- failed: {slot_summary.get('failed_query_ids')}",
                "",
            ]
        )
        for item in slot_summary.get("failed") or []:
            lines.append(
                f"  - `{item.get('query_id')}` intended=`{item.get('intended_slot_id')}` "
                f"rank={item.get('intended_rank')} top=`{item.get('top_id')}` "
                f"{item.get('confusion')}"
            )
    lines.extend(["", "## ノイズ種別まとめ", ""])
    by_type = (summary.get("by_noise_type") or {})
    for noise_type in NOISE_ORDER:
        row = by_type.get(noise_type)
        if not row:
            continue
        lines.append(
            f"- `{noise_type}`: gold_top {row.get('gold_top_n')}/{row.get('n')} "
            f"mean_rank={row.get('mean_gold_rank')} "
            f"mean_gap={row.get('mean_gap_vs_second')} "
            f"mean_delta_vs_clean={row.get('mean_delta_vs_clean')} "
            f"failed={row.get('failed_query_ids')}"
        )
    lines.extend(
        [
            "",
            f"失敗したノイズ種別: {summary.get('noise_types_with_gold_not_top')}",
            "",
            "## 失敗ケース",
            "",
        ]
    )
    failed = summary.get("failed_queries") or []
    if not failed:
        lines.append("なし")
    for item in failed:
        lines.append(
            f"- `{item.get('query_id')}` [{item.get('noise_type')}] {item.get('query_text')} "
            f"gold_rank={item.get('gold_rank')} gold_cos={item.get('gold_cosine')} "
            f"top=`{item.get('top_id')}` {item.get('top_cosine')} "
            f"delta_vs_clean={item.get('delta_vs_clean')}"
        )
    lines.extend(["", "## 各クエリ", ""])
    for item in record.get("evaluations") or []:
        lines.append(
            f"### {item.get('query_id')} [{item.get('noise_type')}] {item.get('query_text')}"
        )
        lines.append("")
        lines.append(
            f"gold=`{item.get('gold_id')}` rank={item.get('gold_rank')} "
            f"cosine={item.get('gold_cosine')} gold_is_top=`{item.get('gold_is_top')}` "
            f"gap_vs_second={item.get('gap_vs_second')} "
            f"delta_vs_clean={item.get('delta_vs_clean')}"
        )
        lines.append("")
        ranked = next(
            (
                row.get("ranked")
                for row in record.get("results") or []
                if row.get("query_id") == item.get("query_id")
            ),
            [],
        )
        for row in ranked:
            marker = " GOLD" if row.get("candidate_id") == item.get("gold_id") else ""
            lines.append(
                f"- r{row.get('rank')} {row.get('cosine')} `{row.get('candidate_id')}` "
                f"{row.get('text')}{marker}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Japanese input-noise embedding harness")
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    parser.add_argument("--gen-model", default=DEFAULT_GEN_MODEL)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--keep-alive", default="30m")
    parser.add_argument("--with-gen", action="store_true")
    parser.add_argument("--run-suffix", default="")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    run_id = base.utc_stamp()
    suffix = f"_{args.run_suffix}" if args.run_suffix else ""
    out_dir = HERE / "runs" / f"{run_id}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = Client(timeout=180)
    snapshots = [base.snapshot("baseline")]

    gen_warmup = None
    if args.with_gen:
        gen_warmup = base.chat_ping(client, args.gen_model, args.keep_alive)
        snapshots.append(base.snapshot("after_gen_warmup"))

    texts: dict[str, str] = {}
    for item in cases["queries"]:
        texts[str(item["id"])] = str(item["text"])
    for item in cases["candidates"]:
        texts[str(item["id"])] = str(item["text"])

    vectors: dict[str, list[float]] = {}
    embed_timings: dict[str, Any] = {}
    embed_error = None
    first_embed_ms = None
    try:
        for key, text in texts.items():
            row = base.embed_one(client, args.embed_model, text, args.keep_alive)
            if first_embed_ms is None:
                first_embed_ms = row["elapsed_ms"]
            if not row.get("vector"):
                raise RuntimeError(f"empty embedding for {key}: keys={row.get('raw_keys')}")
            vectors[key] = row["vector"]
            embed_timings[key] = {"elapsed_ms": row["elapsed_ms"], "dim": row["dim"]}
    except Exception as exc:
        embed_error = f"{type(exc).__name__}:{exc}"

    snapshots.append(base.snapshot("after_embed"))
    gen_after = None
    if args.with_gen:
        gen_after = base.chat_ping(client, args.gen_model, args.keep_alive)
        snapshots.append(base.snapshot("after_gen_reping"))

    results = []
    evaluations: list[dict[str, Any]] = []
    if embed_error is None:
        candidate_vecs = {str(item["id"]): vectors[str(item["id"])] for item in cases["candidates"]}
        ranked_by_query: dict[str, list[dict[str, Any]]] = {}
        for query in cases["queries"]:
            qid = str(query["id"])
            ranked = base.rank_candidates(vectors[qid], candidate_vecs, cases["candidates"])
            ranked_by_query[qid] = ranked
            results.append(
                {
                    "query_id": qid,
                    "query_text": query["text"],
                    "noise_type": query["noise_type"],
                    "anchor_id": query["anchor_id"],
                    "embed_ms": embed_timings[qid]["elapsed_ms"],
                    "ranked": ranked,
                }
            )
        clean_by_anchor: dict[str, dict[str, Any]] = {}
        for query in cases["queries"]:
            if query["noise_type"] != "clean":
                continue
            ranked = ranked_by_query[str(query["id"])]
            clean_by_anchor[str(query["anchor_id"])] = evaluate_query(query, ranked, None)
        for query in cases["queries"]:
            ranked = ranked_by_query[str(query["id"])]
            clean_eval = None
            if query["noise_type"] != "clean":
                clean_eval = clean_by_anchor.get(str(query["anchor_id"]))
            evaluations.append(evaluate_query(query, ranked, clean_eval))

    record = {
        "run_id": run_id,
        "at": base.now_iso(),
        "status": "ok" if embed_error is None else "error",
        "embed_error": embed_error,
        "embed_model": args.embed_model,
        "gen_model": args.gen_model,
        "with_gen": bool(args.with_gen),
        "production_connected": False,
        "grill_connected": False,
        "threshold_canonicalized": False,
        "selected_rule_created": False,
        "vector_dim": next((row["dim"] for row in embed_timings.values()), None),
        "embed_timings": embed_timings,
        "first_embed_ms": first_embed_ms,
        "gen_warmup": gen_warmup,
        "gen_reping": gen_after,
        "snapshots": snapshots,
        "results": results,
        "evaluations": evaluations,
        "slot_metrics": slot_metrics.attach_slot_metrics(cases, results) if results else {},
        "summary": summarize(evaluations) if evaluations else {},
        "cases_path": str(Path(args.cases).resolve()),
        "run_suffix": args.run_suffix or None,
        "evaluation_definition": {
            "gold_is_top": "intended candidate is rank 1 in this candidate set",
            "gap_vs_second": "gold_cosine - second_cosine when gold is top; else gold_cosine - top_cosine",
            "delta_vs_clean": "noisy gold_cosine minus the same-anchor clean gold_cosine",
            "not_a_selected_rule": True,
            "no_canonical_threshold": True,
        },
    }
    (out_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "summary.json").write_text(
        json.dumps(record.get("summary") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_human_review(out_dir / "HUMAN_REVIEW.md", record)
    print(json.dumps({"run_id": run_id, "status": record["status"], "out": str(out_dir)}, ensure_ascii=False))
    return 0 if embed_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
