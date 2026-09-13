from tools.system import llm


def test_hard_timeout_is_separate_from_long_running_threshold():
    profile = {
        "timeout_seconds": 90,
        "long_running_after_seconds": 30,
        "hard_timeout_seconds": 300,
    }
    assert llm.request_hard_timeout_seconds(profile) == 300


def test_legacy_profile_keeps_explicit_timeout_as_safety_cap():
    assert llm.request_hard_timeout_seconds({"timeout_seconds": 120}) == 120


def test_client_uses_hard_timeout_and_reuses_matching_client(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout
            created.append(timeout)

    monkeypatch.setattr(
        llm,
        "_profile",
        lambda: {"timeout_seconds": 90, "hard_timeout_seconds": 300},
    )
    monkeypatch.setattr(llm, "Client", FakeClient)
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.setattr(llm, "_client_timeout", None)

    first = llm.get_client()
    second = llm.get_client()

    assert first is second
    assert first.timeout == 300
    assert created == [300]
