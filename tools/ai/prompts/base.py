"""
自己修復の最小固定契約。空の契約は使わない。

モデル固有の言い回し・短縮は tools.ai.llm.adapter が担当する。
PROFILE はここの項目を翻訳・圧縮するだけで、項目自体は消さない。
種類ごとの直し方（unparsed_output など）は MATERIALS の warning.fix に載せる。
"""

REPAIR_JSON_KEYS = ["path", "function", "code", "unimplemented", "notes"]

REPAIR_JSON_SHAPE = {
    "path": "",
    "function": "",
    "code": "",
    "unimplemented": [],
    "notes": [],
}

# 最小固定契約。id は欠落検知用。ja が正本、en は同一内容の翻訳。
REPAIR_CONTRACT = [
    {
        "id": "output_json",
        "ja": "出力は JSON オブジェクト 1 つだけ。markdown や code fence は使わない。",
        "en": "Output exactly one JSON object. No markdown, no code fences.",
    },
    {
        "id": "json_shape",
        "ja": "キーは path, function, code, unimplemented, notes だけ。",
        "en": "Use only these keys: path, function, code, unimplemented, notes.",
    },
    {
        "id": "code_required",
        "ja": "code が空なら適用しない。code には修正後のソース全体を入れる。",
        "en": "Empty code is rejected. code must be the full repaired source.",
    },
    {
        "id": "existing_file",
        "ja": "既存ファイルだけを直す。新規ファイルは作らない。ファイル書き込みはまだしない。",
        "en": "Repair the existing file only. Do not create files. Do not write files yet.",
    },
    {
        "id": "identity",
        "ja": "path は target_path、function は target_function を使う。対象の name / module / output を変えない。",
        "en": "Use target_path and target_function. Do not change the tool identity or output keys.",
    },
    {
        "id": "scope",
        "ja": "current_source を起点に、repairable_warnings と errors だけを直す。register_tool は使わない。",
        "en": "Start from current_source. Fix only repairable_warnings and errors. Do not call register_tool.",
    },
    {
        "id": "output_keys",
        "ja": "target_output にないキーを return しない。",
        "en": "Do not return keys that are not in target_output.",
    },
    {
        "id": "no_invention",
        "ja": "検証済み材料にない環境・取得方法を想像しない。成功に見える値を埋めない。",
        "en": "Do not invent environment or fetch methods. Do not fill fake success values.",
    },
    {
        "id": "research_gate",
        "ja": "usable_findings の evidence.command と sample があるときだけ、その取得方法を実装する。",
        "en": "Implement a fetch method only when usable_findings has evidence.command and sample.",
    },
    {
        "id": "unimplemented",
        "ja": "未確認・unresolved は '未実装' のままにする。",
        "en": "Keep unconfirmed or unresolved items as '未実装'.",
    },
]

CONTRACT_IDS = [item["id"] for item in REPAIR_CONTRACT]

# ベースが選ぶ MATERIALS。PROFILE はこれらを drop_keys で消してはいけない。
REQUIRED_MATERIAL_KEYS = [
    "tool_name",
    "current_source",
    "target_path",
    "target_function",
    "target_output",
    "repairable_warnings",
    "test_result",
]

OPTIONAL_MATERIAL_KEYS = [
    "blocked_warnings",
    "research_result",
]

NEVER_DROP_MATERIAL_KEYS = frozenset(
    REQUIRED_MATERIAL_KEYS + OPTIONAL_MATERIAL_KEYS
)

WARNING_MATERIAL_FIELDS = [
    "code",
    "message",
    "fix",
    "needs_research_findings",
    "evidence",
]

TEST_RESULT_MATERIAL_FIELDS = [
    "result",
    "status",
    "return_value",
    "error",
    "error_type",
    "traceback",
]
