from config import FIELD_COUNT, READY

LABELS = ["alpha", "beta", "gamma"]


def load_items():
    return LABELS[:FIELD_COUNT]


def is_ready():
    return READY
