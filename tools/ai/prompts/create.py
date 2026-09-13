"""
新規Tool作成用の最小契約。repair 契約とは別。

取得コマンドの正解はここに書かない。
Validator の分岐もここに書かない。
曖昧な要求の調査解決もここに書かない。
Clarity は「ユーザーが何を作りたいか」だけを確定する。実現方法は聞かない。
"""

CLARITY_JSON_SHAPE = {
    "status": "clear",
    "reason": "",
    "question": "",
    "options": [
        {
            "id": "",
            "label": "",
            "decisions": [{"key": "", "value": ""}],
        }
    ],
}

CLARITY_CONTRACT = [
    {
        "id": "output_json",
        "ja": "出力は JSON オブジェクト 1 つだけ。markdown や code fence は使わない。",
        "en": "Output exactly one JSON object. No markdown, no code fences.",
    },
    {
        "id": "json_shape",
        "ja": "キーは status, reason, question, options だけ。",
        "en": "Use only these keys: status, reason, question, options.",
    },
    {
        "id": "status_values",
        "ja": "status は clear / needs_clarification / insufficient_information のどれか。",
        "en": "status must be one of: clear, needs_clarification, insufficient_information.",
    },
    {
        "id": "scope",
        "ja": "判断するのは、ユーザーが何を作りたいかが確定できるかだけである。",
        "en": "Judge only whether what the user wants to build is determined.",
    },
    {
        "id": "clear",
        "ja": "作りたい対象が要求文で確定しているなら clear。質問しない。",
        "en": "Use clear when the desired product is already determined by the request. Do not ask.",
    },
    {
        "id": "needs_clarification",
        "ja": "要求文から複数の異なる成果物が成立し、選ぶと仕様が変わるなら needs_clarification。ユーザーが決める対象だけを聞く。",
        "en": "Use needs_clarification when several different products follow from the request and choosing would change the spec. Ask only about the product the user must choose.",
    },
    {
        "id": "insufficient_information",
        "ja": "何を作るか分からないなら insufficient_information。何を取得・操作するToolか聞く。options は空でもよい。",
        "en": "Use insufficient_information when it is unknown what to build. Ask what to get or operate. options may be empty.",
    },
    {
        "id": "user_decides",
        "ja": "質問してよいのはユーザーが決める成果物だけである。実現方法は聞かない。",
        "en": "Ask only about the product the user must choose. Do not ask how to implement it.",
    },
    {
        "id": "no_research",
        "ja": "調査しない。実現方法は Research の工程に渡す。一般的だからという理由で成果物を選ばない。",
        "en": "Do not research. Hand how-to-implement to the Research stage. Do not pick a product because it is common.",
    },
    {
        "id": "no_default",
        "ja": "複数の成果物があるとき、一つを既定値として採用して clear にしない。",
        "en": "When several products exist, do not adopt one as the default and mark it clear.",
    },
    {
        "id": "no_invention",
        "ja": "取得コマンドを想像して書かない。実装コードも書かない。",
        "en": "Do not invent fetch commands. Do not write implementation code.",
    },
    {
        "id": "options",
        "ja": "options[].decisions の key は request.subject / request.action / request.metric / request.target だけ。value はユーザーが選ぶ内容。",
        "en": "options[].decisions keys may only be request.subject, request.action, request.metric, or request.target. value is what the user would choose.",
    },
]

PROPOSAL_JSON_SHAPE = {
    "proposals": [
        {
            "name": "get_<SUBJECT>_status",
            "category": "system",
            "subcategory": "<SUBJECT>",
            "description": "<WHAT THIS TOOL DOES>",
            "keywords": [],
            "risk": "low",
            "module": "tools.<CATEGORY>.<SUBCATEGORY>.<FILENAME>",
            "function": "get_<SUBJECT>_status",
            "input": {},
            "output": ["status"],
            "dependencies": ["未確認"],
            "runtime": {
                "language": "python",
                "version": "",
                "platform": [],
            },
            "priority": "required",
            "based_on": [],
            "implementation_notes": ["取得方法は未確認"],
        }
    ]
}

