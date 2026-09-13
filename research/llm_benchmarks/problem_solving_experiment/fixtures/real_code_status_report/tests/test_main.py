from main import build_report


def test_build_report_status_is_busy():
    report = build_report()
    assert report["status"] == "Busy"
