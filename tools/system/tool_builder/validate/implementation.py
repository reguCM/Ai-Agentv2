import ast

from tools.system.tool_builder.apply import REJECT_EMPTY_REPAIR_CODE, has_repair_code
from tools.system.tool_builder.validate.warning_actions import (
    ACTION_ACCEPTABLE,
    ACTION_BLOCKED,
    ACTION_REPAIR,
    collect_warning_items,
    finalize_validation_status,
    summarize_disposition,
    warning_item,
)


def module_to_path(module):
    if not module:
        return None
    return module.replace(".", "/") + ".py"


def path_to_module(path):
    if not path:
        return None
    normalized = path.replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.replace("/", ".")


def normalize_path(path):
    if not path:
        return ""
    return path.replace("\\", "/")


def check_path(proposal, implementation):
    errors = []
    warning_items = []
    expected = module_to_path(proposal.get("module"))
    actual = normalize_path(implementation.get("path"))

    if not actual:
        errors.append("path がありません")
    elif expected and actual != expected:
        errors.append(
            f"path が設計案と一致しません: {actual} != {expected}"
        )

    return {
        "status": "fail" if errors else "pass",
        "expected": expected,
        "actual": actual,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_function(proposal, implementation):
    errors = []
    warning_items = []
    expected = proposal.get("function")
    actual = implementation.get("function")

    if not actual:
        errors.append("function がありません")
    elif expected and actual != expected:
        errors.append(
            f"function が設計案と一致しません: {actual} != {expected}"
        )

    return {
        "status": "fail" if errors else "pass",
        "expected": expected,
        "actual": actual,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_code(implementation):
    errors = []
    warning_items = []
    code = implementation.get("code")

    if not has_repair_code(implementation):
        errors.append(REJECT_EMPTY_REPAIR_CODE)
        return {
            "status": "fail",
            "errors": errors,
            "warnings": [item["message"] for item in warning_items],
            "warning_items": warning_items,
        }

    try:
        ast.parse(str(code))
    except SyntaxError as exc:
        errors.append(f"code がPythonとして不正です: {exc.msg}")

    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_function_exists(implementation):
    errors = []
    warning_items = []
    code = implementation.get("code")
    function_name = implementation.get("function")

    if not code or not function_name:
        errors.append("code または function がありません")
        return {
            "status": "fail",
            "errors": errors,
            "warnings": [item["message"] for item in warning_items],
            "warning_items": warning_items,
        }

    try:
        tree = ast.parse(str(code))
    except SyntaxError:
        errors.append("code を解析できません")
        return {
            "status": "fail",
            "errors": errors,
            "warnings": [item["message"] for item in warning_items],
            "warning_items": warning_items,
        }

    defined_functions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]

    if function_name not in defined_functions:
        errors.append(
            f"コード内に関数 '{function_name}' がありません"
        )

    return {
        "status": "fail" if errors else "pass",
        "defined_functions": defined_functions,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_unimplemented(proposal, implementation, repair_mode=False):
    errors = []
    warning_items = []
    unimplemented = implementation.get("unimplemented")
    code = str(implementation.get("code") or "")

    def _node_has_unimplemented_literal(node):
        # "未実装" という文字列が、return の値（辞書/文字列など）に含まれているか。
        if node is None:
            return False
        for n in ast.walk(node):
            if (
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and "未実装" in n.value
            ):
                return True
        return False

    def _is_returncode_compare_to_zero(test):
        # `returncode == 0` / `returncode != 0` の形だけを検出する（例外フォールバック判定のため）。
        if not isinstance(test, ast.Compare):
            return None
        if len(test.ops) != 1 or len(test.comparators) != 1:
            return None
        op = test.ops[0]
        right = test.comparators[0]
        if not (
            isinstance(right, ast.Constant)
            and isinstance(right.value, (int, float))
            and float(right.value) == 0.0
        ):
            return None
        # left が *.returncode であることを確認
        left = test.left
        if not isinstance(left, ast.Attribute):
            return None
        if left.attr != "returncode":
            return None
        # Eq: 成功=body, エラー=orelse / NotEq: 成功=orelse, エラー=body
        if isinstance(op, ast.Eq):
            return "eq0"
        if isinstance(op, ast.NotEq):
            return "ne0"
        return None

    class _StubKindDetector(ast.NodeVisitor):
        def __init__(self):
            self.hard_stub = False
            self.soft_stub = False
            self._in_except = False
            self._in_error_branch = False

        def visit_ExceptHandler(self, node):
            prev = self._in_except
            self._in_except = True
            for stmt in node.body:
                self.visit(stmt)
            self._in_except = prev

        def visit_Raise(self, node):
            # `raise NotImplementedError(...)` は hard_stub と扱う
            exc = node.exc
            is_not_impl = False
            if isinstance(exc, ast.Call):
                func = exc.func
                if isinstance(func, ast.Name) and func.id == "NotImplementedError":
                    is_not_impl = True
                if isinstance(func, ast.Attribute) and func.attr == "NotImplementedError":
                    is_not_impl = True
            elif isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                is_not_impl = True
            elif isinstance(exc, ast.Attribute) and exc.attr == "NotImplementedError":
                is_not_impl = True

            if is_not_impl:
                self.hard_stub = True
            self.generic_visit(node)

        def visit_Return(self, node):
            # return の値から、hard/soft を推定する。
            val = node.value
            in_soft_context = self._in_except or self._in_error_branch

            # return None / {} は hard_stub
            if isinstance(val, ast.Constant) and val.value is None:
                self.hard_stub = True
                return
            if isinstance(val, ast.Dict) and len(val.keys) == 0 and len(val.values) == 0:
                self.hard_stub = True
                return

            if _node_has_unimplemented_literal(val):
                if in_soft_context:
                    self.soft_stub = True
                else:
                    self.hard_stub = True
                return

            self.generic_visit(node)

        def visit_If(self, node):
            comp = _is_returncode_compare_to_zero(node.test)
            if comp == "eq0":
                # returncode == 0 の場合: body=成功, orelse=エラー
                prev = self._in_error_branch
                self._in_error_branch = False
                for stmt in node.body:
                    self.visit(stmt)
                self._in_error_branch = True
                for stmt in node.orelse:
                    self.visit(stmt)
                self._in_error_branch = prev
                return
            if comp == "ne0":
                # returncode != 0 の場合: body=エラー, orelse=成功
                prev = self._in_error_branch
                self._in_error_branch = True
                for stmt in node.body:
                    self.visit(stmt)
                self._in_error_branch = False
                for stmt in node.orelse:
                    self.visit(stmt)
                self._in_error_branch = prev
                return
            self.generic_visit(node)

    # check_code() で AST パースは済んでいる想定だが、安全のため try。
    hard_stub = False
    soft_stub = False
    try:
        tree = ast.parse(code)
        detector = _StubKindDetector()
        detector.visit(tree)
        hard_stub = detector.hard_stub
        soft_stub = detector.soft_stub
    except SyntaxError:
        # 検出不能なら保守的に hard 扱い
        hard_stub = "未実装" in code

    if not isinstance(unimplemented, list):
        errors.append("unimplemented がリストではありません")
        return {
            "status": "fail",
            "errors": errors,
            "warnings": [item["message"] for item in warning_items],
            "warning_items": warning_items,
        }

    notes = proposal.get("implementation_notes") or []
    has_unconfirmed_notes = any(
        "未確認" in str(note) for note in notes
    )

    # hard_stub は従来どおり fatal NG。
    if hard_stub and not unimplemented:
        message = "hard_stub があるのに unimplemented が空です"
        if repair_mode:
            warning_items.append(
                warning_item(
                    "empty_unimplemented",
                    message,
                    ACTION_REPAIR,
                    reason=message,
                    evidence={
                        "unimplemented": unimplemented,
                        "unconfirmed_notes": [
                            str(note)
                            for note in notes
                            if "未確認" in str(note)
                        ],
                        "hard_stub": hard_stub,
                        "soft_stub": soft_stub,
                    },
                )
            )
        else:
            errors.append(message)

    # 未確認メモは「fatal NG」にはせず warning として保存する。
    # soft_stub のような例外フォールバックがある場合でも、実行・Verifierで最終判定する。
    if has_unconfirmed_notes and not unimplemented and not hard_stub:
        message = "未確認項目があるが unimplemented が空です（Verifierで確認）"
        warning_items.append(
            warning_item(
                "unconfirmed_notes_no_unimplemented",
                message,
                ACTION_ACCEPTABLE,
                reason=message,
                evidence={
                    "unimplemented": unimplemented,
                    "unconfirmed_notes": [
                        str(note) for note in notes if "未確認" in str(note)
                    ],
                    "hard_stub": hard_stub,
                    "soft_stub": soft_stub,
                },
            )
        )

    return {
        "status": "fail" if errors else ("warning" if warning_items else "pass"),
        "unimplemented": unimplemented,
        "stub_detected": {
            "hard_stub": hard_stub,
            "soft_stub": soft_stub,
        },
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def check_registry_consistency(
    proposal,
    implementation,
    registry=None,
    repair_mode=False,
):
    errors = []
    warning_items = []
    registry = registry or []

    expected_module = proposal.get("module")
    actual_module = path_to_module(implementation.get("path"))
    expected_name = proposal.get("name")
    actual_function = implementation.get("function")

    if expected_module and actual_module and expected_module != actual_module:
        errors.append(
            f"module が設計案と一致しません: {actual_module} != {expected_module}"
        )

    if expected_name and actual_function and expected_name != actual_function:
        warning_items.append(
            warning_item(
                "name_function_mismatch",
                f"Tool名と関数名が一致しません: {expected_name} != {actual_function}",
                ACTION_ACCEPTABLE,
                reason="Tool名と関数名の一致は必須ではない",
                evidence={
                    "name": expected_name,
                    "function": actual_function,
                },
            )
        )

    module_parts = (expected_module or "").split(".")
    category = proposal.get("category")
    subcategory = proposal.get("subcategory")

    if len(module_parts) >= 4 and module_parts[0] == "tools":
        if category and module_parts[1] != category:
            errors.append(
                f"module の category が設計案と一致しません: "
                f"{module_parts[1]} != {category}"
            )
        if subcategory and module_parts[2] != subcategory:
            errors.append(
                f"module の subcategory が設計案と一致しません: "
                f"{module_parts[2]} != {subcategory}"
            )

    existing_names = {
        tool.get("name")
        for tool in registry
        if isinstance(tool, dict)
    }
    if (
        expected_name
        and expected_name in existing_names
        and not repair_mode
    ):
        warning_items.append(
            warning_item(
                "duplicate_registry_name",
                f"Registry に同名Toolが既に存在します: {expected_name}",
                ACTION_BLOCKED,
                reason="同名Toolが既に存在する",
                next_step="repair_existing",
                evidence={
                    "name": expected_name,
                },
            )
        )

    return {
        "status": "fail" if errors else ("warning" if warning_items else "pass"),
        "expected_module": expected_module,
        "actual_module": actual_module,
        "errors": errors,
        "warnings": [item["message"] for item in warning_items],
        "warning_items": warning_items,
    }


def validate_tool_implementation(
    proposal,
    implementation,
    registry=None,
    repair_mode=False,
):
    """
    実装案を機械的に検査する。コードは実行しない。
    """

    proposal = proposal or {}
    implementation = implementation or {}

    checks = {
        "path": check_path(proposal, implementation),
        "function": check_function(proposal, implementation),
        "code": check_code(implementation),
        "function_exists": check_function_exists(implementation),
        "unimplemented": check_unimplemented(
            proposal,
            implementation,
            repair_mode=repair_mode,
        ),
        "registry_consistency": check_registry_consistency(
            proposal,
            implementation,
            registry=registry,
            repair_mode=repair_mode,
        ),
    }

    errors = []
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
        "errors": errors,
        "warnings": warnings,
        "warning_items": warning_items,
        "disposition": disposition,
    }
