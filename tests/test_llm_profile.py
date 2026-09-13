import unittest

from tools.ai.llm.adapter import (
    build_repair_messages,
    build_repair_prompt,
    prepare_materials,
    render_contract,
)
from tools.ai.prompts.base import (
    CONTRACT_IDS,
    NEVER_DROP_MATERIAL_KEYS,
    REPAIR_CONTRACT,
    REQUIRED_MATERIAL_KEYS,
)
from tools.ai.tool_builder.repair import select_repair_materials
from tools.system.config import LLM_MODELS_PATH, PIPELINE_PATH
from tools.system.config import (
    LLM_MODELS_PATH,
    PIPELINE_PATH,
    active_model_id,
    get_llm_profile,
    get_pipeline,
    load_yaml,
    stage_model_id,
)


class ConfigSeparationTests(unittest.TestCase):
    def test_pipeline_has_no_prompt_style(self):
        pipeline = get_pipeline()
        self.assertIn("active_model", pipeline)
        self.assertIn("max_repair_rounds", pipeline)
        self.assertIn("max_research_rounds", pipeline)
        self.assertIn("max_research_stagnation", pipeline)
        self.assertEqual(pipeline["max_research_rounds"], 10)
        self.assertEqual(pipeline["max_research_stagnation"], 3)
        self.assertEqual(pipeline["max_clarity_rounds"], 5)
        self.assertEqual(
            (pipeline.get("project_context") or {}).get("implementation_method_selection"),
            "Agent",
        )
        self.assertNotIn("prompt_style", pipeline)
        self.assertNotIn("context_limit", pipeline)

    def test_stage_model_falls_back_to_active_model(self):
        self.assertEqual(stage_model_id("implement"), active_model_id())
        self.assertEqual(stage_model_id("research"), active_model_id())

    def test_llm_profiles_exist(self):
        qwen8 = get_llm_profile("qwen3_8b")
        qwen14 = get_llm_profile("qwen3_14b")
        coder7 = get_llm_profile("qwen2_5_coder_7b")
        gemma12 = get_llm_profile("gemma3_12b")
        deepseek = get_llm_profile("deepseek_coder_v2_16b")
        self.assertEqual(qwen8["model"], "qwen3:8b")
        self.assertEqual(qwen8["prompt_style"], "japanese_verbose")
        self.assertEqual(qwen14["model"], "qwen3:14b")
        self.assertEqual(coder7["model"], "qwen2.5-coder:7b")
        self.assertEqual(gemma12["model"], "gemma3:12b")
        for profile in (qwen14, coder7, gemma12):
            self.assertEqual(profile["prompt_style"], qwen8["prompt_style"])
            self.assertEqual(profile["materials"], qwen8["materials"])
        self.assertEqual(deepseek["model"], "deepseek-coder-v2:16b")
        self.assertEqual(deepseek["prompt_style"], "english_compact")
        self.assertNotIn("rules", deepseek["materials"]["drop_keys"])

    def test_yaml_files_parse(self):
        self.assertTrue(load_yaml(PIPELINE_PATH))
        self.assertTrue(load_yaml(LLM_MODELS_PATH))


class ContractTests(unittest.TestCase):
    def test_contract_is_minimal_not_empty(self):
        self.assertGreaterEqual(len(REPAIR_CONTRACT), 1)
        self.assertEqual(CONTRACT_IDS, [item["id"] for item in REPAIR_CONTRACT])
        for item in REPAIR_CONTRACT:
            self.assertTrue(item["ja"].strip())
            self.assertTrue(item["en"].strip())

    def test_both_profiles_keep_every_contract_item(self):
        japanese = render_contract(get_llm_profile("qwen3_8b"))
        english = render_contract(get_llm_profile("deepseek_coder_v2_16b"))
        for item in REPAIR_CONTRACT:
            self.assertIn(item["ja"], japanese)
            self.assertIn(item["en"], english)
            self.assertNotIn(item["en"], japanese)


class MaterialSelectionTests(unittest.TestCase):
    def test_select_drops_rules_and_proposal(self):
        selected = select_repair_materials(
            {
                "tool_name": "cpu_status",
                "rules": ["do not put contract in materials"],
                "proposal": {"name": "cpu_status", "output": ["status"]},
                "current_source": "def cpu_status():\n    return {'status': '28'}\n",
                "target_path": "tools/system/cpu/cpu_status.py",
                "target_function": "cpu_status",
                "target_output": ["status"],
                "repairable_warnings": [
                    {
                        "code": "wrong_output_key",
                        "message": "key",
                        "fix": "キーを合わせる",
                        "action": "repair",
                    }
                ],
                "test_result": {
                    "result": "OK",
                    "return_value": {"load": "28"},
                    "noise": "drop",
                },
                "result_validation": {"result": "NG"},
            }
        )
        self.assertNotIn("rules", selected)
        self.assertNotIn("proposal", selected)
        self.assertNotIn("result_validation", selected)
        for key in REQUIRED_MATERIAL_KEYS:
            self.assertIn(key, selected)
        self.assertEqual(selected["repairable_warnings"][0]["code"], "wrong_output_key")
        self.assertEqual(selected["repairable_warnings"][0]["fix"], "キーを合わせる")
        self.assertNotIn("noise", selected["test_result"])

    def test_research_is_included_when_needed(self):
        selected = select_repair_materials(
            {
                "tool_name": "cpu_status",
                "current_source": "x",
                "target_path": "p",
                "target_function": "cpu_status",
                "target_output": ["status"],
                "repairable_warnings": [
                    {"code": "stub_value", "needs_research_findings": True}
                ],
                "test_result": {"return_value": {"status": "未実装"}},
                "research_result": {
                    "usable_findings": [
                        {"evidence": {"command": "cmd", "sample": "28"}}
                    ],
                    "reference_findings": [{"note": "ignore"}],
                    "unresolved": [],
                },
            }
        )
        self.assertIn("research_result", selected)
        self.assertIn("usable_findings", selected["research_result"])
        self.assertNotIn("reference_findings", selected["research_result"])


