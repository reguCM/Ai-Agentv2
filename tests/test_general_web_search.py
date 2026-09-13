"""
CURSOR_VALIDATION: Agent一般Web検索（F-002経路分離）。
PROJECT_AGENT 能力実績には加算しない。
"""

from __future__ import annotations

import inspect
import unittest
from unittest import mock

from tools.system.network import general_web_search as gws
from tools.system.network import search_web as agent_sw
from tools.system.tool_builder.research import web as pipeline_web


class GeneralWebSearchUnitTests(unittest.TestCase):
    def test_backend_queries_adds_spaced_variant_for_cjk_no(self):
        variants = gws.backend_queries_for_discovery("大阪市の人口", "wikipedia-ja")
        self.assertEqual(variants[0], "大阪市の人口")
        self.assertIn("大阪市 人口", variants)
        self.assertEqual(gws.backend_queries_for_discovery("Python language", "duckduckgo"), ["Python language"])

    def test_no_particle_variant_collects_entity_page(self):
        def wiki_fn(query, limit=5):
            if query == "大阪市 人口":
                return [
                    {
                        "title": "大阪市",
                        "snippet": "",
                        "url": "https://ja.wikipedia.org/wiki/Osaka",
                        "backend": "wikipedia",
                    }
                ]
            return [
                {
                    "title": "大阪市の不祥事",
                    "snippet": "",
                    "url": "https://ja.wikipedia.org/wiki/Bad",
                    "backend": "wikipedia",
                }
            ]

        with mock.patch.object(gws, "search_duckduckgo", return_value=[]), mock.patch.object(
            gws, "search_wikipedia", side_effect=wiki_fn
        ), mock.patch.object(gws, "search_wikipedia_en", return_value=[]):
            result = gws.general_web_search("大阪市の人口", limit=3)

        self.assertIsNone(result.get("error"))
        self.assertTrue(result["hits"])
        self.assertEqual(result["hits"][0]["title"], "大阪市")

    def test_exact_title_token_boost_prefers_primary_topic(self):
        query = "sample topic alpha"
        hits = [
            {
                "title": "Unrelated Windows Lifecycle",
                "snippet": "support dates listing",
                "url": "https://example.com/lifecycle",
                "backend": "x",
            },
            {
                "title": "sample topic alpha",
                "snippet": "details on sample topic",
                "url": "https://example.com/alpha",
                "backend": "y",
            },
        ]
        ranked, scored = gws.rank_hits_for_query(hits, query, limit=2)
        self.assertEqual(ranked[0]["url"], "https://example.com/alpha")
        self.assertGreater(scored[0][0], scored[1][0])

    def test_first_token_title_anchor_beats_snippet_only_match(self):
        query = "Python programming language"
        hits = [
            {
                "title": "NumPy - NumPy is a library for the Python programming language",
                "snippet": "Python programming language arrays",
                "url": "https://duckduckgo.com/NumPy",
                "backend": "duckduckgo",
            },
            {
                "title": "Python (programming language)",
                "snippet": "Python is a language",
                "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
                "backend": "duckduckgo",
            },
        ]
        ranked, _ = gws.rank_hits_for_query(hits, query, limit=2)
        self.assertEqual(ranked[0]["title"], "Python (programming language)")

    def test_ranking_prefers_query_match(self):
        query = "sample topic alpha"
        hits = [
            {
                "title": "Unrelated Windows Lifecycle",
                "snippet": "support dates listing",
                "url": "https://example.com/lifecycle",
                "backend": "x",
            },
            {
                "title": "About sample topic alpha",
                "snippet": "details on sample topic",
                "url": "https://example.com/alpha",
                "backend": "y",
            },
        ]
        ranked, scored = gws.rank_hits_for_query(hits, query, limit=2)
        self.assertEqual(ranked[0]["url"], "https://example.com/alpha")
        self.assertGreater(scored[0][0], scored[1][0])

    def test_limit_one_still_fetches_then_returns_one(self):
        def fake_ddg(query, limit=5):
            return [
                {
                    "title": f"ddg-{i}-{query}",
                    "snippet": query,
                    "url": f"https://ddg.example/{i}",
                    "backend": "duckduckgo",
                }
                for i in range(limit)
            ]

        def fake_wiki(query, limit=5):
            return [
                {
                    "title": f"wiki-{query}",
                    "snippet": "other",
                    "url": "https://wiki.example/1",
                    "backend": "wikipedia",
                }
            ]

        with mock.patch.object(gws, "search_duckduckgo", side_effect=fake_ddg), mock.patch.object(
            gws, "search_wikipedia", side_effect=fake_wiki
        ), mock.patch.object(gws, "search_wikipedia_en", return_value=[]):
            result = gws.general_web_search("alpha beta", limit=1, fetch_limit=5)

        self.assertIsNone(result.get("error"))
        self.assertEqual(result["return_limit"], 1)
        self.assertEqual(result["fetch_limit"], 5)
        self.assertEqual(len(result["hits"]), 1)
        self.assertGreaterEqual(result["candidates_collected"], 2)
        self.assertNotIn("learn.microsoft", "".join(result["backends_tried"]))

    def test_agent_wrapper_does_not_call_pipeline_search_web(self):
        with mock.patch(
            "tools.system.network.search_web.general_web_search",
            return_value={"query": "q", "hits": [], "backends_tried": [], "error": None},
        ) as mocked, mock.patch(
            "tools.system.tool_builder.research.web.search_web"
        ) as pipeline_search:
            agent_sw.search_web("hello world", limit=3)
            mocked.assert_called_once()
            pipeline_search.assert_not_called()

    def test_default_return_limit_is_multiple(self):
        with mock.patch.object(
            gws,
            "search_duckduckgo",
            return_value=[
                {
                    "title": "t",
                    "snippet": "hello world",
                    "url": "https://e/1",
                    "backend": "duckduckgo",
                }
            ],
        ), mock.patch.object(gws, "search_wikipedia", return_value=[]), mock.patch.object(
            gws, "search_wikipedia_en", return_value=[]
        ):
            result = gws.general_web_search("hello world")
        self.assertEqual(result["return_limit"], gws.DEFAULT_RETURN_LIMIT)
        self.assertGreaterEqual(gws.DEFAULT_RETURN_LIMIT, 2)

    def test_no_topic_hardcodes_in_general_module(self):
        source = inspect.getsource(gws)
        for banned in ("首相", "高市", "岸田", "kantei", "prime minister"):
            self.assertNotIn(banned, source.lower() if banned.isascii() else source)


class PipelineSearchUnchangedTests(unittest.TestCase):
    def test_pipeline_search_web_still_lists_microsoft_first(self):
        source = inspect.getsource(pipeline_web.search_web)
        self.assertIn("learn.microsoft-en", source)
        self.assertIn("HIT_KEYWORDS", inspect.getsource(pipeline_web))
        # Agent module must not re-export pipeline search_web as implementation
        agent_src = inspect.getsource(agent_sw)
        self.assertIn("general_web_search", agent_src)
        self.assertNotIn("research.web import search_web", agent_src)


if __name__ == "__main__":
    unittest.main()
