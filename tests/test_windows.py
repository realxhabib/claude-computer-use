"""Window API contracts with doubles, not native host validation."""
import ctypes
from ctypes import wintypes
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.windows import Windows,Mac


class WindowTests(unittest.TestCase):
    def test_maximized_invisible_border_uses_dwm_visible_frame(self):
        windows=Windows.__new__(Windows);windows.wintypes=wintypes
        dwm=Mock()
        windows.ctypes=SimpleNamespace(c_void_p=ctypes.c_void_p,byref=ctypes.byref,sizeof=ctypes.sizeof,WinDLL=Mock(return_value=dwm))
        def bounds(hwnd,key,pointer,size):
            rect=pointer._obj
            rect.left,rect.top,rect.right,rect.bottom=0,0,1920,1080
            return 0
        dwm.DwmGetWindowAttribute.side_effect=bounds
        gui=Mock();gui.IsWindow.return_value=True
        gui.GetWindowRect.return_value=(-8,-8,1928,1088)
        gui.GetWindowPlacement.return_value=(0,3,(0,0),(0,0),(0,0,1920,1080))
        gui.GetWindowText.return_value='Calculator';gui.IsWindowVisible.return_value=True;gui.IsIconic.return_value=False
        process=Mock();process.GetWindowThreadProcessId.return_value=(1,42)
        psutil=Mock();psutil.Process.return_value.name.return_value='Calculator.exe'
        psutil.Process.return_value.create_time.return_value=123
        with patch.dict(sys.modules,{'win32gui':gui,'win32process':process,'psutil':psutil}):
            record=windows.record(123)
        self.assertEqual(record['bounds'],{'x':0,'y':0,'width':1920,'height':1080})
        self.assertEqual(record['native_capture_bounds'],{'x':-8,'y':-8,'width':1936,'height':1096})

    def test_printwindow_crops_border_without_desktop_capture(self):
        windows=Windows.__new__(Windows);windows.wintypes=wintypes;windows.user32=Mock()
        windows.user32.PrintWindow.return_value=1
        gui=Mock();gui.GetWindowDC.return_value=12
        ui=Mock();source=ui.CreateDCFromHandle.return_value
        bitmap=ui.CreateBitmap.return_value
        bitmap.GetBitmapBits.return_value=b'\x01\x02\x03\x00'*(8*8)
        record={'id':'123','bounds':{'x':0,'y':0,'width':4,'height':4},
                'native_capture_bounds':{'x':-2,'y':-2,'width':8,'height':8}}
        with patch.dict(sys.modules,{'win32gui':gui,'win32ui':ui}):
            image=windows.capture(record)
        self.assertEqual(image.size,(4,4))
        windows.user32.PrintWindow.assert_called_once()
        gui.ReleaseDC.assert_called_once_with(123,12)
        gui.GetDC.assert_not_called()

    def test_mac_includes_offscreen_windows_for_explicit_restore(self):
        mac=Mac.__new__(Mac);mac.q=Mock()
        mac.q.kCGWindowListOptionAll=0;mac.q.kCGNullWindowID=0
        mac.q.CGWindowListCopyWindowInfo.return_value=[{'kCGWindowLayer':0,'kCGWindowOwnerPID':42,
            'kCGWindowNumber':7,'kCGWindowOwnerName':'Calculator','kCGWindowName':'Calculator',
            'kCGWindowIsOnscreen':False,'kCGWindowBounds':{'X':0,'Y':0,'Width':100,'Height':100}}]
        psutil=Mock();psutil.Process.return_value.create_time.return_value=123
        with patch.dict(sys.modules,{'psutil':psutil}):
            records=mac.list_windows();record=mac.record('7')
        self.assertTrue(record['minimized']);self.assertFalse(record['visible'])
        self.assertEqual(records[0]['id'],'7')

    def test_mac_exact_mapping_rejects_ambiguous_matches(self):
        mac=Mac.__new__(Mac)
        window={'id':'7','pid':42,'title':'Calculator','bounds':{'x':0,'y':0,'width':100,'height':100}}
        mac.list_windows=lambda:[window,dict(window,id='8')]
        ax=Mock();values={'AXPosition':'position','AXSize':'size','AXTitle':'Calculator'}
        ax.AXUIElementCopyAttributeValue.side_effect=lambda node,key,out:(0,values[key])
        ax.kAXValueCGPointType=1;ax.kAXValueCGSizeType=2
        ax.AXValueGetValue.side_effect=lambda value,kind,out:(True,SimpleNamespace(x=0,y=0)) if value=='position' else (True,SimpleNamespace(width=100,height=100))
        with patch.dict(sys.modules,{'ApplicationServices':ax}):
            self.assertIsNone(mac.ax_id('node',42))
            mac.list_windows=lambda:[window]
            self.assertEqual(mac.ax_id('node',42),'7')
