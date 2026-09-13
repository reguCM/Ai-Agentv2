from bay import BAY_OPEN
from config import LANE_NAMES, LANE_TAKE


def load_lanes():
    return list(LANE_NAMES[:LANE_TAKE])


def pick_lane(lanes, index):
    return lanes[index]


def bay_open():
    return BAY_OPEN
