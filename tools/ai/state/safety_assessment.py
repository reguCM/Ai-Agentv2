"""
Phase B: Execution SafetyAssessment（機械判定）。

- Web 文言は入力に取らない
- LLM の「安全」は参照しない
- safe は既知の read-only 許可パターンに合致するときだけ
- 複合コマンドは一部安全でも全体を safe にしない
"""

from __future__ import annotations

import re
from typing import Any

UNKNOWN = "unknown"
SAFE = "safe"
RISKY = "risky"
DANGEROUS = "dangerous"

SIDE_READ = "read_query"
SIDE_FS_WRITE = "filesystem_write"
SIDE_FS_DELETE = "filesystem_delete"
SIDE_PROCESS = "process_control"
SIDE_SERVICE = "service_control"
SIDE_NET = "network_egress"
SIDE_PRIV = "privilege_escalation"
SIDE_STATE = "state_mutation"
SIDE_UNKNOWN = "unknown"

# 肯定的に許可する読取専用コマンドレット（単体パイプライン想定）
READONLY_CMDLETS = {
    "get-ciminstance",
    "get-wmiobject",
    "get-counter",
    "get-computerinfo",
    "get-volume",
    "get-psdrive",
    "get-process",
    "get-item",
    "get-childitem",
    "get-content",
    "get-date",
    "get-hotfix",
    "select-object",
    "where-object",
    "foreach-object",
    "measure-object",
    "sort-object",
    "format-list",
    "format-table",
    "out-string",
    "convertto-json",
    "write-output",
}

# パイプラインで許可する補助（単独では意味が薄いが Get-* と併用）
READONLY_PIPELINE_HELPERS = {
    "select-object",
    "select",
    "where-object",
    "where",
    "foreach-object",
    "foreach",
    "measure-object",
    "measure",
    "sort-object",
    "sort",
    "format-list",
    "format-table",
    "out-string",
    "convertto-json",
    "write-output",
    "%",
    "?",
}

DANGEROUS_TOKEN_RE = re.compile(
    r"(?i)(?:"
    r"\biex\b|invoke-expression|"
    r"invoke-webrequest|invoke-restmethod|\bcurl\b|\bwget\b|"
    r"invoke-command|start-process|stop-process|start-job|"
    r"remove-item|\bdel\b|\brm\b|rmdir|format-volume|clear-disk|"
    r"new-service|stop-service|start-service|restart-service|set-service|"
    r"stop-computer|restart-computer|net\s+user|"
    r"set-executionpolicy|set-content|add-content|out-file|new-item|"
    r"move-item|copy-item|rename-item|"
    r"new-object\s+net\.|downloadstring|downloadfile|"
    r"add-type|\[reflection\.assembly\]|"
    r"reg\s+add|set-itemproperty|new-itemproperty|"
    r"taskkill|bypass"
    r")"
)

SET_LIKE_RE = re.compile(r"(?i)\bset-[a-z]+|\bnew-[a-z]+|\bremove-[a-z]+|\bstop-[a-z]+|\bstart-[a-z]+")

# 複合を示す区切り（単純パイプライン | 以外）
COMPOUND_RE = re.compile(r"[;\n`]|\$\(|invoke-|\biex\b", re.I)

WMIC_READONLY_TARGETS = {"cpu", "os", "computersystem", "processor", "logicaldisk", "diskdrive"}


def empty_safety_assessment(**overrides) -> dict[str, Any]:
    base = {
        "status": UNKNOWN,
        "side_effects": [SIDE_UNKNOWN],
        "network_access": UNKNOWN,
        "privilege": UNKNOWN,
        "rationale_codes": [],
        "machine_assessed": UNKNOWN,
        "human_decision": None,
        "phase": "kss-phase-b",
        "web_content_used": False,
    }
    base.update(overrides)
    return base


def _command_script(candidate: dict) -> tuple[str, str]:
    command = str(candidate.get("command") or "").strip().lower()
    args = [str(a) for a in (candidate.get("args") or [])]
    return command, " ".join(args)


