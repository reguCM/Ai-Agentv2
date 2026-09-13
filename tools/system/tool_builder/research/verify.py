import re
import shlex
import subprocess

import tools.system.tool_builder.research.local as local_research


VERIFY_TIMEOUT = 15
MAX_OUTPUT_CHARS = 2000

DANGEROUS_PATTERN = re.compile(
    r"Remove-Item|\bStop-Process\b|Invoke-Expression|\bIEX\b|"
    r"Start-Process|Set-ExecutionPolicy|Format-Volume|Clear-Disk|"
    r"New-Service|Stop-Computer|Restart-Computer|net\s+user|"
    r"Invoke-WebRequest|Invoke-RestMethod|\bcurl\b|\bwget\b|"
    r"Out-File|Set-Content|Add-Content|New-Item|Move-Item|"
    r"Copy-Item|del\s+/|rmdir|\brm\s+-|taskkill",
    re.IGNORECASE,
)

POWERSHELL_HINTS = (
    "Get-CimInstance",
    "Get-WmiObject",
    "Get-Counter",
    "Get-ComputerInfo",
    "Win32_Processor",
    "Win32_OperatingSystem",
    "Win32_PerfFormattedData_PerfOS_Memory",
    "LoadPercentage",
    "FreePhysicalMemory",
    "TotalVisibleMemorySize",
    "NumberOfCores",
    "NumberOfLogicalProcessors",
)

ALLOWED_WMIC_TARGETS = {
    "cpu",
    "os",
    "computersystem",
    "processor",
}

COMMAND_ALIASES = {
    "powershell.exe": "powershell",
    "pwsh": "powershell",
    "pwsh.exe": "powershell",
    "wmic.exe": "wmic",
}

POWERSHELL_CMDLETS = {
    "get-ciminstance",
    "get-wmiobject",
    "get-counter",
    "get-computerinfo",
}

POWERSHELL_COMMAND_SWITCHES = {"-command", "-c", "/c"}
POWERSHELL_SKIP_SWITCHES = {
    "-noprofile",
    "-nop",
    "-noninteractive",
    "-noni",
    "-nologo",
    "-sta",
    "-mta",
}
POWERSHELL_VALUE_SWITCHES = {
    "-executionpolicy",
    "-ex",
    "-ep",
    "-outputformat",
    "-of",
    "-inputformat",
    "-if",
    "-windowstyle",
    "-w",
    "-workingdirectory",
    "-wd",
}
POWERSHELL_NO_REWRITE_SWITCHES = {
    "-file",
    "-f",
    "-encodedcommand",
    "-ec",
    "-encodedc",
}


def available_command_names(inventory):
    inventory = inventory or {}
    if inventory.get("available_commands"):
        return {
            str(name).lower()
            for name in inventory.get("available_commands") or []
        }
    compact = local_research.compact_inventory(inventory)
    return {
        str(name).lower()
        for name in compact.get("available_commands") or []
    }


