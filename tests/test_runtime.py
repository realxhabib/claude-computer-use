import io
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.runtime import Runtime
from claude_computer_use.accessibility import Inspector
from test_accessibility import Backend


class WindowsDouble:
    def __init__(self):
        self.window = {'id':'target','pid':42,'process_birth':123,'app':'Calculator','title':'Calc',
            'bounds':{'x':10,'y':20,'width':60,'height':40},'minimized':False,'visible':True}
        self.front='target'; self.capture_calls=0; self.covered=False; self.on_capture=None
    def record(self, id):
        if str(id) != self.window['id']: raise RuntimeError('closed')
        return deepcopy(self.window)
    def list_windows(self): return [deepcopy(self.window)]
    def foreground(self): return self.front
    def activate(self, window): self.front=window['id'];self.window['minimized']=False
    def at_point(self,x,y): return 'overlay' if self.covered else self.front
    def capture(self,window):
        self.capture_calls+=1
        if self.on_capture: self.on_capture()
        return Image.new('RGB',(120,80),(10,20,30))
    def diagnostics(self): return {'guidance':'Interactive session required','input_desktop_accessible':False}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.windows=WindowsDouble(); self.desktop=Mock()
        self.desktop.size.return_value=(1920,1080);self.desktop.position.return_value=(20,30)
        self.desktop.KEYBOARD_KEYS=['ctrl','a','command','enter']
        self.runtime=Runtime(self.windows,self.desktop,Inspector(Backend()))
        self.runtime.dispatch('bind_window',{'window_id':'target'})
        self.runtime.screenshot()
        self.windows.capture_calls=0

    def test_requires_binding_before_capture_or_input(self):
        self.runtime.target=None
        for method,args in [('screenshot',{}),('click',{'x':1,'y':1}),('inspect_ui',{}),('type_text',{'text':'a'})]:
            with self.assertRaisesRegex(RuntimeError,'No target'):self.runtime.dispatch(method,args)
        self.assertEqual(self.windows.capture_calls,0)
        self.desktop.click.assert_not_called()

    def test_rejects_foreground_before_capture_and_input(self):
        self.windows.front='unrelated'
        for method,args in [('screenshot',{}),('click',{'x':1,'y':1}),('inspect_ui',{}),('press_keys',{'keys':['ctrl','a']})]:
            with self.assertRaisesRegex(RuntimeError,'not foreground'):self.runtime.dispatch(method,args)
        self.assertEqual(self.windows.capture_calls,0);self.desktop.click.assert_not_called()

    def test_capture_race_discards_pixels_not_desktop_capture(self):
        self.windows.on_capture=lambda:setattr(self.windows,'front','unrelated')
        with self.assertRaisesRegex(RuntimeError,'not foreground'):self.runtime.screenshot()
        self.assertEqual(self.windows.capture_calls,1)
        self.desktop.screenshot.assert_not_called()

    def test_capture_provenance_and_retina_normalization(self):
        result=self.runtime.screenshot()
        self.assertEqual(Image.open(io.BytesIO(result['png'])).size,(60,40))
        self.assertEqual(result['provenance']['window_id'],'target')
        self.assertFalse(result['provenance']['desktop_capture_used'])
        self.desktop.screenshot.assert_not_called()

    def test_capture_frame_change_discards_result(self):
        self.windows.on_capture=lambda:self.windows.window['bounds'].update(x=11)
        with self.assertRaisesRegex(RuntimeError,'moved'):self.runtime.screenshot()

    def test_pid_reuse_rejected_before_capture(self):
        self.windows.window['process_birth']=456
        with self.assertRaisesRegex(RuntimeError,'identity'):self.runtime.screenshot()
        self.assertIsNone(self.runtime.target);self.assertEqual(self.windows.capture_calls,0)

    def test_recovery_is_explicit_and_invalidates_refs(self):
        self.ref=self.runtime.inspect_ui()['elements'][1]['id']
        self.windows.front='other'
        result=self.runtime.dispatch('activate_window',{})
        self.assertTrue(result['verified_foreground'])
        with self.assertRaises(ValueError):self.runtime.read_element(self.ref)

    def test_coordinates_are_window_local_and_occlusion_rejected(self):
        self.runtime.click(2,3)
        self.desktop.click.assert_called_once_with(12,23,clicks=1,interval=0.12,button='left')
        self.windows.covered=True;self.desktop.click.reset_mock()
        with self.assertRaisesRegex(RuntimeError,'occluded'):self.runtime.click(2,3)
        self.desktop.click.assert_not_called()

    def test_out_of_window_coordinates_and_secondary_display_rejected(self):
        with self.assertRaises(ValueError):self.runtime.click(60,0)
        self.windows.window['bounds']['x']=-10
        with self.assertRaisesRegex(RuntimeError,'primary'):self.runtime.bind_window('target')
        self.assertIsNone(self.runtime.target)

    def test_native_target_root_is_bound_and_partial_failures_expire_refs(self):
        ref=self.runtime.inspect_ui()['elements'][1]['id']
        self.assertEqual(self.runtime.inspector.backend.target_window['id'],'target')
        self.desktop.click.side_effect=RuntimeError('partial')
        with self.assertRaises(RuntimeError):self.runtime.dispatch('click',{'x':2,'y':2})
        with self.assertRaises(ValueError):self.runtime.read_element(ref)

    def test_unicode_input_and_no_clipboard_replacement(self):
        with patch('claude_computer_use.runtime.send_text') as send:
            result=self.runtime.type_text('café 日本語 😀',input_mode='batch')
            send.assert_called_once_with('café 日本語 😀')
            self.assertFalse(result['verified'])
        self.desktop.write.assert_not_called()

    def test_invalid_text_fails_before_any_typing(self):
        for text in ['\x00','\x1b','\x7f','\ud800','a'*10001]:
            with patch('claude_computer_use.runtime.send_text') as send:
                with self.assertRaises((ValueError,UnicodeEncodeError)):self.runtime.type_text(text)
                send.assert_not_called()

    def test_text_chunks_recheck_focus(self):
        def change_focus(text):self.windows.front='other'
        with patch('claude_computer_use.runtime.send_text',side_effect=change_focus) as send:
            with self.assertRaisesRegex(RuntimeError,'not foreground'):self.runtime.type_text('x'*32,input_mode='batch')
            self.assertEqual(send.call_count,1)

    def test_diagnostics_distinguish_com_error_from_corner(self):
        error=RuntimeError('COMError -2147220991');error.hresult=-2147220991
        self.runtime.inspector.backend.root=Mock(side_effect=error)
        self.desktop.position.return_value=(0,0)
        result=self.runtime.desktop_diagnostics()
        self.assertEqual(result['native_error']['hresult'],-2147220991)
        self.assertTrue(result['cursor_at_failsafe_corner'])
        self.assertEqual(result['native_access'],'unavailable')

    def test_truncated_deep_tree_retry(self):
        backend=self.runtime.inspector.backend
        backend.children=lambda node:[node+'x'] if len(node)<20 else []
        result=self.runtime.inspect_ui(max_depth=8)
        self.assertTrue(result['truncated'])
        result=self.runtime.find_elements(name='Save',max_depth=20)
        self.assertFalse(result['truncated'])
        self.assertGreater(len(result['elements']),8)

    def test_all_mutations_invalidate_refs_on_success_and_partial_failure(self):
        operations=[('click',{'x':2,'y':2},'click'),('move_mouse',{'x':2,'y':2},'moveTo'),
            ('drag',{'start_x':1,'start_y':1,'end_x':2,'end_y':2},'dragTo'),
            ('scroll',{'amount':-1,'x':2,'y':2},'scroll'),('press_keys',{'keys':['ctrl','a']},'hotkey')]
        for name,args,method in operations:
            for failure in (False,True):
                with self.subTest(tool=name,failure=failure):
                    ref=self.runtime.inspect_ui()['elements'][1]['id']
                    self.runtime.screenshot()
                    getattr(self.desktop,method).side_effect=RuntimeError('partial') if failure else None
                    if failure:
                        with self.assertRaises(RuntimeError):self.runtime.dispatch(name,args)
                    else:self.runtime.dispatch(name,args)
                    with self.assertRaises(ValueError):self.runtime.read_element(ref)
                    getattr(self.desktop,method).side_effect=None

    def test_list_apps_and_windows_do_not_require_binding(self):
        self.runtime.target=None
        self.assertEqual(self.runtime.list_apps()['apps'][0]['window_ids'],['target'])
        self.assertEqual(self.runtime.list_windows()['windows'][0]['pid'],42)

    def test_native_and_unicode_failsafe_stops_actions(self):
        ref=self.runtime.inspect_ui()['elements'][1]['id']
        self.desktop.failSafeCheck.side_effect=RuntimeError('failsafe')
        for method,args in [('act_on_element',{'element_id':ref}),('type_text',{'text':'日本'})]:
            with self.assertRaisesRegex(RuntimeError,'failsafe'):self.runtime.dispatch(method,args)
        self.assertEqual(self.runtime.inspector.backend.calls,[])

    def test_minimized_target_can_bind_before_explicit_restore(self):
        self.windows.window['minimized']=True
        self.runtime.dispatch('bind_window',{'window_id':'target'})
        with self.assertRaisesRegex(RuntimeError,'minimized'):self.runtime.screenshot()
        self.assertTrue(self.runtime.dispatch('activate_window',{})['verified_foreground'])

    def test_deep_search_absence_is_not_claimed_when_truncated(self):
        backend=self.runtime.inspector.backend
        backend.children=lambda node:[node+'x'] if len(node)<20 else []
        result=self.runtime.find_elements(name='does not exist',max_depth=8)
        self.assertEqual(result['elements'],[])
        self.assertTrue(result['truncated'])

    def test_frame_change_requires_new_capture_before_click(self):
        self.windows.window['bounds']['width']=61
        with self.assertRaisesRegex(RuntimeError,'fresh target screenshot'):self.runtime.click(2,3)
        self.desktop.click.assert_not_called()
        self.runtime.screenshot();self.runtime.click(2,3)

    def test_coordinate_mutation_requires_fresh_capture_for_next_action(self):
        self.runtime.dispatch('click',{'x':2,'y':3})
        with self.assertRaisesRegex(RuntimeError,'fresh target screenshot'):self.runtime.dispatch('click',{'x':2,'y':3})

    def test_injected_ids_remain_platform_neutral(self):
        for name in ['Windows','Darwin','Linux']:
            with self.subTest(platform=name),patch('claude_computer_use.runtime.platform.system',return_value=name):
                self.runtime.bind_window('target')
                self.assertEqual(self.runtime.verify()['id'],'target')
                self.assertTrue(self.runtime.activate_window()['verified_foreground'])

    def test_activation_denial_has_manual_recovery_guidance(self):
        self.windows.activate=Mock(side_effect=RuntimeError('(0, SetForegroundWindow, No error message is available)'))
        with self.assertRaisesRegex(RuntimeError,'Manually select'):self.runtime.dispatch('activate_window',{})
        self.desktop.hotkey.assert_not_called()

    def test_state_wait_does_not_score_async_dispatch_as_completion(self):
        records=[dict(self.windows.window,maximized=False),dict(self.windows.window,maximized=False),
                 dict(self.windows.window,maximized=True)]
        count=[0]
        def record(id):
            index=min(count[0],len(records)-1);count[0]+=1
            return deepcopy(records[index])
        self.windows.record=record
        with patch('claude_computer_use.runtime.time.sleep'):
            result=self.runtime.wait_for_window_state('maximized',1)
        self.assertTrue(result['window_state_verified'])
        self.assertGreaterEqual(count[0],5)

    def test_paced_unicode_guards_each_codepoint_and_stays_unverified(self):
        with patch('claude_computer_use.runtime.send_text') as send,patch('claude_computer_use.runtime.time.sleep'):
            result=self.runtime.type_text('日本😀',input_mode='paced')
            self.assertEqual([call.args[0] for call in send.call_args_list],['日','本','😀'])
        self.assertFalse(result['verified'])
        self.assertIn('CJK',result['warning'])

    def test_probe_rejects_nonempty_editor_without_input(self):
        with patch('claude_computer_use.runtime.platform.system',return_value='Windows'), \
                patch.object(self.runtime,'probe_focus',return_value={'text':'private','runtime_id':[1]}), \
                patch.object(self.runtime,'type_text') as send:
            with self.assertRaisesRegex(RuntimeError,'empty disposable editor'):self.runtime.unicode_probe('batch',True)
            send.assert_not_called()

    def test_probe_reports_japanese_loss_instead_of_success(self):
        before={'text':'','runtime_id':[1],'writable':True};after={'text':'café     😀\rsecond line\ttab','runtime_id':[1]}
        with patch('claude_computer_use.runtime.platform.system',return_value='Windows'), \
                patch.object(self.runtime,'probe_focus',side_effect=[before,before,after]), \
                patch.object(self.runtime,'type_text',return_value={'verified':False}), \
                patch('claude_computer_use.runtime.time.sleep'):
            result=self.runtime.unicode_probe('batch',True)
        self.assertFalse(result['matches_after_newline_normalization'])
        self.assertIn('U+65E5',result['fixed_payload']['codepoints'])
        self.assertNotIn('U+65E5',result['actual_payload']['codepoints'])

    def test_probe_editor_switch_prevents_initial_mutation(self):
        before={'text':'','runtime_id':[1],'writable':True};new={'text':'','runtime_id':[2],'writable':True}
        with patch('claude_computer_use.runtime.platform.system',return_value='Windows'), \
                patch.object(self.runtime,'probe_focus',side_effect=[before,new]), \
                patch.object(self.runtime,'type_text') as send:
            with self.assertRaisesRegex(RuntimeError,'changed before probe'):self.runtime.unicode_probe('batch',True)
            send.assert_not_called()

    def test_pinned_probe_editor_switch_stops_further_chunks(self):
        with patch.object(self.runtime,'probe_focus',side_effect=[{'runtime_id':[1]},{'runtime_id':[1]},{'runtime_id':[2]}]), \
                patch('claude_computer_use.runtime.send_text') as send, \
                patch('claude_computer_use.runtime.time.sleep'):
            with self.assertRaisesRegex(RuntimeError,'Focused editor changed'):
                self.runtime.type_text('日本',input_mode='paced',expected_editor_id=[1])
            self.assertEqual(send.call_count,1)

    def test_probe_tab_switches_field_and_next_text_is_rejected(self):
        field=[1]
        self.desktop.press.side_effect=lambda key:field.__setitem__(0,2) if key=='tab' else None
        with patch.object(self.runtime,'probe_focus',side_effect=lambda:{'runtime_id':list(field)}), \
                patch('claude_computer_use.runtime.send_text') as send:
            with self.assertRaisesRegex(RuntimeError,'Focused editor changed'):
                self.runtime.type_text('a\tb',input_mode='batch',expected_editor_id=[1])
        self.assertEqual([call.args[0] for call in send.call_args_list],['a'])

    def test_default_input_is_paced_and_fingerprint_matches_exact_payload(self):
        import hashlib
        with patch('claude_computer_use.runtime.send_text') as send,patch('claude_computer_use.runtime.time.sleep'):
            result=self.runtime.type_text('ab日本😀')
        self.assertEqual([call.args[0] for call in send.call_args_list],['a','b','日','本','😀'])
        self.assertEqual(result['received_text_sha256'],hashlib.sha256('ab日本😀'.encode('utf-8')).hexdigest())
        self.assertEqual(result['input_mode'],'paced')
        self.assertFalse(result['verified'])

    def test_oversized_paced_request_rejects_before_input(self):
        with patch('claude_computer_use.runtime.send_text') as send:
            with self.assertRaisesRegex(ValueError,'128 characters'):self.runtime.type_text('a'*129)
            send.assert_not_called()
        self.desktop.press.assert_not_called()
