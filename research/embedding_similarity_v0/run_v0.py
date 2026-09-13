"""Independent embedding similarity harness. Not connected to Production Agent / Grill."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ollama import Client

from tools.system.gpu.nvidia_smi import query_gpu_status
from tools.system.gpu.gpu_processes import get_gpu_processes

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "cases.json"
DEFAULT_GEN_MODEL = "qwen3:14b"
DEFAULT_EMBED_MODEL = "qwen3-embedding:0.6b"
GEN_PROMPT = "Reply with exactly: READY"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_cmd(argv: list[str], timeout: float = 20.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": ""}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}", "stdout": "", "stderr": ""}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "error": None if completed.returncode == 0 else f"exit_{completed.returncode}",
    }


def ollama_ps() -> dict[str, Any]:
    result = run_cmd(["ollama", "ps"])
    return {
        "ok": result["ok"],
        "raw": (result.get("stdout") or "").strip(),
        "error": result.get("error"),
    }


def ram_status() -> dict[str, Any]:
    if sys.platform != "win32":
        return {"ok": False, "error": "not_windows", "total_mb": None, "avail_mb": None, "used_mb": None}
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"ok": False, "error": "GlobalMemoryStatusEx_failed", "total_mb": None, "avail_mb": None, "used_mb": None}
    total = int(status.ullTotalPhys / (1024 * 1024))
    avail = int(status.ullAvailPhys / (1024 * 1024))
    return {
        "ok": True,
        "total_mb": total,
        "avail_mb": avail,
        "used_mb": total - avail,
        "load_percent": int(status.dwMemoryLoad),
        "source": "GlobalMemoryStatusEx",
    }


def snapshot(label: str) -> dict[str, Any]:
    gpu = query_gpu_status()
    procs = get_gpu_processes()
    return {
        "label": label,
        "at": now_iso(),
        "gpu": gpu,
        "gpu_processes": procs,
        "ram": ram_status(),
        "ollama_ps": ollama_ps(),
    }


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return float("nan")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return float("nan")
    return dot / (na * nb)


def embed_one(client: Client, model: str, text: str, keep_alive: str) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.embed(model=model, input=text, keep_alive=keep_alive)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    payload = dict(response) if hasattr(response, "model_dump") else None
    if payload is None:
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
            payload = dict(response)
        else:
            payload = {"embeddings": embeddings}
    else:
        embeddings = payload.get("embeddings")
    vector = None
    if isinstance(embeddings, list) and embeddings:
        first = embeddings[0]
        if isinstance(first, list):
            vector = [float(x) for x in first]
    return {
        "elapsed_ms": elapsed_ms,
        "dim": len(vector) if vector else None,
        "vector": vector,
        "raw_keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
    }


def chat_ping(client: Client, model: str, keep_alive: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": GEN_PROMPT}],
            options={"temperature": 0, "num_predict": 16},
            keep_alive=keep_alive,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        message = getattr(response, "message", None)
        content = getattr(message, "content", None) if message is not None else None
        if content is None and isinstance(response, dict):
            content = ((response.get("message") or {}).get("content"))
        return {
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "content": str(content or "")[:200],
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "content": None,
            "error": f"{type(exc).__name__}:{exc}",
        }


def rank_candidates(
    query_vec: list[float],
    candidate_vecs: dict[str, list[float]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for item in candidates:
        cid = str(item["id"])
        score = cosine(query_vec, candidate_vecs[cid])
        rows.append(
            {
                "candidate_id": cid,
                "text": item["text"],
                "kind": item.get("kind"),
                "cosine": round(score, 6) if score == score else None,
            }
        )
    rows.sort(key=lambda row: (row["cosine"] is None, -(row["cosine"] or 0)))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def expected_hit(ranked: list[dict[str, Any]], expected_ids: list[str]) -> dict[str, Any]:
    top = ranked[0] if ranked else None
    top_id = top.get("candidate_id") if top else None
    expected = list(expected_ids)
    return {
        "top_id": top_id,
        "top_in_expected_near": top_id in expected if top_id else False,
        "expected_near": expected,
        "expected_ranks": {
            cid: next((row["rank"] for row in ranked if row["candidate_id"] == cid), None)
            for cid in expected
        },
    }


def write_human_review(path: Path, record: dict[str, Any]) -> None:
    embed = record.get("embed_model")
    gen = record.get("gen_model")
    lines = [
        "# Embedding similarity v0 run",
        "",
        f"- run_id: `{record.get('run_id')}`",
        f"- embed_model: `{embed}`",
        f"- gen_model: `{gen}`",
        f"- Production / Grill 接続: なし",
        "",
        "## 同時利用",
        "",
        json.dumps(record.get("simultaneous") or {}, ensure_ascii=False, indent=2),
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
    lines.extend(["", "## 類似度", ""])
    for item in record.get("results") or []:
        lines.append(f"### {item.get('query_id')}: {item.get('query_text')}")
        lines.append("")
        hit = item.get("expected_hit") or {}
        lines.append(
            f"top=`{hit.get('top_id')}` expected_near_hit=`{hit.get('top_in_expected_near')}`"
        )
        lines.append("")
        for row in item.get("ranked") or []:
            lines.append(
                f"- r{row.get('rank')} {row.get('cosine')} `{row.get('candidate_id')}` {row.get('text')}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Embedding similarity v0 harness")
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    parser.add_argument("--gen-model", default=DEFAULT_GEN_MODEL)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--keep-alive", default="30m")
    parser.add_argument("--skip-gen", action="store_true")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    run_id = utc_stamp()
    out_dir = HERE / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    client = Client(timeout=180)
    snapshots = [snapshot("baseline")]
    simultaneous: dict[str, Any] = {
        "gen_loaded_before_embed": None,
        "both_listed_during_embed": None,
        "gen_responded_after_embed": None,
        "note": "Resident-in-VRAM vs sequential Ollama swap are recorded separately.",
    }

    gen_before = None
    if not args.skip_gen:
        gen_before = chat_ping(client, args.gen_model, args.keep_alive)
        snapshots.append(snapshot("after_gen_warmup"))
        simultaneous["gen_loaded_before_embed"] = bool(gen_before.get("ok"))
        simultaneous["gen_warmup"] = gen_before

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
            row = embed_one(client, args.embed_model, text, args.keep_alive)
            if first_embed_ms is None:
                first_embed_ms = row["elapsed_ms"]
            if not row.get("vector"):
                raise RuntimeError(f"empty embedding for {key}: keys={row.get('raw_keys')}")
            vectors[key] = row["vector"]
            embed_timings[key] = {
                "elapsed_ms": row["elapsed_ms"],
                "dim": row["dim"],
            }
    except Exception as exc:
        embed_error = f"{type(exc).__name__}:{exc}"

    snapshots.append(snapshot("after_embed"))
    listed = (snapshots[-1].get("ollama_ps") or {}).get("raw") or ""
    simultaneous["both_listed_during_embed"] = bool(
        listed and args.gen_model in listed and args.embed_model in listed
    )
    simultaneous["ollama_ps_after_embed"] = listed
    simultaneous["first_embed_ms"] = first_embed_ms

    gen_after = None
    if not args.skip_gen:
        gen_after = chat_ping(client, args.gen_model, args.keep_alive)
        snapshots.append(snapshot("after_gen_reping"))
        simultaneous["gen_responded_after_embed"] = bool(gen_after.get("ok"))
        simultaneous["gen_reping"] = gen_after

    results = []
    if embed_error is None:
        candidate_vecs = {str(item["id"]): vectors[str(item["id"])] for item in cases["candidates"]}
        for query in cases["queries"]:
            qid = str(query["id"])
            ranked = rank_candidates(vectors[qid], candidate_vecs, cases["candidates"])
            results.append(
                {
                    "query_id": qid,
                    "query_text": query["text"],
                    "embed_ms": embed_timings[qid]["elapsed_ms"],
                    "ranked": ranked,
                    "expected_hit": expected_hit(ranked, list(query.get("expected_near") or [])),
                }
            )

    record = {
        "run_id": run_id,
        "at": now_iso(),
        "status": "ok" if embed_error is None else "error",
        "embed_error": embed_error,
        "embed_model": args.embed_model,
        "gen_model": args.gen_model,
        "skip_gen": bool(args.skip_gen),
        "production_connected": False,
        "grill_connected": False,
        "threshold_canonicalized": False,
        "selected_rule_created": False,
        "vector_dim": next((row["dim"] for row in embed_timings.values()), None),
        "embed_timings": embed_timings,
        "simultaneous": simultaneous,
        "snapshots": snapshots,
        "results": results,
        "cases_path": str(Path(args.cases).resolve()),
    }
    (out_dir / "run.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_human_review(out_dir / "HUMAN_REVIEW.md", record)
    print(json.dumps({"run_id": run_id, "status": record["status"], "out": str(out_dir)}, ensure_ascii=False))
    return 0 if embed_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