PROPOSAL_PLACEHOLDERS = (
    "subcategory",
    "filename",
    "<SUBJECT>",
    "<CATEGORY>",
    "<SUBCATEGORY>",
    "<FILENAME>",
    "<WHAT THIS TOOL DOES>",
    "tools.system.subcategory.filename",
    "tools.<CATEGORY>.<SUBCATEGORY>.<FILENAME>",
    "get_<SUBJECT>_status",
)

PROPOSAL_CONTRACT = [
    {
        "id": "output_json",
        "ja": "出力は JSON オブジェクト 1 つだけ。markdown や code fence は使わない。",
        "en": "Output exactly one JSON object. No markdown, no code fences.",
    },
    {
        "id": "json_shape",
        "ja": "キーは proposals だけ。proposals は設計案のリスト。",
        "en": "Use only the proposals key. proposals is a list of tool specs.",
    },
    {
        "id": "target",
        "ja": "target_request の対象を変えない。別の既存Toolを再提案しない。",
        "en": "Do not change the target_request. Do not re-propose an unrelated existing tool.",
    },
    {
        "id": "facts",
        "ja": "MATERIALS にある事実だけを使う。取得コマンドを想像して書かない。",
        "en": "Use only facts in MATERIALS. Do not invent fetch commands.",
    },
    {
        "id": "structure",
        "ja": "module は tools.<category>.<subcategory>.<filename>。runtime は verified_environment を使う。",
        "en": "module must be tools.<category>.<subcategory>.<filename>. Use verified_environment for runtime.",
    },
    {
        "id": "unknown",
        "ja": "取得方法が未確認なら implementation_notes と dependencies に『未確認』と書く。output は status だけにする。",
        "en": "If the fetch method is unconfirmed, write 未確認 in notes and dependencies. Use only status as output.",
    },
    {
        "id": "no_files",
        "ja": "ファイル作成や Registry 変更はしない。",
        "en": "Do not create files or change the registry.",
    },
    {
        "id": "no_placeholder",
        "ja": "JSON shape の <SUBJECT>, <CATEGORY>, <SUBCATEGORY>, <FILENAME>, subcategory, filename はプレースホルダーである。そのまま出力しない。要求に合わせた具体値に置き換えること。例: メモリ使用率なら name=get_memory_status, module=tools.system.memory.memory_status, function=get_memory_status。",
        "en": "Shape fields like <SUBJECT>, <CATEGORY>, <SUBCATEGORY>, <FILENAME>, subcategory, filename are placeholders. Never output them as-is. Replace with concrete values derived from the request. Example: for memory usage, name=get_memory_status, module=tools.system.memory.memory_status, function=get_memory_status.",
    },
    {
        "id": "concrete_names",
        "ja": "name, module, function は Registry に登録できる具体値にすること。name は空にしない。function は空にしない。module は tools.<category>.<subcategory>.<name> の形式で、各部分を要求に合わせた単語にする。",
        "en": "name, module, and function must be concrete values suitable for registry. name must not be empty. function must not be empty. module must follow tools.<category>.<subcategory>.<name> with each part derived from the request.",
    },
]

WEB_CANDIDATE_JSON_SHAPE = {
    "candidates": [
        {
            "route": "",
            "command": "",
            "args": [],
            "question": "",
            "output_key": "status",
            "observation": {
                "problem_confidence": None,
                "solution_confidence": None,
                "source_confidence": None,
                "action_confidence": None,
                "expected_information_gain": None,
                "preferred_source": "",
            },
        }
    ],
    "observation": {
        "problem_confidence": None,
        "solution_confidence": None,
        "source_confidence": None,
        "action_confidence": None,
        "expected_information_gain": None,
        "preferred_source": "",
    },
}

