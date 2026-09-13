"""
Project Agent 向け Web 検索 Tool。

一般質問用の general_web_search を使う。
Tool Builder 用 research.web.search_web（MS Learn + HIT_KEYWORDS）は呼ばない。
"""

from tools.system.network.general_web_search import (
    DEFAULT_RETURN_LIMIT,
    general_web_search,
)


def search_web(query, limit=None):
    """
    実際に Web へ検索しに行く。材料化はしない。

    Args:
        query: 検索クエリ（必須）
        limit: LLM へ返すヒット数（return_limit）。省略時は複数件既定。
               明示的に 1 を指定した場合はその件数を返す（内部では複数候補を集めてから絞る）。
    """
    if query is None or not str(query).strip():
        return {
            "query": "" if query is None else str(query),
            "hits": [],
            "backends_tried": [],
            "error": "query が空です",
            "fetch_limit": None,
            "return_limit": None,
        }

    if limit is None:
        return general_web_search(str(query).strip(), limit=DEFAULT_RETURN_LIMIT)

    return general_web_search(str(query).strip(), limit=limit)
