"""Restartable desktop leases over one persistent MCP connection."""
import asyncio
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from claude_computer_use import server


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(server, name, value) for name, value in
                        [('_worker', None), ('_activity', None), ('_session_state', 'idle'), ('_session_id', 0)]]
        self.factory = patch.object(server, 'make_activity', side_effect=self.make_activity)
        self.clients = patch.object(server, 'WorkerClient', side_effect=self.make_worker)
        self.patches += [self.factory, self.clients]
        for p in self.patches: p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])
        self.activities = []
        self.workers = []

    def make_worker(self, **kwargs):
        client = Mock(); client.epoch.return_value = 0
        client.cancel.side_effect = lambda: setattr(client.epoch, 'return_value', client.epoch.return_value + 1)
        self.workers.append(client)
        return client

    def make_activity(self, cancel, on_exit):
        obj = Mock(); obj.lock = threading.RLock(); obj.stopped.is_set.return_value = False
        obj.on_exit = on_exit
        obj.stop = lambda: (obj.stopped.is_set.__setattr__('return_value', True), cancel(), on_exit())
        self.activities.append(obj)
        return obj

    def test_idle_status_does_not_start_desktop_and_input_rejects(self):
        self.assertEqual(asyncio.run(server.computer_session_status())['state'], 'idle')
        for tool in (server.list_windows, server.screenshot, lambda: server.wait(0)):
            with self.assertRaisesRegex(RuntimeError, 'not active'): asyncio.run(tool())
        self.assertEqual(self.activities, []); self.assertEqual(self.workers, [])

    def test_repeated_start_end_has_fresh_worker_and_does_not_reconnect(self):
        for n in range(3):
            start = asyncio.run(server.start_computer_use())
            self.assertEqual(start['session_id'], n + 1)
            self.assertFalse(asyncio.run(server.start_computer_use())['started'])
            client = self.workers[-1]
            asyncio.run(server.end_computer_use())
            client.cancel.assert_called_once()
            self.activities[-1].close.assert_called_once()
            self.assertIsNone(server._worker); self.assertIsNone(server._activity)
            self.assertEqual(asyncio.run(server.computer_session_status())['state'], 'idle')
        self.assertEqual(len(self.workers), 3)

    def test_escape_latch_survives_end_and_requires_explicit_new_request(self):
        asyncio.run(server.start_computer_use())
        self.activities[-1].stop()
        asyncio.run(server.end_computer_use())
        with self.assertRaisesRegex(RuntimeError, 'User cancelled'): asyncio.run(server.start_computer_use())
        self.assertTrue(asyncio.run(server.start_computer_use(after_user_stop=True))['started'])

    def test_escape_during_end_is_retained_without_monitor_callback(self):
        asyncio.run(server.start_computer_use())
        activity = self.activities[-1]
        activity.close.side_effect = lambda: setattr(activity.stopped.is_set, 'return_value', True)
        ended = asyncio.run(server.end_computer_use())
        self.assertEqual(ended['state'], 'user_stopped')
        with self.assertRaisesRegex(RuntimeError, 'User cancelled'):
            asyncio.run(server.start_computer_use())
        self.assertTrue(asyncio.run(server.start_computer_use(after_user_stop=True))['started'])

    def test_late_old_stop_callback_cannot_stop_new_session(self):
        asyncio.run(server.start_computer_use()); old = self.activities[-1]
        asyncio.run(server.end_computer_use()); asyncio.run(server.start_computer_use())
        old.on_exit()
        self.assertEqual(server._session_state, 'active')

    def test_teardown_failure_keeps_controller_and_blocks_restart_until_cleanup(self):
        asyncio.run(server.start_computer_use()); activity = self.activities[-1]
        activity.close.side_effect = RuntimeError('restore failed')
        with self.assertRaisesRegex(RuntimeError, 'restore failed'): asyncio.run(server.end_computer_use())
        self.assertIs(server._activity, activity)
        with self.assertRaisesRegex(RuntimeError, 'cleanup failed'): asyncio.run(server.start_computer_use())
        activity.close.side_effect = None
        asyncio.run(server.end_computer_use())
        self.assertTrue(asyncio.run(server.start_computer_use())['started'])

    def test_end_fences_already_admitted_calls_and_waits(self):
        asyncio.run(server.start_computer_use())
        client, epoch, _ = server.admitted_session()
        asyncio.run(server.end_computer_use()); asyncio.run(server.start_computer_use())
        self.assertNotEqual(client.epoch(), epoch)
        self.assertIsNot(client, server._worker)

    def test_cancelled_start_cleans_up_new_session(self):
        entered = threading.Event(); release = threading.Event()
        original = self.make_activity
        def blocked(*args):
            entered.set(); release.wait(2); return original(*args)
        async def run():
            with patch.object(server, 'make_activity', side_effect=blocked):
                task = asyncio.create_task(server.start_computer_use())
                await asyncio.to_thread(entered.wait, 2)
                task.cancel(); release.set()
                with self.assertRaises(asyncio.CancelledError): await task
            self.assertEqual(server._session_state, 'idle')
            self.activities[-1].close.assert_called_once()
        asyncio.run(run())

    def test_repeated_cancellation_during_start_cannot_abandon_desktop(self):
        entered = threading.Event(); release = threading.Event()
        original = self.make_activity
        def blocked(*args):
            entered.set(); release.wait(2); return original(*args)
        async def run():
            with patch.object(server, 'make_activity', side_effect=blocked):
                task = asyncio.create_task(server.start_computer_use())
                await asyncio.to_thread(entered.wait, 2)
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
                release.set()
                with self.assertRaises(asyncio.CancelledError): await task
            self.assertEqual(server._session_state, 'idle')
            self.activities[-1].close.assert_called_once()
        asyncio.run(run())

    def test_main_opens_transport_without_acquiring_desktop(self):
        with patch.object(sys, 'argv', ['server']), patch.object(server.mcp, 'run') as run, patch.object(server.atexit, 'register'):
            server.main()
        run.assert_called_once_with(transport='stdio')
        self.assertEqual(self.activities, [])
