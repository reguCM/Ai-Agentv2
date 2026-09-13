from helper import load_rows


def run():
    rows = load_rows()
    value = rows[2]
    return {"status": value}


if __name__ == "__main__":
    print(run())
