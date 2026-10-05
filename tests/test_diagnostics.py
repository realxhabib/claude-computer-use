import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.diagnostics import checkpoint

class DiagnosticsTests(unittest.TestCase):
    def test_opt_in_phase_log_contains_no_request_content(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'CLAUDE_COMPUTER_DIAGNOSTICS_DIR':root}):
            checkpoint('worker.dispatch_begin')
            row=json.loads(next(Path(root).glob('phases-*.jsonl')).read_text())
        self.assertEqual(set(row),{'stage','pid','thread','monotonic','wall_time'})
        self.assertEqual(row['stage'],'worker.dispatch_begin')
    def test_unwritable_diagnostics_do_not_disrupt_worker(self):
        with patch.dict(os.environ,{'CLAUDE_COMPUTER_DIAGNOSTICS_DIR':'bad'}),patch('pathlib.Path.mkdir',side_effect=OSError('denied')):
            checkpoint('worker.bootstrap')
