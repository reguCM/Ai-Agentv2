"""
WEB効果比較パイロット: answer_without_web vs answer_with_web を生成する。

- 観測・収集ハーネスのみ。heuristic / Gate / Pipeline / Clarity は変更しない
- agent.py の本番経路は起動しない（条件を揃えた独立生成）
- pre_web_answer_candidate は使わない（完成回答同士の比較）
- ローカルToolは呼ばない（W0/W1 パイロット）
"""

from __future__ import annotations

import argparse
import json
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import get_llm_profile
from tools.system.llm import chat
from tools.system.network.search_web import search_web

ROOT = Path(__file__).resolve().parents[6]
HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "pilot_cases.json"
DEFAULT_OUT = HERE / "pilot_results"

# agent.py の SYSTEM に近いが、ローカルTool前提を外し WEB 比較に特化
SYSTEM_SHARED = """
あなたはローカル環境のAI Agentです。

ルール:
1. ユーザー向けの完成回答だけを書いてください（内部独白や手順メモは書かない）。
2. 不明なことは「未確認」と書いてください。
3. ユーザー要求の対象を変えてはいけません。
4. 存在しないURLや題名を、確認したかのように補完しないでください。
""".strip()

SYSTEM_WITH_WEB_EXTRA = """
追加ルール（WEB検索結果あり）:
5. 回答で使うタイトル・URLは、実際に渡された検索結果に含まれるものだけを使う。
6. 検索結果に無い情報を、検索で得たように断定しない。
7. 検索でも確認できない場合は「確認できなかった」と書く。
""".strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _message_content(response) -> str:
    msg = getattr(response, "message", None)
    if msg is None:
        return ""
    content = getattr(msg, "content", None)
    return "" if content is None else str(content)


def generate_answer_without_web(*, request: str, model: str) -> dict:
    """
    WEB検索なし・検索結果なし・ローカルToolなしで、ユーザー向け完成回答を生成する。
    """
    response = chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_SHARED},
            {
                "role": "user",
                "content": (
                    f"ユーザー要求:\n{request}\n\n"
                    "Web検索は使えません。手元の知識だけで、"
                    "ユーザーに返す完成回答を書いてください。"
                ),
            },
        ],
    )
    text = _message_content(response).strip()
    return {
        "answer_without_web": text,
        "meta": {
            "path": "without_web",
            "search_web_used": False,
            "local_tools_used": [],
            "model": model,
        },
    }


def _suggest_search_query(*, request: str, model: str) -> str:
    response = chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "検索クエリだけを1行で出力してください。"
                    "可能なら英語の固有名詞・百科事典向けクエリを優先してください。"
                    "説明文や引用符は不要です。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"次のユーザー要求を調べるためのWeb検索クエリを1つ作ってください。\n"
                    f"{request}"
                ),
            },
        ],
    )
    raw = _message_content(response).strip()
    line = raw.splitlines()[0].strip() if raw else request
    line = re.sub(r'^[\s\"「『]+|[\s\"」』]+$', "", line)
    return line or request


def _hit_count(result: dict | None) -> int:
    if not isinstance(result, dict):
        return 0
    hits = result.get("hits")
    return len(hits) if isinstance(hits, list) else 0


