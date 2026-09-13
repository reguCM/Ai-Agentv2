from config import FIELD_COUNT, STATUS_LABELS
from runtime import READY


def load_report_rows():
    return list(STATUS_LABELS[:FIELD_COUNT])


def pick_status(rows, index):
    return rows[index]


def report_ready():
    return READY
