"""Grill-after translation layer experiment. Not connected to Production / Grill."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ollama import Client

from ai_tool.chat_interface.task_orchestration import (
    _clarification_tokens,
    match_clarification_to_candidate_paths,
)

V0_RUN = ROOT / "research" / "embedding_similarity_v0" / "run_v0.py"
_SPEC = importlib.util.spec_from_file_location("embedding_similarity_v0_run", V0_RUN)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load helper module: {V0_RUN}")
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "cases_grill_translate.json"
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
MATCH_RANK = {
    "unique_gold": 3,
    "ambiguous_includes_gold": 1,
    "empty": 0,
    "ambiguous_no_gold": -1,
    "unique_wrong": -2,
}
TRANSLATE_PROMPT = """あなたは、人間の確認文を、残っている候補ファイルを指す短い確認文へ書き直します。

ルール:
- 出力は書き直した確認文だけ。1行。説明しない。
- 候補に無いファイル名や内容は出さない。
- どの候補が正解かは分かっていない。断定できないときは入力文をそのまま出す。
- タイプミス・変換ミス・音声認識の誤りは、候補の表記に合わせて直してよい。
- 「AじゃなくてB」は B を指す。否定された側は残さない。

残候補:
{candidates}

人間の確認文:
{text}
"""


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None or value != value:
        return None
    return round(value, digits)


def candidate_blob(item: dict[str, Any]) -> str:
    hits = [str(row).strip() for row in item.get("hit_texts") or [] if str(row).strip()]
    return str(item["path"]) + "\n" + "\n".join(hits)


def observed_match_texts(candidates: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        str(item["path"]): [str(row).strip() for row in item.get("hit_texts") or [] if str(row).strip()]
        for item in candidates
    }


def ignore_tokens(cases: dict[str, Any]) -> list[str]:
    tokens = [str(cases.get("original_search_query") or "").strip()]
    tokens.extend(_clarification_tokens(str(cases.get("original_request") or "")))
    return [item for item in tokens if item]


def classify_match(matched: list[str], gold_path: str) -> str:
    if not matched:
        return "empty"
    if matched == [gold_path]:
        return "unique_gold"
    if len(matched) == 1:
        return "unique_wrong"
    if gold_path in matched:
        return "ambiguous_includes_gold"
    return "ambiguous_no_gold"


def progress_label(raw_status: str, translated_status: str) -> str:
    delta = MATCH_RANK[translated_status] - MATCH_RANK[raw_status]
    if delta > 0:
        return "closer"
    if delta < 0:
        return "farther"
    return "same"


def format_candidate_block(candidates: list[dict[str, Any]]) -> str:
    blocks = []
    for item in candidates:
        hits = " / ".join(str(row).strip() for row in item.get("hit_texts") or [] if str(row).strip())
        blocks.append(f"- path: {item['path']}\n  hits: {hits}")
    return "\n".join(blocks)


def _message_payload(response: Any) -> dict[str, Any]:
    message = getattr(response, "message", None)
    if message is None and isinstance(response, dict):
        message = response.get("message")
    if isinstance(message, dict):
        return {
            "content": str(message.get("content") or ""),
            "thinking": str(message.get("thinking") or ""),
        }
    return {
        "content": str(getattr(message, "content", None) or ""),
        "thinking": str(getattr(message, "thinking", None) or ""),
    }


def _first_line(text: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return ""
    stripped = re.sub(r"^```(?:\w+)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped).strip()
    line = stripped.splitlines()[0].strip()
    line = line.strip("「」\"'`")
    return line


def translate_one(
    client: Client,
    model: str,
    text: str,
    candidate_block: str,
    keep_alive: str,
) -> dict[str, Any]:
    prompt = TRANSLATE_PROMPT.format(candidates=candidate_block, text=text)
    started = time.perf_counter()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0, "num_predict": 96},
        "keep_alive": keep_alive,
    }
    try:
        response = client.chat(**kwargs, think=False)
    except TypeError:
        response = client.chat(**kwargs)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    payload = _message_payload(response)
    content = _first_line(payload["content"])
    source = "content"
    if not content:
        content = _first_line(payload["thinking"])
        source = "thinking" if content else "empty"
    if not content:
        return {
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "text": text,
            "raw_content": payload["content"][:500],
            "source": "fallback_raw",
            "error": "empty_translation",
        }
    return {
        "ok": True,
        "elapsed_ms": elapsed_ms,
        "text": content,
        "raw_content": payload["content"][:500],
        "source": source,
        "error": None,
    }


def match_one(
    text: str,
    paths: list[str],
    texts: dict[str, list[str]],
    ignored: list[str],
    gold_path: str,
) -> dict[str, Any]:
    matched = match_clarification_to_candidate_paths(
        text,
        paths,
        observed_match_texts=texts,
        ignore_tokens=ignored,
    )
    status = classify_match(matched, gold_path)
    return {
        "text": text,
        "matched_paths": matched,
        "status": status,
        "unique_gold": status == "unique_gold",
        "would_select": status == "unique_gold",
        "would_regrill": status in {"empty", "ambiguous_includes_gold", "ambiguous_no_gold"},
        "would_wrong_read": status == "unique_wrong",
    }


def cosine_eval(
    query_vec: list[float] | None,
    candidate_vecs: dict[str, list[float]],
    candidates: list[dict[str, Any]],
    gold_path: str,
) -> dict[str, Any]:
    if query_vec is None:
        return {
            "gold_cosine": None,
            "gold_rank": None,
            "top_path": None,
            "top_cosine": None,
            "best_wrong_path": None,
            "best_wrong_cosine": None,
            "gap_vs_best_wrong": None,
            "ranked": [],
        }
    ranked = []
    for item in candidates:
        path = str(item["path"])
        score = base.cosine(query_vec, candidate_vecs[path])
        ranked.append(
            {
                "path": path,
                "cosine": _round(score),
            }
        )
    ranked.sort(key=lambda row: (row["cosine"] is None, -(row["cosine"] or 0)))
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    gold_row = next((row for row in ranked if row["path"] == gold_path), None)
    top = ranked[0] if ranked else None
    wrong = [row for row in ranked if row["path"] != gold_path]
    best_wrong = wrong[0] if wrong else None
    gold_cosine = gold_row["cosine"] if gold_row else None
    best_wrong_cosine = best_wrong["cosine"] if best_wrong else None
    gap = None
    if gold_cosine is not None and best_wrong_cosine is not None:
        gap = _round(gold_cosine - best_wrong_cosine)
    return {
        "gold_cosine": gold_cosine,
        "gold_rank": gold_row["rank"] if gold_row else None,
        "top_path": top["path"] if top else None,
        "top_cosine": top["cosine"] if top else None,
        "best_wrong_path": best_wrong["path"] if best_wrong else None,
        "best_wrong_cosine": best_wrong_cosine,
        "gap_vs_best_wrong": gap,
        "ranked": ranked,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    noisy = [row for row in rows if row["noise_type"] != "clean"]
    target = noisy or rows

    def pack(items: list[dict[str, Any]], side: str) -> dict[str, Any]:
        statuses = [item[side]["status"] for item in items]
        counts = {key: statuses.count(key) for key in MATCH_RANK}
        return {
            "n": len(items),
            "unique_gold_n": counts["unique_gold"],
            "unique_gold_rate": _round(counts["unique_gold"] / len(items), 4) if items else None,
            "empty_n": counts["empty"],
            "ambiguous_includes_gold_n": counts["ambiguous_includes_gold"],
            "ambiguous_no_gold_n": counts["ambiguous_no_gold"],
            "unique_wrong_n": counts["unique_wrong"],
            "would_select_n": sum(1 for item in items if item[side]["would_select"]),
            "would_regrill_n": sum(1 for item in items if item[side]["would_regrill"]),
            "would_wrong_read_n": sum(1 for item in items if item[side]["would_wrong_read"]),
        }

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_type[str(row["noise_type"])].append(row)
    progress = {key: 0 for key in ("closer", "same", "farther")}
    for row in target:
        progress[str(row["progress"])] += 1
    cosine_deltas = [
        row["cosine_delta_gold"]
        for row in target
        if row.get("cosine_delta_gold") is not None
    ]
    return {
        "noisy_n": len(target),
        "raw": pack(target, "raw"),
        "translated": pack(target, "translated"),
        "progress": progress,
        "mean_cosine_delta_gold": _round(sum(cosine_deltas) / len(cosine_deltas), 6) if cosine_deltas else None,
        "by_noise_type": {
            key: {
                "raw": pack(by_type[key], "raw"),
                "translated": pack(by_type[key], "translated"),
                "progress": {
                    label: sum(1 for row in by_type[key] if row["progress"] == label)
                    for label in ("closer", "same", "farther")
                },
            }
            for key in NOISE_ORDER
            if key in by_type
        },
    }


def write_listing_md(path: Path, record: dict[str, Any]) -> None:
    summary = record.get("summary") or {}
    raw = summary.get("raw") or {}
    translated = summary.get("translated") or {}
    progress = summary.get("progress") or {}
    lines = [
        "# Grill後 翻訳層 v0",
        "",
        f"- run_id: `{record.get('run_id')}`",
        f"- 翻訳モデル: `{record.get('gen_model')}`",
        f"- Embedding（補助）: `{record.get('embed_model')}`",
        "- Production / Grill 接続: なし",
        "- 主評価: 既存 `match_clarification_to_candidate_paths` が unique gold になるか",
        "- cosine は補助。SELECTED 規則ではない",
        "",
        "## シナリオ（仮置き）",
        "",
        str((record.get("cases_meta") or {}).get("scenario") or ""),
        "",
        "## ノイズ文の照合",
        "",
        f"- 生データ unique gold: **{raw.get('unique_gold_n')} / {raw.get('n')}**",
        f"- 翻訳後 unique gold: **{translated.get('unique_gold_n')} / {translated.get('n')}**",
        f"- 近づいた / 同じ / 遠ざかった: **{progress.get('closer')} / {progress.get('same')} / {progress.get('farther')}**",
        f"- 生で誤読（unique_wrong）: {raw.get('unique_wrong_n')}",
        f"- 翻訳後の誤読: {translated.get('unique_wrong_n')}",
        f"- 補助 cosine（gold）平均差: {summary.get('mean_cosine_delta_gold')}",
        "",
        "## ノイズ種別",
        "",
        "| 種別 | 生 unique gold | 訳 unique gold | closer | same | farther |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    by_type = summary.get("by_noise_type") or {}
    for key in NOISE_ORDER:
        row = by_type.get(key)
        if not row:
            continue
        prog = row.get("progress") or {}
        lines.append(
            f"| {key} | {(row.get('raw') or {}).get('unique_gold_n')} / {(row.get('raw') or {}).get('n')} "
            f"| {(row.get('translated') or {}).get('unique_gold_n')} / {(row.get('translated') or {}).get('n')} "
            f"| {prog.get('closer')} | {prog.get('same')} | {prog.get('farther')} |"
        )
    lines.extend(
        [
            "",
            "## 一覧",
            "",
            "| id | 種別 | 生入力 | 翻訳 | 生の照合 | 訳後の照合 | gold | 生判定 | 訳判定 | 近づいたか | 生 cosine | 訳 cosine | Δcosine |",
            "|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for item in record.get("results") or []:
        raw_match = item.get("raw") or {}
        tr_match = item.get("translated") or {}
        raw_cos = item.get("raw_cosine") or {}
        tr_cos = item.get("translated_cosine") or {}
        lines.append(
            "| {id} | {noise} | {raw_text} | {tr_text} | {raw_paths} | {tr_paths} | `{gold}` | {raw_status} | {tr_status} | {progress} | {raw_cos} | {tr_cos} | {delta} |".format(
                id=item.get("query_id"),
                noise=item.get("noise_type"),
                raw_text=_cell(item.get("raw_text")),
                tr_text=_cell(item.get("translated_text")),
                raw_paths=_paths_cell(raw_match.get("matched_paths")),
                tr_paths=_paths_cell(tr_match.get("matched_paths")),
                gold=item.get("gold_path"),
                raw_status=raw_match.get("status"),
                tr_status=tr_match.get("status"),
                progress=item.get("progress"),
                raw_cos=raw_cos.get("gold_cosine"),
                tr_cos=tr_cos.get("gold_cosine"),
                delta=item.get("cosine_delta_gold"),
            )
        )
    lines.extend(["", "## 資源", ""])
    for snap in record.get("snapshots") or []:
        gpu = snap.get("gpu") or {}
        ram = snap.get("ram") or {}
        lines.append(
            f"- {snap.get('label')}: VRAM {gpu.get('vram_used')} / {gpu.get('vram_total')} MiB, "
            f"RAM used {ram.get('used_mb')} / {ram.get('total_mb')} MB"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cell(value: Any) -> str:
    text = str(value or "").replace("|", "\\|").replace("\n", " ")
    if len(text) > 48:
        return text[:45] + "..."
    return text


def _paths_cell(paths: Any) -> str:
    rows = [str(item) for item in (paths or [])]
    if not rows:
        return "（なし）"
    return ", ".join(f"`{item}`" for item in rows)


def write_listing_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "query_id",
        "noise_type",
        "raw_text",
        "translated_text",
        "raw_matched_paths",
        "translated_matched_paths",
        "gold_path",
        "raw_status",
        "translated_status",
        "progress",
        "raw_gold_cosine",
        "translated_gold_cosine",
        "cosine_delta_gold",
        "translation_ok",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in rows:
            raw_match = item.get("raw") or {}
            tr_match = item.get("translated") or {}
            raw_cos = item.get("raw_cosine") or {}
            tr_cos = item.get("translated_cosine") or {}
            writer.writerow(
                {
                    "query_id": item.get("query_id"),
                    "noise_type": item.get("noise_type"),
                    "raw_text": item.get("raw_text"),
                    "translated_text": item.get("translated_text"),
                    "raw_matched_paths": " | ".join(raw_match.get("matched_paths") or []),
                    "translated_matched_paths": " | ".join(tr_match.get("matched_paths") or []),
                    "gold_path": item.get("gold_path"),
                    "raw_status": raw_match.get("status"),
                    "translated_status": tr_match.get("status"),
                    "progress": item.get("progress"),
                    "raw_gold_cosine": raw_cos.get("gold_cosine"),
                    "translated_gold_cosine": tr_cos.get("gold_cosine"),
                    "cosine_delta_gold": item.get("cosine_delta_gold"),
                    "translation_ok": item.get("translation_ok"),
                    "note": item.get("note"),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Grill-after translation layer harness")
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    parser.add_argument("--gen-model", default=DEFAULT_GEN_MODEL)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--keep-alive", default="30m")
    parser.add_argument("--run-suffix", default="grill-translate")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    candidates = list(cases["candidates"])
    paths = [str(item["path"]) for item in candidates]
    texts = observed_match_texts(candidates)
    ignored = ignore_tokens(cases)
    candidate_block = format_candidate_block(candidates)
    run_id = base.utc_stamp() + "_" + str(args.run_suffix)
    out_dir = HERE / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    client = Client(timeout=180)
    snapshots = [base.snapshot("baseline")]

    results: list[dict[str, Any]] = []
    translations: dict[str, dict[str, Any]] = {}
    for query in cases["queries"]:
        query_id = str(query["id"])
        raw_text = str(query["text"])
        try:
            translation = translate_one(
                client,
                args.gen_model,
                raw_text,
                candidate_block,
                args.keep_alive,
            )
        except Exception as exc:
            translation = {
                "ok": False,
                "elapsed_ms": None,
                "text": raw_text,
                "raw_content": "",
                "source": "exception",
                "error": f"{type(exc).__name__}:{exc}",
            }
        translations[query_id] = translation
        translated_text = str(translation.get("text") or raw_text)
        gold_path = str(query["gold_path"])
        raw_match = match_one(raw_text, paths, texts, ignored, gold_path)
        translated_match = match_one(translated_text, paths, texts, ignored, gold_path)
        results.append(
            {
                "query_id": query_id,
                "anchor_id": query.get("anchor_id"),
                "noise_type": query.get("noise_type"),
                "note": query.get("note"),
                "gold_path": gold_path,
                "raw_text": raw_text,
                "translated_text": translated_text,
                "translation_ok": bool(translation.get("ok")),
                "translation_source": translation.get("source"),
                "translation_error": translation.get("error"),
                "translation_elapsed_ms": translation.get("elapsed_ms"),
                "raw": raw_match,
                "translated": translated_match,
                "progress": progress_label(raw_match["status"], translated_match["status"]),
            }
        )
    snapshots.append(base.snapshot("after_translate"))

    embed_texts: dict[str, str] = {}
    for item in candidates:
        embed_texts[str(item["path"])] = candidate_blob(item)
    for row in results:
        embed_texts[f"raw:{row['query_id']}"] = str(row["raw_text"])
        embed_texts[f"tr:{row['query_id']}"] = str(row["translated_text"])

    vectors: dict[str, list[float]] = {}
    embed_timings: dict[str, Any] = {}
    for key, text in embed_texts.items():
        started = time.perf_counter()
        try:
            payload = base.embed_one(client, args.embed_model, text, args.keep_alive)
            vector = payload.get("vector")
            vectors[key] = vector
            embed_timings[key] = {
                "elapsed_ms": payload.get("elapsed_ms"),
                "dim": payload.get("dim"),
                "ok": vector is not None,
            }
        except Exception as exc:
            vectors[key] = None  # type: ignore[assignment]
            embed_timings[key] = {
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "dim": None,
                "ok": False,
                "error": f"{type(exc).__name__}:{exc}",
            }
    snapshots.append(base.snapshot("after_embed"))

    candidate_vecs = {path: vectors[path] for path in paths if vectors.get(path)}
    for row in results:
        raw_cos = cosine_eval(
            vectors.get(f"raw:{row['query_id']}"),
            candidate_vecs,
            candidates,
            str(row["gold_path"]),
        )
        tr_cos = cosine_eval(
            vectors.get(f"tr:{row['query_id']}"),
            candidate_vecs,
            candidates,
            str(row["gold_path"]),
        )
        row["raw_cosine"] = raw_cos
        row["translated_cosine"] = tr_cos
        delta = None
        if raw_cos.get("gold_cosine") is not None and tr_cos.get("gold_cosine") is not None:
            delta = _round(tr_cos["gold_cosine"] - raw_cos["gold_cosine"])
        row["cosine_delta_gold"] = delta

    record = {
        "run_id": run_id,
        "created_at": base.now_iso(),
        "production_connected": False,
        "grill_connected": False,
        "selected_rule_created": False,
        "threshold_canonicalized": False,
        "eval_primary": "match_clarification_to_candidate_paths unique_gold",
        "eval_auxiliary": "embedding cosine vs path+hit_text blob",
        "gen_model": args.gen_model,
        "embed_model": args.embed_model,
        "cases_path": str(Path(args.cases)),
        "cases_meta": {
            "note": cases.get("note"),
            "evaluation_note": cases.get("evaluation_note"),
            "scenario": cases.get("scenario"),
            "original_request": cases.get("original_request"),
            "original_search_query": cases.get("original_search_query"),
            "translation_layer": cases.get("translation_layer"),
        },
        "ignore_tokens": ignored,
        "candidates": candidates,
        "snapshots": snapshots,
        "embed_timings": embed_timings,
        "translations": {
            key: {
                "ok": value.get("ok"),
                "elapsed_ms": value.get("elapsed_ms"),
                "source": value.get("source"),
                "error": value.get("error"),
                "text": value.get("text"),
            }
            for key, value in translations.items()
        },
        "results": results,
        "summary": summarize(results),
    }
    (out_dir / "run.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(record["summary"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_listing_md(out_dir / "HUMAN.md", record)
    write_listing_csv(out_dir / "listing.csv", results)
    print(out_dir)
    print(json.dumps(record["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
