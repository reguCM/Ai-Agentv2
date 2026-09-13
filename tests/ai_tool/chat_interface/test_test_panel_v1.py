from pathlib import Path
from threading import Event
import time

import pytest

from ai_tool.chat_interface.test_batches import (
    _default_execute,
    batch_job,
    public_cases,
    reset_jobs_for_test,
    start_batch_job,
)


@pytest.fixture(autouse=True)
def clean_jobs():
    reset_jobs_for_test()
    yield
    reset_jobs_for_test()


def test_01_ui_case_list_contains_p216():
    assert public_cases()[0]["test_case_id"] == "P216-GIT-PLAN"


def test_02_ui_static_panel_has_test_mode_and_run_choices():
    html = (Path("ai_tool/chat_interface/static/index.html")).read_text(encoding="utf-8")
    assert 'id="testMode"' in html
    assert all(f'value="{count}"' in html for count in (1, 5, 10))


def test_03_ui_removes_dedicated_button_and_keeps_progress_area():
    html = Path("ai_tool/chat_interface/static/index.html").read_text(encoding="utf-8")
    assert 'id="testRunButton"' not in html
    assert 'id="testProgress"' in html


def test_04_ui_prevents_double_start_in_client():
    script = Path("ai_tool/chat_interface/static/app.js").read_text(encoding="utf-8")
    assert "if (testBatchTimer !== null) return" in script


def test_05_ui_polls_batch_progress():
    script = Path("ai_tool/chat_interface/static/app.js").read_text(encoding="utf-8")
    assert 'fetch("/api/test-batches/"' in script
    assert "current_run_id" in script


def test_06_ui_renders_aggregate_markdown_and_copy():
    script = Path("ai_tool/chat_interface/static/app.js").read_text(encoding="utf-8")
    assert "aggregate_markdown" in script
    assert "navigator.clipboard.writeText" in script


def test_07_individual_reports_are_collapsed_and_copyable():
    script = Path("ai_tool/chat_interface/static/app.js").read_text(encoding="utf-8")
    assert '<details class="test-run-report">' in script
    assert 'data-copy="run-${index}"' in script


def test_08_panel_uses_separate_api_not_chat_messages():
    script = Path("ai_tool/chat_interface/static/app.js").read_text(encoding="utf-8")
    block = script.split("async function startAgentTestBatch(prompt)", 1)[1].split("testMode.addEventListener", 1)[0]
    assert 'fetch("/api/test-batches"' in block
    assert "addBubble" not in block


def test_09_server_exposes_case_and_batch_routes():
    server = Path("ai_tool/chat_interface/server.py").read_text(encoding="utf-8")
    assert 'path == "/api/test-cases"' in server
    assert 'parsed.path == "/api/test-batches"' in server


def test_10_invalid_run_count_is_rejected_before_thread_start():
    with pytest.raises(ValueError):
        start_batch_job("P216-GIT-PLAN", 3, execute=lambda *_: {})


def test_10b_ui_uses_current_message_and_normal_submit_button():
    script = Path("ai_tool/chat_interface/static/app.js").read_text(encoding="utf-8")
    submit = script.split("async function submitMessage()", 1)[1].split("input.addEventListener", 1)[0]
    assert "if (testMode.checked)" in submit
    assert "startAgentTestBatch(text)" in submit
    batch = script.split("async function startAgentTestBatch(prompt)", 1)[1]
    assert "prompt: prompt" in batch


def test_10c_ui_displays_runtime_status_report_for_errors():
    script = Path("ai_tool/chat_interface/static/app.js").read_text(encoding="utf-8")
    assert "data.turn && data.turn.runtime_status_report" in script
    assert "statusReport && statusReport.markdown" in script


def test_11_background_job_completes_and_exposes_result(monkeypatch):
    monkeypatch.setattr(
        "ai_tool.chat_interface.test_batches.run_batch",
        lambda *_args, **_kwargs: {"aggregate": {"total_runs": 5}},
    )
    job = start_batch_job("P216-GIT-PLAN", 5, execute=lambda *_: {})
    for _ in range(100):
        current = batch_job(job["job_id"])
        if current["status"] != "running":
            break
        time.sleep(0.001)
    assert current["status"] == "completed"
    assert current["result"]["aggregate"]["total_runs"] == 5


def test_12_server_side_double_start_is_rejected(monkeypatch):
    release = Event()

    def blocked(*_args, **_kwargs):
        release.wait(1)
        return {}

    monkeypatch.setattr("ai_tool.chat_interface.test_batches.run_batch", blocked)
    start_batch_job("P216-GIT-PLAN", 1, execute=lambda *_: {})
    with pytest.raises(RuntimeError, match="already running"):
        start_batch_job("P216-GIT-PLAN", 1, execute=lambda *_: {})
    release.set()


def test_13_preflight_exception_preserves_selected_model_and_cause(monkeypatch):
    def fail_after_selection(session, _prompt, **_kwargs):
        session["model"] = "qwen3:14b"
        raise RuntimeError("Dedicated Sandbox bootstrap failed: Filename too long")

    monkeypatch.setattr(
        "ai_tool.chat_interface.test_batches.run_chat_turn", fail_after_selection
    )
    result = _default_execute(None)({"prompt": "create file"}, "diagnostic-run")
    diagnostic = result["execution_diagnostics"]
    assert result["model"] == "qwen3:14b"
    assert result["is_error"] is True
    assert diagnostic["model_selection_started"] is True
    assert diagnostic["model_selected"] == "qwen3:14b"
    assert diagnostic["preflight_failed"] is True
    assert diagnostic["exception_type"] == "RuntimeError"
    assert "Filename too long" in diagnostic["exception_message"]
    assert diagnostic["provider_ready"] == "UNKNOWN"
