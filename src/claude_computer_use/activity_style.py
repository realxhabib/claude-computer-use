"""Reference-based desktop indicator geometry in device-independent pixels."""
BANNER_WIDTH = 376
BANNER_HEIGHT = 46
BANNER_TOP = 48
CURSOR_SIZE = 72
CURSOR_HOTSPOT = (36, 36)
ACTIVE_TEXT = 'Claude is using your computer'
CANCEL_TEXT = 'Esc to cancel'


def banner_position(bounds):
    x, y, width, height = bounds
    return (x + max(0, (width - BANNER_WIDTH) // 2), y + min(BANNER_TOP, max(0, height - BANNER_HEIGHT)))
