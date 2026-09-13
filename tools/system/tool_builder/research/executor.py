import os

import tools.system.tool_builder.research.local as local_research
import tools.system.tool_builder.research.web as web_research

SUPPORTED_SOURCES = ("local", "web")

# confidence の意味（research_result が振り分ける）:
# high   → usable_findings（実装事実）
# medium → reference_findings（参考。実装根拠にしない）
# low    → unresolved（未解決）


def make_result(item, finding, evidence, confidence, source="local"):
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "question": item.get("question"),
        "finding": finding,
        "evidence": evidence,
        "confidence": confidence,
        "source": source,
    }


def summarize_capability(inventory):
    compact = local_research.compact_inventory(inventory)
    parts = []
    if compact["available_modules"]:
        parts.append(
            "利用可能なモジュール: " + ", ".join(compact["available_modules"])
        )
    if compact["missing_modules"]:
        parts.append(
            "見つからないモジュール: " + ", ".join(compact["missing_modules"])
        )
    if compact["available_commands"]:
        parts.append(
            "利用可能なコマンド: " + ", ".join(compact["available_commands"])
        )
    if not parts:
        parts.append("ローカルで確認できた取得手段はない")

    psutil_info = local_research.find_module(inventory, "psutil")
    if psutil_info and psutil_info.get("available") and psutil_info.get("attrs"):
        parts.append(
            "psutil の確認済み属性: " + ", ".join(psutil_info["attrs"])
        )

    return "。".join(parts), compact, "high"


def investigate_local_item(item, inventory):
    kind = item.get("kind") or "unconfirmed"
    compact = local_research.compact_inventory(inventory)

    if kind in ("capability", "dependency"):
        finding, evidence, confidence = summarize_capability(inventory)
        return make_result(item, finding, evidence, confidence)

    if kind == "platform":
        finding = f"ローカル platform は {compact['platform']}"
        if compact["available_modules"]:
            finding += (
                "。この環境で import できた: "
                + ", ".join(compact["available_modules"])
            )
        return make_result(item, finding, compact, "high")

    if kind == "output":
        psutil_info = local_research.find_module(inventory, "psutil")
        if psutil_info and psutil_info.get("available"):
            finding = (
                "output の具体値は未取得。"
                "psutil が使えるので、実装時に属性から埋める候補がある"
            )
            evidence = {
                "psutil_attrs": psutil_info.get("attrs") or [],
                "psutil_samples": psutil_info.get("samples") or {},
            }
            return make_result(item, finding, evidence, "medium")
        if compact["available_commands"]:
            finding = (
                "psutil はない。"
                "使えるコマンド: "
                + ", ".join(compact["available_commands"])
                + "。"
                "具体的な取得コマンドと戻り値は未検証"
            )
            return make_result(item, finding, compact, "medium")
        finding = (
            "output の取得方法は未特定。"
            "使えるライブラリもコマンドも見つからない"
        )
        return make_result(item, finding, compact, "low")

    if kind == "unconfirmed":
        psutil_info = local_research.find_module(inventory, "psutil")
        if psutil_info and psutil_info.get("available"):
            finding = (
                "未確認項目の取得可否は psutil 属性の存在まで確認した。"
                "実際の値が取れるかは未検証"
            )
            evidence = {
                "question": item.get("question"),
                "psutil_attrs": psutil_info.get("attrs") or [],
            }
            return make_result(item, finding, evidence, "medium")
        finding = "未確認項目を裏付けるローカル手段は見つかっていない"
        return make_result(
            item,
            finding,
            {"question": item.get("question"), "inventory": compact},
            "low",
        )

    return make_result(
        item,
        "この項目のローカル調査方法は未定義",
        compact,
        "low",
    )


