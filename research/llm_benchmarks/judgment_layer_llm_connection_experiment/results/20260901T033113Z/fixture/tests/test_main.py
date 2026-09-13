from main import assemble


def test_assemble():
    result = assemble()
    assert result["item"] == "gamma"
    assert result["ready"] is True