def normalize_args(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else None
    if not isinstance(value, list):
        return None
    args = [str(item) for item in value if str(item).strip()]
    return args or None


def split_command_and_args(command, args):
    command = str(command or "").strip()
    parsed_args = normalize_args(args) or []
    if command and not parsed_args:
        try:
            parts = shlex.split(command, posix=False)
        except ValueError:
            parts = command.split()
        if parts:
            command = parts[0].strip('"')
            parsed_args = [part.strip('"') for part in parts[1:]]
    elif len(parsed_args) == 1 and " " in parsed_args[0]:
        try:
            parsed_args = shlex.split(parsed_args[0], posix=False)
        except ValueError:
            parsed_args = parsed_args[0].split()
        parsed_args = [part.strip('"') for part in parsed_args]

    lowered = command.lower()
    if lowered in COMMAND_ALIASES:
        command = COMMAND_ALIASES[lowered]
    elif lowered.endswith(".exe"):
        command = command[:-4]
        lowered = command.lower()
        if lowered in COMMAND_ALIASES:
            command = COMMAND_ALIASES[lowered]
    return command, parsed_args


def join_script_parts(parts):
    parts = [str(item) for item in parts if str(item).strip() != ""]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return " ".join(parts)


def extract_powershell_script(args):
    """
    powershell.exe のスイッチを除き、実行したいスクリプト本体を取り出す。
    -File / -EncodedCommand は書き換えない。
    """
    args = [str(item) for item in (args or [])]
    leftover = []
    index = 0
    while index < len(args):
        token = args[index].lower()
        if token in POWERSHELL_NO_REWRITE_SWITCHES:
            return None
        if token in POWERSHELL_COMMAND_SWITCHES:
            return join_script_parts(args[index + 1 :])
        if token in POWERSHELL_SKIP_SWITCHES:
            index += 1
            continue
        if token in POWERSHELL_VALUE_SWITCHES:
            index += 2
            continue
        leftover.append(args[index])
        index += 1
    if leftover:
        return join_script_parts(leftover)
    return None


def wrap_powershell_args(args):
    script = extract_powershell_script(args)
    if script is None or not str(script).strip():
        return list(args or [])
    return ["-NoProfile", "-NonInteractive", "-Command", script]


def canonicalize_verify_argv(command, args):
    """
    LLM の argv の揺れを、Verifier が実行できる形に直す。
    許可リストはその後に、この実行形へ適用する。
    """
    command = str(command or "").strip()
    args = list(args or [])
    lowered = command.lower()
    if lowered == "powershell":
        return "powershell", wrap_powershell_args(args)
    if lowered == "wmic":
        return "wmic", args
    if lowered in POWERSHELL_CMDLETS:
        script = join_script_parts([command, *args])
        return "powershell", wrap_powershell_args(["-Command", script])
    return command, args


def resolve_verify_argv(candidate):
    command, args = split_command_and_args(
        (candidate or {}).get("command"),
        (candidate or {}).get("args"),
    )
    return canonicalize_verify_argv(command, args)


def bind_candidate_question(candidate, items):
    items = items or []
    questions = [
        item.get("question")
        for item in items
        if isinstance(item, dict) and item.get("question")
    ]
    question = candidate.get("question")
    if question in questions:
        return candidate
    for item in items:
        if item.get("kind") == "output" and item.get("question"):
            candidate["question"] = item.get("question")
            return candidate
    if len(questions) == 1:
        candidate["question"] = questions[0]
    return candidate


def normalize_candidate(candidate, items=None):
    if not isinstance(candidate, dict):
        return None
    command, args = resolve_verify_argv(candidate)
    if not command:
        return None
    candidate = {
        **candidate,
        "command": command,
        "args": args,
    }
    return bind_candidate_question(candidate, items)


def is_safe_powershell(args):
    command_text = " ".join(args)
    if DANGEROUS_PATTERN.search(command_text):
        return False
    lowered = [item.lower() for item in args]
    if "-command" not in lowered and "/c" not in lowered:
        return False
    return any(hint.lower() in command_text.lower() for hint in POWERSHELL_HINTS)


def is_safe_wmic(args):
    if DANGEROUS_PATTERN.search(" ".join(str(item) for item in args)):
        return False
    parts = [str(item).lower() for item in args]
    if parts and parts[0] == "wmic":
        parts = parts[1:]
    if not parts:
        return False
    return parts[0] in ALLOWED_WMIC_TARGETS


def candidate_is_allowed(candidate, inventory):
    errors = []
    command, args = resolve_verify_argv(candidate)
    available = available_command_names(inventory)

    if not command:
        errors.append("command がありません")
    elif command.lower() not in available:
        errors.append(f"command '{command}' はこの環境の available_commands にありません")
    if not args:
        errors.append("args がありません")

    if errors:
        return False, errors, command, args or []

    lowered = command.lower()
    if lowered == "powershell":
        if not is_safe_powershell(args):
            errors.append("PowerShell コマンドが許可された取得用途ではありません")
    elif lowered == "wmic":
        if not is_safe_wmic(args):
            errors.append("wmic の対象が許可された取得用途ではありません")
    else:
        errors.append(f"command '{command}' の検証実行は未対応です")

    return not errors, errors, command, args


def looks_like_failure(stdout, stderr, returncode):
    if returncode != 0:
        return True
    text = (stdout or "").strip()
    if not text:
        return True
    lowered = text.lower()
    fail_marks = (
        "not recognized",
        "見つかりません",
        "未実装",
    )
    return any(mark in lowered or mark in text for mark in fail_marks)


def evaluate_candidate_gate(
    candidate,
    inventory,
    *,
    verified_environment=None,
    chat_fn=None,
    skip_llm=False,
    trusted_personal_mode=None,
    git_facts=None,
    web_safety_claims=None,
    collect_observations=True,
    observation_log_dir=None,
    execution_id=None,
):
    """
    Compatibility / Safety / Gate を独立評価して返す（実行はしない）。
    Phase C: machine safety が unknown のときだけ LLM 構造分析を行い、
    日本語 Safety Report と phase_c 監査ログを付与する。
    Phase D-0/D-1a: Gate 直後に Trusted Personal Policy（AUTO 拡大なし）。
    D-1a: Git/Resource 観測を収集するが allow_execute は変えない。
    """
    from tools.ai.state.compatibility import (
        assess_compatibility,
        extract_environment_requirement,
    )
    from tools.ai.state.environment_context import build_environment_context
    from tools.ai.state.execution_gate import (
        build_unknown_safety_handoff,
        decide_execution_gate,
        suggest_followup_after_block,
    )
    from tools.ai.state.execution_observation import (
        append_observation_log,
        build_observation_record,
        new_execution_id,
    )
    from tools.ai.state.git_workspace_facts import collect_git_workspace_facts
    from tools.ai.state.llm_safety_analysis import run_llm_structural_safety_analysis
    from tools.ai.state.resource_probe import (
        build_resource_assessment_from_probe,
        probe_environment_resources,
    )
    from tools.ai.state.safety_assessment import UNKNOWN, assess_candidate_safety
    from tools.ai.state.safety_report import build_japanese_safety_report
    from tools.ai.state.trusted_personal_policy import evaluate_trusted_personal_policy

    # inventory を compact 形式に寄せる
    if inventory and "available_commands" not in inventory:
        inventory = {
            **inventory,
            **local_research.compact_inventory(inventory),
        }
    env = build_environment_context(
        inventory=inventory,
        verified_environment=verified_environment,
    )
    requirement = extract_environment_requirement(candidate)
    compatibility = assess_compatibility(env, requirement)
    safety = assess_candidate_safety(candidate, web_text=None)
    # 機械判定は保持（LLM で上書きしない）
    machine_assessed = str(safety.get("machine_assessed") or safety.get("status") or UNKNOWN)

    llm_bundle = None
    if (not skip_llm) and machine_assessed == UNKNOWN:
        llm_bundle = run_llm_structural_safety_analysis(
            candidate,
            safety.get("rationale_codes") or [],
            chat_fn=chat_fn,
        )
        # safety に分析を添付するが machine_assessed / status は変更しない
        safety = {
            **safety,
            "machine_assessed": machine_assessed,
            "status": machine_assessed,
            "llm_analysis": llm_bundle.get("analysis"),
            "llm_analysis_meta": {
                "ok": llm_bundle.get("ok"),
                "error": llm_bundle.get("error"),
                "model_profile_id": llm_bundle.get("model_profile_id"),
                "not_a_safety_proof": True,
            },
        }
    elif machine_assessed != UNKNOWN:
        llm_bundle = {
            "ok": False,
            "skipped": True,
            "reason": f"machine_assessed_is_{machine_assessed}",
            "phase": "kss-phase-c",
            "model_profile_id": None,
            "error": None,
            "analysis": None,
            "web_content_included": False,
            "not_a_safety_proof": True,
        }

    gate = decide_execution_gate(compatibility, safety, llm_bundle=llm_bundle)

    eid = execution_id or new_execution_id()
    collected_git = git_facts
    resource_before = None
    resource_assessment = None
    observation_meta = {
        "phase": "kss-phase-d1a",
        "execution_id": eid,
        "observation_only": True,
    }
    if collect_observations:
        if collected_git is None:
            collected_git = collect_git_workspace_facts(candidate=candidate)
        resource_before = probe_environment_resources()
        resource_assessment = build_resource_assessment_from_probe(resource_before)
        observation_meta["resource_before"] = resource_before
        observation_meta["git_facts"] = collected_git

    trusted_personal = evaluate_trusted_personal_policy(
        mode=trusted_personal_mode,
        gate=gate,
        compatibility=compatibility,
        safety=safety,
        llm_bundle=llm_bundle,
        git_facts=collected_git,
        resource_assessment=resource_assessment,
        web_safety_claims=web_safety_claims,
        candidate=candidate,
        observation=observation_meta,
        execution_id=eid,
    )
    report = build_japanese_safety_report(
        candidate=candidate,
        compatibility=compatibility,
        safety=safety,
        llm_bundle=llm_bundle,
        gate=gate,
        trusted_personal=trusted_personal,
    )

    phase_c = {
        "phase": "kss-phase-c",
        "candidate": {
            "command": (candidate or {}).get("command"),
            "args": list((candidate or {}).get("args") or []),
        },
        "compatibility": compatibility,
        "machine_safety": {
            "status": safety.get("status"),
            "machine_assessed": machine_assessed,
            "side_effects": safety.get("side_effects"),
            "network_access": safety.get("network_access"),
            "privilege": safety.get("privilege"),
            "rationale_codes": safety.get("rationale_codes"),
        },
        "llm_analysis": llm_bundle,
        "gate": gate,
        "rationale_codes": gate.get("rationale_codes"),
        "safety_report_ja": report,
        "audit": {
            "machine_not_overwritten_by_llm": True,
            "machine_assessed_unchanged": machine_assessed
            == str(safety.get("machine_assessed")),
            "llm_cannot_set_execute": gate.get("decision") != "Execute"
            or machine_assessed == "safe",
            "experiment_candidate_not_auto_executed": not (
                gate.get("decision") == "ExperimentCandidate"
                and gate.get("allow_execute")
            ),
            "web_content_used_for_safety": False,
            "machine_not_loosened_by_llm": gate.get("machine_not_loosened_by_llm", True),
            "cannot_rule_out_empty_is_not_safety_proof": True,
        },
    }

    obs_log_path = None
    if collect_observations:
        pre_record = build_observation_record(
            execution_id=eid,
            stage="pre",
            gate=gate,
            trusted_personal=trusted_personal,
            git_facts=collected_git,
            resource_before=resource_before,
            candidate=candidate,
        )
        obs_log_path = str(
            append_observation_log(pre_record, log_dir=observation_log_dir)
        )

    phase_d = {
        "phase": "kss-phase-d1a",
        "trusted_personal": trusted_personal,
        "audit": trusted_personal.get("audit"),
        "execution_id": eid,
        "git_facts": collected_git,
        "resource_before": resource_before,
        "observation_log_path": obs_log_path,
        "observation_only": True,
        "allow_execute_expanded": False,
    }

    followup = None
    handoff = None
    final_allow = bool(trusted_personal.get("allow_execute"))
    if not final_allow:
        followup = suggest_followup_after_block(gate, candidate)
        if machine_assessed == UNKNOWN or "block_safety_unknown" in (
            gate.get("rationale_codes") or []
        ):
            handoff = build_unknown_safety_handoff(
                purpose=str((candidate or {}).get("question") or ""),
                candidate=candidate,
                compatibility=compatibility,
                safety=safety,
                gate=gate,
                safety_report=report,
            )
        if collect_observations:
            blocked_record = build_observation_record(
                execution_id=eid,
                stage="blocked",
                gate=gate,
                trusted_personal=trusted_personal,
                git_facts=collected_git,
                resource_before=resource_before,
                candidate=candidate,
                extra={"reason": "not_allow_execute"},
            )
            append_observation_log(blocked_record, log_dir=observation_log_dir)

    return {
        "environment": env,
        "requirement": requirement,
        "compatibility": compatibility,
        "safety": safety,
        "gate": gate,
        "trusted_personal": trusted_personal,
        "followup": followup,
        "safety_unknown_handoff": handoff,
        "llm_bundle": llm_bundle,
        "safety_report": report,
        "phase_c": phase_c,
        "phase_d": phase_d,
        "execution_id": eid,
        "git_facts": collected_git,
        "resource_before": resource_before,
    }


def run_candidate(
    candidate,
    inventory,
    timeout=VERIFY_TIMEOUT,
    *,
    verified_environment=None,
    trusted_personal_mode=None,
    collect_observations=True,
    observation_log_dir=None,
):
    from tools.ai.state.execution_observation import (
        append_observation_log,
        begin_execution_observation,
        build_observation_record,
        finalize_execution_observation,
    )
    from tools.ai.state.resource_probe import (
        diff_resource_snapshots,
        probe_environment_resources,
    )

    assessment = evaluate_candidate_gate(
        candidate,
        inventory,
        verified_environment=verified_environment,
        trusted_personal_mode=trusted_personal_mode,
        collect_observations=collect_observations,
        observation_log_dir=observation_log_dir,
    )
    gate = assessment.get("gate") or {}
    trusted_personal = assessment.get("trusted_personal") or {}
    eid = assessment.get("execution_id")
    command, args = resolve_verify_argv(candidate)

    # D-0/D-1a: Trusted Personal の allow_execute（観測で拡大しない）
    allow_execute = trusted_personal.get("allow_execute", gate.get("allow_execute"))
    if not allow_execute:
        return {
            "ok": False,
            "command": command,
            "args": args,
            "error": (
                "execution_gate_blocked:"
                + ",".join(gate.get("rationale_codes") or [gate.get("decision") or "Block"])
            ),
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "phase_b": assessment,
            "phase_c": assessment.get("phase_c"),
            "phase_d": assessment.get("phase_d"),
            "execution_id": eid,
            "blocked_by_gate": True,
            "blocked_by_trusted_personal": not gate.get("allow_execute")
            or not trusted_personal.get("allow_execute"),
        }

    # Gate 通過後は inventory 実在のみ再確認（旧 HINTS 二重判定で read-only を落とさない）
    available = available_command_names(inventory)
    command, args = resolve_verify_argv(candidate)
    inv_errors = []
    if not command:
        inv_errors.append("command がありません")
    elif command.lower() not in available:
        inv_errors.append(
            f"command '{command}' はこの環境の available_commands にありません"
        )
    if not args and command.lower() != "nvidia-smi":
        # nvidia-smi は args 空もあり得るが、通常は query 付き
        pass
    if not args:
        inv_errors.append("args がありません")
    if inv_errors:
        return {
            "ok": False,
            "command": command,
            "args": args or [],
            "error": "; ".join(inv_errors),
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "phase_b": assessment,
            "phase_c": assessment.get("phase_c"),
            "phase_d": assessment.get("phase_d"),
            "execution_id": eid,
            "blocked_by_gate": False,
        }

    argv = [command, *args]
    resource_before = assessment.get("resource_before")
    begun = begin_execution_observation(eid)
    from tools.ai.state.execution_observation import UNKNOWN as OBS_UNKNOWN

    timed_out = False
    child_count = OBS_UNKNOWN
    child_spawned = OBS_UNKNOWN
    completed = None
    run_error = None
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        # subprocess.run 終了後は子は通常終了済み。実行中カウントは unknown。
        child_count = OBS_UNKNOWN
        child_spawned = OBS_UNKNOWN
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        run_error = f"TimeoutExpired: {exc}"
        completed = type(
            "C",
            (),
            {
                "returncode": None,
                "stdout": getattr(exc, "stdout", "") or "",
                "stderr": getattr(exc, "stderr", "") or "",
            },
        )()
    except Exception as exc:
        run_error = f"{type(exc).__name__}: {exc}"
        resource_after = (
            probe_environment_resources() if collect_observations else None
        )
        exec_facts = finalize_execution_observation(
            begun,
            returncode=OBS_UNKNOWN,
            timed_out=False,
            child_process_count=OBS_UNKNOWN,
            child_process_spawned=OBS_UNKNOWN,
            error=run_error,
        )
        if collect_observations:
            delta = diff_resource_snapshots(resource_before, resource_after)
            append_observation_log(
                build_observation_record(
                    execution_id=eid,
                    stage="post",
                    gate=gate,
                    trusted_personal=trusted_personal,
                    git_facts=assessment.get("git_facts"),
                    resource_before=resource_before,
                    resource_after=resource_after,
                    resource_delta=delta,
                    execution_facts=exec_facts,
                    candidate=candidate,
                ),
                log_dir=observation_log_dir,
            )
            phase_d = dict(assessment.get("phase_d") or {})
            phase_d.update(
                {
                    "resource_after": resource_after,
                    "resource_delta": delta,
                    "execution_facts": exec_facts,
                }
            )
            assessment = {**assessment, "phase_d": phase_d}
        return {
            "ok": False,
            "command": command,
            "args": args,
            "error": run_error,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "phase_b": assessment,
            "phase_c": assessment.get("phase_c"),
            "phase_d": assessment.get("phase_d"),
            "execution_id": eid,
            "execution_facts": exec_facts,
            "blocked_by_gate": False,
        }

    resource_after = probe_environment_resources() if collect_observations else None
    exec_facts = finalize_execution_observation(
        begun,
        returncode=getattr(completed, "returncode", None),
        timed_out=timed_out,
        child_process_count=child_count,
        child_process_spawned=child_spawned,
        error=run_error,
    )
    delta = None
    if collect_observations:
        delta = diff_resource_snapshots(resource_before, resource_after)
        append_observation_log(
            build_observation_record(
                execution_id=eid,
                stage="post",
                gate=gate,
                trusted_personal=trusted_personal,
                git_facts=assessment.get("git_facts"),
                resource_before=resource_before,
                resource_after=resource_after,
                resource_delta=delta,
                execution_facts=exec_facts,
                candidate=candidate,
            ),
            log_dir=observation_log_dir,
        )
        phase_d = dict(assessment.get("phase_d") or {})
        phase_d.update(
            {
                "resource_after": resource_after,
                "resource_delta": delta,
                "execution_facts": exec_facts,
            }
        )
        assessment = {**assessment, "phase_d": phase_d}

    if timed_out:
        return {
            "ok": False,
            "command": command,
            "args": args,
            "error": run_error or "TimeoutExpired",
            "returncode": None,
            "stdout": str(getattr(completed, "stdout", "") or "")[:MAX_OUTPUT_CHARS],
            "stderr": str(getattr(completed, "stderr", "") or "")[:MAX_OUTPUT_CHARS],
            "phase_b": assessment,
            "phase_c": assessment.get("phase_c"),
            "phase_d": assessment.get("phase_d"),
            "execution_id": eid,
            "execution_facts": exec_facts,
            "blocked_by_gate": False,
        }

    stdout = (completed.stdout or "")[:MAX_OUTPUT_CHARS]
    stderr = (completed.stderr or "")[:MAX_OUTPUT_CHARS]
    ok = not looks_like_failure(stdout, stderr, completed.returncode)
    return {
        "ok": ok,
        "command": command,
        "args": args,
        "error": None if ok else (stderr.strip() or "出力が空、またはエラーに見える"),
        "returncode": completed.returncode,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "phase_b": assessment,
        "phase_c": assessment.get("phase_c"),
        "phase_d": assessment.get("phase_d"),
        "execution_id": eid,
        "execution_facts": exec_facts,
        "resource_before": resource_before,
        "resource_after": resource_after,
        "resource_delta": delta,
        "blocked_by_gate": False,
    }


def research_verifier(
    candidates=None,
    items=None,
    inventory=None,
    timeout=VERIFY_TIMEOUT,
    *,
    verified_environment=None,
):
    """
    Web調査から得た検証用コマンドを実環境で実行し、confidence を付け直す。
    成功したものだけ high。それ以外は low。
    Phase B: Compatibility/Safety Gate を通過したものだけ実行する。
    """

    candidates = candidates or []
    items = items or []
    inventory = inventory or local_research.collect_local_inventory()

    by_question = {}
    for item in items:
        if isinstance(item, dict) and item.get("question"):
            by_question.setdefault(item["question"], item)

    results = []
    gate_log = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate = normalize_candidate(candidate, items)
        if not candidate:
            continue
        question = candidate.get("question")
        item = by_question.get(question) or {"question": question}
        run = run_candidate(
            candidate,
            inventory,
            timeout=timeout,
            verified_environment=verified_environment,
        )
        phase_b = run.get("phase_b") or {}
        gate_log.append(
            {
                "command": run.get("command"),
                "args": run.get("args"),
                "compatibility": (phase_b.get("compatibility") or {}).get("status"),
                "safety": (phase_b.get("safety") or {}).get("status"),
                "machine_assessed": ((phase_b.get("safety") or {}).get("machine_assessed")),
                "gate": (phase_b.get("gate") or {}).get("decision"),
                "rationale_codes": (phase_b.get("gate") or {}).get("rationale_codes"),
                "blocked_by_gate": run.get("blocked_by_gate"),
                "allow_execute": (phase_b.get("gate") or {}).get("allow_execute"),
                "trusted_personal": (phase_b.get("trusted_personal") or {}).get("decision"),
                "trusted_personal_allow_execute": (phase_b.get("trusted_personal") or {}).get(
                    "allow_execute"
                ),
                "phase_c": run.get("phase_c") or phase_b.get("phase_c"),
                "phase_d": run.get("phase_d") or phase_b.get("phase_d"),
            }
        )
        sample = []
        if run["ok"]:
            sample = run["stdout"].splitlines()
            sample = [line.strip() for line in sample if line.strip()][:8]
            finding = (
                "実環境で取得できた。"
                f"command={run['command']}。"
                "戻り値サンプルあり"
            )
            confidence = "high"
        else:
            finding = (
                "実環境で確認できなかった。"
                f"{run.get('error') or '失敗'}"
            )
            confidence = "low"

        results.append(
            {
                "id": item.get("id"),
                "kind": item.get("kind") or "output",
                "question": question,
                "finding": finding,
                "evidence": {
                    "command": run.get("command"),
                    "args": run.get("args"),
                    "returncode": run.get("returncode"),
                    "sample": sample if run["ok"] else [],
                    "stderr": run.get("stderr") or "",
                    "error": run.get("error"),
                    "output_key": candidate.get("output_key"),
                    "phase_b": phase_b,
                },
                "confidence": confidence,
                "source": "web",
            }
        )

    return {
        "result": "OK",
        "status": "completed" if results else "partial",
        "source": "web",
        "results": results,
        "result_count": len(results),
        "phase_b_gate_log": gate_log,
        "notes": [
            "Web候補を実環境で実行した結果である。",
            "成功したものだけ confidence=high にする。",
            "Phase B: Compatibility と Safety を独立評価してから実行する。",
        ],
    }


def merge_research_results(local_results, verified_results, subject=None):
    verified_by_question = {}
    for item in verified_results or []:
        if isinstance(item, dict) and item.get("question"):
            current = verified_by_question.get(item["question"])
            if current is None or (
                item.get("confidence") == "high"
                and current.get("confidence") != "high"
            ):
                verified_by_question[item["question"]] = item

    merged = []
    for item in local_results or []:
        if not isinstance(item, dict):
            continue
        if item.get("confidence") == "high":
            merged.append(item)
            continue
        question = item.get("question")
        verified = verified_by_question.get(question)
        if verified and verified.get("confidence") == "high":
            merged.append(verified)
            continue
        merged.append(
            {
                **item,
                "confidence": "low",
                "source": (verified or item).get("source") or item.get("source"),
                "finding": (
                    (verified or {}).get("finding")
                    or "Web調査後も取得方法を実環境で確認できなかった"
                ),
                "evidence": (verified or item).get("evidence") or item.get("evidence"),
            }
        )

    low_count = sum(1 for item in merged if item.get("confidence") == "low")
    return {
        "result": "OK",
        "status": "partial" if low_count else "completed",
        "source": "mixed",
        "subject": subject or {},
        "results": merged,
        "result_count": len(merged),
        "notes": [
            "local の high は維持した。",
            "medium/low は Web検証後、成功なら high、失敗なら unresolved にした。",
        ],
    }
