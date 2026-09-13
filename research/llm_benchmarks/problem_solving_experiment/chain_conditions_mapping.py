"""
調査連鎖実験の記録補助。

LLM の自然文は書き換えない。Mapping は別記録であり、正式仕様ではない。
識別子を search_files の query にしない（前回の may/and 誤認を繰り返さない）。
"""

from __future__ import annotations

import re
from pathlib import Path


_REQUEST = re.compile(
    r"(?:need(?:ed)?(?:\s+to)?|require(?:d)?|should|"
    r"want(?:\s+to)?|please|"
    r"read|inspect|check|examine|open|review|investigate|fetch|"
    r"look(?:ing)?\s+at|see|show|"
    r"implementation|definition|source|contents?|"
    r"必要|確認|読[むんで]|見[てる]|中身|実装|内容|取得|開[きく]|調べ|参照|ソース)",
    re.IGNORECASE,
)

_PY_FILE = re.compile(
    r"(?:`(?P<tick>[^`\n]+\.py)`|"
    r"(?P<path>(?:[A-Za-z]:)?(?:[/\\][\w.\-]+)+\.py)|"
    r"(?P<base>\b[\w.\-]+\.py\b))",
    re.IGNORECASE,
)

_CODE_FENCE = re.compile(r"```(?:python)?\n", re.IGNORECASE)


def split_keep(text):
    chunks = re.split(r"(?:\n{2,}|(?<=[.!?])\s+)", text or "")
    return [item.strip() for item in chunks if item and item.strip()]


def py_mentions_in(text):
    found = []
    for match in _PY_FILE.finditer(text or ""):
        raw = match.group("tick") or match.group("path") or match.group("base")
        if not raw:
            continue
        found.append(
            {
                "raw": raw,
                "basename": Path(str(raw).replace("\\", "/")).name,
                "span": [match.start(), match.end()],
            }
        )
    return found


def llm_investigation_record(raw_output):
    """自然文のまま抜粋する。ファイル/関数/行への正規化はしない。"""
    excerpts = []
    for chunk in split_keep(raw_output):
        if _REQUEST.search(chunk):
            excerpts.append(chunk)
    mentions = py_mentions_in(raw_output)
    return {
        "raw_output": raw_output,
        "raw_request_excerpts": excerpts,
        "py_filenames_as_written": [item["raw"] for item in mentions],
    }


def map_read_file(raw_output, *, fixture_files, already_read, source_already_given):
    """
    明示された fixture 内 .py だけ read_file に落とす。
    search_files / 識別子検索はしない。
    同一ファイルの後段 Inspect も見る（先頭の言い直しだけで捨てない）。
    """
    already = set(already_read or [])
    given = set(source_already_given or [])
    mapped = []
    not_converted = []
    for chunk in split_keep(raw_output):
        requestish = bool(_REQUEST.search(chunk))
        for mention in py_mentions_in(chunk):
            basename = mention["basename"]
            rel = fixture_files.get(basename) or fixture_files.get(basename.lower())
            if rel is None:
                # case-insensitive lookup
                rel = next(
                    (
                        path
                        for name, path in fixture_files.items()
                        if name.lower() == basename.lower()
                    ),
                    None,
                )
            if rel is None:
                if requestish:
                    not_converted.append(
                        {
                            "reason": "filename_not_in_fixture",
                            "excerpt": chunk,
                            "raw": mention["raw"],
                        }
                    )
                continue
            if basename in given or Path(rel).name in given:
                not_converted.append(
                    {
                        "reason": "source_already_in_prompt",
                        "excerpt": chunk,
                        "raw": mention["raw"],
                    }
                )
                continue
            if rel in already:
                not_converted.append(
                    {
                        "reason": "already_read",
                        "excerpt": chunk,
                        "raw": mention["raw"],
                    }
                )
                continue
            if not requestish:
                not_converted.append(
                    {
                        "reason": "filename_in_chunk_without_request_words",
                        "excerpt": chunk,
                        "raw": mention["raw"],
                    }
                )
                continue
            mapped.append(
                {
                    "tool_selected": "read_file",
                    "tool_arguments": {"path": rel},
                    "mapping_input_excerpt": chunk,
                    "mapping_note": (
                        "experiment continuation only: fixture basename near "
                        "request-like words in the same chunk. not a schema."
                    ),
                }
            )
    # 同じファイルへの重複は先頭だけ実行
    unique = []
    seen = set()
    for item in mapped:
        path = item["tool_arguments"]["path"]
        if path in seen:
            continue
        seen.add(path)
        unique.append(item)
    return {
        "mapped": unique,
        "not_converted": not_converted,
        "search_files_used": False,
    }


def next_read_mapping(raw_output, *, fixture_files, already_read, source_already_given):
    result = map_read_file(
        raw_output,
        fixture_files=fixture_files,
        already_read=already_read,
        source_already_given=source_already_given,
    )
    if result["mapped"]:
        return result["mapped"][0], result
    return None, result


def observation_flags(turns):
    joined = "\n".join(turn.get("llm_output") or "" for turn in turns)
    file_request = any(
        (turn.get("llm_investigation") or {}).get("py_filenames_as_written")
        and (turn.get("llm_investigation") or {}).get("raw_request_excerpts")
        for turn in turns
    )
    tool_turns = [turn for turn in turns if turn.get("tool_selected")]
    first = turns[0]["llm_output"] if turns else ""
    return {
        "investigation_started": bool(
            turns
            and (turns[0].get("llm_investigation") or {}).get("raw_request_excerpts")
        ),
        "file_request_observed": bool(file_request),
        "multi_step_investigation": len(tool_turns) >= 2,
        "hypothesis_updated": "NOT_SCORED_IN_HARNESS",
        "premature_repair": bool(_CODE_FENCE.search(first or ""))
        and not tool_turns,
        "note": "experiment log helpers only; not a success schema",
    }
