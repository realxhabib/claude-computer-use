import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from claude_computer_use.validation import point, bounded

class ValidationTests(unittest.TestCase):
    def test_screen_edges(self):
        self.assertEqual(point(1919, 1079, 1920, 1080), (1919, 1079))
        for x, y in [(-1, 0), (1920, 0), (0, 1080), (True, 0)]:
            with self.assertRaises(ValueError):
                point(x, y, 1920, 1080)

    def test_invalid_durations(self):
        for value in [float("nan"), float("inf"), -1, 4]:
            with self.assertRaises(ValueError):
                bounded(value, 0, 3)
        self.assertEqual(bounded(0.5, 0, 3), 0.5)
