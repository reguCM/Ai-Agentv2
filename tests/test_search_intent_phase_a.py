"""Phase A: SearchIntent / 探索クエリ生成の単体テスト。"""

import unittest

from tools.system.tool_builder.research.query_intent import (
    UNSPECIFIED,
    build_exploration_queries,
    build_followup_queries,
    dedupe_queries,
    extract_discovered_techniques,
    extract_search_intent,
    fallback_intent_from_text,
    normalize_query,
)
from tools.system.tool_builder.research.web import build_search_queries


DISK_REQUEST = "Windowsのディスク使用率を取得するToolを作ってください。"


class SearchIntentPhaseATests(unittest.TestCase):
    def test_disk_intent_does_not_guess_powershell(self):
        intent = extract_search_intent(
            DISK_REQUEST, prefer_llm=False, subject={"subcategory": "disk"}
        )
        self.assertEqual(intent["platform"], "Windows")
        self.assertEqual(intent["target"], "disk")
        self.assertEqual(intent["metric"], "usage")
        self.assertEqual(intent["unit"], "%")
        self.assertEqual(intent["implementation_context"], UNSPECIFIED)
        self.assertEqual(intent["purpose"], "tool_output")

    def test_disk_exploration_queries_are_meaningful(self):
        intent = fallback_intent_from_text(DISK_REQUEST, subject={"subcategory": "disk"})
        queries = build_exploration_queries(intent, max_queries=3)
        self.assertTrue(queries)
        self.assertLessEqual(len(queries), 3)
        joined = "\n".join(queries).lower()
        self.assertIn("disk", joined)
        self.assertIn("windows", joined)
        self.assertTrue("usage" in joined or "utilization" in joined)
        for query in queries:
            self.assertNotEqual(normalize_query(query), "disk")
            self.assertNotIn("get-volume", query.lower())
            self.assertNotIn("disk disk", normalize_query(query))

    def test_build_search_queries_disk_via_user_request(self):
        queries = build_search_queries(
            {"kind": "output", "question": "output 'status' の取得方法"},
            subject={"subcategory": "disk"},
            inventory={"available_commands": []},
            user_request=DISK_REQUEST,
            allow_legacy_fallback=False,
        )
        self.assertTrue(queries)
        joined = "\n".join(queries).lower()
        self.assertNotEqual(joined.strip(), "disk")
        self.assertNotIn("get-volume", joined)
        self.assertNotIn("disk disk", joined)

    def test_followup_avoids_disk_disk(self):
        intent = fallback_intent_from_text(DISK_REQUEST, subject={"subcategory": "disk"})
        queries = build_followup_queries(
            intent,
            ["output 'status' の取得方法"],
            searched=[],
            max_queries=2,
        )
        joined = "\n".join(queries).lower()
        self.assertNotIn("disk disk", joined)
        self.assertTrue(any("disk" in q.lower() for q in queries))

    def test_dedupe_and_normalize(self):
        searched = ["Windows disk usage percentage"]
        again = dedupe_queries(
            ["windows   disk  usage  percentage", "Windows disk utilization command"],
            searched=searched,
            limit=3,
        )
        self.assertEqual(len(again), 1)
        self.assertIn("utilization", again[0].lower())

    def test_cpu_gpu_memory_reflect_request(self):
        cases = [
            (
                "WindowsのCPU温度を取得するToolを作ってください。",
                "cpu",
                "temperature",
            ),
            ("GPUの使用率を取得するToolを作ってください。", "gpu", "usage"),
            (
                "GPU VRAMの使用量をMB単位で取得するToolを作ってください。",
                "gpu",
                "vram_usage",
            ),
            (
                "Windowsのメモリ使用率を取得するToolを作ってください。",
                "memory",
                "usage",
            ),
        ]
        for request, target, metric in cases:
            intent = extract_search_intent(request, prefer_llm=False)
            self.assertEqual(intent["target"], target, request)
            self.assertEqual(intent["metric"], metric, request)
            self.assertEqual(intent["implementation_context"], UNSPECIFIED, request)
            queries = build_exploration_queries(intent)
            self.assertTrue(queries, request)
            # 旧 SEARCH_HINTS の決め打ち断片に依存しない（主経路）
            joined = "\n".join(queries)
            self.assertFalse(joined.strip() in {"cpu", "gpu", "memory", "disk"})

    def test_discovered_techniques_from_hits(self):
        hits = [
            {
                "title": "Get-Counter",
                "snippet": "Use Get-Counter to read Performance Counter values",
                "url": "https://example.com",
            }
        ]
        found = extract_discovered_techniques(hits)
        self.assertTrue(any("Get-Counter" in x for x in found))


if __name__ == "__main__":
    unittest.main()
