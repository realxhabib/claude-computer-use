"""Desktop operations run exclusively inside a killable, stateful worker."""
import io
import platform
import time
from .diagnostics import checkpoint
from .validation import point, bounded
from .unicode_input import validate_text, send_text


class Runtime:
    MUTATIONS = {'bind_window', 'activate_window', 'click', 'move_mouse', 'drag',
                 'type_text', 'press_keys', 'scroll', 'act_on_element', 'unicode_probe'}

    def __init__(self, windows=None, desktop=None, inspector=None):
        from .windows import create_windows
        # Configure DPI before importing input/UIA libraries.
        checkpoint("runtime.windows_begin")
        self.windows = windows or create_windows()
        checkpoint("runtime.windows_end")
        if desktop is None:
            checkpoint("runtime.pyautogui_import_begin")
            import pyautogui
            checkpoint("runtime.pyautogui_import_end")
            desktop = pyautogui
        desktop.FAILSAFE = True
        desktop.PAUSE = 0.1
        self.desktop = desktop
        self.inspector = inspector
        self.target = None
        self.capture_frame = None

    def native(self):
        if self.inspector is None:
            from .accessibility import create_inspector
            self.inspector = create_inspector()
        if self.target is not None:
            self.inspector.backend.target_window = self.target
        return self.inspector

    def dispatch(self, method, arguments):
        try:
            return getattr(self, method)(**arguments)
        finally:
            if method in self.MUTATIONS:
                self.capture_frame = None
                if self.inspector is not None: self.inspector.invalidate()

    def list_windows(self):
        return {'windows': self.windows.list_windows(), 'limit': 300,
                'note': 'Visible titled windows on Windows; layer-zero application windows including off-screen/minimized entries on macOS. IDs must be bound explicitly.'}

    def list_apps(self):
        apps = {}
        for window in self.windows.list_windows():
            key = window['pid']
            apps.setdefault(key, {'pid': key, 'app': window['app'], 'window_ids': []})['window_ids'].append(window['id'])
        return {'apps': list(apps.values()), 'scope': 'apps with enumerated windows; not all background processes'}

    def bind_window(self, window_id: str):
        self.target = None
        self.capture_frame = None
        candidate = self.windows.record(window_id)
        if candidate['visible'] and not candidate['minimized']:
            self.check_geometry(candidate)
        self.target = candidate
        return {'target': self.target, 'foreground': self.windows.foreground() == self.target['id'],
                'next': 'Activate explicitly if needed. Coordinates are target-window local.'}

    def check_geometry(self, window):
        b = window['bounds']; w, h = self.desktop.size()
        if b['width'] <= 0 or b['height'] <= 0 or b['width'] * b['height'] > 40_000_000:
            raise RuntimeError('Invalid or oversized target frame')
        if b['x'] < 0 or b['y'] < 0 or b['x']+b['width'] > w or b['y']+b['height'] > h:
            raise RuntimeError('Target must be entirely on the primary display; reposition it and bind again')

    def verify(self, foreground=True):
        if self.target is None: raise RuntimeError('No target bound; list_windows then bind_window')
        old = self.target
        new = self.windows.record(old['id'])
        if any(new[k] != old[k] for k in ('id', 'pid', 'process_birth')):
            self.target = None
            raise RuntimeError('Target identity changed; re-list and bind')
        if new['minimized'] or not new['visible']: raise RuntimeError('Target is minimized or hidden; activate explicitly')
        self.check_geometry(new)
        if foreground and self.windows.foreground() != new['id']:
            raise RuntimeError('Target is not foreground; no capture/input performed. Use activate_window to recover')
        return new

    def activate_window(self):
        if self.target is None: raise RuntimeError('Bind a window first')
        # Validate ownership before raising/restoring a minimized window.
        new = self.windows.record(self.target['id'])
        if any(new[k] != self.target[k] for k in ('id', 'pid', 'process_birth')):
            self.target = None
            raise RuntimeError('Target identity changed; re-list and bind')
        self.desktop.failSafeCheck()
        try:self.windows.activate(new)
        except Exception as error:
            raise RuntimeError('OS foreground activation was denied or failed. Manually select the bound window using the taskbar/Dock or Alt-Tab, then retry. No focus-rule bypass is attempted; restore may already have occurred. Native error: '+str(error)[:512]) from error
        deadline = time.monotonic() + 1
        while self.windows.foreground() != new['id'] and time.monotonic() < deadline:
            time.sleep(0.05)
        return {'target': self.verify(), 'verified_foreground': True}

    def wait_for_window_state(self, state='stable', timeout=3):
        bounded(timeout, 0.1, 5)
        if state not in {'stable','visible','minimized','maximized','foreground'}:
            raise ValueError('Unsupported window state')
        if self.target is None:raise RuntimeError('Bind a target first')
        deadline=time.monotonic()+timeout
        last=None; consecutive=0
        while time.monotonic()<deadline:
            record=self.windows.record(self.target['id'])
            if any(record[k]!=self.target[k] for k in ('id','pid','process_birth')):
                self.target=None;raise RuntimeError('Target identity changed while waiting')
            if state=='maximized' and record.get('maximized') is None:
                raise RuntimeError('Maximized state is unavailable on this adapter')
            conditions={'stable':record['visible'] and not record['minimized'],
                'visible':record['visible'] and not record['minimized'],
                'minimized':record['minimized'], 'maximized':record.get('maximized') is True,
                'foreground':self.windows.foreground()==record['id']}
            signature=(record['bounds'],record['minimized'],record.get('maximized'),record['visible'])
            consecutive=consecutive+1 if conditions[state] and signature==last else (1 if conditions[state] else 0)
            if consecutive>=3:
                return {'window_state_verified':True,'requested_state':state,'window':record,
                        'note':'OS state sampled stable; app content/render completion still requires screenshot or native content verification.'}
            last=signature;time.sleep(0.075)
        raise TimeoutError('Expected window state not observed before timeout; do not score dispatch as completed')

    def computer_status(self):
        w, h = self.desktop.size(); x, y = self.desktop.position()
        return {'os': platform.system(), 'runtime_machine': platform.node()[:128],
                'session_mode': 'Shares this runtime desktop. An independent cursor requires running this server inside a separate VM/session.', 'screen_width': w, 'screen_height': h,
                'cursor': {'x': x, 'y': y}, 'target': self.target,
                'foreground_window_id': self.windows.foreground(),
                'coordinate_space': 'window-local coordinates for capture and mouse tools',
                'corner_failsafe_currently_active': (x, y) in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)],
                'note': 'A corner cursor does not diagnose whether this process has desktop access; run desktop_diagnostics.'}

    def desktop_diagnostics(self):
        result = self.windows.diagnostics()
        try:
            root = self.native().backend.root()
            self.native().backend.describe(root)
            result['native_access'] = 'available'
        except Exception as error:
            result['native_access'] = 'unavailable'
            result['native_error'] = {'type': type(error).__name__, 'message': str(error)[:512],
                'hresult': getattr(error, 'hresult', None)}
            result['guidance'] += ' Native errors indicate a session/sandbox/permission or provider failure; do not mislabel them as a mouse-corner failsafe.'
        try:
            x, y = self.desktop.position(); w, h = self.desktop.size()
            result['cursor_at_failsafe_corner'] = (x, y) in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]
        except Exception as error:
            result['cursor_error'] = type(error).__name__
        return result

    def screenshot(self):
        before = self.verify()
        image = self.windows.capture(before)  # Never captures primary desktop, even during races.
        after = self.verify()
        if before['bounds'] != after['bounds']:
            raise RuntimeError('Target moved during capture; pixels discarded, retry after reinspection')
        b = after['bounds']
        if image.size != (b['width'], b['height']):
            from PIL import Image
            image = image.resize((b['width'], b['height']), Image.Resampling.LANCZOS)
        buffer = io.BytesIO(); image.save(buffer, format='PNG')
        if buffer.tell() > 16_000_000:
            raise RuntimeError('Capture exceeds 16 MB; resize target window')
        self.capture_frame = dict(after['bounds'])
        return {'png': buffer.getvalue(), 'provenance': {
            'window_id': after['id'], 'pid': after['pid'], 'bounds': b,
            'coordinate_space': 'window-local', 'capture_api': 'PrintWindow' if platform.system() == 'Windows' else 'screencapture -l',
            'desktop_capture_used': False, 'foreground_verified_before_and_after': True}}

    def screen_point(self, x, y):
        target = self.verify(); b = target['bounds']
        if self.capture_frame != b:
            raise RuntimeError('Capture a fresh target screenshot before coordinate input; frame changed or snapshot invalidated')
        point(x, y, b['width'], b['height'])
        sx, sy = x+b['x'], y+b['y']
        if self.windows.at_point(sx, sy) != target['id']:
            raise RuntimeError('Point is occluded by another window; no input performed')
        return sx, sy

    def click(self, x, y, button='left', clicks=1):
        if button not in {'left','right','middle'} or clicks not in {1,2}: raise ValueError('Invalid click')
        sx, sy = self.screen_point(x, y)
        self.desktop.click(sx, sy, clicks=clicks, interval=0.12, button=button)
        return {'dispatched': True, 'verified': False}

    def move_mouse(self, x, y):
        sx, sy = self.screen_point(x, y); self.desktop.moveTo(sx, sy, duration=0.2)
        return {'dispatched': True, 'verified': False}

    def drag(self, start_x, start_y, end_x, end_y, duration=0.5):
        bounded(duration, 0.2, 3)
        start = self.screen_point(start_x, start_y); end = self.screen_point(end_x, end_y)
        self.desktop.moveTo(*start, duration=0.2)
        self.verify(); self.desktop.dragTo(*end, duration=duration, button='left')
        return {'dispatched': True, 'verified': False}

    def type_text(self, text, input_mode='paced', expected_editor_id=None):
        if input_mode not in {'batch','paced'}:raise ValueError('input_mode must be batch or paced')
        validate_text(text)
        if input_mode=='paced' and len(text)>128:
            raise ValueError('Paced input accepts at most 128 characters per call; split and verify chunks to avoid deterministic deadline overruns')
        self.verify(); self.desktop.failSafeCheck()
        # Guard between short Unicode chunks; do not use/overwrite the clipboard.
        chunk_size = 16 if input_mode == 'batch' else 1
        receipts = []
        def guard():
            self.verify();self.desktop.failSafeCheck()
            if expected_editor_id is not None and self.probe_focus()['runtime_id']!=expected_editor_id:
                raise RuntimeError('Focused editor changed; no further probe input dispatched')
        for start in range(0, len(text), chunk_size):
            chunk = text[start:start+chunk_size]
            self.verify(); self.desktop.failSafeCheck()
            if expected_editor_id is not None:
                focused=self.probe_focus()
                if focused['runtime_id']!=expected_editor_id:
                    raise RuntimeError('Focused editor changed; no further probe input dispatched')
            for segment in chunk.splitlines(keepends=True):
                pieces = segment.split('\t')
                for index, piece in enumerate(pieces):
                    if index: guard(); self.desktop.press('tab')
                    newline = piece.endswith('\n')
                    value = piece[:-1] if newline else piece
                    if value:
                        guard()
                        receipt = send_text(value,trace=True) if expected_editor_id is not None else send_text(value)
                        if isinstance(receipt,dict):receipts.append(receipt)
                    if newline: guard(); self.desktop.press('enter')
            if input_mode == 'paced':time.sleep(0.015)
        import hashlib
        return {'dispatched': True, 'verified': False, 'characters': len(text),
                'input_mode': input_mode, 'received_text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'native_receipts': receipts,
                'warning': 'Input-event acceptance does not verify editor content. Batch input corrupted CJK and Latin text in a measured Windows Notepad trial. Paced input passed one controlled smoke trial only; reliability and root cause remain unverified.'}


    def probe_focus(self):
        self.verify()
        from pywinauto.uia_defines import IUIA
        from pywinauto.uia_element_info import UIAElementInfo
        from pywinauto.controls.uiawrapper import UIAWrapper
        api=IUIA().iuia
        node=api.GetFocusedElement()
        if not node or node.CurrentIsPassword:
            raise RuntimeError('Focused editor missing or protected')
        ancestor=node
        for _ in range(64):
            if ancestor.CurrentNativeWindowHandle == int(self.target['id']):break
            ancestor=api.ControlViewWalker.GetParentElement(ancestor)
            if ancestor is None:raise RuntimeError('Focused element is outside target window')
        else:raise RuntimeError('Cannot establish focused editor ancestry')
        if node.CurrentControlType not in {50004,50030} or not node.CurrentIsEnabled or not node.CurrentIsKeyboardFocusable:
            raise RuntimeError('Focused control is not an enabled writable editor')
        wrapper=UIAWrapper(UIAElementInfo(node))
        read_only=wrapper.iface_text.DocumentRange.GetAttributeValue(40015)  # UIA_IsReadOnlyAttributeId
        if read_only not in (False,0):
            raise RuntimeError('Editor is read-only or writability is unknown')
        text=wrapper.iface_text.DocumentRange.GetText(512)
        state={'name':str(node.CurrentName)[:128],'class_name':str(node.CurrentClassName),
               'native_handle':node.CurrentNativeWindowHandle,
               'runtime_id':list(node.GetRuntimeId()),'writable':True,'text':text}
        self.verify()
        return state

    def unicode_probe(self, mode='observe', confirm_empty_editor=False, case='mixed'):
        if platform.system() != 'Windows':raise RuntimeError('This controlled probe is Windows-only')
        if mode not in {'observe','batch','paced'}:raise ValueError('Unknown probe mode')
        from .unicode_probe import CASES, payload_description
        if case not in CASES:raise ValueError('Unknown diagnostic case')
        text=CASES[case]
        before=self.probe_focus()
        result={'mode':mode,'case':case,'fixed_payload':payload_description(text),'before':before}
        if mode=='observe':
            actual=before['text'].replace('\r\n','\n').replace('\r','\n')
            result['observed_text_matches_case']=actual==text
            return result
        if not confirm_empty_editor or not before.get('writable') or before['text'].strip('\r\n')!='':
            raise RuntimeError('Probe requires an explicitly confirmed empty disposable editor; no input performed')
        current=self.probe_focus()
        if current['runtime_id']!=before['runtime_id'] or current['text'].strip('\r\n')!='':
            raise RuntimeError('Focused editor or empty state changed before probe; no input performed')
        result['dispatch']=self.type_text(text,input_mode=mode,expected_editor_id=before['runtime_id'])
        time.sleep(0.5)
        after=self.probe_focus()
        result['after']=after
        result['same_editor']=before['runtime_id']==after['runtime_id']
        actual=after['text'].replace('\r\n','\n').replace('\r','\n')
        result['matches_after_newline_normalization']=result['same_editor'] and actual==text
        result['actual_payload']=payload_description(after['text'])
        return result

    def press_keys(self, keys):
        if not 1 <= len(keys) <= 5 or len(set(keys)) != len(keys) or any(k not in self.desktop.KEYBOARD_KEYS for k in keys):
            raise ValueError('Provide one to five distinct supported key names')
        self.verify(); self.desktop.hotkey(*keys)
        return {'dispatched': True, 'verified': False}

    def scroll(self, amount, x, y):
        if not -20 <= amount <= 20: raise ValueError('Scroll amount must be -20..20')
        sx, sy = self.screen_point(x, y); self.desktop.scroll(amount, x=sx, y=sy)
        return {'dispatched': True, 'verified': False}

    def inspect_ui(self, max_nodes=150, max_depth=8):
        self.verify()
        result = self.native().inspect(max_nodes, max_depth)
        self.verify()
        result['target_window_id'] = self.target['id']
        return result

    def find_elements(self, name='', role='', exact=False, max_nodes=150, max_depth=8):
        if not name and not role: raise ValueError('Provide a name or role')
        result = self.inspect_ui(max_nodes, max_depth)
        def match(value, query):
            return not query or (value.casefold()==query.casefold() if exact else query.casefold() in value.casefold())
        result['elements'] = [e for e in result['elements'] if match(e['name'], name) and match(e['role'], role)]
        return result

    def read_element(self, element_id):
        self.verify(); return self.native().read(element_id)

    def act_on_element(self, element_id, action='activate'):
        self.verify(); self.desktop.failSafeCheck()
        return self.native().act(element_id, action)

    def wait(self, seconds=0.5):
        bounded(seconds, 0, 3); time.sleep(seconds)
        return {'waited': seconds}
