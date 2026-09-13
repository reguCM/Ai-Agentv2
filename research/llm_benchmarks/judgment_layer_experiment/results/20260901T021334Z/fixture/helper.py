from config import BIN_LABELS, BIN_SPAN
from gate import DOCK_OPEN


def load_bins():
    return list(BIN_LABELS[:BIN_SPAN])


def pick_bin(bins, index):
    return bins[index]


def dock_open():
    return DOCK_OPEN
