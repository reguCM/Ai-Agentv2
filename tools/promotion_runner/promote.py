#!/usr/bin/env python3
"""Promotion Runner — config-driven Local/fixed promote automation (no Strong LLM).

Exit codes:
  0 PASS / dry-run-ok
  1 ERROR (usage / config / runtime)
  2 FAIL (policy / path / tests)
  3 NEED_HUMAN (conflict, gated action, stop-before-commit)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

EXIT_PASS = 0
EXIT_ERROR = 1
EXIT_FAIL = 2
EXIT_NEED_HUMAN = 3


class Result:
    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self.failed = False
        self.need_human = False
        self.plan: Dict[str, Any] = {}
        self.paths: List[str] = []
        self.promote_branch: Optional[str] = None
        self.promote_sha: Optional[str] = None
        self.worktree: Optional[str] = None
        self.impact: List[Dict[str, str]] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.checks.append({"name": name, "status": "PASS", "detail": detail})

    def fail(self, name: str, detail: str) -> None:
        self.failed = True
        self.checks.append({"name": name, "status": "FAIL", "detail": detail})

    def human(self, name: str, detail: str) -> None:
        self.need_human = True
        self.checks.append({"name": name, "status": "NEED_HUMAN", "detail": detail})

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def exit_code(self) -> int:
        if self.errors:
            return EXIT_ERROR
        if self.need_human:
            return EXIT_NEED_HUMAN
        if self.failed:
            return EXIT_FAIL
        return EXIT_PASS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.exit_code() == EXIT_PASS,
            "exit_code": self.exit_code(),
            "checks": self.checks,
            "errors": self.errors,
            "plan": self.plan,
            "paths": self.paths,
            "promote_branch": self.promote_branch,
            "promote_sha": self.promote_sha,
            "worktree": self.worktree,
            "impact_sync": self.impact,
        }


def run_git(repo: str, args: Sequence[str], timeout: int = 120) -> Tuple[int, str, str]:
    cmd = ["git", "-C", repo, *args]
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "git not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"git timed out: {' '.join(args)}"


def match_any(path: str, patterns: Sequence[str]) -> bool:
    path = path.replace("\\", "/")
    for pat in patterns:
        pat_n = pat.replace("\\", "/")
        if fnmatch.fnmatch(path, pat_n) or fnmatch.fnmatch(Path(path).name, pat_n):
            return True
        if "/" not in pat_n.rstrip("/") and fnmatch.fnmatch(path, f"**/{pat_n}"):
            return True
    return False


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config root must be an object")
    if "repo" not in data:
        raise ValueError("config.repo is required")
    return data


def resolve_repo(cfg_repo: Any) -> str:
    env_repo = (os.environ.get("PROMOTION_RUNNER_REPO") or "").strip()
    if env_repo:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(env_repo)))
    raw = "" if cfg_repo is None else str(cfg_repo).strip()
    if raw in ("", "."):
        p = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        top = (p.stdout or "").strip()
        if p.returncode != 0 or not top:
            raise ValueError(f"cannot resolve repo '.': {(p.stderr or '').strip()}")
        return os.path.abspath(top)
    return os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))


def ref_exists(repo: str, ref: str) -> bool:
    code, _, _ = run_git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    return code == 0


def rev_parse(repo: str, ref: str) -> Optional[str]:
    code, out, _ = run_git(repo, ["rev-parse", ref])
    return out if code == 0 else None


def collect_delta_paths(repo: str, cfg: Dict[str, Any], result: Result) -> List[str]:
    paths: List[str] = []
    seen = set()

    def add(text: str) -> None:
        for ln in text.splitlines():
            p = ln.strip().replace("\\", "/")
            if p and p not in seen:
                seen.add(p)
                paths.append(p)

    explicit = cfg.get("paths")
    if explicit:
        for p in explicit:
            add(str(p))
        result.ok("paths", f"{len(paths)} explicit paths")
        return paths

    source_from = cfg.get("source_from")
    source_to = cfg.get("source_to") or cfg.get("source_ref")
    if source_from and source_to:
        code, out, err = run_git(repo, ["diff", "--name-only", f"{source_from}..{source_to}"])
        if code != 0:
            result.fail("delta_paths", f"diff failed: {err or out}")
            return []
        add(out)
        result.ok("delta_paths", f"{source_from}..{source_to} -> {len(paths)} paths")
        return paths

    if source_to and cfg.get("paths") is None:
        # tip tree listing requires paths or from..to
        result.error("need source_from+source_to or paths[]")
        return []

    result.error("cannot determine path set (set source_from/source_to or paths)")
    return []


def filter_paths(paths: List[str], cfg: Dict[str, Any], result: Result) -> List[str]:
    ignore = cfg.get("ignore_path_globs") or []
    deny = cfg.get("deny_path_globs") or []
    allow = cfg.get("allow_path_globs")

    if ignore:
        before = len(paths)
        paths = [p for p in paths if not match_any(p, ignore)]
        result.ok("ignore_path_globs", f"ignored {before - len(paths)}")

    denied = [p for p in paths if deny and match_any(p, deny)]
    if denied:
        result.fail("deny_path_globs", f"denied: {denied[:30]}")
    else:
        result.ok("deny_path_globs", "ok")

    if allow is not None:
        bad = [p for p in paths if not match_any(p, allow)]
        if bad:
            result.fail("allow_path_globs", f"outside allow: {bad[:30]}")
        else:
            result.ok("allow_path_globs", f"all {len(paths)} allowed")
    return paths


def check_forbid_overlap(repo: str, cfg: Dict[str, Any], paths: List[str], result: Result) -> None:
    refs = cfg.get("forbid_overlap_refs") or []
    if not refs:
        return
    current = set(paths)
    for ref in refs:
        code, out, err = run_git(repo, ["diff-tree", "--no-commit-id", "--name-only", "-r", ref])
        if code != 0:
            result.fail("forbid_overlap_refs", f"{ref}: {err or out}")
            continue
        other = {ln.replace("\\", "/") for ln in out.splitlines() if ln.strip()}
        overlap = sorted(current & other)
        if overlap:
            result.fail("forbid_overlap_refs", f"overlap with {ref}: {overlap[:30]}")
        else:
            result.ok("forbid_overlap_refs", f"no overlap with {ref}")


def invoke_git_guard(cfg: Dict[str, Any], result: Result, *, phase: str) -> None:
    gg = cfg.get("git_guard_config")
    if not gg:
        return
    # Resolve guard.py: sibling _git-guard, or in-repo tools/git_guard, or env
    candidates = []
    env_g = (os.environ.get("GIT_GUARD_ROOT") or "").strip()
    if env_g:
        candidates.append(Path(env_g) / "guard.py")
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "_git-guard" / "guard.py")
    candidates.append(here / ".." / ".." / ".." / "AI-Agent" / "tools" / "git_guard" / "guard.py")
    repo = cfg.get("repo") or ""
    if repo:
        candidates.append(Path(repo) / "tools" / "git_guard" / "guard.py")
    guard_py = None
    for c in candidates:
        c = c.resolve()
        if c.is_file():
            guard_py = c
            break
    if not guard_py:
        result.fail(f"git_guard_{phase}", "guard.py not found")
        return
    gg_path = Path(gg)
    if not gg_path.is_file():
        # relative to runner root or repo
        for base in (here, Path(repo) if repo else Path(".")):
            cand = (base / gg).resolve()
            if cand.is_file():
                gg_path = cand
                break
    cmd = [sys.executable, str(guard_py), "--config", str(gg_path)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        result.fail(f"git_guard_{phase}", f"{type(exc).__name__}: {exc}")
        return
    if p.returncode == 0:
        result.ok(f"git_guard_{phase}", "PASS")
    elif p.returncode == 3:
        result.human(f"git_guard_{phase}", (p.stdout or p.stderr or "")[-400:])
    else:
        result.fail(f"git_guard_{phase}", f"exit {p.returncode}: {(p.stdout or p.stderr or '')[-400:]}")


def build_impact(cfg: Dict[str, Any], result: Result) -> None:
    surfaces = cfg.get("impact_sync") or [
        "正本",
        "Rule",
        "Help",
        "Registry",
        "Test",
    ]
    for s in surfaces:
        result.impact.append(
            {
                "surface": s,
                "status": "checked",
                "note": "Recorded by Promotion Runner; fill details in report if needed.",
            }
        )
    result.ok("impact_sync", f"{len(result.impact)} surfaces listed")


def write_report(cfg: Dict[str, Any], result: Result, report_dir: Path, name: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    base = report_dir / f"{name}-{stamp}"
    base.mkdir(parents=True, exist_ok=True)
    plan_path = base / "PLAN.md"
    paths_path = base / "paths.json"
    json_path = base / "report.json"
    md_path = base / "REPORT.md"

    paths_path.write_text(json.dumps(result.paths, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    plan_lines = [
        f"# Promotion PLAN — {name}",
        "",
        f"- generated: {stamp}",
        f"- mode: {cfg.get('mode')}",
        f"- target_base: {cfg.get('target_base')}",
        f"- target_branch: {cfg.get('target_branch')}",
        f"- source: {cfg.get('source_from')}..{cfg.get('source_to') or cfg.get('source_ref')}",
        f"- paths: {len(result.paths)}",
        f"- apply: {result.plan.get('apply')}",
        f"- promote_branch: {result.promote_branch}",
        f"- promote_sha: {result.promote_sha}",
        "",
        "## Paths",
        "",
    ]
    for p in result.paths:
        plan_lines.append(f"- `{p}`")
    plan_lines += ["", "## Checks", ""]
    for c in result.checks:
        plan_lines.append(f"- [{c['status']}] {c['name']}: {c.get('detail','')}")
    if result.errors:
        plan_lines += ["", "## Errors", ""]
        for e in result.errors:
            plan_lines.append(f"- {e}")
    plan_path.write_text("\n".join(plan_lines) + "\n", encoding="utf-8")

    impact_rows = "\n".join(
        f"| {i['surface']} | {i['status']} | {i['note']} |" for i in result.impact
    )
    md = f"""# Promotion REPORT — {name}

