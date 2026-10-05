import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.activity import Activity

class ActivityTests(unittest.TestCase):
    def controller(self):
        obj=Activity.__new__(Activity)
        obj.process=Mock();obj.process.is_alive.return_value=True
        obj.stopped=threading.Event();obj.acknowledged=threading.Event();obj.lock=threading.Lock()
        return obj
    def test_escape_latches_cancel_once_and_blocks(self):
        obj=self.controller();cancel=Mock();obj.stopped.set()
        obj.poll_stop(cancel);obj.poll_stop(cancel)
        cancel.assert_called_once();self.assertTrue(obj.acknowledged.is_set())
        with self.assertRaises(RuntimeError):obj.check()
    def test_companion_death_cancels_and_cannot_resume(self):
        obj=self.controller();obj.process.is_alive.return_value=False;cancel=Mock()
        obj.poll_stop(cancel);cancel.assert_called_once()
        obj.stopped.clear()
        with self.assertRaises(RuntimeError):obj.check()
    def test_cancel_failure_does_not_enable_resume(self):
        obj=self.controller();obj.stopped.set()
        with self.assertRaises(RuntimeError):obj.poll_stop(Mock(side_effect=RuntimeError('kill failed')))
        self.assertFalse(obj.acknowledged.is_set())
        with self.assertRaises(RuntimeError):obj.check()

    def test_resume_ack_requires_worker_stop_and_cursor_restoration(self):
        obj=self.controller();obj.stopped.set();obj.cursor_guard=Mock();obj.cursor_guard.process.is_alive.return_value=True
        events=[];obj.cursor_guard.wait_restored.side_effect=lambda:events.append('restore')
        obj.poll_stop(lambda:events.append('cancel'))
        self.assertEqual(events,['cancel','restore']);self.assertTrue(obj.acknowledged.is_set())
    def test_cursor_restore_failure_keeps_resume_disabled(self):
        obj=self.controller();obj.stopped.set();obj.cursor_guard=Mock();obj.cursor_guard.process.is_alive.return_value=True
        obj.cursor_guard.wait_restored.side_effect=RuntimeError('restore failed')
        with self.assertRaises(RuntimeError):obj.poll_stop(Mock())
        self.assertFalse(obj.acknowledged.is_set())

    def test_dead_guard_restore_failure_still_cancels_native_work_first(self):
        obj=self.controller();obj.cursor_guard=Mock();obj.cursor_guard.process.is_alive.return_value=False
        obj.cursor_guard.wait_restored.side_effect=RuntimeError('fallback failed')
        cancel=Mock()
        with self.assertRaises(RuntimeError):obj.poll_stop(cancel)
        cancel.assert_called_once();self.assertTrue(obj.stopped.is_set());self.assertFalse(obj.acknowledged.is_set())

    def test_coordination_failure_still_cancels_before_lock(self):
        obj=self.controller();obj.stopped.set()
        obj.lock=Mock();obj.lock.__enter__=Mock(side_effect=RuntimeError('orphaned'))
        obj.lock.__exit__=Mock();cancel=Mock()
        with self.assertRaises(RuntimeError):obj.poll_stop(cancel)
        cancel.assert_called_once();self.assertFalse(obj.acknowledged.is_set())

    def test_terminal_stop_restores_closes_then_exits(self):
        obj=self.controller();obj.stopped.set();obj.cursor_guard=Mock();obj.cursor_guard.process.is_alive.return_value=True
        order=[];obj.cursor_guard.wait_restored.side_effect=lambda:order.append('restore')
        obj.close=Mock(side_effect=lambda:order.append('close'))
        obj.on_exit=Mock(side_effect=lambda:order.append('exit'))
        self.assertTrue(obj.finish_stop(lambda:order.append('cancel')))
        self.assertEqual(order,['cancel','restore','close','exit'])
        self.assertTrue(obj.stopped.is_set())
    def test_terminal_cleanup_failure_does_not_exit_without_restoration(self):
        obj=self.controller();obj.stopped.set();obj.on_exit=Mock();obj.close=Mock(side_effect=RuntimeError('cleanup failed'))
        with self.assertRaises(RuntimeError):obj.finish_stop(Mock())
        obj.on_exit.assert_not_called()
    def test_running_session_does_not_exit(self):
        obj=self.controller();obj.close=Mock();obj.on_exit=Mock()
        self.assertFalse(obj.finish_stop(Mock()));obj.close.assert_not_called();obj.on_exit.assert_not_called()

    def test_unconfirmed_companion_termination_prevents_terminal_exit(self):
        obj=self.controller();obj.cursor_guard=None;obj.shutdown=threading.Event();obj.stopped.set();obj.on_exit=Mock()
        with self.assertRaisesRegex(RuntimeError,'termination not confirmed'):
            obj.finish_stop(Mock())
        obj.on_exit.assert_not_called();obj.process.kill.assert_called_once()
    def test_close_is_idempotent(self):
        obj=self.controller();obj.cursor_guard=None;obj.shutdown=threading.Event();obj.process.is_alive.return_value=False
        obj.close();obj.close();self.assertEqual(obj.process.join.call_count,1)
