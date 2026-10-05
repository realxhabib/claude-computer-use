"""Native-adapter contracts with doubles, not real Windows/macOS validation."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from claude_computer_use.accessibility import WindowsBackend, MacBackend, create_inspector



class AdapterTests(unittest.TestCase):
    def windows_node(self):
        node = Mock()
        node.element_info = SimpleNamespace(runtime_id=[1, 2, 3], name='Save',
            control_type='Button', element=SimpleNamespace(CurrentIsPassword=False,
                CurrentHasKeyboardFocus=True, CurrentIsKeyboardFocusable=True))
        node.rectangle.return_value = SimpleNamespace(left=10, top=20,
            width=lambda: 30, height=lambda: 40)
        node.is_enabled.return_value = True
        node.is_visible.return_value = True
        return node

    def test_windows_state_and_native_dispatch(self):
        backend = WindowsBackend.__new__(WindowsBackend)
        node = self.windows_node()
        state = backend.describe(node)
        self.assertEqual(state['name'], 'Save')
        self.assertTrue(state['focused'])
        self.assertEqual(state['actions'], ['focus', 'activate'])
        self.assertEqual(backend.identity(node), (1, 2, 3))
        backend.act(node, 'activate')
        node.iface_invoke.Invoke.assert_called_once_with()
        backend.act(node, 'focus')
        node.set_focus.assert_called_once_with()

    def test_windows_protected_and_nonfocusable(self):
        backend = WindowsBackend.__new__(WindowsBackend)
        node = self.windows_node()
        node.element_info.element.CurrentIsKeyboardFocusable = False
        node.element_info.element.CurrentIsPassword = True
        state = backend.describe(node)
        self.assertEqual(state['name'], '[protected]')
        self.assertNotIn('focus', state['actions'])

    def mac_backend(self, attrs):
        backend = MacBackend.__new__(MacBackend)
        backend.ax = Mock()
        backend.ax.AXUIElementCopyAttributeValue.side_effect = lambda node, key, output: (
            (0, attrs[key]) if key in attrs else (-25205, None))
        backend.ax.AXUIElementCopyActionNames.return_value = (0, ['AXPress'])
        backend.ax.AXUIElementIsAttributeSettable.return_value = (0, True)
        return backend

    def test_mac_state_and_action_error_handling(self):
        backend = self.mac_backend({'AXRole': 'AXButton', 'AXTitle': 'Save',
            'AXEnabled': True, 'AXFocused': False})
        state = backend.describe('node')
        self.assertEqual(state['name'], 'Save')
        self.assertIsNone(state['visible'])
        self.assertFalse(state['focused'])
        backend.ax.AXUIElementPerformAction.return_value = 0
        backend.act('node', 'activate')
        backend.ax.AXUIElementPerformAction.assert_called_once_with('node', 'AXPress')
        backend.ax.AXUIElementSetAttributeValue.return_value = -25204
        with self.assertRaises(RuntimeError): backend.act('node', 'focus')

    def test_mac_protected_fields_and_unsupported_actions(self):
        backend = self.mac_backend({'AXRole': 'AXTextField', 'AXTitle': 'private',
            'AXSubrole': 'AXSecureTextField'})
        backend.ax.AXUIElementCopyActionNames.return_value = (-25205, None)
        backend.ax.AXUIElementIsAttributeSettable.return_value = (-25205, False)
        state = backend.describe('node')
        self.assertEqual(state['name'], '[protected]')
        self.assertEqual(state['actions'], [])

    def test_macos_trust_failure_and_foreground_window(self):
        ax = Mock()
        ax.AXIsProcessTrusted.return_value = False
        appkit = SimpleNamespace(NSWorkspace=Mock())
        with patch.dict(sys.modules, {'ApplicationServices': ax, 'AppKit': appkit}):
            with self.assertRaisesRegex(RuntimeError, 'Accessibility'): MacBackend()
            ax.AXIsProcessTrusted.return_value = True
            backend = MacBackend()
            backend.workspace.frontmostApplication.return_value.processIdentifier.return_value = 123
            ax.AXUIElementCreateApplication.return_value = 'app'
            ax.AXUIElementCopyAttributeValue.return_value = (0, 'window')
            self.assertEqual(backend.root(), 'window')
            ax.AXUIElementCreateApplication.assert_called_once_with(123)

    def test_platform_routing(self):
        for os_name, adapter in [('Windows', 'WindowsBackend'), ('Darwin', 'MacBackend')]:
            with patch('claude_computer_use.accessibility.platform.system', return_value=os_name), \
                    patch('claude_computer_use.accessibility.' + adapter) as factory:
                self.assertIs(create_inspector().backend, factory.return_value)
        with patch('claude_computer_use.accessibility.platform.system', return_value='Linux'):
            with self.assertRaisesRegex(RuntimeError, 'Windows and macOS'): create_inspector()