class PromptAdapterTests(unittest.TestCase):
    def test_deepseek_shortens_source_but_keeps_required_materials(self):
        profile = get_llm_profile("deepseek_coder_v2_16b")
        selected = select_repair_materials(
            {
                "rules": ["contract does not belong here"],
                "proposal": {"name": "cpu_status"},
                "current_source": "x" * 4000,
                "target_path": "tools/system/cpu/cpu_status.py",
                "target_function": "cpu_status",
                "target_output": ["status"],
                "repairable_warnings": [{"code": "wrong_output_key"}],
                "test_result": {"return_value": {"load": "1"}},
            }
        )
        prepared = prepare_materials(selected, profile)
        self.assertNotIn("rules", prepared)
        self.assertNotIn("proposal", prepared)
        self.assertEqual(len(prepared["current_source"]), 2500)
        self.assertIn("repairable_warnings", prepared)

    def test_profile_cannot_drop_required_materials(self):
        profile = dict(get_llm_profile("deepseek_coder_v2_16b"))
        profile["materials"] = {
            "compact_json": True,
            "drop_keys": list(NEVER_DROP_MATERIAL_KEYS),
            "current_source_max_chars": 10,
        }
        prepared = prepare_materials(
            {
                "current_source": "abcdefghijklmnop",
                "repairable_warnings": [{"code": "wrong_output_key"}],
                "test_result": {"return_value": {"status": "1"}},
            },
            profile,
        )
        self.assertIn("repairable_warnings", prepared)
        self.assertIn("test_result", prepared)
        self.assertEqual(prepared["current_source"], "abcdefghij")

    def test_deepseek_translates_warning_fix_by_profile(self):
        profile = get_llm_profile("deepseek_coder_v2_16b")
        prepared = prepare_materials(
            {
                "repairable_warnings": [
                    {
                        "code": "unparsed_output",
                        "fix": "固定フォーマットを仮定しない。",
                    }
                ]
            },
            profile,
        )
        self.assertIn("repairable_warnings", prepared)
        self.assertIn(
            "If evidence.parsed_table is present",
            prepared["repairable_warnings"][0]["fix"],
        )
        self.assertIn(
            "Do not re-parse the table in code",
            prepared["repairable_warnings"][0]["fix"],
        )

    def test_qwen_keeps_full_source(self):
        profile = get_llm_profile("qwen3_8b")
        source = "def cpu_status():\n    return {'status': '1'}\n"
        prepared = prepare_materials({"current_source": source}, profile)
        self.assertEqual(prepared["current_source"], source)

    def test_qwen_keeps_warning_fix_in_japanese(self):
        profile = get_llm_profile("qwen3_8b")
        prepared = prepare_materials(
            {
                "repairable_warnings": [
                    {"code": "unparsed_output", "fix": "固定フォーマットを仮定しない。"}
                ]
            },
            profile,
        )
        self.assertEqual(
            prepared["repairable_warnings"][0]["fix"],
            "固定フォーマットを仮定しない。",
        )

    def test_messages_split_contract_and_materials(self):
        materials = {
            "current_source": "source",
            "repairable_warnings": [{"code": "wrong_output_key"}],
        }
        messages = build_repair_messages(
            materials, profile=get_llm_profile("qwen3_8b")
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("SYSTEM / CONTRACT", messages[0]["content"])
        self.assertIn("TASK MATERIALS", messages[1]["content"])
        self.assertNotIn("TASK MATERIALS", messages[0]["content"])

    def test_prompt_style_changes_language_not_contract_ids(self):
        materials = {"repairable_warnings": []}
        japanese = build_repair_prompt(materials, profile=get_llm_profile("qwen3_8b"))
        english = build_repair_prompt(
            materials, profile=get_llm_profile("deepseek_coder_v2_16b")
        )
        self.assertIn("出力は JSON オブジェクト 1 つだけ", japanese)
        self.assertIn("Output exactly one JSON object", english)
        self.assertNotIn("Output exactly one JSON object", japanese)


if __name__ == "__main__":
    unittest.main()