def investigate_web_item(
    item,
    subject,
    inventory,
    *,
    user_request=None,
    search_intent=None,
    searched_queries=None,
):
    from tools.system.tool_builder.research import query_intent as qi

    compact = local_research.compact_inventory(inventory)
    searched = list(searched_queries or [])
    request_text = qi.resolve_user_request(user_request, item=item)
    intent = search_intent
    if not isinstance(intent, dict) or not intent:
        if request_text:
            intent = qi.extract_search_intent(
                request_text,
                subject=subject,
                proposal={"subcategory": (subject or {}).get("subcategory")},
            )
        else:
            intent = qi.fallback_intent_from_text(
                str(item.get("question") or ""),
                subject=subject,
            )

    queries = web_research.build_search_queries(
        item,
        subject=subject,
        inventory=compact,
        user_request=request_text,
        search_intent=intent,
        searched_queries=searched,
        allow_legacy_fallback=True,
    )
    keywords = qi.intent_filter_keywords(intent)
    if item.get("followup") and item.get("question"):
        gap = qi.clean_missing_gap(item.get("question"))
        if gap:
            keywords.append(gap)

    collected = []
    tried = []
    errors = []
    used_queries = []
    used_query = queries[0] if queries else ""
    for query in queries or []:
        if qi.query_already_searched(query, searched):
            continue
        search = web_research.search_web(query)
        tried.extend(search.get("backends_tried") or [])
        searched.append(query)
        used_queries.append(query)
        if search.get("error"):
            errors.append(search.get("error"))
        hits = search.get("hits") or []
        if hits:
            used_query = query
            collected.extend(hits)

    discovered = qi.extract_discovered_techniques(collected, limit=5)
    pursuit = None
    for tech in discovered:
        pursuit = qi.build_pursuit_query(tech, intent, searched=searched)
        if pursuit:
            break
    if pursuit:
        search = web_research.search_web(pursuit)
        tried.extend(search.get("backends_tried") or [])
        searched.append(pursuit)
        used_queries.append(pursuit)
        queries = list(queries) + [pursuit]
        if search.get("error"):
            errors.append(search.get("error"))
        hits = search.get("hits") or []
        if hits:
            used_query = pursuit
            collected.extend(hits)
            discovered = qi.extract_discovered_techniques(collected, limit=5)

    ranked = web_research.rank_hits(collected)
    filtered = web_research.filter_relevant_hits(
        ranked,
        keywords=keywords,
        subject=subject,
    )
    hits = filtered["hits"]
    if hits:
        finding = (
            f"Web検索で {len(hits)} 件ヒット。"
            "具体的な取得方法は未検証"
        )
        confidence = "medium"
    else:
        finding = (
            "Web検索結果が得られなかった。"
            f"{' / '.join(errors)}".strip()
        )
        confidence = "low"

    # KSS-1.5: kept/dropped 観測用パーティション（filter 結果は変更しない）
    obs_hit_partition = None
    try:
        from tools.ai.state.web_hit_partition import (
            build_search_partition,
            kss15_obs_enabled,
        )

        if kss15_obs_enabled() or os.environ.get("AI_AGENT_KSS14_OBS"):
            obs_hit_partition = build_search_partition(
                ranked_hits=ranked,
                kept_hits=hits,
                dropped_irrelevant=filtered.get("dropped") or [],
                query=used_query,
                keywords=keywords,
                subject=subject,
                item_id=item.get("id"),
                max_store=40,
            )
    except Exception:
        obs_hit_partition = None

    # dropped_hits 保存件数を観測用に拡大（採否ロジックは同じ filtered）
    dropped_store_n = 5
    if str(os.environ.get("AI_AGENT_KSS15_OBS") or "").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    ) or str(os.environ.get("AI_AGENT_KSS14_OBS") or "").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    ):
        dropped_store_n = 24

    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "question": item.get("question"),
        "finding": finding,
        "evidence": {
            "query": used_query,
            "queries": used_queries or queries,
            "keywords": keywords,
            "hits": hits,
            "dropped_hits": filtered["dropped"][:dropped_store_n],
            "dropped_count": filtered["dropped_count"],
            "backends_tried": list(dict.fromkeys(tried)),
            "error": None if hits else (" / ".join(errors) or None),
            "inventory": compact,
            "obs_hit_partition": obs_hit_partition,
            "search_intent": intent,
            "searched_queries": searched,
            "discovered_techniques": discovered,
            "user_request": request_text or None,
        },
        "confidence": confidence,
        "source": "web",
        "search_query": used_query,
        "hits": hits,
    }


def research_executor(
    research_items=None,
    subject=None,
    source="local",
    environment=None,
    *,
    user_request=None,
    search_intent=None,
    searched_queries=None,
):
    """
    調査項目を実際に調べ、構造化した結果を返す。
    source=local は import / which。
    source=web は検索ヒットまで。実環境確認は research_verifier が行う。
    """

    subject = subject or {}
    research_items = research_items or []

    if source not in SUPPORTED_SOURCES:
        return {
            "result": "NG",
            "status": "fail",
            "source": source,
            "error": (
                f"source '{source}' は未対応。"
                f"現在使えるのは {list(SUPPORTED_SOURCES)}。"
            ),
            "results": [],
        }

    if not research_items:
        return {
            "result": "NG",
            "status": "fail",
            "source": source,
            "error": "research_items がありません",
            "results": [],
        }

    inventory = local_research.collect_local_inventory(subject.get("subcategory"))
    if source == "web":
        searched = list(searched_queries or [])
        intent = search_intent
        results = []
        for item in research_items:
            if not isinstance(item, dict):
                continue
            result = investigate_web_item(
                item,
                subject,
                inventory,
                user_request=user_request,
                search_intent=intent,
                searched_queries=searched,
            )
            evidence = result.get("evidence") or {}
            searched = list(evidence.get("searched_queries") or searched)
            if evidence.get("search_intent"):
                intent = evidence.get("search_intent")
            results.append(result)
        notes = [
            "source=web の検索結果である。",
            "未検証のため、research_verifier で実環境確認する。",
        ]
    else:
        results = [
            investigate_local_item(item, inventory)
            for item in research_items
            if isinstance(item, dict)
        ]
        notes = [
            "source=local の調査結果である。",
            "medium/low は Web調査の対象になる。",
        ]
        searched = list(searched_queries or [])
        intent = search_intent

    if not results:
        return {
            "result": "NG",
            "status": "fail",
            "source": source,
            "error": "調査できる項目がありません",
            "results": [],
        }

    low_count = sum(1 for item in results if item.get("confidence") == "low")
    status = "partial" if low_count else "completed"

    payload = {
        "result": "OK",
        "status": status,
        "source": source,
        "subject": subject,
        "results": results,
        "result_count": len(results),
        "notes": notes,
    }
    if source == "web":
        payload["searched_queries"] = searched
        payload["search_intent"] = intent
    return payload