def _extract_powershell_script(args: list[str]) -> str:
    lowered = [a.lower() for a in args]
    script_parts = []
    i = 0
    while i < len(args):
        token = lowered[i]
        if token in ("-command", "-c", "/c"):
            script_parts.extend(args[i + 1 :])
            break
        i += 1
    if not script_parts:
        # -Command が無い場合は全体を対象（unknown になりやすい）
        script_parts = list(args)
    return " ".join(script_parts).strip()


def _tokenize_cmdlets(script: str) -> list[str]:
    # Get-Foo / Select-Object 等
    return [m.group(0).lower() for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_-]*", script)]


def _is_readonly_powershell_script(script: str) -> tuple[bool, list[str], list[str]]:
    """
    既知 read-only パターンか。
    戻り値: (is_safe_shape, side_effects, rationale)
    """
    rationale = []
    if not script.strip():
        return False, [SIDE_UNKNOWN], ["empty_script"]

    if DANGEROUS_TOKEN_RE.search(script):
        return False, [SIDE_UNKNOWN], ["dangerous_token"]

    if COMPOUND_RE.search(script):
        # 単純な | パイプライン以外の複合 → 全体を safe にしない
        return False, [SIDE_UNKNOWN], ["compound_or_dynamic_powershell"]

    # パイプライン分割
    segments = [s.strip() for s in script.split("|") if s.strip()]
    if not segments:
        return False, [SIDE_UNKNOWN], ["empty_segments"]

    cmdlets = []
    for seg in segments:
        tokens = _tokenize_cmdlets(seg)
        if not tokens:
            return False, [SIDE_UNKNOWN], ["unparsed_segment"]
        head = tokens[0].lower()
        cmdlets.append(head)
        # セグメント先頭が許可 cmdlet / helper か
        if head not in READONLY_CMDLETS and head not in READONLY_PIPELINE_HELPERS:
            if SET_LIKE_RE.search(seg):
                return False, [SIDE_UNKNOWN], ["mutating_cmdlet_shape"]
            return False, [SIDE_UNKNOWN], [f"unapproved_cmdlet:{head}"]

    # 少なくとも1つは Get-* 系の情報取得であること
    primary = [
        c
        for c in cmdlets
        if c.startswith("get-") and c in READONLY_CMDLETS
    ]
    if not primary:
        return False, [SIDE_UNKNOWN], ["no_primary_readonly_get"]

    rationale.append("matched_readonly_allowlist")
    rationale.append("primary:" + ",".join(primary))
    return True, [SIDE_READ], rationale


