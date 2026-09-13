import json

from helper import dock_open, load_bins, pick_bin


def assemble_pack():
    bins = load_bins()
    return {
        "bin": pick_bin(bins, 2),
        "dock": dock_open(),
    }


def main():
    print(json.dumps(assemble_pack()))


if __name__ == "__main__":
    main()
