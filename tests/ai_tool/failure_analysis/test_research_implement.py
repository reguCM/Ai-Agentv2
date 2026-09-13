import json
import tempfile
import unittest
from pathlib import Path

from ai_tool.failure_analysis import (
    FailureRecordValidationError,
    extract_research_implement_failures,
    load_research_implement_failures,
    validate_failure_record,
)


FIXTURE = (
    Path(__file__).parent / "fixtures" / "research_implement_results_small.json"
)
EXTRACTED_AT = "2026-09-03T00:00:00+00:00"
SOURCE_URI = "fixture/research_implement_results_small.json"


class ResearchImplementFailureExtractorTests(unittest.TestCase):
    def load_fixture(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def extract(self):
        return extract_research_implement_failures(
            self.load_fixture(),
            source_uri=SOURCE_URI,
            extracted_at=EXTRACTED_AT,
        )

    def test_only_ok_false_is_extracted(self):
        failures = self.extract()
        self.assertEqual(len(failures), 1)
        self.assertIs(failures[0]["outcome"]["ok"], False)

    def test_ok_true_is_not_extracted(self):
        failures = self.extract()
        self.assertNotIn("qwen", [item["subject"]["model"] for item in failures])

    def test_other_failure_like_fields_do_not_select_a_run(self):
        data = {
            "runs": [
                {
                    "pass": False,
                    "fail_stage": "implementation",
                    "research_stop_reason": "stagnation",
                    "error": "boom",
                }
            ]
        }
        self.assertEqual(
            extract_research_implement_failures(
                data, source_uri=SOURCE_URI, extracted_at=EXTRACTED_AT
            ),
            [],
        )

    def test_fail_stage_is_normalized(self):
        self.assertEqual(self.extract()[0]["outcome"]["failure_stage"], "research")

    def test_research_stop_reason_is_normalized(self):
        self.assertEqual(self.extract()[0]["outcome"]["stop_reason"], "stagnation")

    def test_failure_id_is_stable(self):
        first = self.extract()[0]["failure_id"]
        second = self.extract()[0]["failure_id"]
        self.assertEqual(first, second)

    def test_raw_payload_is_referenced_not_copied(self):
        encoded = json.dumps(self.extract()[0], ensure_ascii=False)
        self.assertNotIn("large raw content", encoded)
        self.assertNotIn("def generated", encoded)
        self.assertEqual(
            self.extract()[0]["raw_refs"][0]["json_pointer"], "/runs/0"
        )

    def test_unknown_and_missing_fields_are_not_inferred(self):
        data = {"runs": [{"ok": False, "unknown": "value"}]}
        record = extract_research_implement_failures(
            data, source_uri=SOURCE_URI, extracted_at=EXTRACTED_AT
        )[0]
        self.assertIsNone(record["timestamp"])
        self.assertIsNone(record["subject"]["model"])
        self.assertIsNone(record["outcome"]["failure_stage"])
        self.assertEqual(record["outcome"]["failure_type"], "UNKNOWN")

    def test_missing_request_has_no_input_ref(self):
        data = {"runs": [{"ok": False}]}
        record = extract_research_implement_failures(
            data, source_uri=SOURCE_URI, extracted_at=EXTRACTED_AT
        )[0]
        self.assertIsNone(record["input_ref"])

    def test_evidence_only_references_fields_present_in_source(self):
        data = {"runs": [{"ok": False}]}
        record = extract_research_implement_failures(
            data, source_uri=SOURCE_URI, extracted_at=EXTRACTED_AT
        )[0]
        pointers = {item["json_pointer"] for item in record["evidence"]}
        self.assertEqual(pointers, {"/runs/0/ok"})

        observed_nulls = {
            "runs": [
                {
                    "ok": False,
                    "fail_stage": None,
                    "research_stop_reason": None,
                    "error": None,
                }
            ]
        }
        record = extract_research_implement_failures(
            observed_nulls, source_uri=SOURCE_URI, extracted_at=EXTRACTED_AT
        )[0]
        pointers = {item["json_pointer"] for item in record["evidence"]}
        self.assertEqual(
            pointers,
            {
                "/runs/0/ok",
                "/runs/0/fail_stage",
                "/runs/0/research_stop_reason",
                "/runs/0/error",
            },
        )

    def test_failure_record_requires_false_outcome(self):
        record = self.extract()[0]
        validate_failure_record(record)
        invalid = {**record, "outcome": {**record["outcome"], "ok": True}}
        with self.assertRaises(FailureRecordValidationError):
            validate_failure_record(invalid)

    def test_file_loader_is_read_only_and_uses_requested_source_uri(self):
        before = FIXTURE.read_bytes()
        records = load_research_implement_failures(
            FIXTURE, source_uri=SOURCE_URI, extracted_at=EXTRACTED_AT
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"]["uri"], SOURCE_URI)
        self.assertEqual(FIXTURE.read_bytes(), before)

    def test_absolute_external_path_is_not_exposed_as_source_uri(self):
        payload = {"runs": [{"ok": False}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "results.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            record = load_research_implement_failures(
                path, extracted_at=EXTRACTED_AT
            )[0]

        uri = record["source"]["uri"]
        self.assertTrue(uri.startswith("external-source:sha256:"))
        self.assertNotIn(str(path), uri)
        if path.drive:
            self.assertNotIn(path.drive, uri)
        self.assertNotIn(Path.home().name, uri)


if __name__ == "__main__":
    unittest.main()
