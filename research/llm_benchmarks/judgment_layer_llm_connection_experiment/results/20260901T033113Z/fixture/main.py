from helper import is_ready, load_items


def assemble():
    items = load_items()
    return {"item": items[2], "ready": is_ready()}


def main():
    import json

    print(json.dumps(assemble()))


if __name__ == "__main__":
    main()
