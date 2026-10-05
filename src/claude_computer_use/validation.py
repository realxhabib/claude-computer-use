import math


def point(x: int, y: int, width: int, height: int):
    if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
        raise ValueError("Coordinates must be integers")
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"Point outside primary screen: {width}x{height}")
    return x, y


def bounded(value: float, low: float, high: float):
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Value must be between {low} and {high}")
    return value
