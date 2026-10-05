"""OS window adapters. Captures use window APIs, never a desktop screenshot."""
import io
import os
import subprocess
import tempfile
from pathlib import Path


class Windows:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        # Configure DPI before PyAutoGUI/UIA imports. Coordinates are physical pixels.
        self.user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetAncestor.restype = wintypes.HWND
        self.user32.WindowFromPoint.argtypes = [wintypes.POINT]
        self.user32.WindowFromPoint.restype = wintypes.HWND

    def record(self, hwnd):
        hwnd = int(hwnd)  # OS adapter owns handle conversion; doubles need not mimic HWNDs.
        import win32gui, win32process, psutil
        if not win32gui.IsWindow(hwnd):
            raise RuntimeError('Window no longer exists')
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        native_bounds = {'x': left, 'y': top, 'width': right-left, 'height': bottom-top}
        # Maximized Win32 rects often include an off-screen invisible resize border.
        rect = self.wintypes.RECT()
        dwm = self.ctypes.WinDLL('dwmapi')
        dwm.DwmGetWindowAttribute.argtypes = [self.wintypes.HWND, self.wintypes.DWORD,
                                             self.ctypes.c_void_p, self.wintypes.DWORD]
        if dwm.DwmGetWindowAttribute(hwnd, 9, self.ctypes.byref(rect), self.ctypes.sizeof(rect)) == 0:
            left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        return {'id': str(hwnd), 'pid': pid, 'process_birth': process.create_time(),
                'app': process.name(), 'title': win32gui.GetWindowText(hwnd)[:512],
                'bounds': {'x': left, 'y': top, 'width': right-left, 'height': bottom-top},
                'native_capture_bounds': native_bounds, 'visible': bool(win32gui.IsWindowVisible(hwnd)),
                'minimized': bool(win32gui.IsIconic(hwnd)),
                'maximized': win32gui.GetWindowPlacement(hwnd)[1] == 3}

    def list_windows(self):
        import win32gui
        result = []
        def collect(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                try: result.append(self.record(hwnd))
                except Exception: pass
            return len(result) < 300
        win32gui.EnumWindows(collect, None)
        return result

    def foreground(self):
        return str(self.user32.GetForegroundWindow())

    def activate(self, window):
        import win32gui, win32con
        hwnd = int(window['id'])
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Windows may deny foreground activation. Never claim success without verification.
        win32gui.SetForegroundWindow(hwnd)

    def at_point(self, x, y):
        hwnd = self.user32.WindowFromPoint(self.wintypes.POINT(x, y))
        return str(self.user32.GetAncestor(hwnd, 2))

    def capture(self, window):
        import win32gui, win32ui
        from PIL import Image
        hwnd = int(window['id'])
        bounds = window.get('native_capture_bounds', window['bounds'])
        w, h = bounds['width'], bounds['height']
        dc = win32gui.GetWindowDC(hwnd)
        source = memory = bitmap = None
        try:
            source = win32ui.CreateDCFromHandle(dc)
            memory = source.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(source, w, h)
            memory.SelectObject(bitmap)
            self.user32.PrintWindow.argtypes = [self.wintypes.HWND, self.wintypes.HDC, self.wintypes.UINT]
            if not self.user32.PrintWindow(hwnd, memory.GetSafeHdc(), 2):
                raise RuntimeError('Window capture unavailable; no desktop fallback is permitted')
            image = Image.frombuffer('RGB', (w, h), bitmap.GetBitmapBits(True), 'raw', 'BGRX', 0, 1)
            visible = window['bounds']
            x, y = visible['x']-bounds['x'], visible['y']-bounds['y']
            if x < 0 or y < 0 or x+visible['width'] > w or y+visible['height'] > h:
                raise RuntimeError('Visible/native frame mismatch; capture discarded')
            return image.crop((x, y, x+visible['width'], y+visible['height']))
        finally:
            if memory: memory.DeleteDC()
            if source: source.DeleteDC()
            if bitmap: win32gui.DeleteObject(bitmap.GetHandle())
            if dc: win32gui.ReleaseDC(hwnd, dc)

    def diagnostics(self):
        import ctypes
        user32 = self.user32
        user32.OpenInputDesktop.argtypes = [self.wintypes.DWORD, self.wintypes.BOOL, self.wintypes.DWORD]
        user32.OpenInputDesktop.restype = self.wintypes.HANDLE
        handle = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
        accessible = bool(handle)
        error = None if accessible else ctypes.get_last_error()
        if handle:
            user32.CloseDesktop.argtypes = [self.wintypes.HANDLE]
            user32.CloseDesktop(handle)
        return {'input_desktop_accessible': accessible, 'win32_error': error,
                'guidance': 'Run in an unlocked interactive user session. Sandboxes, services, UAC and a different session can block desktop/UIA access. A cursor at (0,0) alone does not prove a user-triggered failsafe.'}


class Mac:
    def __init__(self):
        import Quartz
        from AppKit import NSWorkspace
        self.q, self.workspace = Quartz, NSWorkspace.sharedWorkspace()

    def list_windows(self):
        import psutil
        result = []
        info = self.q.CGWindowListCopyWindowInfo(self.q.kCGWindowListOptionAll,
                                               self.q.kCGNullWindowID) or []
        for item in info:
            if item.get('kCGWindowLayer') != 0: continue
            pid = int(item['kCGWindowOwnerPID'])
            try: birth = psutil.Process(pid).create_time()
            except Exception: continue
            b = item['kCGWindowBounds']
            result.append({'id': str(item['kCGWindowNumber']), 'pid': pid,
                'process_birth': birth, 'app': item.get('kCGWindowOwnerName', ''),
                'title': str(item.get('kCGWindowName', ''))[:512],
                'bounds': {'x': int(b['X']), 'y': int(b['Y']), 'width': int(b['Width']), 'height': int(b['Height'])},
                'visible': bool(item.get('kCGWindowIsOnscreen', False)),
                'minimized': not bool(item.get('kCGWindowIsOnscreen', False)), 'maximized': None})
            if len(result) == 300: break
        return result

    def record(self, window_id):
        return next((w for w in self.list_windows() if w['id'] == str(window_id)), None) or self.missing()

    @staticmethod
    def missing():
        raise RuntimeError('Window is no longer on screen; re-list windows')

    def ax_id(self, node, pid):
        import ApplicationServices as ax
        def attr(key):
            error, value = ax.AXUIElementCopyAttributeValue(node, key, None)
            return value if error == 0 else None
        # Public AX geometry/title crosswalk; never pick the first ambiguous window.
        position, size = attr('AXPosition'), attr('AXSize')
        if position is None or size is None: return None
        ok1, pos = ax.AXValueGetValue(position, ax.kAXValueCGPointType, None)
        ok2, extent = ax.AXValueGetValue(size, ax.kAXValueCGSizeType, None)
        if not ok1 or not ok2: return None
        title = attr('AXTitle') or ''
        matches = []
        for window in self.list_windows():
            b = window['bounds']
            if window['pid'] == pid and (not title or window['title'] == title) and all(
                abs(a-z) <= 2 for a, z in zip((pos.x, pos.y, extent.width, extent.height),
                                             (b['x'], b['y'], b['width'], b['height']))):
                matches.append(window['id'])
        return matches[0] if len(matches) == 1 else None

    def ax_window(self, window):
        import ApplicationServices as ax
        app = ax.AXUIElementCreateApplication(window['pid'])
        error, nodes = ax.AXUIElementCopyAttributeValue(app, 'AXWindows', None)
        for node in (nodes or []) if error == 0 else []:
            if self.ax_id(node, window['pid']) == window['id']: return node
        raise RuntimeError('Exact AX/CG window mapping unavailable or ambiguous')

    def foreground(self):
        import ApplicationServices as ax
        app = self.workspace.frontmostApplication()
        if app is None: return None
        pid = app.processIdentifier()
        error, node = ax.AXUIElementCopyAttributeValue(ax.AXUIElementCreateApplication(pid), 'AXFocusedWindow', None)
        return self.ax_id(node, pid) if error == 0 and node is not None else None

    def activate(self, window):
        import ApplicationServices as ax
        from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(window['pid'])
        if app is None or not app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps):
            raise RuntimeError('Application activation refused')
        node = self.ax_window(window)
        err, miniaturized = ax.AXUIElementCopyAttributeValue(node, 'AXMinimized', None)
        if err == 0 and miniaturized:
            err = ax.AXUIElementSetAttributeValue(node, 'AXMinimized', False)
            if err: raise RuntimeError(f'Window restore failed: {err}')
        error = ax.AXUIElementPerformAction(node, 'AXRaise')
        if error: raise RuntimeError(f'AXRaise failed: {error}')

    def at_point(self, x, y):
        info = self.q.CGWindowListCopyWindowInfo(self.q.kCGWindowListOptionOnScreenOnly,
                                               self.q.kCGNullWindowID) or []
        for item in info:
            if (str(item.get('kCGWindowOwnerPID')) == os.environ.get('CLAUDE_COMPUTER_ACTIVITY_PID')
                    and item.get('kCGWindowName') == 'Claude computer use pointer halo'):
                continue  # Only our named, input-transparent halo; banner still occludes.
            b = item['kCGWindowBounds']
            if b['X'] <= x < b['X']+b['Width'] and b['Y'] <= y < b['Y']+b['Height']:
                return str(item['kCGWindowNumber'])
        return None

    def capture(self, window):
        from PIL import Image
        if hasattr(self.q, 'CGPreflightScreenCaptureAccess') and not self.q.CGPreflightScreenCaptureAccess():
            raise RuntimeError('Grant Screen Recording permission before window capture')
        with tempfile.TemporaryDirectory(prefix='claude-window-',dir=os.environ.get('CLAUDE_COMPUTER_CAPTURE_DIR')) as directory:
            path = Path(directory)/'capture.png'
            result = subprocess.run(['/usr/sbin/screencapture', '-x', '-o', '-l', window['id'], str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=4)
            if result.returncode or not path.exists():
                raise RuntimeError('Window capture failed; no desktop fallback is permitted')
            with Image.open(path) as image: return image.convert('RGB').copy()

    def diagnostics(self):
        import ApplicationServices as ax
        return {'accessibility_trusted': bool(ax.AXIsProcessTrusted()),
                'screen_capture_allowed': bool(self.q.CGPreflightScreenCaptureAccess()),
                'guidance': 'Grant Accessibility and Screen Recording to the actual launcher/runtime, then restart. Use an unlocked interactive session.'}


def create_windows():
    import platform
    if platform.system() == 'Windows': return Windows()
    if platform.system() == 'Darwin': return Mac()
    raise RuntimeError('An interactive Windows or macOS desktop is required')
