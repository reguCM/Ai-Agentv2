import ast
import os
import re

from tools.system.tool_builder.validate.warning_actions import (
    ACTION_BLOCKED,
    ACTION_REPAIR,
    collect_warning_items,
    finalize_validation_status,
    proposal_unconfirmed_notes,
    research_has_verified_method,
    stub_required_information,
    summarize_disposition,
    warning_item,
)


FIX_BY_CODE = {
    "unparsed_output": (
        "見出しや区切り線ではなく、実際の値だけを返す。"
        "subprocess の実行・stdout 取得部分を変更しない。"
        "evidence.parsed_table があるキーは、その value を戻り値にする。"
        "表のパース方法をコードで再発明しない。"
        "抽出に失敗しても例外を投げず、失敗値（例: {'status':'error'}）を返す。"
    ),
    "meaningless_output": (
        "見出し・区切り線・空文字は値ではない。"
        "usable_findings の sample に値行があるなら、その値行を返す"
    ),
    "wrong_output_key": "戻り値のキーを proposal.output に合わせる。値は変えない",
    "return_value_not_dict": "戻り値を dict にし、proposal.output のキーで返す",
    "subprocess_result_handling": (
        "subprocess.run は capture_output=True, text=True にし、"
        "returncode を確認してから stdout を使う"
    ),
    "stub_value": "usable_findings の evidence.command と sample があるときだけ実装する",
    "runtime_exception": (
        "test_result の error と traceback を見て例外を直す。"
        "見出し行や区切り線を split して落ちない。"
        "usable_findings の sample に値行があるなら、その行を返す"
    ),
    "semantic_mismatch": (
        "戻り値の形は正しいが、要求した種類の値ではない。"
        "usable_findings の sample にある具体値と同じ種類の値を返す"
    ),
}


def normalize_output_names(output):
    if not isinstance(output, list):
        return []
    return [str(item) for item in output if str(item).strip()]


TABLE_RULE_RE = re.compile(r"^[-_=.*~]{3,}$")
NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
PROPERTY_SELECT_RE = re.compile(
    r"(?:Select(?:-Object)?|\bget)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)",
    re.I,
)


def output_lines(value):
    if value is None:
        return []
    return [
        line.strip()
        for line in str(value).replace("\r\n", "\n").split("\n")
        if line.strip()
    ]


def parse_tabular_text(text):
    """
    既知の表形式（見出し / 区切り線 / 値）を機械的に分解する。
    当てはまらなければ None。値の意味はここでは決めない。
    """

    lines = output_lines(text)
    sep_indexes = [
        index for index, line in enumerate(lines) if is_separator_text(line)
    ]
    if not sep_indexes:
        return None

    first_sep = sep_indexes[0]
    headers = lines[:first_sep]
    separators = [lines[index] for index in sep_indexes]
    values = [
        line
        for index, line in enumerate(lines)
        if index > first_sep and not is_separator_text(line)
    ]
    if not headers or not values:
        return None

    parsed = {
        "headers": headers,
        "separators": separators,
        "values": values,
        "header": headers[0] if len(headers) == 1 else headers,
        "separator": separators[0] if len(separators) == 1 else separators,
        "value": values[0] if len(values) == 1 else values,
    }
    return parsed


def parsed_tables_from_mapping(mapping):
    parsed_tables = {}
    if not isinstance(mapping, dict):
        return parsed_tables
    for key, value in mapping.items():
        parsed = parse_tabular_text(value)
        if parsed:
            parsed_tables[key] = parsed
    return parsed_tables


def parsed_table_from_sample(sample):
    if isinstance(sample, list):
        text = "\n".join(str(line) for line in sample)
    else:
        text = sample
    return parse_tabular_text(text)


def attach_parsed_tables_to_research(research_result):
    """
    調査 sample が既知の表なら、見出し / 区切り / 値に分解して evidence に載せる。
    元の research_result は変更しない。
    """

    if not research_result:
        return research_result

    updated = dict(research_result)
    for key in ("usable_findings", "reference_findings"):
        items = research_result.get(key)
        if not items:
            continue
        new_items = []
        for item in items:
            item = dict(item)
            evidence = dict(item.get("evidence") or {})
            if "parsed_table" not in evidence:
                parsed = parsed_table_from_sample(evidence.get("sample"))
                if parsed:
                    evidence["parsed_table"] = parsed
            item["evidence"] = evidence
            new_items.append(item)
        updated[key] = new_items
    return updated


