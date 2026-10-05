"""Native Unicode injection, without replacing the clipboard."""
import ctypes
import platform


def validate_text(text):
    if len(text) > 10000 or any((ord(c) < 32 and c not in '\n\t') or ord(c) == 127 for c in text):
        raise ValueError('Use at most 10000 characters; only tab/newline control characters')
    # Reject lone surrogates before any input is dispatched.
    text.encode('utf-16-le')


def windows_send(text, trace=False):
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', ctypes.c_uint16), ('wScan', ctypes.c_uint16),
                    ('dwFlags', ctypes.c_uint32), ('time', ctypes.c_uint32), ('dwExtraInfo', ctypes.c_size_t)]
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', ctypes.c_int32), ('dy', ctypes.c_int32), ('mouseData', ctypes.c_uint32),
                    ('dwFlags', ctypes.c_uint32), ('time', ctypes.c_uint32), ('dwExtraInfo', ctypes.c_size_t)]
    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', ctypes.c_uint32), ('wParamL', ctypes.c_uint16), ('wParamH', ctypes.c_uint16)]
    class Union(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]
    class INPUT(ctypes.Structure):
        _anonymous_ = ('u',)
        _fields_ = [('type', ctypes.c_uint32), ('u', Union)]
    raw = text.encode('utf-16-le')
    units = [int.from_bytes(raw[i:i+2], 'little') for i in range(0, len(raw), 2)]
    events = []
    for unit in units:
        for flags in (4, 6):
            event = INPUT(); event.type = 1
            event.ki = KEYBDINPUT(0, unit, flags, 0, 0)
            events.append(event)
    if not events: return {'accepted_input_events':0,'expected_input_events':0,'utf16_units':0}
    array = (INPUT * len(events))(*events)
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SendInput.argtypes = [ctypes.c_uint32, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = ctypes.c_uint32
    prepared = [array[i].ki.wScan for i in range(0,len(events),2)] if trace else None
    sent = user32.SendInput(len(events), array, ctypes.sizeof(INPUT))
    if sent != len(events):
        raise RuntimeError('Unicode input partially dispatched or denied (possibly integrity/session boundary); inspect before retrying')
    result={'accepted_input_events':sent,'expected_input_events':len(events),'utf16_units':len(units)}
    if trace:result['prepared_scan_units']=[f'{unit:04X}' for unit in prepared]
    return result


def mac_send(text):
    import Quartz as q
    for down in (True, False):
        event = q.CGEventCreateKeyboardEvent(None, 0, down)
        q.CGEventKeyboardSetUnicodeString(event, len(text.encode('utf-16-le')) // 2, text)
        q.CGEventPost(q.kCGHIDEventTap, event)


def send_text(text, trace=False):
    validate_text(text)
    if platform.system() == 'Windows': return windows_send(text, trace=True) if trace else windows_send(text)
    elif platform.system() == 'Darwin': return mac_send(text)
    else: raise RuntimeError('Unicode injection requires Windows or macOS')
