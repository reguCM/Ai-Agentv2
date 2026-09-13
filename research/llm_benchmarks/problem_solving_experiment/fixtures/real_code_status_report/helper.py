from config import FIELD_COUNT, STATUS_LABELS


def load_report_rows():
    return list(STATUS_LABELS[:FIELD_COUNT])


def pick_status(rows, index):
    return rows[index]
