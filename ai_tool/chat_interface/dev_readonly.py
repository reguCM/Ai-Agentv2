"""Chat UI 用の読み取り専用 Development 情報。

Git 書き込み・pytest 実行・Cursor API はしない。
新しい Core ではない。
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
RUNS_DIR = _REPO / "runs" / "ai_tool"
REPORTS_DIR = _REPO / "docs" / "ai_tool" / "project_audit"
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_REPORT = re.compile(r"^[A-Za-z0-9._-]+\.md$")
DIFF_LIMIT = 80_000
FILES_LIMIT = 250
GIT_TIMEOUT = 20

GIT_ALLOWED = {
    ("status", "--porcelain", "-uall"): "status",
    ("diff", "--stat", "--no-color"): "diff_stat",
    ("diff", "--no-color"): "diff",
    ("rev-parse", "--abbrev-ref", "HEAD"): "branch",
    ("rev-parse", "HEAD"): "head",
    ("log", "-n", "20", "--date=iso-strict", "--pretty=format:%H%x09%ad%x09%s"): "log",
}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO)).replace("\\", "/")
    except ValueError:
        return path.name


def _iso_from_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def _resolve_under(root: Path, name: str) -> Path | None:
    if not name or ".." in name or "/" in name or "\\" in name:
        return None
    root_r = root.resolve()
    candidate = (root_r / name).resolve()
    try:
        candidate.relative_to(root_r)
    except ValueError:
        return None
    return candidate


def mechanical_tests() -> dict[str, Any]:
    """pytest の機械結果ファイルだけを見る。報告書の passed は使わない。"""
    found: list[str] = []
    if RUNS_DIR.is_dir():
        for path in RUNS_DIR.rglob("*"):
            if path.is_file() and path.name.lower() in {"pytest.xml", "junit.xml", "pytest-junit.xml"}:
                found.append(_rel(path))
    return {
        "available": bool(found),
        "source": "pytest_xml" if found else "missing",
        "files": found,
        "user_message": "機械的テスト結果：未取得" if not found else "機械的テスト結果ファイルがあります",
        "note": "Cursor の報告書にある passed 件数は、この欄に使いません。",
    }


def _cursor_claim_from_observations(data: dict[str, Any]) -> dict[str, Any] | None:
    unit = data.get("unit_tests")
    if not isinstance(unit, dict):
        return None
    text = str(unit.get("result") or "").strip()
    if not text:
        return None
    return {
        "source": "cursor_report",
        "executor": unit.get("executor") or "cursor",
        "text": text,
        "counts_as_pytest": False,
        "counts_as_local_agent": bool(unit.get("counts_as_local_agent")),
        "note": "Cursor の報告です。pytest の機械結果ではありません。",
    }


def list_runs() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if RUNS_DIR.is_dir():
        for folder in sorted(RUNS_DIR.iterdir(), reverse=True):
            if not folder.is_dir() or not SAFE_ID.match(folder.name):
                continue
            summary_path = folder / "summary.json"
            if not summary_path.is_file():
                continue
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(summary, dict):
                continue
            items.append(
                {
                    "run_id": folder.name,
                    "judgment": summary.get("judgment"),
                    "judgment_ja": summary.get("judgment_ja"),
                    "summary_mtime": _iso_from_mtime(summary_path),
                    "session_id": summary.get("session_id"),
                    "has_observations": (folder / "observations.json").is_file(),
                    "source": "summary.json",
                }
            )
    return {
        "ok": True,
        "source": "runs/ai_tool",
        "kind": "development",
        "runs": items,
        "mechanical_tests": mechanical_tests(),
    }


def get_run(run_id: str) -> dict[str, Any]:
    folder = _resolve_under(RUNS_DIR, run_id)
    if folder is None or not SAFE_ID.match(run_id):
        return {"ok": False, "error": "不正な Run ID です", "error_kind": "invalid_id"}
    if not folder.is_dir():
        return {"ok": False, "error": "指定された Run はありません", "error_kind": "not_found"}
    summary_path = folder / "summary.json"
    if not summary_path.is_file():
        return {"ok": False, "error": "指定された Run はありません", "error_kind": "not_found"}
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"summary.json を読めません: {exc}", "error_kind": "read_error"}
    if not isinstance(summary, dict):
        summary = {}
    observations = None
    obs_path = folder / "observations.json"
    if obs_path.is_file():
        try:
            raw = json.loads(obs_path.read_text(encoding="utf-8"))
            observations = raw if isinstance(raw, dict) else None
        except (OSError, json.JSONDecodeError):
            observations = None
    files = sorted(p.name for p in folder.iterdir() if p.is_file())
    junit = [
        name
        for name in files
        if name.lower() in {"pytest.xml", "junit.xml", "pytest-junit.xml"}
    ]
    return {
        "ok": True,
        "kind": "development",
        "run_id": run_id,
        "summary": summary,
        "observations": observations,
        "files": files,
        "summary_mtime": _iso_from_mtime(summary_path),
        "path": _rel(folder),
        "cursor_test_report": _cursor_claim_from_observations(observations or {}),
        "mechanical_tests": {
            "available": bool(junit),
            "source": "pytest_xml" if junit else "missing",
            "files": junit,
            "user_message": "機械的テスト結果：未取得" if not junit else "機械的テスト結果ファイルがあります",
            "note": "Cursor の報告書にある passed 件数は、この欄に使いません。",
        },
    }


def list_reports() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if REPORTS_DIR.is_dir():
        for path in sorted(REPORTS_DIR.iterdir(), reverse=True):
            if not path.is_file() or not SAFE_REPORT.match(path.name):
                continue
            items.append(
                {
                    "name": path.name,
                    "mtime": _iso_from_mtime(path),
                    "chars": path.stat().st_size,
                    "source": "docs/ai_tool/project_audit",
                }
            )
    return {"ok": True, "kind": "development", "reports": items}


def get_report(name: str) -> dict[str, Any]:
    path = _resolve_under(REPORTS_DIR, name)
    if path is None or not SAFE_REPORT.match(name):
        return {"ok": False, "error": "不正な報告書名です", "error_kind": "invalid_id"}
    if not path.is_file():
        return {"ok": False, "error": "指定された報告書はありません", "error_kind": "not_found"}
    text = path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "kind": "development",
        "name": name,
        "text": text,
        "mtime": _iso_from_mtime(path),
        "path": _rel(path),
        "note": "報告書は説明です。Run / Git / pytest 機械結果の代わりではありません。",
    }


def _git(args: tuple[str, ...]) -> tuple[int, str, str]:
    if args not in GIT_ALLOWED:
        return 1, "", "許可されていない git 引数です"
    proc = subprocess.run(
        ["git", *args],
        cwd=_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT,
        shell=False,
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _count_porcelain(lines: list[str]) -> tuple[dict[str, int], list[dict[str, str]]]:
    modified = added = deleted = untracked = 0
    files: list[dict[str, str]] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line:
            continue
        code = line[:2]
        path = line[3:] if len(line) > 3 else ""
        if code == "??":
            untracked += 1
            state = "untracked"
        elif "D" in code:
            deleted += 1
            state = "deleted"
        elif "A" in code:
            added += 1
            state = "added"
        else:
            modified += 1
            state = "modified"
        files.append({"path": path, "code": code, "state": state})
    return (
        {
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "untracked": untracked,
        },
        files,
    )


def _parse_git_log(text: str) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        commits.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
    return commits


def git_snapshot() -> dict[str, Any]:
    try:
        st_code, st_out, st_err = _git(("status", "--porcelain", "-uall"))
        stat_code, stat_out, stat_err = _git(("diff", "--stat", "--no-color"))
        diff_code, diff_out, diff_err = _git(("diff", "--no-color"))
        br_code, br_out, br_err = _git(("rev-parse", "--abbrev-ref", "HEAD"))
        hd_code, hd_out, hd_err = _git(("rev-parse", "HEAD"))
        lg_code, lg_out, lg_err = _git(
            ("log", "-n", "20", "--date=iso-strict", "--pretty=format:%H%x09%ad%x09%s")
        )
    except FileNotFoundError:
        return {"ok": False, "error": "git コマンドが見つかりません", "error_kind": "git_missing"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "git の読み取りが時間切れです", "error_kind": "timeout"}
    counts, files = _count_porcelain(st_out.splitlines())
    files_truncated = False
    if len(files) > FILES_LIMIT:
        files = files[:FILES_LIMIT]
        files_truncated = True
    truncated = False
    if len(diff_out) > DIFF_LIMIT:
        diff_out = diff_out[:DIFF_LIMIT] + "\n…（以降は省略）"
        truncated = True
    read_ok = st_code == 0 and stat_code == 0 and diff_code == 0
    return {
        "ok": read_ok,
        "kind": "development",
        "read_only": True,
        "commands": [
            "git status --porcelain -uall",
            "git diff --stat --no-color",
            "git diff --no-color",
            "git rev-parse --abbrev-ref HEAD",
            "git rev-parse HEAD",
            "git log -n 20 --date=iso-strict",
        ],
        "status_code": st_code,
        "status": st_out,
        "status_error": st_err or None,
        "diff_stat": stat_out,
        "diff_stat_error": stat_err or None,
        "diff": diff_out,
        "diff_error": diff_err or None,
        "diff_truncated": truncated,
        "counts": counts,
        "files": files,
        "files_truncated": files_truncated,
        "branch": br_out.strip() if br_code == 0 else None,
        "head": hd_out.strip() if hd_code == 0 else None,
        "commits": _parse_git_log(lg_out) if lg_code == 0 else [],
        "log_error": lg_err or None,
        "note": "読み取り専用です。commit / push / checkout はしません。",
    }


def tests_snapshot() -> dict[str, Any]:
    mech = mechanical_tests()
    return {
        "ok": True,
        "kind": "development",
        "mechanical_tests": mech,
        "cursor_test_report": None,
        "cursor_live": {
            "status": "NOT_OBSERVED",
            "label": "Cursor live status: NOT OBSERVED",
        },
        "note": (
            "機械的テスト結果と Cursor 報告は別です。"
            "Cursor 報告は各 Run の observations.json にある場合のみ Run 詳細で表示します。"
        ),
    }
