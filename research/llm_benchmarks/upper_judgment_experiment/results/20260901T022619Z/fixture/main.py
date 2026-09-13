import json

from helper import bay_open, load_lanes, pick_lane


def assemble_shipment():
    lanes = load_lanes()
    return {
        "lane": pick_lane(lanes, 2),
        "bay": bay_open(),
    }


def main():
    print(json.dumps(assemble_shipment()))


if __name__ == "__main__":
    main()
