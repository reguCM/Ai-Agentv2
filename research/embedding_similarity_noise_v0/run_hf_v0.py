"""HuggingFace backends for the Japanese input-noise embedding experiment.

Not connected to Production / Grill. No cosine threshold and no SELECTED rule.

Backends:
- cl-nagoya/ruri-small-v2: mean-pool last hidden state with official クエリ/文章 prefixes
- llm-jp/llm-jp-3-150m: NOT an embedding model. Provisional mean-pool of last hidden state.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_FLAX", "0")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HERE = Path(__file__).resolve().parent
NOISE_RUN = HERE / "run_v0.py"
_SPEC = importlib.util.spec_from_file_location("embedding_similarity_noise_run_v0", NOISE_RUN)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load helper module: {NOISE_RUN}")
noise = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(noise)
base = noise.base

DEFAULT_CASES = HERE / "cases.json"
PREVIOUS_QWEN_SUMMARY = HERE / "runs" / "20260909T143156Z" / "summary.json"

BACKENDS = {
    "ruri-small-v2": {
        "model_id": "cl-nagoya/ruri-small-v2",
        "kind": "sentence_embedding",
        "embedding_method": "mean_pool_last_hidden_state_with_ruri_prefix",
        "query_prefix": "クエリ: ",
        "doc_prefix": "文章: ",
        "provisional": False,
        "note": "Official Ruri v2 query/passage prefixes. Mean-pool last hidden state, matching the published pooling_mode_mean_tokens.",
    },
    "llm-jp-3-150m": {
        "model_id": "llm-jp/llm-jp-3-150m",
        "kind": "causal_lm_mean_pool",
        "embedding_method": "mean_pool_last_hidden_state",
        "query_prefix": "",
        "doc_prefix": "",
        "provisional": True,
        "note": "llm-jp-3-150m is a generative LM, not an embedding model. Mean-pooling last hidden states is a provisional probe only.",
    },
}


def _to_list(vector: Any) -> list[float]:
    if hasattr(vector, "detach"):
        vector = vector.detach().cpu().numpy()
    if hasattr(vector, "tolist"):
        return [float(x) for x in vector.tolist()]
    return [float(x) for x in vector]


def _mean_pool_embedder(
    model_id: str,
    device: str,
    prefixes: dict[str, str],
    max_length: int,
) -> tuple[Callable[[str, str], list[float]], dict[str, Any]]:
    import torch
    from transformers import AutoModel, AutoTokenizer

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_id, torch_dtype=torch.float32, trust_remote_code=True)
    model.to(device)
    model.eval()
    load_ms = round((time.perf_counter() - started) * 1000, 1)

    def embed(text: str, role: str) -> list[float]:
        prefixed = prefixes.get(role, "") + text
        encoded = tokenizer(
            prefixed,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
            add_special_tokens=True,
        )
        keep = ("input_ids", "attention_mask")
        encoded = {key: value.to(device) for key, value in encoded.items() if key in keep}
        with torch.no_grad():
            hidden = model(**encoded).last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        return _to_list(pooled[0])

    dim = int(getattr(model.config, "hidden_size", 0) or 0) or None
    return embed, {
        "load_ms": load_ms,
        "device": device,
        "dim": dim,
        "prefixes": prefixes,
        "max_length": max_length,
    }


def load_ruri(model_id: str, device: str) -> tuple[Callable[[str, str], list[float]], dict[str, Any]]:
    return _mean_pool_embedder(
        model_id,
        device,
        prefixes={"query": "クエリ: ", "candidate": "文章: "},
        max_length=512,
    )


def load_llmjp_mean_pool(model_id: str, device: str) -> tuple[Callable[[str, str], list[float]], dict[str, Any]]:
    return _mean_pool_embedder(model_id, device, prefixes={}, max_length=512)


def choose_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def embed_cases(
    cases: dict[str, Any],
    embed_fn: Callable[[str, str], list[float]],
) -> tuple[dict[str, list[float]], dict[str, Any], str | None]:
    texts: list[tuple[str, str, str]] = []
    for item in cases["queries"]:
        texts.append((str(item["id"]), str(item["text"]), "query"))
    for item in cases["candidates"]:
        texts.append((str(item["id"]), str(item["text"]), "candidate"))

    vectors: dict[str, list[float]] = {}
    embed_timings: dict[str, Any] = {}
    first_embed_ms = None
    try:
        for key, text, role in texts:
            started = time.perf_counter()
            vector = embed_fn(text, role)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            if first_embed_ms is None:
                first_embed_ms = elapsed_ms
            if not vector:
                raise RuntimeError(f"empty embedding for {key}")
            vectors[key] = vector
            embed_timings[key] = {"elapsed_ms": elapsed_ms, "dim": len(vector), "role": role}
    except Exception as exc:
        return {}, embed_timings, f"{type(exc).__name__}:{exc}"
    embed_timings["_first_embed_ms"] = first_embed_ms
    return vectors, embed_timings, None


def evaluate_vectors(cases: dict[str, Any], vectors: dict[str, list[float]], embed_timings: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_vecs = {str(item["id"]): vectors[str(item["id"])] for item in cases["candidates"]}
    ranked_by_query: dict[str, list[dict[str, Any]]] = {}
    results = []
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
                "embed_ms": (embed_timings.get(qid) or {}).get("elapsed_ms"),
                "ranked": ranked,
            }
        )
    clean_by_anchor: dict[str, dict[str, Any]] = {}
    evaluations: list[dict[str, Any]] = []
    for query in cases["queries"]:
        if query["noise_type"] != "clean":
            continue
        ranked = ranked_by_query[str(query["id"])]
        clean_by_anchor[str(query["anchor_id"])] = noise.evaluate_query(query, ranked, None)
    for query in cases["queries"]:
        ranked = ranked_by_query[str(query["id"])]
        clean_eval = None
        if query["noise_type"] != "clean":
            clean_eval = clean_by_anchor.get(str(query["anchor_id"]))
        evaluations.append(noise.evaluate_query(query, ranked, clean_eval))
    return results, evaluations


def write_comparison(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Embedding noise comparison (independent experiment)",
        "",
        "Production / Grill 接続なし。閾値正本化なし。SELECTED規則なし。",
        "",
        "`gold_is_top` はこの候補集合で意図候補が1位だった観測。",
        "",
        "## モデル要約",
        "",
        "| model | method | device | noisy gold_top | mean_rank | mean_gap | mean_delta_vs_clean | failed_types |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        summary = row.get("summary") or {}
        noisy = summary.get("all_noisy") or {}
        lines.append(
            "| `{model}` | `{method}` | `{device}` | {top}/{n} | {rank} | {gap} | {delta} | {failed} |".format(
                model=row.get("embed_model"),
                method=row.get("embedding_method"),
                device=row.get("device"),
                top=noisy.get("gold_top_n"),
                n=noisy.get("n"),
                rank=noisy.get("mean_gold_rank"),
                gap=noisy.get("mean_gap_vs_second"),
                delta=noisy.get("mean_delta_vs_clean"),
                failed=", ".join(summary.get("noise_types_with_gold_not_top") or []) or "(none)",
            )
        )
    type_names = noise.NOISE_ORDER
    lines.extend(["", "## ノイズ種別ごとの gold_top", ""])
    header = "| type | " + " | ".join(row.get("embed_model") for row in rows) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(rows) + 1))
    for noise_type in type_names:
        cells = [f"`{noise_type}`"]
        for row in rows:
            packed = ((row.get("summary") or {}).get("by_noise_type") or {}).get(noise_type) or {}
            if not packed:
                cells.append("-")
            else:
                cells.append(f"{packed.get('gold_top_n')}/{packed.get('n')}")
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(["", "## 失敗クエリ", ""])
    for row in rows:
        lines.append(f"### {row.get('embed_model')}")
        lines.append("")
        failed = (row.get("summary") or {}).get("failed_queries") or []
        if not failed:
            lines.append("なし")
        for item in failed:
            lines.append(
                f"- `{item.get('query_id')}` [{item.get('noise_type')}] {item.get('query_text')} "
                f"gold_rank={item.get('gold_rank')} gold_cos={item.get('gold_cosine')} "
                f"top=`{item.get('top_id')}`"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_one(
    backend_key: str,
    cases: dict[str, Any],
    device: str,
    *,
    cases_path: Path,
    run_suffix: str = "",
) -> dict[str, Any]:
    spec = BACKENDS[backend_key]
    snapshots = [base.snapshot("baseline")]
    loader = load_ruri if backend_key == "ruri-small-v2" else load_llmjp_mean_pool
    embed_fn, load_info = loader(spec["model_id"], device)
    snapshots.append(base.snapshot("after_model_load"))
    vectors, embed_timings, embed_error = embed_cases(cases, embed_fn)
    snapshots.append(base.snapshot("after_embed"))
    first_embed_ms = embed_timings.pop("_first_embed_ms", None) if embed_timings else None
    results: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    if embed_error is None:
        results, evaluations = evaluate_vectors(cases, vectors, embed_timings)
    run_id = base.utc_stamp()
    suffix = f"_{run_suffix}" if run_suffix else ""
    out_dir = HERE / "runs" / f"{run_id}_{backend_key}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": out_dir.name,
        "at": base.now_iso(),
        "status": "ok" if embed_error is None else "error",
        "embed_error": embed_error,
        "embed_model": spec["model_id"],
        "backend": backend_key,
        "device": load_info.get("device"),
        "embedding_method": spec["embedding_method"],
        "embedding_provisional": spec["provisional"],
        "embedding_note": spec["note"],
        "prefixes": load_info.get("prefixes") or {
            "query": spec["query_prefix"],
            "candidate": spec["doc_prefix"],
        },
        "gen_model": None,
        "with_gen": False,
        "production_connected": False,
        "grill_connected": False,
        "threshold_canonicalized": False,
        "selected_rule_created": False,
        "vector_dim": load_info.get("dim") or next((row["dim"] for row in embed_timings.values() if isinstance(row, dict) and "dim" in row), None),
        "model_load_ms": load_info.get("load_ms"),
        "embed_timings": embed_timings,
        "first_embed_ms": first_embed_ms,
        "snapshots": snapshots,
        "results": results,
        "evaluations": evaluations,
        "slot_metrics": noise.slot_metrics.attach_slot_metrics(cases, results) if results else {},
        "summary": noise.summarize(evaluations) if evaluations else {},
        "cases_path": str(cases_path),
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
    noise.write_human_review(out_dir / "HUMAN_REVIEW.md", record)
    print(json.dumps({"run_id": record["run_id"], "status": record["status"], "out": str(out_dir)}, ensure_ascii=False))
    return record


def load_previous_qwen() -> dict[str, Any] | None:
    if not PREVIOUS_QWEN_SUMMARY.exists():
        return None
    summary = json.loads(PREVIOUS_QWEN_SUMMARY.read_text(encoding="utf-8"))
    return {
        "embed_model": "qwen3-embedding:0.6b",
        "embedding_method": "ollama_embed",
        "device": "gpu_ollama_previous_run",
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="HF Japanese input-noise embedding harness")
    parser.add_argument("--backend", choices=["ruri-small-v2", "llm-jp-3-150m", "both"], default="both")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--include-previous-qwen", action="store_true")
    args = parser.parse_args()

    cases_path = Path(args.cases).resolve()
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    device = choose_device(args.device)
    keys = ["ruri-small-v2", "llm-jp-3-150m"] if args.backend == "both" else [args.backend]
    records = []
    status_ok = True
    for key in keys:
        record = run_one(key, cases, device, cases_path=cases_path, run_suffix=args.run_suffix)
        records.append(record)
        if record.get("status") != "ok":
            status_ok = False
    compare_rows = []
    if args.include_previous_qwen:
        previous = load_previous_qwen()
        if previous is not None:
            compare_rows.append(previous)
    compare_rows.extend(records)
    stamp = base.utc_stamp()
    compare_path = HERE / "runs" / f"{stamp}_COMPARE.md"
    write_comparison(compare_path, compare_rows)
    print(json.dumps({"compare": str(compare_path), "device": device}, ensure_ascii=False))
    return 0 if status_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