def search_until_hits(
    *,
    request: str,
    model: str,
    seed_queries: list[str] | None,
    limit: int = 5,
    max_attempts: int = 6,
    pause_sec: float = 2.5,
) -> dict:
    """
    ハーネス専用: 複数クエリを試し、hits>0 になるまで search_web を呼ぶ。
    general_web_search / heuristic / Gate は変更しない。
    """
    queries: list[str] = []
    for q in seed_queries or []:
        q = str(q or "").strip()
        if q and q not in queries:
            queries.append(q)
    try:
        suggested = _suggest_search_query(request=request, model=model)
        if suggested and suggested not in queries:
            queries.insert(0, suggested)
    except Exception:  # noqa: BLE001
        pass
    if request.strip() and request.strip() not in queries:
        queries.append(request.strip())

    attempts: list[dict] = []
    best: dict | None = None
    for i, query in enumerate(queries[:max_attempts]):
        if i:
            time.sleep(pause_sec)
        result = search_web(query, limit=limit)
        attempt = {
            "query": query,
            "hit_count": _hit_count(result),
            "error": result.get("error") if isinstance(result, dict) else None,
            "backends_tried": result.get("backends_tried")
            if isinstance(result, dict)
            else None,
        }
        attempts.append(attempt)
        if _hit_count(result) > 0:
            best = {
                "query": query,
                "result": result,
                "attempts": attempts,
                "got_hits": True,
            }
            break
        # 429 系は追加待機
        err = str((result or {}).get("error") or "")
        if "429" in err or "Too Many" in err:
            time.sleep(pause_sec * 2)

    if best is None:
        last = attempts[-1] if attempts else {"query": request}
        # 最後の失敗結果を再検索せず、空hitsとして返す
        best = {
            "query": last.get("query") or request,
            "result": {
                "query": last.get("query") or request,
                "hits": [],
                "error": last.get("error") or "検索結果がありません",
                "backends_tried": last.get("backends_tried"),
            },
            "attempts": attempts,
            "got_hits": False,
        }
    return best


def generate_answer_with_web(
    *,
    request: str,
    model: str,
    limit: int = 5,
    seed_queries: list[str] | None = None,
    require_hits: bool = False,
) -> dict:
    """
    同一要求に対し search_web を実行し、結果を与えて完成回答を生成する。
    ローカルToolは使わない。
    """
    searched = search_until_hits(
        request=request,
        model=model,
        seed_queries=seed_queries,
        limit=limit,
    )
    search_result = searched.get("result") or {}
    hits = []
    if isinstance(search_result, dict):
        raw_hits = search_result.get("hits")
        if isinstance(raw_hits, list):
            hits = raw_hits

    if require_hits and not hits:
        raise RuntimeError(
            "require_hits: search_web returned 0 hits after retries "
            f"(attempts={searched.get('attempts')})"
        )

    query = searched.get("query") or request
    hits_text = json.dumps(hits, ensure_ascii=False, indent=2)
    system = SYSTEM_SHARED + "\n\n" + SYSTEM_WITH_WEB_EXTRA
    response = chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"ユーザー要求:\n{request}\n\n"
                    f"Web検索クエリ:\n{query}\n\n"
                    f"Web検索結果(hits JSON):\n{hits_text}\n\n"
                    "上記の検索結果を必要に応じて使い、"
                    "ユーザーに返す完成回答を書いてください。"
                ),
            },
        ],
    )
    text = _message_content(response).strip()
    return {
        "answer_with_web": text,
        "web_search": {
            "query": query,
            "got_hits": bool(hits),
            "attempts": searched.get("attempts"),
            "result": {
                "query": (search_result or {}).get("query")
                if isinstance(search_result, dict)
                else query,
                "hit_count": len(hits),
                "error": (search_result or {}).get("error")
                if isinstance(search_result, dict)
                else None,
                "hits": [
                    {
                        "title": (h or {}).get("title"),
                        "url": (h or {}).get("url"),
                        "snippet": (h or {}).get("snippet")
                        or (h or {}).get("description"),
                    }
                    for h in hits
                    if isinstance(h, dict)
                ],
                "backends_tried": (search_result or {}).get("backends_tried")
                if isinstance(search_result, dict)
                else None,
            },
        },
        "meta": {
            "path": "with_web",
            "search_web_used": True,
            "local_tools_used": [],
            "model": model,
            "require_hits": require_hits,
        },
    }


