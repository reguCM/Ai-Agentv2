from config import STAGE_LIMIT, STAGE_NAMES
from flags import WINDOW_OPEN


def load_stages():
    return list(STAGE_NAMES[:STAGE_LIMIT])


def select_stage(rows, index):
    return rows[index]


def window_open():
    return WINDOW_OPEN
