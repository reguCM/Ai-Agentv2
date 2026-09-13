#!/usr/bin/env python3
"""Git Guard — config-driven safety checks for Local/fixed automation (no LLM).

Exit codes:
  0 PASS
  1 usage / config / runtime error
  2 FAIL (policy block)
  3 NEED_HUMAN (dangerous op requires confirmation)
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


EXIT_PASS = 0
EXIT_USAGE = 1
EXIT_FAIL = 2
EXIT_NEED_HUMAN = 3


class GuardResult:
    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.failed = False
        self.need_human = False
        self.errors: List[str] = []

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
            return EXIT_USAGE
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
        }


def run_git(repo: str, args: Sequence[str], timeout: int = 60) -> Tuple[int, str, str]:
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
        return 127, "", "git not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"git timed out: {' '.join(args)}"


def match_any(path: str, patterns: Sequence[str]) -> bool:
    path = path.replace("\\", "/")
    for pat in patterns:
        pat_n = pat.replace("\\", "/")
        if fnmatch.fnmatch(path, pat_n) or fnmatch.fnmatch(Path(path).name, pat_n):
            return True
        # also match **/pattern style if pattern has no slash
        if "/" not in pat_n.rstrip("/") and fnmatch.fnmatch(path, f"**/{pat_n}"):
            return True
    return False


def parse_porcelain(text: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for line in text.splitlines():
        if not line:
            continue
        # XY PATH or XY ORIG -> PATH for renames
        if len(line) < 4:
            continue
        xy = line[:2]
        rest = line[3:]
        if " -> " in rest:
            path = rest.split(" -> ", 1)[1]
        else:
            path = rest
        entries.append({"xy": xy, "path": path.replace("\\", "/"), "raw": line})
    return entries


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config root must be an object")
    if "repo" not in data:
        raise ValueError("config.repo is required")
    # Allow "." or "" — resolved later via cwd / GIT_GUARD_REPO
    return data


def check_branch(repo: str, cfg: Dict[str, Any], result: GuardResult) -> None:
    code, out, err = run_git(repo, ["branch", "--show-current"])
    if code != 0:
        result.fail("current_branch", f"git branch failed: {err or out}")
        return
    branch = out or "(detached)"
    require = cfg.get("require_branch")
    if require is not None and require != "":
        if branch != require:
            result.fail("require_branch", f"expected '{require}', got '{branch}'")
        else:
            result.ok("require_branch", branch)
    allow = cfg.get("allow_branches") or []
    deny = cfg.get("deny_branches") or []
    if allow:
        if not any(fnmatch.fnmatch(branch, p) for p in allow):
            result.fail("allow_branches", f"'{branch}' not in {allow}")
        else:
            result.ok("allow_branches", branch)
    if deny:
        if any(fnmatch.fnmatch(branch, p) for p in deny):
            result.fail("deny_branches", f"'{branch}' matches deny {deny}")
        else:
            result.ok("deny_branches", f"'{branch}' ok")
    if require is None and not allow and not deny:
        result.ok("current_branch", branch)


def check_clean(repo: str, cfg: Dict[str, Any], result: GuardResult) -> None:
    if not cfg.get("require_clean"):
        return
    code, out, err = run_git(repo, ["status", "--porcelain"])
    if code != 0:
        result.fail("require_clean", f"git status failed: {err or out}")
        return
    ignore = cfg.get("ignore_untracked") or cfg.get("ignore_untracked_patterns") or []
    entries = parse_porcelain(out)
    dirty: List[str] = []
    for e in entries:
        path = e["path"]
        xy = e["xy"]
        # untracked
        if xy == "??" and ignore and match_any(path, ignore):
            continue
        dirty.append(e["raw"])
    if dirty:
        preview = "; ".join(dirty[:12])
        more = f" (+{len(dirty)-12} more)" if len(dirty) > 12 else ""
        result.fail("require_clean", f"dirty tree: {preview}{more}")
    else:
        result.ok("require_clean", "clean" + (f" (ignored {len(ignore)} patterns)" if ignore else ""))


def check_forbid_staged(repo: str, cfg: Dict[str, Any], result: GuardResult) -> None:
    if not cfg.get("forbid_staged"):
        return
    code, out, err = run_git(repo, ["diff", "--cached", "--name-only"])
    if code != 0:
        result.fail("forbid_staged", f"git diff --cached failed: {err or out}")
        return
    staged = [ln.replace("\\", "/") for ln in out.splitlines() if ln.strip()]
    if staged:
        result.fail("forbid_staged", f"staged files present: {staged[:20]}")
    else:
        result.ok("forbid_staged", "no staged files")


def collect_diff_paths(repo: str, cfg: Dict[str, Any], result: GuardResult) -> List[str]:
    paths: List[str] = []
    base = cfg.get("base_ref")
    diff_refs = cfg.get("diff_refs")
    seen = set()

    def add_lines(text: str) -> None:
        for ln in text.splitlines():
            p = ln.strip().replace("\\", "/")
            if p and p not in seen:
                seen.add(p)
                paths.append(p)

    if diff_refs and isinstance(diff_refs, dict):
        fr = diff_refs.get("from")
        to = diff_refs.get("to")
        if not fr or not to:
            result.error("diff_refs requires 'from' and 'to'")
            return []
        code, out, err = run_git(repo, ["diff", "--name-only", f"{fr}...{to}"])
        if code != 0:
            # fallback two-dot
            code, out, err = run_git(repo, ["diff", "--name-only", fr, to])
        if code != 0:
            result.fail("diff_refs", f"diff failed {fr}..{to}: {err or out}")
            return []
        add_lines(out)
        result.ok("diff_refs", f"{fr}...{to} -> {len(paths)} paths")
    elif base:
        # working tree + staged vs base
        code, out, err = run_git(repo, ["diff", "--name-only", base])
        if code != 0:
            result.fail("base_ref_diff", f"git diff {base} failed: {err or out}")
            return []
        add_lines(out)
        code2, out2, err2 = run_git(repo, ["diff", "--cached", "--name-only", base])
        if code2 == 0:
            add_lines(out2)
        else:
            # older git may not like base on --cached; try without base
            code2, out2, _ = run_git(repo, ["diff", "--cached", "--name-only"])
            if code2 == 0:
                add_lines(out2)
        result.ok("base_ref_diff", f"vs {base} -> {len(paths)} paths")
    else:
        # default: working tree + staged vs HEAD / index
        code, out, err = run_git(repo, ["diff", "--name-only"])
        if code == 0:
            add_lines(out)
        code2, out2, _ = run_git(repo, ["diff", "--cached", "--name-only"])
        if code2 == 0:
            add_lines(out2)
        # untracked if deny/allow present and we care about WT
        if cfg.get("allow_path_globs") or cfg.get("deny_path_globs"):
            code3, out3, _ = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
            if code3 == 0:
                add_lines(out3)

    return paths


def check_path_globs(paths: List[str], cfg: Dict[str, Any], result: GuardResult) -> None:
    allow = cfg.get("allow_path_globs")
    deny = cfg.get("deny_path_globs") or []
    if not allow and not deny:
        return
    if not paths:
        result.ok("path_globs", "no changed paths")
        return

    denied = [p for p in paths if deny and match_any(p, deny)]
    if denied:
        result.fail("deny_path_globs", f"denied paths in diff: {denied[:30]}")
    else:
        result.ok("deny_path_globs", "none matched" if deny else "not configured")

    if allow is not None:
        # every path must match at least one allow
        bad = [p for p in paths if not match_any(p, allow)]
        if bad:
            result.fail("allow_path_globs", f"paths outside allow list: {bad[:30]}")
        else:
            result.ok("allow_path_globs", f"all {len(paths)} paths allowed")


def check_forbid_overlap(repo: str, cfg: Dict[str, Any], paths: List[str], result: GuardResult) -> None:
    refs = cfg.get("forbid_overlap_refs") or []
    if not refs:
        return
    if not paths:
        result.ok("forbid_overlap_refs", "no current paths to overlap")
        return
    current = set(paths)
    for ref in refs:
        code, out, err = run_git(
            repo, ["diff-tree", "--no-commit-id", "--name-only", "-r", ref]
        )
        if code != 0:
            result.fail("forbid_overlap_refs", f"diff-tree {ref} failed: {err or out}")
            continue
        other = {ln.replace("\\", "/") for ln in out.splitlines() if ln.strip()}
        overlap = sorted(current & other)
        if overlap:
            result.fail(
                "forbid_overlap_refs",
                f"overlap with {ref}: {overlap[:30]}",
            )
        else:
            result.ok("forbid_overlap_refs", f"no overlap with {ref}")


def check_remotes(repo: str, cfg: Dict[str, Any], result: GuardResult) -> None:
    remotes_cfg = cfg.get("remotes") or []
    if not remotes_cfg:
        return
    for rcfg in remotes_cfg:
        name = rcfg.get("name")
        if not name:
            result.error("remotes[].name required")
            continue
        code, url, err = run_git(repo, ["remote", "get-url", name])
        if code != 0:
            result.fail("remotes", f"remote '{name}' missing: {err or url}")
            continue
        must = rcfg.get("url_must_contain")
        if must and must not in url:
            result.fail("remotes", f"remote '{name}' url '{url}' missing '{must}'")
        else:
            result.ok("remotes", f"{name} -> {url}")
        # forbid_push is advisory for action gate; note it here
        if rcfg.get("forbid_push"):
            result.ok("remotes_forbid_push", f"{name}: push forbidden by config")


def check_action(cfg: Dict[str, Any], result: GuardResult, repo: str) -> None:
    action = cfg.get("action")
    if not action:
        return
    if isinstance(action, str):
        action = {"type": action}
    atype = (action.get("type") or "").strip().lower()
    if not atype:
        result.error("action.type required")
        return

    forbid = [a.lower() for a in (cfg.get("forbid_actions") or [])]
    human_gate = [a.lower() for a in (cfg.get("human_gate_actions") or [])]

    # normalize aliases
    aliases = {
        "force-push": "force_push",
        "reset-hard": "reset_hard",
        "merge-ff": "merge_ff",
        "ff-merge": "merge_ff",
    }
    atype = aliases.get(atype, atype)

    # remotes forbid_push
    remotes_cfg = cfg.get("remotes") or []
    target_remote = action.get("target_remote")
    if atype in ("push", "force_push") and target_remote:
        for rcfg in remotes_cfg:
            if rcfg.get("name") == target_remote and rcfg.get("forbid_push"):
                result.fail(
                    "action",
                    f"push to remote '{target_remote}' forbidden by remotes[].forbid_push",
                )
                return

    if atype in forbid:
        result.fail("action", f"action '{atype}' is in forbid_actions")
        return

    push_safety = str(cfg.get("push_safety") or "").strip().lower().replace(".", "_")
    if atype == "push" and push_safety in ("v2_1", "v2_1_safe"):
        import importlib.util

        _sp_path = Path(__file__).resolve().parent / "safe_push.py"
        _spec = importlib.util.spec_from_file_location("git_guard_safe_push", _sp_path)
        if _spec is None or _spec.loader is None:
            result.error(f"cannot load safe_push from {_sp_path}")
            return
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.apply_safe_push_gate(repo, cfg, action, result)
        return

    local_safety = str(cfg.get("local_safety") or "").strip().lower().replace(".", "_")
    if atype in ("local_git", "local_git_op") and local_safety in ("v2_2", "v2_2_safe"):
        import importlib.util

        _lp_path = Path(__file__).resolve().parent / "safe_local_operation.py"
        _spec = importlib.util.spec_from_file_location("git_guard_safe_local", _lp_path)
        if _spec is None or _spec.loader is None:
            result.error(f"cannot load safe_local_operation from {_lp_path}")
            return
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.apply_local_git_gate(repo, cfg, action, result)
        return

    if atype in human_gate:
        target = action.get("target_branch") or action.get("target_remote") or ""
        result.human(
            "action",
            f"action '{atype}' requires human confirmation"
            + (f" (target={target})" if target else ""),
        )
        return

    # high-risk defaults even without human_gate if clearly dangerous
    if atype in ("force_push", "reset_hard"):
        result.human("action", f"dangerous action '{atype}' requires human confirmation")
        return

    result.ok("action", f"action '{atype}' allowed by policy")


def run_required_tests(cfg: Dict[str, Any], result: GuardResult, do_run: bool) -> None:
    tests = cfg.get("required_tests") or []
    if not tests:
        return
    if not do_run:
        result.ok("required_tests", f"{len(tests)} configured (skipped; pass --run-tests)")
        return
    if result.failed or result.need_human or result.errors:
        result.ok("required_tests", "skipped because prior checks did not pass")
        return
    repo = cfg["repo"]
    for i, t in enumerate(tests):
        cmd = t.get("cmd")
        if not cmd:
            result.error(f"required_tests[{i}].cmd required")
            continue
        cwd = t.get("cwd") or repo
        timeout = int(t.get("timeout_sec") or 300)
        name = f"required_tests[{i}]"
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
                tail = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()[-500:]
                result.fail(name, f"exit {p.returncode}: {tail}")
            else:
                result.ok(name, f"ok ({cmd})")
        except subprocess.TimeoutExpired:
            result.fail(name, f"timed out after {timeout}s: {cmd}")
        except Exception as exc:  # noqa: BLE001
            result.fail(name, f"{type(exc).__name__}: {exc}")



def resolve_repo(cfg_repo: Any) -> str:
    """Resolve repo path.

    Precedence:
      1. Env GIT_GUARD_REPO (if set and non-empty)
      2. Config value: absolute/relative path as usual
      3. Config "." or empty -> git rev-parse --show-toplevel from process cwd
         (so hooks work in any worktree without hardcoding the path)
    """
    env_repo = (os.environ.get("GIT_GUARD_REPO") or "").strip()
    if env_repo:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(env_repo)))

    raw = "" if cfg_repo is None else str(cfg_repo).strip()
    if raw in ("", "."):
        try:
            p = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise ValueError("git not found on PATH; cannot resolve repo '.'") from exc
        top = (p.stdout or "").strip()
        if p.returncode != 0 or not top:
            detail = (p.stderr or p.stdout or "").strip()
            raise ValueError(
                f"repo is '{raw or '.'}' but git rev-parse --show-toplevel failed: {detail}"
            )
        return os.path.abspath(top)

    return os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))


def validate_repo(repo: str, result: GuardResult) -> bool:
    if not os.path.isdir(repo):
        result.error(f"repo path does not exist: {repo}")
        return False
    code, out, err = run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    if code != 0 or out.strip() != "true":
        result.error(f"not a git worktree: {repo} ({err or out})")
        return False
    return True


def run_guard(cfg: Dict[str, Any], run_tests: bool = False) -> GuardResult:
    result = GuardResult()
    try:
        repo = resolve_repo(cfg.get("repo"))
    except ValueError as exc:
        result.error(str(exc))
        return result
    cfg = {**cfg, "repo": repo}
    if not validate_repo(repo, result):
        return result

    check_branch(repo, cfg, result)
    check_clean(repo, cfg, result)
    check_forbid_staged(repo, cfg, result)

    need_paths = bool(
        cfg.get("allow_path_globs")
        or cfg.get("deny_path_globs")
        or cfg.get("forbid_overlap_refs")
        or cfg.get("base_ref")
        or cfg.get("diff_refs")
    )
    paths: List[str] = []
    if need_paths:
        paths = collect_diff_paths(repo, cfg, result)
        ignore_paths = cfg.get("ignore_path_globs") or []
        if ignore_paths and paths:
            before = len(paths)
            paths = [p for p in paths if not match_any(p, ignore_paths)]
            result.ok(
                "ignore_path_globs",
                f"ignored {before - len(paths)} of {before} paths",
            )
        check_path_globs(paths, cfg, result)
        check_forbid_overlap(repo, cfg, paths, result)

    check_remotes(repo, cfg, result)
    check_action(cfg, result, repo)
    run_required_tests(cfg, result, run_tests)
    return result


def print_human(result: GuardResult) -> None:
    for c in result.checks:
        status = c["status"]
        detail = c.get("detail") or ""
        line = f"[{status}] {c['name']}"
        if detail:
            line += f": {detail}"
        print(line)
    for e in result.errors:
        print(f"[ERROR] {e}")
    code = result.exit_code()
    label = {0: "PASS", 1: "ERROR", 2: "FAIL", 3: "NEED_HUMAN"}.get(code, str(code))
    print(f"RESULT: {label} (exit {code})")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Git Guard — config-driven local safety checks (no LLM)."
    )
    parser.add_argument("--config", required=True, help="Path to JSON config")
    parser.add_argument("--json", action="store_true", help="Emit JSON report on stdout")
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run required_tests from config after other checks pass",
    )
    parser.add_argument(
        "--action",
        help="Override/propose action type (e.g. push, force_push, merge_ff, reset_hard)",
    )
    parser.add_argument("--target-remote", help="For action override: remote name")
    parser.add_argument("--target-branch", help="For action override: branch name")
    parser.add_argument(
        "--push-ref",
        action="append",
        default=[],
        metavar="SPEC",
        help="Pre-push ref line: local_ref|local_sha|remote_ref|remote_sha (repeatable)",
    )
    parser.add_argument(
        "--local-op",
        action="append",
        default=[],
        metavar="SPEC",
        help="Local git op: operation|paths|key=value (repeatable; see safe_local_operation.py)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"[ERROR] config not found: {args.config}", file=sys.stderr)
        return EXIT_USAGE
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"[ERROR] config: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.action:
        action = dict(cfg.get("action") or {}) if isinstance(cfg.get("action"), dict) else {}
        action["type"] = args.action
        if args.target_remote:
            action["target_remote"] = args.target_remote
        if args.target_branch:
            action["target_branch"] = args.target_branch
        push_refs: List[Dict[str, str]] = []
        for spec in args.push_ref or []:
            parts = spec.split("|")
            if len(parts) != 4:
                print(
                    f"[ERROR] --push-ref must be local_ref|local_sha|remote_ref|remote_sha, got: {spec}",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            push_refs.append(
                {
                    "local_ref": parts[0],
                    "local_sha": parts[1],
                    "remote_ref": parts[2],
                    "remote_sha": parts[3],
                }
            )
        if push_refs:
            action["push_refs"] = push_refs
        if args.local_op:
            action["local_ops"] = list(args.local_op)
        cfg["action"] = action

    t0 = time.time()
    result = run_guard(cfg, run_tests=args.run_tests)
    elapsed = round(time.time() - t0, 3)

    if args.json:
        payload = result.to_dict()
        payload["elapsed_sec"] = elapsed
        payload["config"] = args.config
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_human(result)

    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
