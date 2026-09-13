from config import ITEM_LABELS, ITEM_SPAN
from store import STORE_OPEN


def load_items():
    return list(ITEM_LABELS[:ITEM_SPAN])


def pick_item(items, index):
    return items[index]


def store_open():
    return STORE_OPEN