def run_case(
    case: dict,
    *,
    model: str,
    require_hits: bool = False,
    limit_hits: int = 5,
) -> dict:
    request = str(case.get("request") or "").strip()
    case_id = str(case.get("id") or "case")
    seed_queries = [
        str(q).strip()
        for q in (case.get("seed_queries") or [])
        if str(q).strip()
    ]
    payload: dict = {
        "case_id": case_id,
        "band": case.get("band"),
        "request": request,
        "why_selected": case.get("why"),
        "seed_queries": seed_queries,
        "ts": _now(),
        "model": model,
        "definition": {
            "answer_without_web": (
                "Final user-facing answer generated without search_web "
                "and without web results (not an internal draft)."
            ),
            "answer_with_web": (
                "Final user-facing answer generated after executing search_web "
                "and providing hits to the LLM."
            ),
            "not_agent_judgment_score": True,
            "not_using_pre_web_answer_candidate": True,
            "local_tools_forbidden": True,
        },
        "web_need": "",
        "web_effect": "",
        "factual_effect": "",
        "overall_effect": "",
        "reason": "",
        "reviewer_note": "",
    }
    try:
        without = generate_answer_without_web(request=request, model=model)
        payload.update(without)
    except Exception as exc:  # noqa: BLE001
        payload["answer_without_web"] = ""
        payload["without_web_error"] = f"{type(exc).__name__}: {exc}"
        payload["without_web_traceback"] = traceback.format_exc()

    try:
        with_web = generate_answer_with_web(
            request=request,
            model=model,
            limit=limit_hits,
            seed_queries=seed_queries,
            require_hits=require_hits,
        )
        payload["answer_with_web"] = with_web.get("answer_with_web") or ""
        payload["web_search"] = with_web.get("web_search")
        payload["with_web_meta"] = with_web.get("meta")
    except Exception as exc:  # noqa: BLE001
        payload["answer_with_web"] = ""
        payload["with_web_error"] = f"{type(exc).__name__}: {exc}"
        payload["with_web_traceback"] = traceback.format_exc()
        payload["skipped_no_hits"] = require_hits

    return payload


