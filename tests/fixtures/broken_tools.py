def pass_status():
    return {"status": "28"}


def repair_unparsed():
    return {
        "status": "LoadPercentage\n--------------\n            28",
    }


def research_stub():
    return {"status": "未実装"}


def repair_missing_key():
    return {"load": "28"}


def repair_not_dict():
    return "28"


def mixed_unparsed_and_stub():
    return {
        "status": "LoadPercentage\n--------------\n            28",
        "temp": "未実装",
    }


def empty_body():
    pass


def index_error_status():
    rows = ["LoadPercentage", "--------------"]
    return {"status": rows[2]}


def key_error_status():
    data = {"load": "28"}
    return {"status": data["status"]}


def type_error_status():
    return {"status": None + 1}


def semantic_name_as_status():
    return {"status": "Intel Xeon"}


def execution_error():
    raise RuntimeError("意図的な実行エラー")


def command_error_status():
    return {"status": "error"}


def header_as_status():
    return {"status": "LoadPercentage"}


def separator_as_status():
    return {"status": "--------------"}


def empty_status():
    return {"status": ""}


SOURCE_UNPARSED = """
import subprocess

def cpu_status():
    result = subprocess.run(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command',
         'Get-CimInstance -ClassName Win32_Processor | Select LoadPercentage'],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return {'status': result.stdout.strip()}
    return {'status': 'error'}
"""

SOURCE_WRONG_KEY = """
def cpu_status():
    return {'load': '28'}
"""

SOURCE_NOT_DICT = """
def cpu_status():
    return '28'
"""

SOURCE_SUBPROCESS_BAD = """
import subprocess

def cpu_status():
    result = subprocess.run(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command',
         'Get-CimInstance -ClassName Win32_Processor | Select LoadPercentage'],
        capture_output=True,
        text=True,
    )
    return {'status': result.stdout}
"""

SOURCE_STUB = """
def cpu_status():
    return {'status': '未実装'}
"""

SOURCE_EMPTY_BODY = """
def cpu_status():
    pass
"""

SOURCE_INDEX_ERROR = """
def cpu_status():
    rows = ['LoadPercentage', '--------------']
    return {'status': rows[2]}
"""

SOURCE_KEY_ERROR = """
def cpu_status():
    data = {'load': '28'}
    return {'status': data['status']}
"""

SOURCE_TYPE_ERROR = """
def cpu_status():
    return {'status': None + 1}
"""

SOURCE_SEMANTIC = """
def cpu_status():
    return {'status': 'Intel Xeon'}
"""

SOURCE_WRONG_COMMAND = """
import subprocess

def cpu_status():
    result = subprocess.run(
        ['wmic', 'cpu', 'get', 'LoadPercentage'],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return {'status': lines[-1] if lines else 'error'}
    return {'status': 'error'}
"""

VERIFIED_RESEARCH = {
    "result": "OK",
    "usable_findings": [
        {
            "kind": "output",
            "question": "output 'status' の取得方法",
            "finding": "powershell で取得できた",
            "confidence": "high",
            "source": "web",
            "evidence": {
                "command": "powershell",
                "args": [
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Get-CimInstance -ClassName Win32_Processor | Select LoadPercentage",
                ],
                "sample": ["LoadPercentage", "--------------", "38"],
            },
        }
    ],
}
