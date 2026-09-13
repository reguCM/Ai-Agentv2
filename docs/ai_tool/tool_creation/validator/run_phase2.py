#!/usr/bin/env python3
"""Tool Creation Layer Phase 2 experiment runner."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from validator.catalog_draft import generate_catalog_draft, write_catalog_draft
from validator.test_skeleton import write_test_skeleton
from validator.validate import validate_tool_spec_file

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
RUN_DIR = Path(__file__).resolve().parents[4] / "runs" / "ai_tool" / f"{RUN_ID}_tool_creation_phase2"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    specs_dir = _ROOT / "specs"
    failure_dir = _ROOT / "failure_cases"
    drafts_dir = RUN_DIR / "drafts"
    tests_dir = RUN_DIR / "generated_tests"
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "experiment": "tool_creation_phase2",
        "run_dir": str(RUN_DIR),
        "validator": {"valid": [], "invalid": []},
        "catalog_drafts": [],
        "test_skeletons": [],
        "registry_modified": False,
        "production_code_modified": False,
    }

    # Valid specs
    for spec_path in sorted(specs_dir.glob("*.json")):
        result = validate_tool_spec_file(spec_path)
        entry = result.to_dict()
        report["validator"]["valid"].append(entry)

        if result.verdict == "ACCEPT":
            spec = _load_json(spec_path)
            draft_path = write_catalog_draft(
                spec,
                drafts_dir,
                spec_ref=str(spec_path.relative_to(_ROOT)).replace("\\", "/"),
            )
            test_path = write_test_skeleton(spec, tests_dir)
            draft = generate_catalog_draft(spec, spec_ref=str(spec_path))
            report["catalog_drafts"].append(
                {
                    "tool_id": draft.get("tool_id"),
                    "path": str(draft_path.relative_to(RUN_DIR)),
                    "experiment_status": draft.get("experiment_status"),
                    "adoption_status": draft.get("adoption_status"),
                    "inferred_fields": draft.get("_draft_meta", {}).get("inferred_fields"),
                }
            )
            report["test_skeletons"].append(
                {
                    "tool_id": spec.get("tool_id"),
                    "path": str(test_path.relative_to(RUN_DIR)),
                }
            )

    # Failure cases
    for fc_path in sorted(failure_dir.glob("*.json")):
        result = validate_tool_spec_file(fc_path)
        report["validator"]["invalid"].append(result.to_dict())

    # fc08: valid schema but catalog draft must not coerce bad hints
    fc08 = _load_json(failure_dir / "fc08_invalid_catalog_hints.json")
    if validate_tool_spec_file(failure_dir / "fc08_invalid_catalog_hints.json").verdict == "ACCEPT":
        draft08 = generate_catalog_draft(fc08)
        report["fc08_catalog_draft_check"] = {
            "experiment_status": draft08.get("experiment_status"),
            "adoption_status": draft08.get("adoption_status"),
            "coerced": draft08.get("experiment_status") != "UNKNOWN"
            or draft08.get("adoption_status") != "UNKNOWN",
        }

    # Summary counts
    valid_accept = sum(1 for v in report["validator"]["valid"] if v["verdict"] == "ACCEPT")
    valid_reject = len(report["validator"]["valid"]) - valid_accept
    invalid_reject = sum(1 for v in report["validator"]["invalid"] if v["verdict"] == "REJECT")
    invalid_accept = len(report["validator"]["invalid"]) - invalid_reject

    report["summary"] = {
        "valid_specs_accept": valid_accept,
        "valid_specs_reject": valid_reject,
        "failure_cases_reject": invalid_reject,
        "failure_cases_accept": invalid_accept,
        "false_accept": invalid_accept + valid_reject,
        "false_reject": 0 if valid_reject == 0 else valid_reject,
    }

    out = RUN_DIR / "results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Full report: {out}")
    return 0 if invalid_accept == 0 and valid_accept == len(report["validator"]["valid"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