def looks_like_raw_table(value):
    if not isinstance(value, str):
        return False
    lines = [
        line.strip()
        for line in value.replace("\r\n", "\n").split("\n")
        if line.strip()
    ]
    if len(lines) < 2:
        return False
    return any(TABLE_RULE_RE.fullmatch(line) for line in lines)


def is_separator_text(value):
    if value is None:
        return False
    return bool(TABLE_RULE_RE.fullmatch(str(value).strip()))


def is_numeric_text(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    return bool(NUMBER_RE.fullmatch(value.strip()))


def sample_output_lines(research_result):
    lines = []
    for item in (research_result or {}).get("usable_findings") or []:
        sample = (item.get("evidence") or {}).get("sample") or []
        if isinstance(sample, str):
            sample = sample.splitlines()
        for line in sample:
            text = str(line).strip()
            if text:
                lines.append(text)
    return lines


def sample_non_value_texts(research_result):
    lines = sample_output_lines(research_result)
    separators = [line for line in lines if is_separator_text(line)]
    numbers = [line for line in lines if is_numeric_text(line)]
    if not separators and not numbers:
        return []
    non_values = []
    for line in lines:
        if is_separator_text(line) or not is_numeric_text(line):
            non_values.append(line)
    return non_values


def selected_property_names(source, research_result=None):
    texts = []
    for argv in analyze_subprocess_source(source).get("commands") or []:
        texts.append(" ".join(argv))
    for argv in finding_argvs(research_result):
        texts.append(" ".join(argv))
    names = []
    seen = set()
    for text in texts:
        for match in PROPERTY_SELECT_RE.finditer(text):
            for name in match.group(1).split(","):
                name = name.strip()
                key = name.lower()
                if name and key not in seen:
                    seen.add(key)
                    names.append(name)
    return names


def collect_stub_values(value):
    stubs = []

    if isinstance(value, dict):
        for key, item in value.items():
            if item == "未実装":
                stubs.append(key)
    elif value == "未実装":
        stubs.append("value")

    return stubs


def module_to_path(module):
    if not module:
        return None
    return module.replace(".", "/") + ".py"


def resolve_source(proposal, implementation, source=None):
    if source:
        return source
    implementation = implementation or {}
    if implementation.get("code"):
        return implementation.get("code")
    if implementation.get("current_source"):
        return implementation.get("current_source")
    path = module_to_path((proposal or {}).get("module"))
    if not path:
        return None
    normalized = path.replace("\\", "/")
    if not os.path.exists(normalized):
        return None
    with open(normalized, "r", encoding="utf-8") as f:
        return f.read()


def call_name(node):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return None


def const_argv(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    parts = []
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            parts.append(element.value)
        else:
            return None
    return parts


def analyze_subprocess_source(source):
    analysis = {
        "has_run": False,
        "problems": [],
        "commands": [],
        "uses_returncode": False,
        "uses_stdout": False,
        "has_capture": False,
    }
    if not source or not str(source).strip():
        return analysis

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return analysis

    run_names = {"subprocess.run", "subprocess.check_output", "run", "check_output"}
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and call_name(node.func) in run_names
    ]
    if not calls:
        return analysis

    analysis["has_run"] = True
    for call in calls:
        keywords = {keyword.arg for keyword in call.keywords if keyword.arg}
        if "capture_output" in keywords or "stdout" in keywords:
            analysis["has_capture"] = True
        if call.args:
            argv = const_argv(call.args[0])
            if argv:
                analysis["commands"].append(argv)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr == "returncode":
                analysis["uses_returncode"] = True
            if node.attr in ("stdout", "stderr"):
                analysis["uses_stdout"] = True

    if not analysis["has_capture"]:
        analysis["problems"].append("capture_output または stdout パイプがありません")
    if analysis["uses_stdout"] and not analysis["uses_returncode"]:
        analysis["problems"].append("stdout を使っていますが returncode を確認していません")
    if not analysis["uses_stdout"] and not analysis["uses_returncode"]:
        analysis["problems"].append("subprocess の戻り値を使っていません")
    return analysis


def finding_argvs(research_result):
    argvs = []
    for item in (research_result or {}).get("usable_findings") or []:
        evidence = item.get("evidence") or {}
        command = evidence.get("command")
        if not command:
            continue
        args = evidence.get("args") or []
        if isinstance(args, str):
            args = [args]
        argvs.append([str(command), *[str(part) for part in args]])
    return argvs


def argv_matches(source_argv, finding_argv):
    if not source_argv or not finding_argv:
        return False
    if source_argv[0].lower() != finding_argv[0].lower():
        return False
    source_text = " ".join(source_argv[1:]).lower()
    finding_text = " ".join(finding_argv[1:]).lower()
    if source_text == finding_text:
        return True
    if finding_argv[-1] and finding_argv[-1].lower() in source_text:
        return True
    if source_argv[-1] and source_argv[-1].lower() in finding_text:
        return True
    return False


CODE_EXCEPTION_TYPES = {
    "IndexError",
    "KeyError",
    "ValueError",
    "TypeError",
    "AttributeError",
    "ZeroDivisionError",
    "NameError",
    "UnboundLocalError",
}


def is_code_exception(test_result):
    error_type = (test_result or {}).get("error_type")
    return error_type in CODE_EXCEPTION_TYPES


def looks_like_command_failure(test_result):
    if not test_result:
        return False
    if test_result.get("result") != "OK":
        return True
    return_value = test_result.get("return_value")
    if return_value == "error":
        return True
    return False


def make_item(code, message, action, **kwargs):
    return warning_item(
        code,
        message,
        action,
        fix=kwargs.pop("fix", None) or FIX_BY_CODE.get(code),
        **kwargs,
    )


def check_execution(test_result, source=None, research_result=None):
    errors = []
    warning_items = []

    if not test_result:
        errors.append("test_result がありません")
    elif test_result.get("result") != "OK":
        if is_code_exception(test_result):
            warning_items.append(
                make_item(
                    "runtime_exception",
                    (
                        "Tool実行が例外で失敗しました: "
                        f"{test_result.get('error_type')}: {test_result.get('error')}"
                    ),
                    ACTION_REPAIR,
                    reason="コードの例外であり、取得方法の調査ではない",
                    evidence={
                        "error_type": test_result.get("error_type"),
                        "error": test_result.get("error"),
                        "traceback": test_result.get("traceback"),
                    },
                )
            )
        else:
            analysis = analyze_subprocess_source(source)
            if not analysis["has_run"]:
                errors.append(
                    f"Tool実行が失敗しました: {test_result.get('error')}"
                )

    return {
        "status": "fail" if errors else ("warning" if warning_items else "pass"),
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_return_value(test_result):
    errors = []
    warning_items = []
    return_value = test_result.get("return_value") if test_result else None

    if test_result and test_result.get("result") == "OK" and not isinstance(return_value, dict):
        warning_items.append(
            make_item(
                "return_value_not_dict",
                "return_value が dict ではありません",
                ACTION_REPAIR,
                reason="戻り値の形が間違っている",
                evidence={"return_type": type(return_value).__name__},
            )
        )

    return {
        "status": "warning" if warning_items else "pass",
        "return_value": return_value,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_output_keys(proposal, test_result):
    errors = []
    warning_items = []
    missing_outputs = []
    extra_keys = []
    expected_outputs = normalize_output_names(proposal.get("output"))
    return_value = test_result.get("return_value") if test_result else None

    if test_result and test_result.get("result") != "OK":
        return {
            "status": "pass",
            "expected_outputs": expected_outputs,
            "missing_outputs": missing_outputs,
            "errors": errors,
            "warnings": [],
            "warning_items": warning_items,
        }

    if not expected_outputs:
        warning_items.append(
            make_item(
                "empty_output_spec",
                "proposal.output が空です",
                ACTION_BLOCKED,
                reason="設計案の output が未定義",
                required_information=[
                    "proposal.output に含める項目",
                    "各項目の取得可否",
                ],
                evidence={"output": proposal.get("output")},
            )
        )
        return {
            "status": "warning",
            "expected_outputs": expected_outputs,
            "missing_outputs": missing_outputs,
            "errors": errors,
            "warnings": [item["message"] for item in warning_items],
            "warning_items": warning_items,
        }

    if not isinstance(return_value, dict):
        missing_outputs = expected_outputs.copy()
        return {
            "status": "pass",
            "expected_outputs": expected_outputs,
            "missing_outputs": missing_outputs,
            "errors": errors,
            "warnings": [],
            "warning_items": warning_items,
        }

    actual_keys = [str(key) for key in return_value.keys()]
    actual_set = set(actual_keys)
    expected_set = set(expected_outputs)
    missing_outputs = [name for name in expected_outputs if name not in actual_set]
    extra_keys = [name for name in actual_keys if name not in expected_set]

    if missing_outputs:
        warning_items.append(
            make_item(
                "wrong_output_key",
                f"戻り値のキーが設計案と一致しません: missing={missing_outputs}",
                ACTION_REPAIR,
                reason="output キーが間違っている",
                evidence={
                    "expected": expected_outputs,
                    "actual": actual_keys,
                    "missing": missing_outputs,
                    "extra": extra_keys,
                },
            )
        )

    return {
        "status": "warning" if warning_items else "pass",
        "expected_outputs": expected_outputs,
        "missing_outputs": missing_outputs,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_output_format(test_result):
    errors = []
    warning_items = []
    unparsed_keys = []
    return_value = test_result.get("return_value") if test_result else None
    parsed_tables = parsed_tables_from_mapping(return_value)

    if isinstance(return_value, dict):
        for key, value in return_value.items():
            if looks_like_raw_table(value):
                unparsed_keys.append(key)

    if unparsed_keys:
        warning_items.append(
            make_item(
                "unparsed_output",
                f"戻り値がコマンドの生出力のままです: {unparsed_keys}",
                ACTION_REPAIR,
                reason="取得はできているが、値の整形が間違っている",
                evidence={
                    "unparsed_keys": unparsed_keys,
                    "parsed_table": parsed_tables,
                },
            )
        )

    return {
        "status": "warning" if warning_items else "pass",
        "unparsed_keys": unparsed_keys,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def classify_meaningless_value(value, *, property_names=None, sample_non_values=None):
    if value == "未実装":
        return None
    if looks_like_raw_table(value):
        return None
    if value is None:
        return "empty"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return None
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return "empty"
    if is_separator_text(text):
        return "separator"

    lowered = text.lower()
    for name in property_names or []:
        if lowered == str(name).strip().lower():
            return "header"
    for non_value in sample_non_values or []:
        if lowered == str(non_value).strip().lower():
            return "header" if not is_separator_text(non_value) else "separator"
    return None


def research_has_numeric_sample(research_result):
    for item in (research_result or {}).get("usable_findings") or []:
        evidence = item.get("evidence") or {}
        sample = evidence.get("sample")
        lines = sample if isinstance(sample, list) else [sample]
        for line in lines:
            text = str(line).strip() if line is not None else ""
            if NUMBER_RE.match(text):
                return True
    return False


def value_looks_numeric(value):
    if value is None:
        return False
    return bool(NUMBER_RE.match(str(value).strip()))


def check_output_values(test_result, source=None, research_result=None):
    warning_items = []
    bad_keys = []
    kinds = {}
    return_value = test_result.get("return_value") if test_result else None
    property_names = selected_property_names(source, research_result)
    non_values = sample_non_value_texts(research_result)

    if isinstance(return_value, dict):
        for key, value in return_value.items():
            kind = classify_meaningless_value(
                value,
                property_names=property_names,
                sample_non_values=non_values,
            )
            if kind:
                bad_keys.append(key)
                kinds[key] = kind

    if bad_keys:
        warning_items.append(
            make_item(
                "meaningless_output",
                f"戻り値が見出し・区切り線・空文字です: {bad_keys}",
                ACTION_REPAIR,
                reason="取得結果の値ではなく、表の見出しや区切りを返している",
                evidence={
                    "keys": bad_keys,
                    "kinds": kinds,
                    "property_names": property_names,
                    "sample_non_values": non_values,
                },
            )
        )
    elif (
        isinstance(return_value, dict)
        and research_has_numeric_sample(research_result)
        and not collect_stub_values(return_value)
    ):
        skip_values = {"error", "未実装"}
        semantic_keys = [
            key
            for key, value in return_value.items()
            if value not in (None, "")
            and str(value).strip() not in skip_values
            and not value_looks_numeric(value)
            and parse_tabular_text(value) is None
            and "\n" not in str(value)
        ]
        if semantic_keys:
            warning_items.append(
                make_item(
                    "semantic_mismatch",
                    f"戻り値は形として通るが、要求した数値ではない: {semantic_keys}",
                    ACTION_REPAIR,
                    reason="コードは動いているが、要求と違う種類の値を返している",
                    evidence={"keys": semantic_keys},
                )
            )

    return {
        "status": "warning" if warning_items else "pass",
        "keys": bad_keys,
        "errors": [],
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_subprocess_handling(source, test_result=None):
    warning_items = []
    analysis = analyze_subprocess_source(source)
    parsed_tables = parsed_tables_from_mapping(
        (test_result or {}).get("return_value")
    )

    if analysis["has_run"] and analysis["problems"]:
        evidence = {"problems": analysis["problems"]}
        if parsed_tables:
            evidence["parsed_table"] = parsed_tables
        warning_items.append(
            make_item(
                "subprocess_result_handling",
                "subprocess の戻り値処理が間違っています",
                ACTION_REPAIR,
                reason="returncode / stdout の扱いが不足している",
                evidence=evidence,
            )
        )

    return {
        "status": "warning" if warning_items else "pass",
        "problems": analysis.get("problems") or [],
        "commands": analysis.get("commands") or [],
        "errors": [],
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_command(source, test_result, research_result=None):
    warning_items = []
    if is_code_exception(test_result):
        return {
            "status": "pass",
            "errors": [],
            "warnings": [],
            "warning_items": warning_items,
        }

    analysis = analyze_subprocess_source(source)
    if not analysis["has_run"]:
        return {
            "status": "pass",
            "errors": [],
            "warnings": [],
            "warning_items": warning_items,
        }

    if analysis["problems"]:
        return {
            "status": "pass",
            "errors": [],
            "warnings": [],
            "warning_items": warning_items,
        }

    if collect_stub_values(test_result.get("return_value") if test_result else None):
        return {
            "status": "pass",
            "errors": [],
            "warnings": [],
            "warning_items": warning_items,
        }

    verified = research_has_verified_method(research_result)
    findings = finding_argvs(research_result)
    source_commands = analysis["commands"]
    matched = any(
        argv_matches(source_argv, finding_argv)
        for source_argv in source_commands
        for finding_argv in findings
    )

    if verified and findings and source_commands and not matched:
        warning_items.append(
            make_item(
                "wrong_command",
                "実装中のコマンドが調査済みの取得方法と一致しません",
                ACTION_REPAIR,
                reason="確認済みのコマンドへ置き換える必要がある",
                evidence={
                    "source_commands": source_commands,
                    "verified_commands": findings,
                },
                needs_research_findings=True,
            )
        )
        return {
            "status": "warning",
            "errors": [],
            "warnings": [item["message"] for item in warning_items],
            "warning_items": warning_items,
        }

    if not verified and looks_like_command_failure(test_result):
        warning_items.append(
            make_item(
                "wrong_command",
                "コマンド実行に失敗しているため、正しい取得方法の確認が必要です",
                ACTION_BLOCKED,
                reason="コマンドが間違っている可能性がある",
                required_information=["正しい取得コマンドと戻り値"],
                evidence={"source_commands": source_commands},
                needs_research_findings=True,
            )
        )

    return {
        "status": "warning" if warning_items else "pass",
        "errors": [],
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_stub_status(proposal, test_result, implementation=None, research_result=None):
    errors = []
    warning_items = []
    return_value = test_result.get("return_value") if test_result else None
    stub_keys = collect_stub_values(return_value)

    unimplemented = []
    if implementation:
        unimplemented = implementation.get("unimplemented") or []

    unconfirmed_notes = proposal_unconfirmed_notes(proposal)
    verified = research_has_verified_method(research_result)

    if stub_keys:
        if verified:
            warning_items.append(
                make_item(
                    "stub_value",
                    f"未実装の戻り値があります: {stub_keys}",
                    ACTION_REPAIR,
                    reason="調査済みの取得方法がある",
                    evidence={
                        "stub_keys": stub_keys,
                        "unimplemented": unimplemented,
                    },
                    needs_research_findings=True,
                )
            )
        else:
            warning_items.append(
                make_item(
                    "stub_value",
                    f"未実装の戻り値があります: {stub_keys}",
                    ACTION_BLOCKED,
                    reason="取得方法が未確認",
                    required_information=stub_required_information(
                        proposal,
                        stub_keys,
                        unimplemented=unimplemented,
                    ),
                    evidence={
                        "stub_keys": stub_keys,
                        "unimplemented": unimplemented,
                        "unconfirmed_notes": unconfirmed_notes,
                        "dependencies": (proposal or {}).get("dependencies") or [],
                        "platform": ((proposal or {}).get("runtime") or {}).get("platform") or [],
                    },
                    needs_research_findings=True,
                )
            )

    if unimplemented and not stub_keys and isinstance(return_value, dict):
        warning_items.append(
            make_item(
                "missing_stub_marker",
                "implementation.unimplemented があるのに、"
                "戻り値に未実装の明示がありません",
                ACTION_REPAIR,
                reason="未実装の明示が不足している",
                evidence={
                    "unimplemented": unimplemented,
                    "return_keys": list(return_value.keys()),
                },
            )
        )

    if unconfirmed_notes and not stub_keys and isinstance(return_value, dict):
        warning_items.append(
            make_item(
                "unconfirmed_looks_complete",
                "設計案に未確認項目があるのに、戻り値がすべて実装済みに見えます",
                ACTION_REPAIR,
                reason="未確認項目を成功値で埋めている可能性がある",
                evidence={
                    "unconfirmed_notes": unconfirmed_notes,
                    "return_keys": list(return_value.keys()),
                },
            )
        )

    return {
        "status": "warning" if warning_items else "pass",
        "stub_keys": stub_keys,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def validate_tool_result(
    proposal,
    test_result,
    implementation=None,
    research_result=None,
    source=None,
):
    """
    実行結果が設計案で要求されたものを満たしているか確認する。
    コードは再実行しない。
    """

    proposal = proposal or {}
    test_result = test_result or {}
    implementation = implementation or {}
    research_result = research_result or {}
    source = resolve_source(proposal, implementation, source)

    research_result = attach_parsed_tables_to_research(research_result) if research_result else research_result

    checks = {
        "execution": check_execution(
            test_result,
            source=source,
            research_result=research_result,
        ),
        "return_value": check_return_value(test_result),
        "output_keys": check_output_keys(proposal, test_result),
        "output_format": check_output_format(test_result),
        "output_values": check_output_values(
            test_result,
            source=source,
            research_result=research_result,
        ),
        "subprocess_handling": check_subprocess_handling(source, test_result),
        "command": check_command(source, test_result, research_result),
        "stub_status": check_stub_status(
            proposal,
            test_result,
            implementation=implementation,
            research_result=research_result,
        ),
    }

    errors = []
    missing_outputs = checks["output_keys"].get("missing_outputs", [])
    warning_items = collect_warning_items(checks)

    for name, result in checks.items():
        errors.extend(
            f"[{name}] {message}"
            for message in result.get("errors", [])
        )

    warnings = [
        f"[{item.get('check')}] {item.get('message')}"
        for item in warning_items
    ]
    disposition = summarize_disposition(warning_items)
    result, status = finalize_validation_status(
        errors,
        disposition,
        treat_repairable_as_fail=False,
    )

    return {
        "result": result,
        "status": status,
        "checks": checks,
        "missing_outputs": missing_outputs,
        "errors": errors,
        "warnings": warnings,
        "warning_items": warning_items,
        "disposition": disposition,
        "research_ready": research_has_verified_method(research_result),
        "research_result": {
            "usable_finding_count": len(research_result.get("usable_findings") or []),
            "usable_findings": research_result.get("usable_findings") or [],
        } if research_result else {},
    }
