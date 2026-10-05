import ctypes
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.unicode_input import windows_send,mac_send,validate_text,send_text


class UnicodeTests(unittest.TestCase):
    def test_windows_utf16_surrogate_pairs_and_key_up_abi(self):
        dll=Mock();captured=[]
        def inject(count,events,size):
            captured.append((size,[(e.type,e.ki.wScan,e.ki.dwFlags) for e in events]))
            return count
        dll.SendInput.side_effect=inject
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):windows_send('é😀')
        size,events=captured[0]
        self.assertEqual(size,40 if ctypes.sizeof(ctypes.c_void_p)==8 else 28)
        self.assertEqual(events,[(1,233,4),(1,233,6),(1,0xD83D,4),(1,0xD83D,6),(1,0xDE00,4),(1,0xDE00,6)])

    def test_windows_partial_dispatch_reports_uncertainty(self):
        dll=Mock();dll.SendInput.return_value=1
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
            with self.assertRaisesRegex(RuntimeError,'partially'):windows_send('日本')

    def test_macos_unicode_length_is_utf16_units_not_codepoints(self):
        q=Mock();q.kCGHIDEventTap=0
        q.CGEventCreateKeyboardEvent.side_effect=['down','up']
        with patch.dict(sys.modules,{'Quartz':q}):mac_send('é😀')
        self.assertEqual(q.CGEventKeyboardSetUnicodeString.call_args_list[0].args,('down',3,'é😀'))
        self.assertEqual(q.CGEventKeyboardSetUnicodeString.call_args_list[1].args,('up',3,'é😀'))
        self.assertEqual(q.CGEventPost.call_count,2)

    def test_validation_happens_before_native_input(self):
        for value in ['\x00','\x7f','\ud800','a'*10001]:
            with patch('claude_computer_use.unicode_input.windows_send') as native:
                with self.assertRaises((ValueError,UnicodeEncodeError)):send_text(value)
                native.assert_not_called()
        validate_text('café 日本語 😀\n\t')

    def test_cjk_scan_units_are_exact_and_receipts_are_not_editor_verification(self):
        dll=Mock();captured=[]
        def inject(count,events,size):
            captured.extend((e.ki.wScan,e.ki.dwFlags) for e in events)
            return count
        dll.SendInput.side_effect=inject
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):receipt=windows_send('日本語')
        self.assertEqual(captured,[(0x65E5,4),(0x65E5,6),(0x672C,4),(0x672C,6),(0x8A9E,4),(0x8A9E,6)])
        self.assertEqual(receipt['accepted_input_events'],6)
        self.assertNotIn('verified',receipt)

    def test_diagnostic_receipt_records_constructed_array_scans_not_delivery(self):
        dll=Mock();dll.SendInput.return_value=6
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):receipt=windows_send('日本語',trace=True)
        self.assertEqual(receipt['prepared_scan_units'],['65E5','672C','8A9E'])
        self.assertNotIn('delivered',receipt)
        self.assertNotIn('verified',receipt)
