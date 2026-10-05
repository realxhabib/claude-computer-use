import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.activity_style import banner_position,CURSOR_SIZE,CURSOR_HOTSPOT

class StyleTests(unittest.TestCase):
    def test_banner_centers_on_each_display_including_negative_origin(self):
        self.assertEqual(banner_position((0,0,1920,1080)),(772,48))
        self.assertEqual(banner_position((-1920,0,1920,1080)),(-1148,48))
        self.assertEqual(banner_position((1920,90,1280,720)),(2372,138))
    def test_native_cursor_glow_is_centered_on_pointer(self):
        self.assertEqual(CURSOR_HOTSPOT,(CURSOR_SIZE//2,CURSOR_SIZE//2))
