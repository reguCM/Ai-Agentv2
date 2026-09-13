def validate_rows(rows):
    if not isinstance(rows, list):
        raise TypeError("expected list")
    return True
