"""Table Y lock: halfway from the rest shoulder to the bottom of the frame."""

TABLE_BELOW_SHOULDER_RATIO = 0.5


def table_y_from_shoulder_ratio(shoulder_y, ratio=TABLE_BELOW_SHOULDER_RATIO):
    if shoulder_y is None:
        return None
    try:
        sy = float(shoulder_y)
        r = float(ratio)
    except (TypeError, ValueError):
        return None
    if sy != sy or r <= 0:  # NaN check without numpy
        return None
    y = sy + r * (1.0 - sy)
    if y != y or y <= sy:
        return None
    return min(0.98, max(sy + 0.02, y))
