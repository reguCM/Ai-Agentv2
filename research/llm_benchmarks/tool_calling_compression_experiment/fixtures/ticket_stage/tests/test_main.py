from main import assemble_ticket


def test_assemble_ticket():
    ticket = assemble_ticket()
    assert ticket["stage"] == "closed"
    assert ticket["window"] is True
