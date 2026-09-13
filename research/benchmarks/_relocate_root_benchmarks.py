#!/usr/bin/env python3
"""Move root-level research benchmarks to research/benchmarks/ and patch paths."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "research" / "benchmarks"

MOVES: dict[str, list[str]] = {
    "phases/phase1": [
        "_phase1_run_benchmarks.py",
        "_phase1_benchmark_summary.json",
        "_phase1_benchmarks.log",
        "_phase1_cpu_temperature.log",
    ],
    "phases/phase2": [
        "_phase2_run_benchmarks.py",
        "_phase2_benchmark_summary.json",
        "_phase2_benchmarks.log",
    ],
    "phases/phase3": [
        "_phase3_run_benchmarks.py",
        "_phase3_benchmark_summary.json",
        "_phase3_benchmarks.log",
        "_phase3_5_run_observation.py",
        "_phase3_5_observation_summary.json",
        "_phase3_5_observation.log",
        "_phase3_live_skip_run_benchmarks.py",
        "_phase3_live_skip_summary.json",
        "_phase3_live_skip_benchmarks.log",
        "_phase3_live_skip_benchmarks_v2.log",
    ],
    "phases/phase4": [
        "_phase4_run_benchmarks.py",
        "_phase4_benchmark_summary.json",
        "_phase4_1_run_benchmarks.py",
        "_phase4_1_benchmark_summary.json",
        "_phase4_1_live_summary.json",
    ],
    "phases/phase5": [
        "_phase5_run_benchmarks.py",
        "_phase5_benchmark_summary.json",
        "_phase5_vs_phase4_compare.py",
        "_phase5_vs_phase4_compare.json",
        "_phase5_1_analyze_repetition.py",
        "_phase5_1_repetition_analysis.json",
        "_phase5_1_controlled_compare.py",
        "_phase5_1_repro_investigation.json",
        "_phase5_memory_recall_v5_restore.py",
        "_investigate_phase5_repro.py",
    ],
    "kss": [
        "_kss1_measurement_bench.py",
        "_kss11_measurement_bench.py",
        "_kss13_measurement_bench.py",
        "_kss14_measurement_bench.py",
        "_kss15_measurement_bench.py",
        "_kss151_human_audit.py",
    ],
    "observe": ["_knowledge_source_observe_bench.py"],
    "debug": [
        "_debug_bottleneck_target.py",
        "_debug_impl.py",
        "_debug_impl_call.py",
        "_debug_judge_adopt_last.py",
        "_debug_research.py",
        "_debug_research2.py",
        "_debug_research3.py",
        "_debug_trace.py",
        "_debug_val.py",
    ],
    "verify": [
        "_verify_agent_tools_phase34.py",
        "_verify_execution_identity.py",
    ],
    "smoke": ["_phase_a_query_smoke.py"],
}

IMPORT_BLOCK = '''import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT

ROOT = REPO_ROOT
HERE = Path(__file__).resolve().parent
'''

DEBUG_HEADER = '''import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT, bootstrap_repo_root

bootstrap_repo_root()
ROOT = REPO_ROOT
'''

VERIFY_HEADER = DEBUG_HEADER

CROSS_PHASE = {
    "_phase4_run_benchmarks.py": {
        "P35_PATH = ROOT / \"_phase3_5_observation_summary.json\"":
        'P35_PATH = HERE.parent / "phase3" / "_phase3_5_observation_summary.json"',
        "OUT_PATH = ROOT / \"_phase4_benchmark_summary.json\"":
        'OUT_PATH = HERE / "_phase4_benchmark_summary.json"',
    },
    "_phase4_1_run_benchmarks.py": {
        "P4_PATH = ROOT / \"_phase4_benchmark_summary.json\"":
        'P4_PATH = HERE / "_phase4_benchmark_summary.json"',
        "OUT_PATH = ROOT / \"_phase4_1_benchmark_summary.json\"":
        'OUT_PATH = HERE / "_phase4_1_benchmark_summary.json"',
        "OUT_PATH_LIVE = ROOT / \"_phase4_1_live_summary.json\"":
        'OUT_PATH_LIVE = HERE / "_phase4_1_live_summary.json"',
    },
}

PHASE5_LOCAL = {
    "_phase5_run_benchmarks.py": {
        "OUT_PATH = ROOT / \"_phase5_benchmark_summary.json\"":
        'OUT_PATH = HERE / "_phase5_benchmark_summary.json"',
    },
    "_phase5_vs_phase4_compare.py": {
        "OUT_PATH = ROOT / \"_phase5_vs_phase4_compare.json\"":
        'OUT_PATH = HERE / "_phase5_vs_phase4_compare.json"',
    },
    "_phase5_1_analyze_repetition.py": {
        "COMPARE_PATH = ROOT / \"_phase5_vs_phase4_compare.json\"":
        'COMPARE_PATH = HERE / "_phase5_vs_phase4_compare.json"',
        "OUT_PATH = ROOT / \"_phase5_1_repetition_analysis.json\"":
        'OUT_PATH = HERE / "_phase5_1_repetition_analysis.json"',
    },
    "_investigate_phase5_repro.py": {
        "COMPARE = ROOT / \"_phase5_vs_phase4_compare.json\"":
        'COMPARE = HERE / "_phase5_vs_phase4_compare.json"',
        "SUMMARY = ROOT / \"_phase5_benchmark_summary.json\"":
        'SUMMARY = HERE / "_phase5_benchmark_summary.json"',
        "ANALYSIS = ROOT / \"_phase5_1_repetition_analysis.json\"":
        'ANALYSIS = HERE / "_phase5_1_repetition_analysis.json"',
        "V5_RESTORE = ROOT / \"_phase5_memory_recall_v5_restore.py\"":
        'V5_RESTORE = HERE / "_phase5_memory_recall_v5_restore.py"',
        "COMPARE_SCRIPT = ROOT / \"_phase5_vs_phase4_compare.py\"":
        'COMPARE_SCRIPT = HERE / "_phase5_vs_phase4_compare.py"',
        "RUN_SCRIPT = ROOT / \"_phase5_run_benchmarks.py\"":
        'RUN_SCRIPT = HERE / "_phase5_run_benchmarks.py"',
        "out_path = ROOT / \"_phase5_1_repro_investigation.json\"":
        'out_path = HERE / "_phase5_1_repro_investigation.json"',
    },
}

GENERIC_OUT = [
    (r'OUT_PATH = ROOT / "(_phase[^"]+)"', r'OUT_PATH = HERE / "\1"'),
    (r'out_path = ROOT / "(_phase[^"]+)"', r'out_path = HERE / "\1"'),
]


def move_files() -> None:
    for subdir, names in MOVES.items():
        dest_dir = BENCH / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            src = REPO / name
            dst = dest_dir / name
            if not src.exists():
                print(f"SKIP missing: {name}")
                continue
            if dst.exists():
                print(f"SKIP exists: {dst}")
                continue
            src.rename(dst)
            print(f"MOVED {name} -> {subdir}/")


def patch_root_line(text: str, header: str) -> str:
    text = re.sub(
        r"^ROOT = Path\(__file__\)\.resolve\(\)\.parent\s*\n",
        "",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if "from common_paths import REPO_ROOT" in text:
        return text
    # insert after module docstring if present
    m = re.match(r'((?:\"\"\"[\s\S]*?\"\"\"\n|\'\'\'[\s\S]*?\'\'\'\n)?)', text)
    if m and m.group(1):
        pos = m.end()
        return text[:pos] + header + text[pos:]
    return header + text


def patch_phase_py(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = patch_root_line(text, IMPORT_BLOCK)
    name = path.name
    if name in CROSS_PHASE:
        for old, new in CROSS_PHASE[name].items():
            text = text.replace(old, new)
    if name in PHASE5_LOCAL:
        for old, new in PHASE5_LOCAL[name].items():
            text = text.replace(old, new)
    for pat, repl in GENERIC_OUT:
        text = re.sub(pat, repl, text)
    if name == "_phase5_1_controlled_compare.py":
        text = text.replace("live = ROOT / name", "live = HERE / name")
        text = text.replace(
            "py -3.14 _phase5_1_controlled_compare.py",
            "py -3.14 research/benchmarks/phases/phase5/_phase5_1_controlled_compare.py",
        )
    if name == "_phase4_1_run_benchmarks.py":
        text = text.replace(
            "py -3.14 _phase4_1_run_benchmarks.py",
            "py -3.14 research/benchmarks/phases/phase4/_phase4_1_run_benchmarks.py",
        )
    path.write_text(text, encoding="utf-8")


def patch_debug_py(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "bootstrap_repo_root" in text:
        return
    text = DEBUG_HEADER + text
    text = text.replace(
        '"research/llm_benchmarks/',
        'str(ROOT / "research" / "llm_benchmarks" / "',
    )
    # fix open() calls - crude but works for these scripts
    text = re.sub(
        r'open\("research/llm_benchmarks/([^"]+)"',
        r'open(ROOT / "research" / "llm_benchmarks" / "\1"',
        text,
    )
    text = re.sub(
        r'json\.load\(open\(path',
        r'json.load(open(ROOT / path if not str(path).startswith(str(ROOT)) else path',
        text,
    )
    # fix judge path variable
    text = text.replace(
        'path = "research/llm_benchmarks/judge_adopt_usable_results.json"',
        'path = ROOT / "research" / "llm_benchmarks" / "judge_adopt_usable_results.json"',
    )
    path.write_text(text, encoding="utf-8")


def patch_verify_py(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = patch_root_line(text, VERIFY_HEADER)
    text = text.replace('Path("registry/tools.json")', 'ROOT / "registry" / "tools.json"')
    text = text.replace('Path("agent.py")', 'ROOT / "agent.py"')
    path.write_text(text, encoding="utf-8")


def patch_smoke_py(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = patch_root_line(text, IMPORT_BLOCK)
    text = text.replace(
        'Path("research/llm_benchmarks/phase_a_query_smoke.json")',
        'ROOT / "research" / "llm_benchmarks" / "phase_a_query_smoke.json"',
    )
    path.write_text(text, encoding="utf-8")


def patch_kss_py(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = patch_root_line(text, IMPORT_BLOCK)
    path.write_text(text, encoding="utf-8")


def patch_all() -> None:
    for subdir, names in MOVES.items():
        for name in names:
            if not name.endswith(".py"):
                continue
            path = BENCH / subdir / name
            if not path.is_file():
                continue
            if subdir.startswith("phases/"):
                patch_phase_py(path)
            elif subdir == "debug":
                patch_debug_py(path)
            elif subdir == "verify":
                patch_verify_py(path)
            elif subdir == "smoke":
                patch_smoke_py(path)
            else:
                patch_kss_py(path)
            print(f"PATCHED {path.relative_to(REPO)}")


def main() -> None:
    move_files()
    patch_all()
    print("DONE")


if __name__ == "__main__":
    main()
