"""
STATE をプロンプトへ出す契約。実体の保存は tools.ai.state。

STATE は確定済み。LLM は読めるが、書き換え案は proposed_decisions にだけ書く。
"""

STATE_CONTRACT = [
    {
        "id": "state_readonly",
        "ja": "STATE は確定済みの情報である。勝手に変更してはいけない。",
        "en": "STATE is confirmed information. Do not change it.",
    },
    {
        "id": "state_first",
        "ja": "MATERIALS より先に STATE の確定事項を使う。",
        "en": "Use confirmed STATE facts before interpreting MATERIALS.",
    },
]

STATE_QUERY_JSON_SHAPE = {
    "answer": "",
    "reason": "",
    "used_state_keys": [],
}

STATE_QUERY_CONTRACT = [
    {
        "id": "output_json",
        "ja": "出力は JSON オブジェクト 1 つだけ。markdown や code fence は使わない。",
        "en": "Output exactly one JSON object. No markdown, no code fences.",
    },
    {
        "id": "json_shape",
        "ja": "キーは answer, reason, used_state_keys だけ。answer は答え、reason はそう判断した理由。",
        "en": "Use only these keys: answer, reason, used_state_keys. answer is the reply. reason is why.",
    },
    {
        "id": "no_command",
        "ja": "取得コマンドは書かない。",
        "en": "Do not write fetch commands.",
    },
]
