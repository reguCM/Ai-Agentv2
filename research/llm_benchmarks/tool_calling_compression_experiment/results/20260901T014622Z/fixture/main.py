import json

from helper import load_stages, select_stage, window_open


def assemble_ticket():
    rows = load_stages()
    return {
        "stage": select_stage(rows, 2),
        "window": window_open(),
    }


def main():
    print(json.dumps(assemble_ticket()))


if __name__ == "__main__":
    main()
