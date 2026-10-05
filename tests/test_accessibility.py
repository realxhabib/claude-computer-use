import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from claude_computer_use.accessibility import Inspector


class Backend:
    def __init__(self):
        self.window = 'window'
        self.data = {'name': 'Save', 'role': 'Button', 'enabled': True,
                     'visible': True, 'protected': False, 'actions': ['activate', 'focus']}
        self.calls = []

    def root(self): return self.window
    def identity(self, node): return node
    def describe(self, node): return dict(self.data)
    def children(self, node): return ['button'] if node == self.window else []
    def act(self, node, action): self.calls.append((node, action))


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.backend = Backend()
        self.inspector = Inspector(self.backend, lambda: self.now)
        self.ref = self.inspector.inspect()['elements'][1]['id']

    def test_dispatch_requires_verification_and_invalidates_ids(self):
        result = self.inspector.act(self.ref, 'activate')
        self.assertFalse(result['verified'])
        self.assertEqual(self.backend.calls, [('button', 'activate')])
        with self.assertRaises(ValueError): self.inspector.act(self.ref, 'activate')

    def test_expired_ref_cannot_act(self):
        self.now = 31
        with self.assertRaises(ValueError): self.inspector.act(self.ref, 'activate')
        self.assertEqual(self.backend.calls, [])

    def test_foreground_change_cannot_act(self):
        self.backend.window = 'other-window'
        with self.assertRaises(ValueError): self.inspector.act(self.ref, 'activate')

    def test_changed_label_cannot_act(self):
        self.backend.data['name'] = 'Delete'
        with self.assertRaises(ValueError): self.inspector.act(self.ref, 'activate')

    def test_disabled_hidden_protected_unsupported(self):
        for key, value in [('enabled', False), ('visible', False), ('protected', True), ('actions', [])]:
            with self.subTest(key=key):
                backend = Backend()
                inspector = Inspector(backend)
                ref = inspector.inspect()['elements'][1]['id']
                backend.data[key] = value
                with self.assertRaises(ValueError): inspector.act(ref, 'activate')
                self.assertEqual(backend.calls, [])

    def test_bounded_tree_marks_truncation(self):
        result = self.inspector.inspect(max_nodes=1)
        self.assertEqual(len(result['elements']), 1)
        self.assertTrue(result['truncated'])

    def test_new_inspection_invalidates_old_refs(self):
        self.inspector.inspect()
        with self.assertRaises(ValueError): self.inspector.read(self.ref)

    def test_failed_dispatch_invalidates_references(self):
        def partial_action(*args): raise RuntimeError('may have acted')
        self.backend.act = partial_action
        with self.assertRaises(RuntimeError): self.inspector.act(self.ref, 'activate')
        with self.assertRaises(ValueError): self.inspector.read(self.ref)

    def test_long_labels_are_bounded_but_full_label_checked(self):
        self.backend.data['name'] = 'x' * 2000
        self.backend.data['role'] = 'r' * 1000
        data = self.inspector.inspect()['elements'][1]
        self.assertEqual(len(data['name']), 512)
        self.assertEqual(len(data['role']), 128)
        self.assertTrue(data['label_truncated'])
        self.backend.data['name'] += 'changed suffix'
        with self.assertRaises(ValueError): self.inspector.act(data['id'], 'activate')
