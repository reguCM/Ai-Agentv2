import time
import unittest

from tools.system.timing import Timing, empty_timing, record_llm, stage


class TimingTests(unittest.TestCase):
    def test_stage_adds_wall_clock(self):
        with Timing() as clock:
            with stage("implementation"):
                time.sleep(0.12)
            with stage("validation"):
                time.sleep(0.12)
            snap = clock.snapshot()
        self.assertGreaterEqual(snap["implementation_seconds"], 0.1)
        self.assertGreaterEqual(snap["validation_seconds"], 0.1)
        self.assertEqual(snap["repair_seconds"], 0.0)
        self.assertGreaterEqual(snap["total_seconds"], 0.2)

    def test_llm_and_machine_split(self):
        with Timing() as clock:
            started = time.perf_counter()
            time.sleep(0.12)
            record_llm(time.perf_counter() - started)
            snap = clock.snapshot()
        self.assertGreaterEqual(snap["llm_seconds"], 0.1)
        self.assertEqual(snap["llm_calls"], 1)
        self.assertGreaterEqual(snap["machine_seconds"], 0.0)
        self.assertGreaterEqual(snap["total_seconds"], snap["llm_seconds"])
        self.assertAlmostEqual(
            snap["machine_seconds"] + snap["llm_seconds"],
            snap["total_seconds"],
            delta=0.1,
        )

    def test_stage_without_timing_is_noop(self):
        with stage("research"):
            time.sleep(0.01)
        empty = empty_timing()
        self.assertEqual(empty["total_seconds"], 0.0)
        self.assertEqual(empty["research_seconds"], 0.0)

    def test_record_llm_without_timing_is_noop(self):
        record_llm(9.9)