- exit: {result.exit_code()}
- promote_branch: `{result.promote_branch}`
- promote_sha: `{result.promote_sha}`
- worktree: `{result.worktree}`

## IMPACT_SYNC

| Surface | Status | Note |
|---------|--------|------|
{impact_rows}

## Human gate

Merge promote → stabilize, push, reset_hard, delete_branch require human (exit 3).
Do not auto-merge. Do not GitHub push from Runner.

See PLAN.md and paths.json in this folder.
"""
    md_path.write_text(md, encoding="utf-8")
    result.ok("report", str(base))
    return base


def ensure_sparse_worktree(
    repo: str,
    branch: str,
    base_ref: str,
    worktree: str,
    sparse_dirs: List[str],
    result: Result,
    create_branch: bool,
) -> Optional[str]:
    wt = Path(worktree)
    if wt.exists():
        # reuse if already a worktree
        code, out, _ = run_git(repo, ["worktree", "list", "--porcelain"])
        if str(wt).replace("\\", "/") not in out.replace("\\", "/"):
            result.error(f"worktree path exists but not registered: {wt}")
            return None
        result.ok("worktree", f"reuse {wt}")
        return str(wt)

    wt.parent.mkdir(parents=True, exist_ok=True)
    if create_branch:
        # create branch from base if missing
        if not ref_exists(repo, branch):
            code, _, err = run_git(repo, ["branch", branch, base_ref])
            if code != 0:
                result.error(f"create branch {branch}: {err}")
                return None
        code, _, err = run_git(
            repo,
            ["worktree", "add", "--no-checkout", str(wt), branch],
        )
    else:
        code, _, err = run_git(
            repo,
            ["worktree", "add", "--no-checkout", str(wt), "-b", branch, base_ref],
        )
    if code != 0:
        # maybe branch exists
        code2, _, err2 = run_git(repo, ["worktree", "add", "--no-checkout", str(wt), branch])
        if code2 != 0:
            result.error(f"worktree add failed: {err or err2}")
            return None

    # sparse checkout
    code, _, err = run_git(str(wt), ["sparse-checkout", "init", "--cone"])
    if code != 0:
        result.error(f"sparse-checkout init: {err}")
        return None
    if sparse_dirs:
        code, _, err = run_git(str(wt), ["sparse-checkout", "set", *sparse_dirs])
        if code != 0:
            result.error(f"sparse-checkout set: {err}")
            return None
    code, _, err = run_git(str(wt), ["checkout"])
    if code != 0:
        result.error(f"sparse checkout: {err}")
        return None
    result.ok("worktree", f"created {wt} on {branch}")
    result.worktree = str(wt)
    return str(wt)


def sparse_dirs_from_paths(paths: List[str]) -> List[str]:
    tops = set()
    for p in paths:
        parts = p.replace("\\", "/").split("/")
        if len(parts) >= 2:
            tops.add("/".join(parts[:2]))
        elif parts:
            tops.add(parts[0])
    # always include tools if promoting tooling
    return sorted(tops)


def apply_diff(
    wt: str,
    repo: str,
    cfg: Dict[str, Any],
    paths: List[str],
    result: Result,
) -> bool:
    mode = (cfg.get("mode") or "diff_apply").strip()
    source_from = cfg.get("source_from")
    source_to = cfg.get("source_to") or cfg.get("source_ref")

    if mode == "path_checkout":
        tip = source_to
        if not tip:
            result.error("path_checkout requires source_to/source_ref")
            return False
        code, _, err = run_git(wt, ["checkout", tip, "--", *paths])
        if code != 0:
            result.human("path_checkout", f"conflict or fail: {err}")
            return False
        result.ok("path_checkout", f"checked out {len(paths)} paths from {tip}")
        return True

    if mode != "diff_apply":
        result.error(f"unknown mode: {mode}")
        return False

    if not source_from or not source_to:
        result.error("diff_apply requires source_from and source_to")
        return False

    # Write patch to temp
    patch_dir = Path(cfg.get("report_dir") or Path(__file__).parent / "reports")
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_path = patch_dir / "_last_delta.patch"
    code, out, err = run_git(repo, ["diff", "--binary", f"{source_from}..{source_to}", "--", *paths])
    if code != 0:
        result.fail("diff_apply", f"git diff failed: {err}")
        return False
    patch_path.write_bytes((out + "\n").encode("utf-8", errors="replace") if out else b"")
    if not out.strip():
        result.ok("diff_apply", "empty diff for filtered paths")
        return True

    code, _, err = run_git(wt, ["apply", "--check", str(patch_path)])
    if code != 0:
        result.human(
            "diff_apply",
            f"patch does not apply cleanly onto target (conflict). Stop for human/Strong port. detail={err[:500]}",
        )
        return False
    code, _, err = run_git(wt, ["apply", str(patch_path)])
    if code != 0:
        result.human("diff_apply", f"apply failed: {err[:500]}")
        return False
    result.ok("diff_apply", f"applied patch ({patch_path})")
    return True


def maybe_commit(wt: str, cfg: Dict[str, Any], result: Result) -> None:
    auto = bool(cfg.get("auto_commit", True))
    if not auto:
        result.human("commit", "auto_commit false — index left for human")
        return
    code, status, _ = run_git(wt, ["status", "--porcelain"])
    if code != 0:
        result.error("status failed")
        return
    if not status.strip():
        result.ok("commit", "nothing to commit")
        return
    run_git(wt, ["add", "-A"])
    msg_tmpl = cfg.get("commit_message") or "promote: apply delta onto {target_base}"
    msg = msg_tmpl.format(
        target_base=cfg.get("target_base", ""),
        target_branch=cfg.get("target_branch", ""),
        source_from=cfg.get("source_from", ""),
        source_to=cfg.get("source_to") or cfg.get("source_ref", ""),
        name=cfg.get("name", "delta"),
    )
    code, _, err = run_git(wt, ["commit", "-m", msg])
    if code != 0:
        # hooks may NEED_HUMAN on some configs — treat as human
        if "NEED_HUMAN" in (err or "") or "NEED_HUMAN" in _:
            result.human("commit", err or _)
        else:
            result.error(f"commit failed: {err}")
        return
    sha = rev_parse(wt, "HEAD")
    result.promote_sha = sha
    result.ok("commit", f"committed {sha}")


def run_tests(cfg: Dict[str, Any], wt: str, result: Result, do_run: bool) -> None:
    tests = cfg.get("required_tests") or []
    if not tests:
        return
    if not do_run:
        result.ok("required_tests", f"{len(tests)} configured (skipped; pass --run-tests)")
        return
    if result.failed or result.need_human or result.errors:
        result.ok("required_tests", "skipped due to prior failure")
        return
    for i, t in enumerate(tests):
        cmd = t.get("cmd")
        if not cmd:
            result.error(f"required_tests[{i}].cmd required")
            continue
        cwd = t.get("cwd") or wt
        timeout = int(t.get("timeout_sec") or 300)
        try:
            p = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            if p.returncode != 0:
                tail = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()[-600:]
                result.fail(f"required_tests[{i}]", f"exit {p.returncode}: {tail}")
            else:
                result.ok(f"required_tests[{i}]", f"ok ({cmd})")
        except Exception as exc:  # noqa: BLE001
            result.fail(f"required_tests[{i}]", f"{type(exc).__name__}: {exc}")


def check_human_gates(cfg: Dict[str, Any], result: Result) -> None:
    gates = [a.lower() for a in (cfg.get("human_gate_actions") or [])]
    proposed = cfg.get("proposed_actions") or []
    for a in proposed:
        al = str(a).lower()
        if al in gates or al in ("merge", "push", "reset_hard", "delete_branch", "force_push"):
            result.human("human_gate_actions", f"action '{al}' requires human — Runner stops")


def run_promote(cfg: Dict[str, Any], *, apply: bool, run_tests_flag: bool) -> Result:
    result = Result()
    try:
        repo = resolve_repo(cfg.get("repo"))
    except ValueError as exc:
        result.error(str(exc))
        return result
    cfg = {**cfg, "repo": repo}
    result.plan = {
        "apply": apply,
        "mode": cfg.get("mode"),
        "repo": repo,
    }

    # validate refs
    target_base = cfg.get("target_base")
    target_branch = cfg.get("target_branch")
    source_from = cfg.get("source_from")
    source_to = cfg.get("source_to") or cfg.get("source_ref")
    for label, ref in [
        ("target_base", target_base),
        ("source_from", source_from),
        ("source_to", source_to),
    ]:
        if ref and not ref_exists(repo, str(ref)):
            result.error(f"{label} ref missing: {ref}")
    if result.errors:
        return result
    result.ok("refs", "required refs exist")

    if not target_branch:
        result.error("target_branch required")
        return result
    if not target_base:
        result.error("target_base required")
        return result

    result.promote_branch = target_branch
    paths = collect_delta_paths(repo, cfg, result)
    if result.errors or result.failed:
        return result
    paths = filter_paths(paths, cfg, result)
    result.paths = paths
    if result.failed:
        return result
    check_forbid_overlap(repo, cfg, paths, result)
    if result.failed:
        return result

    check_human_gates(cfg, result)
    build_impact(cfg, result)

    # optional guard before apply
    if cfg.get("git_guard_config"):
        invoke_git_guard(cfg, result, phase="before_apply")

    report_dir = Path(cfg.get("report_dir") or (Path(__file__).parent / "reports"))
    name = str(cfg.get("name") or Path(target_branch).name)

    if not apply:
        result.plan["note"] = "dry-run only; no git mutations"
        write_report(cfg, result, report_dir, name)
        return result

    if result.need_human and not cfg.get("apply_even_if_need_human"):
        write_report(cfg, result, report_dir, name)
        return result

    # apply worktree
    wt_cfg = cfg.get("apply_worktree") or ""
    if not wt_cfg:
        wt_cfg = str(Path(repo).parent / "AI-Agent-worktrees" / f"_promote-{name}")
        # better: sibling of canonical
        alt = Path(r"D:\AI-Agent-worktrees") / f"_promote-{name}"
        wt_cfg = str(alt)

    sparse = cfg.get("sparse_dirs") or sparse_dirs_from_paths(paths)
    # ensure tools dir if present in paths
    create_new = not ref_exists(repo, target_branch)
    if create_new:
        code, _, err = run_git(repo, ["branch", target_branch, target_base])
        if code != 0:
            result.error(f"branch create: {err}")
            write_report(cfg, result, report_dir, name)
            return result
        # reset branch to base if existed with wrong tip? only create path here
    else:
        # branch exists — verify it is based appropriately; do not rewrite history
        sha = rev_parse(repo, target_branch)
        result.ok("target_branch_exists", f"{target_branch} @ {sha}")

    wt = ensure_sparse_worktree(
        repo, target_branch, target_base, wt_cfg, list(sparse), result, create_branch=False
    )
    if not wt:
        write_report(cfg, result, report_dir, name)
        return result
    result.worktree = wt

    # If branch already had commits, leave them; still try apply on current tip
    # Prefer: reset soft not allowed; if branch just created from base, tip == base
    ok = apply_diff(wt, repo, cfg, paths, result)
    if not ok:
        write_report(cfg, result, report_dir, name)
        return result

    if cfg.get("git_guard_config"):
        # run guard in worktree context via env
        os.environ["GIT_GUARD_REPO"] = wt
        invoke_git_guard(cfg, result, phase="before_commit")

    maybe_commit(wt, cfg, result)
    if not result.promote_sha:
        result.promote_sha = rev_parse(wt, "HEAD")

    run_tests(cfg, wt, result, run_tests_flag)
    write_report(cfg, result, report_dir, name)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Promotion Runner (Local/fixed, no LLM)")
    parser.add_argument("--config", required=True)
    parser.add_argument("--apply", action="store_true", help="Apply into promote branch (default dry-run)")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        cfg = load_config(args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] config: {exc}", file=sys.stderr)
        return EXIT_ERROR

    t0 = time.time()
    result = run_promote(cfg, apply=args.apply, run_tests_flag=args.run_tests)
    elapsed = round(time.time() - t0, 3)

    if args.json:
        payload = result.to_dict()
        payload["elapsed_sec"] = elapsed
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for c in result.checks:
            print(f"[{c['status']}] {c['name']}: {c.get('detail','')}")
        for e in result.errors:
            print(f"[ERROR] {e}")
        code = result.exit_code()
        label = {0: "PASS", 1: "ERROR", 2: "FAIL", 3: "NEED_HUMAN"}.get(code, str(code))
        print(f"RESULT: {label} (exit {code}) elapsed={elapsed}s")
        if result.promote_branch:
            print(f"promote_branch={result.promote_branch} sha={result.promote_sha}")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
