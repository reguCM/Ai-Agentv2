from main import assemble_pack


def test_assemble_pack():
    pack = assemble_pack()
    assert pack["bin"] == "ready"
    assert pack["dock"] is True
