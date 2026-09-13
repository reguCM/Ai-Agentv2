from helper import pick_status


def run():
    return {"status": pick_status()}


if __name__ == "__main__":
    print(run())
