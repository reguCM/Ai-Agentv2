from ai_tool.input_interpretation.tool_comparison import render_tool_comparison_markdown, run_tool_comparison

class FakeCompressor:
    def compress_prompt(self, context, **kwargs):
        return {"compressed_prompt": context[0], "origin_tokens": 10, "compressed_tokens": 10, "rate": "100%"}

def test_tool_quality_and_request_ir_scores_are_separate(tmp_path):
    fixture = tmp_path / "case.json"
    fixture.write_text('[{"case_id":"c1","level":"REALISTIC","evaluation_type":"HARD_GOLD","input":"A.mdを読んで","expected_request_ir":{"operations":["READ"]}}]', encoding="utf-8")
    report = run_tool_comparison(fixture, compressor=FakeCompressor(), model_name="fake")
    row = report["cases"][0]
    assert report["report_contract"]["tool_output_quality_is_not_request_ir_success"] is True
    assert row["llmlingua"]["compressed_text"] == "A.mdを読んで"
    assert row["request_ir_benchmark"]["separate_from_tool_output_quality"] is True
    assert report["environment"]["gpu_used"] is False

def test_tool_comparison_markdown_has_required_side_by_side_sections(tmp_path):
    fixture = tmp_path / "case.json"
    fixture.write_text('[{"case_id":"micro_typo_001","level":"MICRO","input":"実際にこの文章をｙｐんで","expected_request_ir":{"operations":["READ"]}}]', encoding="utf-8")
    markdown = render_tool_comparison_markdown(run_tool_comparison(fixture, compressor=FakeCompressor(), model_name="fake"))
    for heading in ("RAW", "Safe Normalizer", "Sudachi tokens", "LLMLingua", "Baseline Semantic / Expected"):
        assert heading in markdown
