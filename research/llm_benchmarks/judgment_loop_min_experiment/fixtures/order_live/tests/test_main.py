from main import assemble_order


def test_assemble_order():
    order = assemble_order()
    assert order["item"] == "live"
    assert order["store"] is True
