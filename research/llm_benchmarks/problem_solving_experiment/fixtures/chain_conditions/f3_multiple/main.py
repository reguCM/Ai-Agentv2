from helper import load_rows
from validator import validate_rows


def run():
    rows = load_rows()
    validate_rows(rows)
    value = rows[2]
    return {"status": value}


if __name__ == "__main__":
    print(run())
