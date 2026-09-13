from tools.system.tool_builder.research.local import compact_inventory

CANDIDATE_SEARCH_RESULT_LIMIT = 3
CANDIDATE_SNIPPET_MAX_CHARS = 160
JUDGE_REASON_MAX_CHARS = 240


def _truncate_text(text, max_len):
    text = str(text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def compact_search_results_for_candidate(
    search_results, *, limit=CANDIDATE_SEARCH_RESULT_LIMIT, snippet_max=CANDIDATE_SNIPPET_MAX_CHARS
):
    """
    Web candidate 用 search_results を圧縮する。
    入力順（検索ランキング順）を維持し、上位 limit 件だけ title/snippet を残す。
    """
    compacted = []
    for hit in (search_results or [])[:limit]:
        if not isinstance(hit, dict):
            continue
        compacted.append(
            {
                "title": str(hit.get("title") or "").strip(),
                "snippet": _truncate_text(hit.get("snippet"), snippet_max),
            }
        )
    return compacted


def compact_judge_reason_for_candidate(judge_reason, *, max_len=JUDGE_REASON_MAX_CHARS):
    """Web candidate 用 judge_reason。元の Judge 結果は変更しない。"""
    return _truncate_text(judge_reason, max_len)


def compact_prior_failures_for_candidate(prior_failures, rejected_commands=None):
    """
    Web candidate 用 prior_failures。
    rejected_commands と (command, args) が一致する件は command/args を省略し narrative だけ残す。
    空文字の error 等はフィールドごと省略。入力リスト・各 dict は変更しない。
    """
    from tools.ai.tool_builder.research_result import command_key

    rejected = set()
    for item in rejected_commands or []:
        if not isinstance(item, dict):
            continue
        command, args = command_key(item)
        if command:
            rejected.add((command, args))

    compacted = []
    for item in prior_failures or []:
        if not isinstance(item, dict):
            continue
        command, args = command_key(item)
        entry = {}
        question = str(item.get("question") or "").strip()
        if question:
            entry["question"] = question
        finding = str(item.get("finding") or "").strip()
        if finding:
            entry["finding"] = finding
        error = str(item.get("error") or "").strip()
        if error:
            entry["error"] = error
        if (command, args) not in rejected:
            if command:
                entry["command"] = command
            if "args" in item or args:
                entry["args"] = list(args)
        compacted.append(entry)
    return compacted


def exploration_retry_needed(materials, candidates):
    # follow-up の失敗履歴（prior_failures / rejected_commands）があるのに
    # LLM が候補を出さなかった / 同じ拒否候補しか出さない場合、
    # exploration（別経路）を明示してもう一度呼び直す。
    if not (materials.get("prior_failures") or materials.get("rejected_commands")):
        return False
    if not candidates:
        return True
    from tools.ai.tool_builder.research_result import filter_rejected_candidates

    kept = filter_rejected_candidates(
        candidates, materials.get("rejected_commands") or []
    )
    return len(kept) == 0


def build_exploration_hints(
    *,
    empty_search,
    search_keywords=None,
    inventory=None,
    prior_failures=None,
    followup_questions=None,
    rejected_commands=None,
):
    if not empty_search:
        return []
    inventory = inventory or {}
    commands = list(inventory.get("available_commands") or [])
    keywords = [
        str(item).strip()
        for item in (search_keywords or [])
        if str(item).strip()
    ]
    hints = [
        "search_results is empty. Irrelevant hits were removed or search found nothing useful.",
        "Start a new exploration using inventory.available_commands only.",
        "Do not repeat rejected_commands or prior_failures command/args.",
        "Pick a different command or a clearly different script from the failed attempt.",
    ]
    if commands:
        hints.append(
            "Available commands for this exploration: "
            + ", ".join(commands)
            + "."
        )
    if len(commands) > 1:
        hints.append(
            "When the failed attempt used one command, try another from available_commands."
        )
    if keywords:
        hints.append(
            "Verify gaps related to: " + ", ".join(keywords) + "."
        )
    if followup_questions:
        hints.append(
            "followup_questions name what is still unconfirmed. "
            "The new candidate must address one of them."
        )
    if prior_failures:
        hints.append(
            "Read prior_failures error/finding to understand why the last attempt failed, "
            "then choose a different verification approach."
        )
    if rejected_commands:
        hints.append(
            "rejected_commands lists scripts that must not appear again in candidates."
        )
    failed_commands = set()
    for item in (prior_failures or []) + (rejected_commands or []):
        command = str(item.get("command") or "").strip().lower()
        if command:
            failed_commands.add(command)
    command_names = [str(item).strip() for item in commands if str(item).strip()]
    lowered = {item.lower(): item for item in command_names}
    untried = [lowered[key] for key in lowered if key not in failed_commands]
    if untried:
        hints.append(
            "Commands not yet tried in this round: " + ", ".join(untried) + "."
        )
    if "powershell" in failed_commands and "wmic" in lowered:
        hints.append(
            "The failed scripts used PowerShell. Restart exploration with wmic "
            "and os-related references instead of repeating PowerShell WMI scripts."
        )
    return hints


def build_route_hints(state, inventory=None):
    """STATE から、要求を満たす複数の実現経路のヒントを生成する。"""
    if not state:
        return []
    decisions = {}
    for item in getattr(state, "decisions", None) or []:
        if isinstance(item, dict):
            decisions[item.get("key", "")] = item.get("value", "")
    meaning = decisions.get("status.meaning", "")
    unit = decisions.get("status.unit", "")
    if not meaning:
        return []
    hints = [
        f"要求: {meaning}" + (f" ({unit})" if unit else ""),
        "要求を満たし得る異なる実現経路を複数考えること。例:",
    ]
    low = meaning.lower()
    if "使用率" in low or "usage" in low or "rate" in low:
        hints.append("  1. 使用率/使用パーセントを直接返すプロパティ/コマンド")
        hints.append("  2. 総容量と空き容量を取得し計算で求める")
        hints.append("  3. 総容量と使用容量を取得し計算で求める")
        hints.append("  4. OSが提供する別のメモリ/CPU統計から計算")
    elif "温度" in low or "temperature" in low:
        hints.append("  1. 温度を直接返すセンサー/プロパティ")
        hints.append("  2. WMI/CIM の温度クラスから取得")
        hints.append("  3. 外部ツール経由で取得")
    elif "電力" in low or "power" in low or "watt" in low:
        hints.append("  1. 電力(W)を直接返すセンサー/プロパティ")
        hints.append("  2. 電圧×電流から計算")
        hints.append("  3. kW等の別単位で取得し変換")
    else:
        hints.append("  1. 値を直接返すコマンド/プロパティ")
        hints.append("  2. 関連する複数の値から計算で求める")
        hints.append("  3. 別のAPI/ツール経由で取得")
    hints.append("各経路に対して異なる candidate を出すこと。同一プロパティの書き方違いは別経路としない。")
    return hints


def web_research(
    items=None,
    search_results=None,
    inventory=None,
    subject=None,
    environment=None,
    rejected_commands=None,
    followup_questions=None,
    prior_failures=None,
    judge_reason=None,
    search_keywords=None,
    exploration_hints=None,
    state=None,
):
    """
    Web検索結果から、実環境で試す検証用コマンドの材料をまとめる。
    コマンドは実行しない。ファイルは作らない。
    """

    inventory = inventory or {}
    if "available_commands" not in inventory:
        inventory = compact_inventory(inventory)

    followup_questions = [
        str(item).strip()
        for item in (followup_questions or [])
        if str(item).strip()
    ]
    search_keywords = [
        str(item).strip()
        for item in (search_keywords or [])
        if str(item).strip()
    ]
    empty_search = not (search_results or [])
    if exploration_hints is None:
        exploration_hints = build_exploration_hints(
            empty_search=empty_search,
            search_keywords=search_keywords,
            inventory=inventory,
            prior_failures=prior_failures,
            followup_questions=followup_questions,
            rejected_commands=rejected_commands,
        )
    rules = [
        "JSONだけ出力すること。",
        "inventory.available_commands にある command だけを使うこと。",
        "これは実装コードではない。実環境で実行する検証用コマンドである。",
        "危険な操作（削除、ダウンロード、ファイル書き込み）は禁止。",
        "PowerShell は -NoProfile -NonInteractive -Command を使うこと。",
        "wmic は cpu / os などの参照だけにすること。",
        "rejected_commands と同じ command と args は出さないこと。",
        "followup_questions があるとき、候補はその不足情報を埋める検証用コマンドであること。",
        "prior_failures にある command/args は rejected_commands と同様に繰り返さないこと。",
    ]
    if empty_search and (prior_failures or rejected_commands):
        rules.append(
            "search_results が空のときは available_commands から rejected/prior_failures と異なる新しい検証用コマンドを探す。"
        )
    else:
        rules.append(
            "search_results のヒットと available_commands だけから検証用コマンドを出す。ヒットにない取得方法を想像しない。"
        )
    route_hints = build_route_hints(state, inventory)
    candidate_search_results = compact_search_results_for_candidate(search_results)
    rejected_commands = rejected_commands or []
    candidate_prior_failures = compact_prior_failures_for_candidate(
        prior_failures, rejected_commands
    )

    return {
        "items": items or [],
        "search_results": candidate_search_results,
        "inventory": inventory or {},
        "subject": subject or {},
        "environment": environment or {},
        "rejected_commands": rejected_commands,
        "followup_questions": followup_questions,
        "prior_failures": candidate_prior_failures,
        "judge_reason": compact_judge_reason_for_candidate(judge_reason),
        "search_keywords": search_keywords,
        "exploration_hints": exploration_hints,
        "empty_search": empty_search,
        "route_hints": route_hints,
        "rules": rules,
    }
