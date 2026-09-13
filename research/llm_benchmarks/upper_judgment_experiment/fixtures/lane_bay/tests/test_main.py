from main import assemble_shipment


def test_assemble_shipment():
    shipment = assemble_shipment()
    assert shipment["lane"] == "west"
    assert shipment["bay"] is True