def build_review_outputs(
    results: list[dict],
    out_dir: Path,
    *,
    title: str = "WEB効果比較カード",
    stem: str = "web_effect_review",
) -> None:
    """CSV / JSON / COMPARE を書き出す。"""
    import csv

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"
    compare_path = out_dir / (
        "COMPARE.md" if stem == "web_effect_review" else f"COMPARE_{stem}.md"
    )

    json_path.write_text(
        json.dumps(
            {
                "kind": stem,
                "not_agent_gold": True,
                "no_auto_labels": True,
                "case_count": len(results),
                "hits_gt_0_count": sum(
                    1
                    for r in results
                    if ((r.get("web_search") or {}).get("result") or {}).get("hit_count")
                    or 0
                ),
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    fields = [
        "case_id",
        "band",
        "request",
        "answer_without_web",
        "answer_with_web",
        "web_search_query",
        "web_hit_count",
        "web_search_error",
        "web_need",
        "web_effect",
        "factual_effect",
        "overall_effect",
        "reason",
        "reviewer_note",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in results:
            ws = row.get("web_search") or {}
            res = ws.get("result") or {}
            writer.writerow(
                {
                    "case_id": row.get("case_id"),
                    "band": row.get("band"),
                    "request": row.get("request"),
                    "answer_without_web": row.get("answer_without_web") or "",
                    "answer_with_web": row.get("answer_with_web") or "",
                    "web_search_query": ws.get("query") or "",
                    "web_hit_count": res.get("hit_count"),
                    "web_search_error": res.get("error") or "",
                    "web_need": "",
                    "web_effect": "",
                    "factual_effect": "",
                    "overall_effect": "",
                    "reason": "",
                    "reviewer_note": "",
                }
            )

    compare_lines = [
        f"# {title}",
        "",
        "主比較は **answer_without_web（完成回答）** と **answer_with_web（完成回答）**。",
        "検索結果は補助。heuristic / search呼否は正解ラベルではない。",
        "",
        "記入列: web_need / web_effect / factual_effect / overall_effect / reason / reviewer_note",
        "",
    ]
    for row in results:
        ws = row.get("web_search") or {}
        res = ws.get("result") or {}
        compare_lines.extend(
            [
                f"## {row.get('case_id')} · band={row.get('band')} · hits={res.get('hit_count')}",
                "",
                "### request",
                "",
                "```text",
                str(row.get("request") or ""),
                "```",
                "",
                "### answer_without_web（WEBなし・完成回答）",
                "",
                "```text",
                str(row.get("answer_without_web") or "(empty)"),
                "```",
                "",
                "### web_search（補助）",
                "",
                f"- query: `{ws.get('query')}`",
                f"- hit_count: `{res.get('hit_count')}`",
                f"- error: `{res.get('error')}`",
                "",
                "```json",
                json.dumps(res.get("hits") or [], ensure_ascii=False, indent=2),
                "```",
                "",
                "### answer_with_web（WEBあり・完成回答）",
                "",
                "```text",
                str(row.get("answer_with_web") or "(empty)"),
                "```",
                "",
                "---",
                "",
            ]
        )
    compare_path.write_text("\n".join(compare_lines), encoding="utf-8")
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    print(f"wrote {compare_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--limit-hits", type=int, default=5)
    parser.add_argument(
        "--require-hits",
        action="store_true",
        help="hits>0 のケースだけレビュー成果物に含める",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=0,
        help="hits成功がこの件数に達したら打ち切り（0=全件）",
    )
    parser.add_argument(
        "--review-stem",
        default="web_effect_review",
        help="出力ファイル名の stem（例: web_effect_review_hits）",
    )
    parser.add_argument("--case-pause", type=float, default=2.0)
    args = parser.parse_args(argv)

    profile = get_llm_profile()
    model = profile["model"]
    data = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = list(data.get("cases") or [])
    if args.only:
        wanted = set(args.only)
        cases = [c for c in cases if c.get("id") in wanted]

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    accepted: list[dict] = []
    skipped: list[dict] = []
    print(
        f"model={model} cases={len(cases)} out={out_dir} "
        f"require_hits={args.require_hits} target={args.target or 'all'}"
    )
    for case in cases:
        if args.target and len(accepted) >= args.target:
            print(f"target reached: {args.target}")
            break
        cid = case.get("id")
        print(f"\n=== {cid} ({case.get('band')}) ===")
        print(case.get("request"))
        row = run_case(
            case,
            model=model,
            require_hits=args.require_hits,
            limit_hits=args.limit_hits,
        )
        case_path = out_dir / f"{cid}.json"
        case_path.write_text(
            json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        results.append(row)
        hit_n = ((row.get("web_search") or {}).get("result") or {}).get("hit_count") or 0
        ok_pair = bool(
            (row.get("answer_without_web") or "").strip()
            and (row.get("answer_with_web") or "").strip()
            and hit_n > 0
        )
        print(
            f"without_len={len(row.get('answer_without_web') or '')} "
            f"with_len={len(row.get('answer_with_web') or '')} "
            f"hits={hit_n} accepted={ok_pair}"
        )
        if ok_pair:
            accepted.append(row)
        else:
            skipped.append(
                {
                    "case_id": cid,
                    "hits": hit_n,
                    "error": row.get("with_web_error")
                    or ((row.get("web_search") or {}).get("result") or {}).get("error"),
                }
            )
        time.sleep(args.case_pause)

    review_rows = accepted if args.require_hits else results
    build_review_outputs(
        review_rows,
        HERE,
        title="WEB効果比較（hits取得ケース）"
        if args.require_hits
        else "WEB効果比較カード",
        stem=args.review_stem,
    )
    manifest = {
        "finished_at": _now(),
        "model": model,
        "temperature": profile.get("temperature"),
        "require_hits": args.require_hits,
        "attempted": [r.get("case_id") for r in results],
        "accepted_hits": [r.get("case_id") for r in accepted],
        "skipped": skipped,
        "accepted_count": len(accepted),
        "out_dir": str(out_dir),
        "review_stem": args.review_stem,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"\naccepted_hits={len(accepted)} skipped={len(skipped)} "
        f"review_stem={args.review_stem}"
    )
    return 0 if (not args.require_hits or len(accepted) >= 20) else 2


if __name__ == "__main__":
    raise SystemExit(main())