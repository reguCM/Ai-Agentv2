"""Measure Actual Map from workspace files and tests. Observer only."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _imported_workspace_modules(tree: ast.AST, workspace_pkg: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if workspace_pkg in mod or (mod and "workspace" in mod.split(".")):
                names = [a.name for a in node.names]
                found.append({"module": mod, "names": ",".join(names)})
        if isinstance(node, ast.Import):
            for alias in node.names:
                if workspace_pkg in alias.name or "workspace" in alias.name.split("."):
                    found.append({"module": alias.name, "names": alias.asname or alias.name})
    return found


def _function_calls(fn: ast.FunctionDef) -> list[str]:
    names: list[str] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.append(func.id)
            elif isinstance(func, ast.Attribute):
                names.append(func.attr)
    return names


def _defined_functions(tree: ast.AST) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.FunctionDef):
            out.append(
                {
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "calls": _function_calls(node),
                }
            )
    return out


def measure_actual_map(*, workspace: Path, tests: Path, workspace_pkg: str) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    import_edges: list[dict[str, str]] = []
    defined: dict[str, set[str]] = {}

    if workspace.is_dir():
        for path in sorted(workspace.glob("*.py")):
            if path.name == "__init__.py":
                continue
            src = _read(path)
            tree = ast.parse(src)
            fns = _defined_functions(tree)
            defined[path.stem] = {f["name"] for f in fns}
            imports = _imported_workspace_modules(tree, workspace_pkg)
            for imp in imports:
                import_edges.append(
                    {
                        "from": path.stem,
                        "to_module": imp["module"],
                        "names": imp["names"],
                    }
                )
            components.append(
                {
                    "file": _rel(path, workspace),
                    "id": path.stem,
                    "functions": fns,
                    "workspace_imports": imports,
                }
            )

    call_edges: list[dict[str, str]] = []
    fn_index: dict[str, str] = {}
    for stem, names in defined.items():
        for name in names:
            fn_index[name] = stem
    for comp in components:
        for fn in comp["functions"]:
            for called in fn["calls"]:
                target = fn_index.get(called)
                if target and target != comp["id"]:
                    call_edges.append(
                        {
                            "from_file": comp["id"],
                            "from_fn": fn["name"],
                            "to_file": target,
                            "to_fn": called,
                        }
                    )

    tests_covering: list[dict[str, Any]] = []
    if tests.is_dir():
        for path in sorted(tests.glob("test_*.py")):
            src = _read(path)
            tree = ast.parse(src)
            imports = _imported_workspace_modules(tree, workspace_pkg)
            tests_covering.append(
                {
                    "file": path.name,
                    "workspace_imports": imports,
                }
            )

    imported_stems: set[str] = set()
    for edge in import_edges:
        for stem in defined:
            if stem in edge["to_module"] or stem in edge["names"]:
                imported_stems.add(stem)

    unconnected: list[dict[str, str]] = []
    entry = "window_loop" if "window_loop" in defined else None
    for stem in defined:
        if stem == entry:
            continue
        used_by_other_component = any(
            e["from"] != stem and (stem in e["to_module"] or stem in e["names"])
            for e in import_edges
        )
        called_from_other = any(e["to_file"] == stem for e in call_edges)
        if not used_by_other_component and not called_from_other:
            unconnected.append(
                {
                    "component": stem,
                    "fact": "no other workspace component imports or calls this module",
                }
            )
    if entry:
        entry_comp = next((c for c in components if c["id"] == entry), None)
        if entry_comp is not None:
            other_calls = [
                e for e in call_edges if e["from_file"] == entry
            ]
            other_imports = [e for e in import_edges if e["from"] == entry]
            if not other_calls and not other_imports:
                unconnected.append(
                    {
                        "component": entry,
                        "fact": "window_loop does not import or call other workspace components",
                    }
                )

    return {
        "kind": "actual_map",
        "source": "workspace files + tests AST. Not conversation history.",
        "workspace": str(workspace),
        "components": components,
        "import_edges": import_edges,
        "call_edges": call_edges,
        "tests": tests_covering,
        "unconnected_paths": unconnected,
        "tested_range": [t["file"] for t in tests_covering],
    }


def python_env_facts() -> dict[str, Any]:
    env = dict(os.environ)
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    py = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    pg = subprocess.run(
        [sys.executable, "-c", "import pygame; print(pygame.version.ver)"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return {
        "python": (py.stdout or "").strip() if py.returncode == 0 else None,
        "pygame_import_ok": pg.returncode == 0,
        "pygame_version": (pg.stdout or "").strip() if pg.returncode == 0 else None,
    }
