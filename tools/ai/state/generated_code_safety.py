"""
Phase B: 生成 Python Tool の軽量 AST Safety 検査。
検査できないものは safe にしない。
静的な read-only subprocess（許可 PowerShell / wmic / nvidia-smi）は safe 候補とする。
"""

from __future__ import annotations

import ast
from typing import Any

from tools.ai.state.safety_assessment import (
    DANGEROUS,
    SAFE,
    SIDE_FS_DELETE,
    SIDE_FS_WRITE,
    SIDE_NET,
    SIDE_PROCESS,
    SIDE_READ,
    SIDE_STATE,
    SIDE_UNKNOWN,
    UNKNOWN,
    assess_candidate_safety,
    empty_safety_assessment,
)


DANGEROUS_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
}


def assess_generated_code_safety(code: str | None) -> dict[str, Any]:
    text = str(code or "")
    if not text.strip():
        return empty_safety_assessment(
            status=UNKNOWN,
            rationale_codes=["empty_code"],
            machine_assessed=UNKNOWN,
        )
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return empty_safety_assessment(
            status=UNKNOWN,
            rationale_codes=["unparseable_code"],
            machine_assessed=UNKNOWN,
            side_effects=[SIDE_UNKNOWN],
        )

    findings = []
    effects = set()
    has_shell_true = False
    has_network = False
    has_delete = False
    has_write = False
    has_dynamic = False
    unverified_subprocess = False
    readonly_subprocess_ok = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in DANGEROUS_NAMES:
                has_dynamic = True
                findings.append(f"dangerous_builtin:{name}")
                effects.add(SIDE_STATE)

            for kw in node.keywords or []:
                if kw.arg == "shell" and _is_true(kw.value):
                    has_shell_true = True
                    findings.append("shell_true")
                    effects.add(SIDE_PROCESS)
                    effects.add(SIDE_STATE)

            if name in (
                "subprocess.run",
                "subprocess.call",
                "subprocess.Popen",
                "subprocess.check_output",
                "subprocess.check_call",
            ):
                static = _static_subprocess_candidate(node)
                if static is None:
                    unverified_subprocess = True
                    findings.append(f"subprocess_unverified:{name}")
                    effects.add(SIDE_PROCESS)
                    effects.add(SIDE_UNKNOWN)
                else:
                    safety = assess_candidate_safety(static)
                    if safety.get("status") == SAFE:
                        readonly_subprocess_ok = True
                        findings.append("subprocess_readonly_allowlisted")
                        effects.add(SIDE_READ)
                    else:
                        unverified_subprocess = True
                        findings.append(
                            "subprocess_not_readonly:"
                            + ",".join(safety.get("rationale_codes") or [])
                        )
                        effects.update(safety.get("side_effects") or [SIDE_UNKNOWN])

            if name in ("os.system", "os.popen"):
                findings.append(f"os_process:{name}")
                effects.add(SIDE_PROCESS)
                effects.add(SIDE_STATE)
                unverified_subprocess = True

            if name in ("os.remove", "os.unlink", "os.rmdir", "shutil.rmtree"):
                has_delete = True
                findings.append(f"fs_delete:{name}")
                effects.add(SIDE_FS_DELETE)

            if name in ("open",):
                if len(node.args) >= 2:
                    mode = _const_str(node.args[1]) or ""
                    if any(m in mode for m in ("w", "a", "x", "+")):
                        has_write = True
                        findings.append("file_write_open")
                        effects.add(SIDE_FS_WRITE)
                for kw in node.keywords or []:
                    if kw.arg == "mode":
                        mode = _const_str(kw.value) or ""
                        if any(m in mode for m in ("w", "a", "x", "+")):
                            has_write = True
                            findings.append("file_write_open")
                            effects.add(SIDE_FS_WRITE)

            if (
                name.startswith("urllib.")
                or name.startswith("requests.")
                or name.startswith("httpx.")
            ):
                has_network = True
                findings.append(f"network:{name}")
                effects.add(SIDE_NET)

            if name == "socket.socket":
                has_network = True
                findings.append("network:socket")
                effects.add(SIDE_NET)

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            else:
                mods = [node.module.split(".")[0]] if node.module else []
            for mod in mods:
                if mod in ("ctypes", "socket"):
                    findings.append(f"import:{mod}")
                    if mod == "socket":
                        has_network = True
                        effects.add(SIDE_NET)
                    if mod == "ctypes":
                        effects.add(SIDE_STATE)
                        unverified_subprocess = True

    if has_shell_true or has_dynamic or has_delete or has_network:
        status = DANGEROUS
    elif unverified_subprocess or has_write:
        status = UNKNOWN
        effects.add(SIDE_UNKNOWN)
        if has_write:
            findings.append("filesystem_write_present")
    elif readonly_subprocess_ok:
        status = SAFE
        effects = {SIDE_READ}
    elif not findings:
        status = SAFE
        effects = {SIDE_READ}
        findings.append("no_dangerous_ast_nodes")
    else:
        status = UNKNOWN
        effects.add(SIDE_UNKNOWN)

    return empty_safety_assessment(
        status=status,
        side_effects=sorted(effects) or [SIDE_UNKNOWN],
        network_access="outbound" if has_network else ("none" if status == SAFE else UNKNOWN),
        privilege=UNKNOWN if status != SAFE else "none",
        rationale_codes=findings or ["generated_code_assessed"],
        machine_assessed=status,
    )


def _static_subprocess_candidate(node: ast.Call) -> dict | None:
    """subprocess.run([...]) の静的リストだけ Candidate 形式へ。動的なら None。"""
    if not node.args:
        return None
    argv_node = node.args[0]
    if not isinstance(argv_node, (ast.List, ast.Tuple)):
        return None
    parts = []
    for elt in argv_node.elts:
        value = _const_str(elt)
        if value is None:
            return None
        parts.append(value)
    if not parts:
        return None
    return {"command": parts[0], "args": parts[1:]}


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = []
        cur = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        parts.reverse()
        return ".".join(parts)
    return ""


def _const_str(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_true(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is True
