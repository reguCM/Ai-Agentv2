import unittest

from tools.system.tool_builder.validate.implementation import (
    validate_tool_implementation,
)


PROPOSAL_SOFT = {
    "name": "cpu_status",
    "module": "tools.system.cpu.cpu_status",
    "function": "cpu_status",
    "category": "system",
    "subcategory": "cpu",
    "output": ["status"],
    # "未確認" を含まない＝ unconfirmed_notes は false
    "implementation_notes": ["取得方法確認済み"],
}


PROPOSAL_HARD = {
    **PROPOSAL_SOFT,
    "implementation_notes": ["取得方法確認済み"],
}

PROPOSAL_UNCONFIRMED_SOFT = {
    **PROPOSAL_SOFT,
    "implementation_notes": ["取得方法は未確認"],
}


class TestValidationStubDetection(unittest.TestCase):
    def test_soft_stub_does_not_require_unimplemented(self):
        code = """
import subprocess

def cpu_status():
    try:
        result = subprocess.run(
            ['echo', 'ok'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {'status': 1.0}
        else:
            # 例外/エラー時フォールバック（soft_stub）
            return {'status': '未実装'}
    except Exception:
        # 例外時フォールバック（soft_stub）
        return {'status': '未実装'}
"""
        result = validate_tool_implementation(
            PROPOSAL_SOFT,
            {
                "path": "tools/system/cpu/cpu_status.py",
                "function": "cpu_status",
                "code": code,
                "unimplemented": [],
                "notes": [],
            },
            registry=[],
            repair_mode=False,
        )
        self.assertEqual(result["result"], "OK")

    def test_unconfirmed_notes_soft_stub_becomes_warning(self):
        code = """
import subprocess

def cpu_status():
    try:
        result = subprocess.run(
            ['echo', 'ok'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {'status': 1.0}
        else:
            # 例外/エラー時フォールバック（soft_stub）
            return {'status': '未実装'}
    except Exception:
        # 例外時フォールバック（soft_stub）
        return {'status': '未実装'}
"""
        result = validate_tool_implementation(
            PROPOSAL_UNCONFIRMED_SOFT,
            {
                "path": "tools/system/cpu/cpu_status.py",
                "function": "cpu_status",
                "code": code,
                "unimplemented": [],
                "notes": [],
            },
            registry=[],
            repair_mode=False,
        )
        self.assertEqual(result["result"], "OK")
        self.assertEqual(result["status"], "warning")
        self.assertTrue(any("未確認項目" in w for w in result["warnings"]))

    def test_hard_stub_requires_unimplemented(self):
        code = """
def cpu_status():
    # hard_stub（return None）
    return None
"""
        result = validate_tool_implementation(
            PROPOSAL_HARD,
            {
                "path": "tools/system/cpu/cpu_status.py",
                "function": "cpu_status",
                "code": code,
                "unimplemented": [],
                "notes": [],
            },
            registry=[],
            repair_mode=False,
        )
        self.assertEqual(result["result"], "NG")
        self.assertTrue(any("hard_stub" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()

