import importlib
import json
import traceback

from tools.ai.state.generated_code_safety import assess_generated_code_safety
from tools.ai.state.safety_assessment import SAFE


def find_tool_in_registry(tools, tool_name):
    for tool in tools:
        if tool.get("name") == tool_name:
            return tool
    return None


def assess_registry_tool_code(tool, *, source_path=None):
    """
    Registry tool のソースを読み、生成コード Safety を評価する。
    """
    code = None
    module_path = (tool or {}).get("module") or ""
    if source_path:
        try:
            code = open(source_path, "r", encoding="utf-8").read()
        except OSError as exc:
            return {
                "ok": False,
                "safety": assess_generated_code_safety(""),
                "error": f"read_failed:{exc}",
            }
    elif module_path:
        # tools.system.x.y → tools/system/x/y.py
        rel = module_path.replace(".", "/") + ".py"
        try:
            code = open(rel, "r", encoding="utf-8").read()
        except OSError:
            # パッケージ相対
            try:
                import importlib.util

                spec = importlib.util.find_spec(module_path)
                if spec and spec.origin:
                    code = open(spec.origin, "r", encoding="utf-8").read()
            except Exception as exc:
                return {
                    "ok": False,
                    "safety": assess_generated_code_safety(""),
                    "error": f"locate_failed:{exc}",
                }
    safety = assess_generated_code_safety(code or "")
    return {
        "ok": safety.get("machine_assessed") == SAFE or safety.get("status") == SAFE,
        "safety": safety,
        "error": None
        if (safety.get("machine_assessed") == SAFE or safety.get("status") == SAFE)
        else "generated_code_not_safe_for_auto_test",
    }


def test_tool(
    tool_name,
    registry_path="registry/tools.json",
    *,
    skip_safety_gate=False,
    code_text=None,
):
    """
    Registryに登録されたToolを引数なしで1回実行し、結果を返す。
    Phase B: 実行前に生成コードの軽量 AST Safety を評価する。
    """

    if not tool_name:
        return {
            "status": "fail",
            "result": "NG",
            "tool_name": tool_name,
            "error_type": "ValueError",
            "error": "tool_name がありません",
        }

    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    tools = registry_data.get("tools", [])
    tool = find_tool_in_registry(tools, tool_name)

    if tool is None:
        return {
            "status": "fail",
            "result": "NG",
            "tool_name": tool_name,
            "error_type": "LookupError",
            "error": f"Registry に Tool が見つかりません: {tool_name}",
        }

    module_path = tool.get("module")
    function_name = tool.get("function")

    if not module_path or not function_name:
        return {
            "status": "fail",
            "result": "NG",
            "tool_name": tool_name,
            "error_type": "ValueError",
            "error": "module または function が Registry にありません",
        }

    if not skip_safety_gate:
        if code_text is not None:
            safety = assess_generated_code_safety(code_text)
            code_ok = safety.get("status") == SAFE
            code_assessment = {"ok": code_ok, "safety": safety}
        else:
            code_assessment = assess_registry_tool_code(tool)
            safety = code_assessment.get("safety") or {}
            code_ok = bool(code_assessment.get("ok"))
        if not code_ok:
            return {
                "status": "fail",
                "result": "NG",
                "tool_name": tool_name,
                "module": module_path,
                "function": function_name,
                "error_type": "SafetyGateBlocked",
                "error": code_assessment.get("error")
                or "generated_code_not_safe_for_auto_test",
                "phase_b_code_safety": safety,
                "blocked_by_safety_gate": True,
            }

    try:
        module = importlib.import_module(module_path)
        importlib.reload(module)
        function = getattr(module, function_name)
        return_value = function()

        return {
            "status": "pass",
            "result": "OK",
            "tool_name": tool_name,
            "module": module_path,
            "function": function_name,
            "return_value": return_value,
            "blocked_by_safety_gate": False,
        }

    except Exception as exc:
        return {
            "status": "fail",
            "result": "NG",
            "tool_name": tool_name,
            "module": module_path,
            "function": function_name,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "blocked_by_safety_gate": False,
        }
