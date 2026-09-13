import json
from types import SimpleNamespace

from ai_tool.input_interpretation.llm_comparison import INPUT_VIEWS, run_comparison


class FakeCompressor:
    def compress_prompt(self, context, **kwargs):
        return {"compressed_prompt": context[0], "origin_tokens": 5, "compressed_tokens": 5}


def fake_chat(**kwargs):
    packet = json.loads(kwargs["messages"][1]["content"])
    candidate = packet["candidates"][0]
    payload = {
        "semantic_selection": {"selected_candidate_ids":[candidate["candidate_id"]],"interpreted_text":packet["raw_input"],"fusion_used":False,"none_of_the_above":False,"needs_clarification":False,"certainty":"KNOWN","confidence":0.9,"ambiguities":[],"assumptions":[],"unknowns":[],"provisional_fields":[],"clarification_questions":[],"candidate_interpretations":[],"ambiguity_reason":None},
        "request_ir": {"intents":["workspace_observation"],"targets":[{"value":"A.md","type":"path"}],"operations":["READ"],"operation_order":[],"constraints":[],"conditions":[],"negations":[],"output_requirements":[],"ambiguities":[],"certainty":"KNOWN","assumptions":[],"unknowns":[],"provisional_fields":[],"needs_clarification":False,"clarification_questions":[],"candidate_interpretations":[],"ambiguity_reason":None},
    }
    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))


def test_runner_uses_same_case_for_all_five_views_and_keeps_raw(tmp_path):
    fixture=tmp_path/"cases.json"; fixture.write_text('[{"case_id":"c1","level":"MICRO","evaluation_type":"HARD_GOLD","input":"A.mdを読んで","expected_request_ir":{"operations":["READ"]}}]',encoding="utf-8")
    report=run_comparison(fixture_path=fixture,models=["fake:model"],chat_fn=fake_chat,compressor=FakeCompressor())
    assert set(report["groups"]["fake:model"]) == set(INPUT_VIEWS)
    assert all(group["summary"]["passed"] == 1 for group in report["groups"]["fake:model"].values())
    assert report["contract"] == {"raw_always_present":True,"tool_candidates_not_canonical":True,"llm_output_is_semantic_proposal":True,"gold_not_in_prompt":True}
    assert all("raw" in group["summary"]["selected_candidate_sources"] for group in report["groups"]["fake:model"].values())
