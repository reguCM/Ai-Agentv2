from helper import load_metrics


def run():
    data = load_metrics()
    return {"status": data["cpu"]}


if __name__ == "__main__":
    print(run())
