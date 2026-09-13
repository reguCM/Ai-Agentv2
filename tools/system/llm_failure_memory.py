"""
ベンチで観測した失敗パターンを後から参照する。

いまは repair ループに接続しない。
将来、「このモデルは research 結果を実装しなかった」を材料にするときに使う。
"""

import json

from tools.system.config import ROOT, load_yaml


BLACKLIST_PATH = ROOT / "research" / "llm_benchmarks" / "repair_blacklist.yaml"
FAILURES_PATH = ROOT / "research" / "llm_benchmarks" / "repair_failures.json"
ENVIRONMENT_BLACKLIST_PATH = (
    ROOT / "research" / "llm_benchmarks" / "environment_blacklist.yaml"
)
ENVIRONMENT_CASES_DIR = ROOT / "research" / "llm_benchmarks" / "cases"

_blacklist = None
_environment_blacklist = None


def load_blacklist(reload=False):
    global _blacklist
    if _blacklist is None or reload:
        _blacklist = load_yaml(BLACKLIST_PATH) or {}
    return _blacklist


def load_failure_entries():
    if not FAILURES_PATH.exists():
        return []
    data = json.loads(FAILURES_PATH.read_text(encoding="utf-8"))
    return data.get("entries") or []


def patterns_for(profile_id, *, repair_type=None, pattern_id=None):
    patterns = load_blacklist().get("patterns") or []
    matched = []
    for item in patterns:
        models = item.get("models") or []
        if profile_id and profile_id not in models:
            continue
        if repair_type and repair_type not in (item.get("repair_types") or []):
            continue
        if pattern_id and item.get("id") != pattern_id:
            continue
        matched.append(item)
    return matched


def failures_for(profile_id, *, repair_type=None, failure_pattern=None):
    matched = []
    for item in load_failure_entries():
        if profile_id and item.get("profile") != profile_id:
            continue
        if repair_type and item.get("repair_type") != repair_type:
            continue
        if failure_pattern and item.get("failure_pattern") != failure_pattern:
            continue
        matched.append(item)
    return matched


def ignored_research_implementation(profile_id):
    """このモデルが、調査済みでもスタブのまま返したことがあるか（整理済みパターン）。"""
    return bool(
        patterns_for(
            profile_id,
            repair_type="stub_value",
            pattern_id="stub_echo_ignores_findings",
        )
    )


def load_environment_blacklist(reload=False):
    global _environment_blacklist
    if _environment_blacklist is None or reload:
        _environment_blacklist = load_yaml(ENVIRONMENT_BLACKLIST_PATH) or {}
    return _environment_blacklist


def environment_patterns(*, pattern_id=None, class_name=None, profile_id=None):
    matched = []
    for item in load_environment_blacklist().get("patterns") or []:
        if pattern_id and item.get("id") != pattern_id:
            continue
        if class_name and item.get("class") != class_name:
            continue
        models = item.get("models") or []
        if profile_id and models and profile_id not in models:
            continue
        matched.append(item)
    return matched


def load_environment_case(case_id):
    path = ENVIRONMENT_CASES_DIR / f"{case_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


IMPLEMENTATION_FAILURES_PATH = (
    ROOT / "research" / "llm_benchmarks" / "implementation_failures.json"
)


def load_implementation_failures():
    if not IMPLEMENTATION_FAILURES_PATH.exists():
        return []
    data = json.loads(IMPLEMENTATION_FAILURES_PATH.read_text(encoding="utf-8"))
    return data.get("entries") or []


def implementation_failures_for(profile_id, *, class_name=None):
    matched = []
    for item in load_implementation_failures():
        if profile_id and item.get("profile") != profile_id:
            continue
        kind = (item.get("implementation_class") or {}).get("class")
        if class_name and kind != class_name:
            continue
        matched.append(item)
    return matched