WEB_CANDIDATE_CONTRACT = [
    {
        "id": "output_json",
        "ja": "出力は JSON オブジェクト 1 つだけ。markdown や code fence は使わない。",
        "en": "Output exactly one JSON object. No markdown, no code fences.",
    },
    {
        "id": "json_shape",
        "ja": "必須キーは candidates。任意で observation（自己評価の記録用）を付けてよい。observation は行動選択を変える指示ではない。",
        "en": "Required key is candidates. Optional observation records self-evaluation only and must not change which actions you propose.",
    },
    {
        "id": "observation_recording_only",
        "ja": "observation の confidence（0.0-1.0）と preferred_source は監査用の自己評価である。値によって候補を増やしたり減らしたりしない。preferred_source は history / state / local_llm / external_research / higher_llm / human_help / unknown のいずれか。",
        "en": "observation confidences (0.0-1.0) and preferred_source are self-evaluation for audit only. Do not add or drop candidates because of these values. preferred_source must be one of history, state, local_llm, external_research, higher_llm, human_help, unknown.",
    },
    {
        "id": "from_hits",
        "ja": "search_results があるときは、ヒットと available_commands だけから検証用コマンドを出す。ヒットにない取得方法を想像しない。",
        "en": "When search_results is non-empty, propose verify commands only from search_results hits and available_commands.",
    },
    {
        "id": "empty_search_restart",
        "ja": "search_results が空で prior_failures または rejected_commands があるとき、available_commands から rejected/prior_failures と異なる新しい検証用コマンドを探す。exploration_hints と search_keywords を使う。失敗した command/script をそのまま繰り返さない。",
        "en": "When search_results is empty and prior_failures or rejected_commands exist, start new exploration from available_commands. Use exploration_hints and search_keywords. Do not repeat the failed command/script.",
    },
    {
        "id": "exploration_hints",
        "ja": "MATERIALS の exploration_hints があるとき、空ヒット後の新探索指示として使う。",
        "en": "When MATERIALS includes exploration_hints, use them as restart guidance after empty search results.",
    },
    {
        "id": "safe",
        "ja": "inventory.available_commands にある command だけ。PowerShell は -NoProfile -NonInteractive -Command。危険な操作は禁止。",
        "en": "Use only inventory.available_commands. PowerShell must use -NoProfile -NonInteractive -Command. No dangerous operations.",
    },
    {
        "id": "not_code",
        "ja": "これは実装コードではない。実環境で試す検証用コマンドである。",
        "en": "This is not implementation code. It is a command to verify in the real environment.",
    },
    {
        "id": "skip_rejected",
        "ja": "rejected_commands と同じ command と args は出さない。",
        "en": "Do not repeat command and args already listed in rejected_commands.",
    },
    {
        "id": "followup_questions",
        "ja": "followup_questions があるとき、各 candidate はその不足情報を埋める検証用コマンドであること。candidate.question には対応する followup を書く。",
        "en": "When followup_questions is present, each candidate must verify one of those gaps. Set candidate.question to the matching followup.",
    },
    {
        "id": "prior_failures",
        "ja": "prior_failures にある command/args は rejected_commands と同様に繰り返さない。error/finding を読んで別の取得方法を探す。",
        "en": "Do not repeat command/args listed in prior_failures, same as rejected_commands. Read error/finding and look for a different fetch method.",
    },
    {
        "id": "multi_route",
        "ja": "要求を満たし得る異なる実現経路を複数考え、各経路に1つ以上の candidate を出す。route に経路の説明を書く（例: '使用率を直接取得', '総容量と空き容量から計算'）。candidates は最大5つ。",
        "en": "Consider multiple different routes that could satisfy the request. Produce at least one candidate per route. Set route to a short description of the approach. Maximum 5 candidates total.",
    },
    {
        "id": "route_diversity",
        "ja": "同じプロパティ/APIの書き方違いは別経路としない。取得する情報の種類が異なるものを別経路とする。例: Get-WmiObject と Get-CimInstance で同じプロパティを取るのは同一経路。空き容量から計算する方法と使用率を直接読む方法は別経路。",
        "en": "Syntax variations for the same property/API are not different routes. Different routes must fetch different kinds of information. Example: Get-WmiObject vs Get-CimInstance for the same property is the same route. Computing from free capacity vs reading a usage percentage directly are different routes.",
    },
]

RESEARCH_JUDGE_JSON_SHAPE = {
    "satisfies_request": False,
    "reason": "",
    "missing": [],
    "proposed_decisions": [
        {"key": "", "value": ""},
    ],
}

