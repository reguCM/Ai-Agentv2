from main import build_report


def test_build_report():
    report = build_report()
    assert report["status"] == "Busy"
    assert report["ready"] is True
