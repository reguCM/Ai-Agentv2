import json

from helper import load_report_rows, pick_status


def build_report():
    rows = load_report_rows()
    return {"status": pick_status(rows, 2)}


def main():
    print(json.dumps(build_report()))


if __name__ == "__main__":
    main()