RESEARCH_JUDGE_CONTRACT = [
    {
        "id": "output_json",
        "ja": "出力は JSON オブジェクト 1 つだけ。markdown や code fence は使わない。",
        "en": "Output exactly one JSON object. No markdown, no code fences.",
    },
    {
        "id": "json_shape",
        "ja": "キーは satisfies_request, reason, missing, proposed_decisions だけ。",
        "en": "Use only these keys: satisfies_request, reason, missing, proposed_decisions.",
    },
    {
        "id": "compare",
        "ja": "要求を満たしているかは、キー名ではなく usable_findings の sample の意味で判断する。output は戻り値のキー名であり、値の種類ではない。",
        "en": "Judge whether the request is met by the meaning of usable_findings sample, not by the key name. output is only the return key name, not the kind of value.",
    },
    {
        "id": "success_not_enough",
        "ja": "コマンドが実行できただけでは足りない。要求した量と sample の意味が違うなら satisfies_request は false。",
        "en": "A successful command is not enough. If the sample does not measure what the request asked, satisfies_request is false.",
    },
    {
        "id": "generic_key",
        "ja": "キー名が status / value / result など一般的なことだけを理由に、finding を不十分としない。sample に要求した情報の具体値があるなら、その値が要求を満たすかを評価する。",
        "en": "Do not reject a finding only because the key is a generic name such as status, value, or result. If sample contains a concrete value of the requested information, judge whether that value satisfies the request.",
    },
    {
        "id": "question_is_gap_label",
        "ja": "finding.question は Research の不足ラベルであり、sample の種類を決めない。question の語句と sample の語句が一致しなくても、sample の意味と STATE を優先して判断する。",
        "en": "finding.question is the research gap label, not the kind of value in sample. Even when question wording differs from sample, judge by the meaning of sample and STATE.",
    },
    {
        "id": "sample_usage_percent",
        "ja": "STATE の status.meaning が使用率系、status.unit が %、status.range が 0-100 のとき、usable_findings の sample が 0〜100 の数値（または末尾 % の数値）なら、比率×100 の計算結果はメモリ使用率として satisfies_request を true にできる。",
        "en": "When STATE says status.meaning is a usage rate, status.unit is %, and status.range is 0-100, a sample numeric value from 0 to 100 (or ending with %) from a ratio-times-100 calculation may set satisfies_request true as memory usage rate.",
    },
    {
        "id": "state_for_meaning",
        "ja": "sample の意味は STATE の status.meaning / status.unit / status.range を参照する。STATE と矛盾しない sample を、finding.question の語句だけで reject しない。",
        "en": "Use STATE status.meaning, status.unit, and status.range when judging sample meaning. Do not reject a sample that matches STATE just because finding.question wording differs.",
    },
    {
        "id": "read_sample_first",
        "ja": "satisfies_request を false にする前に usable_findings の sample を読む。sample が空でないのに『数値がない』と書かない。",
        "en": "Read usable_findings sample before setting satisfies_request false. Do not claim there is no numeric sample when sample is non-empty.",
    },
    {
        "id": "judging_hints",
        "ja": "MATERIALS の judging_hints があれば sample 評価に使う。hint が採用可能と示すとき、追加のユーザー確認を求めない。",
        "en": "When MATERIALS includes judging_hints, use them when evaluating sample. When a hint says the sample may be accepted, do not ask for extra user confirmation.",
    },
    {
        "id": "confirmed_state_accept",
        "ja": "STATE decisions は confirmed 情報。status.meaning が使用率系、status.unit が %、sample が 0-100 の数値なら、satisfies_request=true にできる。",
        "en": "STATE decisions are confirmed. When status.meaning is a usage rate, status.unit is %, and sample is a numeric value from 0 to 100, you may set satisfies_request true.",
    },
    {
        "id": "sample_is_command_output",
        "ja": "sample はコマンド stdout からの値。単一の 0-100 数値なら、別途使用率への変換を求めない。",
        "en": "sample comes from command stdout. When it is a single numeric value from 0 to 100, do not ask for another conversion to usage rate.",
    },
    {
        "id": "missing_not_question",
        "ja": "finding.question の文言を missing にそのまま書き戻さない。",
        "en": "Do not copy finding.question verbatim into missing.",
    },
    {
        "id": "verify_failure_missing",
        "ja": "usable_findings が空で unresolved に sample 空または実行エラーがあるときだけ適用。missing は計測対象（総物理メモリ、使用中メモリ等）の未確認を書く。『正しい方法』『コマンドやスクリプトを調査/調べる』は禁止。",
        "en": "Apply only when usable_findings is empty and unresolved has empty sample or execution error. missing must name unconfirmed measurement targets such as total physical memory or used memory. Do not use 'correct method' or 'investigate commands/scripts'.",
    },
    {
        "id": "accept_over_verify_failure",
        "ja": "usable_findings に sample があるときは verify_failure_missing より sample_usage_percent / judging_hints の採用判断を優先する。",
        "en": "When usable_findings has sample, prefer sample_usage_percent and judging_hints acceptance over verify_failure_missing.",
    },
    {
        "id": "missing",
        "ja": "false のとき missing に、次に調べる質問を書く。コマンドは書かない。",
        "en": "When false, put follow-up research questions in missing. Do not write commands.",
    },
    {
        "id": "missing_not_echo",
        "ja": "false のとき、finding・error・stderr の文言をそのまま missing にコピーしない。missing は次の Research が調べる質問である。",
        "en": "When false, do not copy finding, error, or stderr text verbatim into missing. missing must be follow-up research questions.",
    },
    {
        "id": "verify_failure_reason",
        "ja": "unresolved で sample が空、または実行エラーがあるとき、reason には『なぜ今の候補では要求を満たせないか』を書く。エラー文のコピーだけにしない。",
        "en": "When unresolved has empty sample or execution error, reason must explain why the current candidate does not satisfy the request. Do not copy the error text alone.",
    },
    {
        "id": "missing_gap",
        "ja": "missing には、要求を満たすためにまだ確認・取得する必要がある『情報・計測対象』を具体的に記述すること。『正しい方法を確認する』『取得方法を調査する』など、方法だけを示す表現は禁止。コマンド、API、ライブラリなどの実装手段は記述しない。例: ❌『正しい計算方法を確認する』 ❌『メモリ使用率の取得方法を調査する』 ⭕『総物理メモリを取得する方法が未確認』 ⭕『使用中メモリを取得する方法が未確認』",
        "en": "In missing, name the specific information or measurement still needed to satisfy the request. Do not use method-only phrases such as 'confirm the correct method' or 'investigate how to obtain'. Do not write commands, APIs, or libraries. Good: 'total physical memory is still unconfirmed', 'used memory is still unconfirmed'. Bad: 'investigate how to obtain memory usage'.",
    },
    {
        "id": "proposed_decisions",
        "ja": "要求を満たす sample から、戻り値の意味・単位・範囲だけを proposed_decisions に書く。取得コマンドは書かない。STATE の既存 decisions は上書きしない。",
        "en": "When the sample satisfies the request, put only meaning, unit, and range of the return value in proposed_decisions. Do not write fetch commands. Do not overwrite existing STATE decisions.",
    },
    {
        "id": "no_invention",
        "ja": "取得コマンドを想像して書かない。実装コードも書かない。",
        "en": "Do not invent fetch commands. Do not write implementation code.",
    },
]

