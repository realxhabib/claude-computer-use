import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.runtime import Runtime
from claude_computer_use.unicode_probe import PROBE_TEXT,CASES,payload_description


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.runtime=Runtime.__new__(Runtime);self.runtime.target={'id':'123'}
        self.runtime.verify=Mock()
        self.node=Mock();self.node.CurrentIsPassword=False
        self.node.CurrentNativeWindowHandle=0;self.node.CurrentControlType=50030
        self.node.CurrentIsEnabled=True;self.node.CurrentIsKeyboardFocusable=True
        self.node.CurrentName='Text Editor';self.node.CurrentClassName='RichEdit'
        self.node.GetRuntimeId.return_value=[42,1]
        self.api=Mock();self.api.GetFocusedElement.return_value=self.node
        ancestor=SimpleNamespace(CurrentNativeWindowHandle=123)
        self.api.ControlViewWalker.GetParentElement.return_value=ancestor
        self.wrapper=Mock();self.wrapper.iface_text.DocumentRange.GetAttributeValue.return_value=False
        self.wrapper.iface_text.DocumentRange.GetText.return_value=''
        self.modules={'pywinauto':SimpleNamespace(),
            'pywinauto.uia_defines':SimpleNamespace(IUIA=lambda:SimpleNamespace(iuia=self.api)),
            'pywinauto.uia_element_info':SimpleNamespace(UIAElementInfo=lambda node:node),
            'pywinauto.controls':SimpleNamespace(),
            'pywinauto.controls.uiawrapper':SimpleNamespace(UIAWrapper=lambda info:self.wrapper)}

    def test_real_probe_focus_contract_checks_ancestry_and_writability(self):
        with patch.dict(sys.modules,self.modules):state=self.runtime.probe_focus()
        self.assertEqual(state['runtime_id'],[42,1]);self.assertTrue(state['writable'])
        self.wrapper.iface_text.DocumentRange.GetAttributeValue.assert_called_once_with(40015)
        self.assertEqual(self.runtime.verify.call_count,2)

    def test_protected_field_is_not_read(self):
        self.node.CurrentIsPassword=True
        with patch.dict(sys.modules,self.modules):
            with self.assertRaisesRegex(RuntimeError,'protected'):self.runtime.probe_focus()
        self.wrapper.iface_text.DocumentRange.GetText.assert_not_called()

    def test_out_of_target_focus_is_not_read(self):
        self.api.ControlViewWalker.GetParentElement.return_value=None
        with patch.dict(sys.modules,self.modules):
            with self.assertRaisesRegex(RuntimeError,'outside target'):self.runtime.probe_focus()
        self.wrapper.iface_text.DocumentRange.GetText.assert_not_called()

    def test_readonly_unknown_or_non_editor_is_rejected(self):
        for value in [True,object()]:
            self.wrapper.iface_text.DocumentRange.GetAttributeValue.return_value=value
            with patch.dict(sys.modules,self.modules):
                with self.assertRaisesRegex(RuntimeError,'read-only'):self.runtime.probe_focus()
        self.wrapper.iface_text.DocumentRange.GetText.assert_not_called()
        self.node.CurrentControlType=50000
        with patch.dict(sys.modules,self.modules):
            with self.assertRaisesRegex(RuntimeError,'writable editor'):self.runtime.probe_focus()

    def test_fixed_payload_has_exact_cjk_units_and_surrogate_pair(self):
        result=payload_description(PROBE_TEXT)
        for code in ['65E5','672C','8A9E','D83D','DE00']:self.assertIn(code,result['utf16_units'])

    def test_diagnostic_cases_cover_latin_repeats_cjk_and_nonbmp(self):
        self.assertEqual(set(CASES),{'mixed','ascii-distinct','ascii-repeat','cjk','emoji'})
        self.assertEqual(CASES['ascii-distinct'],'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        self.assertIn('本本',CASES['cjk'])
        self.assertTrue(any(ord(c)>0xFFFF for c in CASES['emoji']))
