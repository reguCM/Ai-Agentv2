from config import FIELD_COUNT, STATUS_LABELS


def load_rows():
    return list(STATUS_LABELS[:FIELD_COUNT])