IMPLEMENT_JSON_SHAPE = {
    "path": "",
    "function": "",
    "code": "",
    "unimplemented": [],
    "notes": [],
}

IMPLEMENT_CONTRACT = [
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
        "id": "identity",
        "ja": "path は target_path、function は target_function を使う。proposal の name / module / output を変えない。",
        "en": "Use target_path and target_function. Do not change the proposal name, module, or output keys.",
    },
    {
        "id": "research_gate",
        "ja": "usable_findings の evidence.command と sample があるときだけ、その取得方法を実装する。insufficient_findings は要求を満たさないので使わない。",
        "en": "Implement a fetch method only when usable_findings has evidence.command and sample. Do not use insufficient_findings.",
    },
    {
        "id": "no_invention",
        "ja": "検証済み材料にない環境・取得方法を想像しない。成功に見える値を埋めない。",
        "en": "Do not invent environment or fetch methods. Do not fill fake success values.",
    },
    {
        "id": "unimplemented",
        "ja": "未確認・unresolved は return {'status': '未実装'} にする。",
        "en": "Keep unconfirmed or unresolved items as return {'status': '未実装'}.",
    },
    {
        "id": "structure",
        "ja": "既存Toolの配置と dict 戻り値の形に合わせる。参考ソースのコマンドをそのままコピーしない。",
        "en": "Match existing tool layout and dict return shape. Do not copy commands from reference source.",
    },
    {
        "id": "no_write",
        "ja": "ファイル書き込みはまだしない。code にソース全体を入れる。",
        "en": "Do not write files yet. Put the full source in code.",
    },
]
