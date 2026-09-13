import json

from helper import load_items, pick_item, store_open


def assemble_order():
    items = load_items()
    return {
        "item": pick_item(items, 2),
        "store": store_open(),
    }


def main():
    print(json.dumps(assemble_order()))


if __name__ == "__main__":
    main()