def assess_candidate_safety(candidate: dict | None, *, web_text: str | None = None) -> dict[str, Any]:
    """
    web_text を渡されても Safety には使わない（明示的に無視）。
    """
    _ = web_text  # Web を根拠にしない
    if not isinstance(candidate, dict):
        return empty_safety_assessment(
            status=UNKNOWN,
            rationale_codes=["invalid_candidate"],
            machine_assessed=UNKNOWN,
        )

    command, joined_args = _command_script(candidate)
    args = [str(a) for a in (candidate.get("args") or [])]

    if not command:
        return empty_safety_assessment(
            status=UNKNOWN,
            rationale_codes=["missing_command"],
            machine_assessed=UNKNOWN,
        )

    # 明示的危険
    blob = f"{command} {joined_args}"
    if DANGEROUS_TOKEN_RE.search(blob):
        effects = []
        low = blob.lower()
        if re.search(r"invoke-webrequest|invoke-restmethod|curl|wget|downloadstring", low):
            effects.append(SIDE_NET)
        if re.search(r"remove-item|\bdel\b|\brm\b|format-volume", low):
            effects.append(SIDE_FS_DELETE)
        if re.search(r"set-content|out-file|add-content|new-item", low):
            effects.append(SIDE_FS_WRITE)
        if re.search(r"stop-process|start-process|taskkill", low):
            effects.append(SIDE_PROCESS)
        if re.search(r"stop-service|start-service|set-service|new-service", low):
            effects.append(SIDE_SERVICE)
        if re.search(r"iex|invoke-expression|add-type|downloadstring", low):
            effects.append(SIDE_STATE)
            effects.append(SIDE_NET)
        if not effects:
            effects = [SIDE_UNKNOWN]
        return empty_safety_assessment(
            status=DANGEROUS,
            side_effects=effects,
            network_access="outbound" if SIDE_NET in effects else "none",
            privilege="unknown",
            rationale_codes=["dangerous_pattern_matched"],
            machine_assessed=DANGEROUS,
        )

    if command in ("powershell", "pwsh", "powershell.exe"):
        script = _extract_powershell_script(args)
        ok, effects, rationale = _is_readonly_powershell_script(script)
        if ok:
            return empty_safety_assessment(
                status=SAFE,
                side_effects=effects,
                network_access="none",
                privilege="none",
                rationale_codes=rationale,
                machine_assessed=SAFE,
            )
        # 危険トークンは上で処理済み。未解析・複合 → unknown
        status = UNKNOWN
        if "compound_or_dynamic_powershell" in rationale:
            status = UNKNOWN
        if any(r.startswith("unapproved_cmdlet") for r in rationale):
            # 未知コマンドレット → 危険と断定せず unknown
            status = UNKNOWN
        if "mutating_cmdlet_shape" in rationale:
            status = DANGEROUS
            effects = [SIDE_STATE]
        return empty_safety_assessment(
            status=status,
            side_effects=effects if status != SAFE else [SIDE_READ],
            network_access=UNKNOWN if status == UNKNOWN else "none",
            privilege=UNKNOWN,
            rationale_codes=rationale or ["powershell_not_allowlisted"],
            machine_assessed=status,
        )

    if command == "wmic":
        parts = [str(a).lower() for a in args]
        if parts and parts[0] == "wmic":
            parts = parts[1:]
        target = parts[0] if parts else ""
        if target in WMIC_READONLY_TARGETS:
            return empty_safety_assessment(
                status=SAFE,
                side_effects=[SIDE_READ],
                network_access="none",
                privilege="none",
                rationale_codes=["wmic_readonly_target", f"target:{target}"],
                machine_assessed=SAFE,
            )
        return empty_safety_assessment(
            status=UNKNOWN,
            side_effects=[SIDE_UNKNOWN],
            network_access=UNKNOWN,
            privilege=UNKNOWN,
            rationale_codes=["wmic_target_not_allowlisted", f"target:{target or 'missing'}"],
            machine_assessed=UNKNOWN,
        )

    if command == "nvidia-smi":
        # クエリ用途に限定（追加の破壊フラグが無いこと）
        if re.search(r"(?i)-?(reset|pstate|gom|applications|remove)", joined_args):
            return empty_safety_assessment(
                status=DANGEROUS,
                side_effects=[SIDE_STATE],
                network_access="none",
                privilege=UNKNOWN,
                rationale_codes=["nvidia_smi_mutating_flag"],
                machine_assessed=DANGEROUS,
            )
        return empty_safety_assessment(
            status=SAFE,
            side_effects=[SIDE_READ],
            network_access="none",
            privilege="none",
            rationale_codes=["nvidia_smi_query_readonly"],
            machine_assessed=SAFE,
        )

    # 未対応コマンド → unknown（dangerous と断定しない）
    return empty_safety_assessment(
        status=UNKNOWN,
        side_effects=[SIDE_UNKNOWN],
        network_access=UNKNOWN,
        privilege=UNKNOWN,
        rationale_codes=["unsupported_command_for_safety", f"command:{command}"],
        machine_assessed=UNKNOWN,
    )


def apply_human_decision(assessment: dict, decision: str | None) -> dict[str, Any]:
    """
    人間承認は machine_assessed を書き換えない。
    """
    out = dict(assessment or empty_safety_assessment())
    out["human_decision"] = decision
    # machine_assessed / status は維持
    out["machine_assessed"] = assessment.get("machine_assessed", assessment.get("status"))
    return out
