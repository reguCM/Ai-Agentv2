import unittest

from tools.ai.tool_builder.web import (
    CANDIDATE_SEARCH_RESULT_LIMIT,
    CANDIDATE_SNIPPET_MAX_CHARS,
    compact_search_results_for_candidate,
    web_research,
)


class WebCandidateSearchResultsTests(unittest.TestCase):
    def test_compact_keeps_ranking_order_and_top_three(self):
        hits = [
            {"title": f"hit-{index}", "snippet": "x" * 200, "url": f"http://{index}", "backend": "ddg"}
            for index in range(5)
        ]
        compacted = compact_search_results_for_candidate(hits)
        self.assertEqual(len(compacted), CANDIDATE_SEARCH_RESULT_LIMIT)
        self.assertEqual([item["title"] for item in compacted], ["hit-0", "hit-1", "hit-2"])
        self.assertEqual(set(compacted[0].keys()), {"title", "snippet"})

    def test_compact_truncates_snippet_to_160(self):
        hits = [{"title": "t", "snippet": "a" * 200, "url": "http://x", "backend": "ddg"}]
        compacted = compact_search_results_for_candidate(hits)
        self.assertLessEqual(len(compacted[0]["snippet"]), CANDIDATE_SNIPPET_MAX_CHARS + 1)
        self.assertTrue(compacted[0]["snippet"].endswith("…"))

    def test_web_research_uses_compacted_search_results(self):
        hits = [
            {"title": f"hit-{index}", "snippet": "snippet", "url": "http://x", "backend": "ddg"}
            for index in range(5)
        ]
        materials = web_research(search_results=hits, inventory={"available_commands": ["powershell"]})
        self.assertEqual(len(materials["search_results"]), 3)
        self.assertEqual(materials["search_results"][0]["title"], "hit-0")
        self.assertFalse(materials["empty_search"])


if __name__ == "__main__":
    unittest.main()
