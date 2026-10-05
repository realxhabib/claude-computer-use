"""Private Windows pipe inheritance and subprocess lifecycle contracts."""
import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.worker import launch_windows_worker,SubprocessWorker,WorkerClient

class LaunchTests(unittest.TestCase):
    def test_launcher_detaches_stdio_and_inherits_only_private_handle(self):
        child=Mock();child.fileno.return_value=123
        startup=Mock();process=Mock();process.pid=456
        with patch.object(subprocess,'STARTUPINFO',return_value=startup,create=True),patch.object(subprocess,'CREATE_NO_WINDOW',0x08000000,create=True),patch('os.get_handle_inheritable',return_value=False,create=True),patch('os.set_handle_inheritable',create=True) as inherit,patch.object(subprocess,'Popen',return_value=process) as launch:
            result=launch_windows_worker(child,'capture',8)
        self.assertEqual(result.pid,456)
        self.assertEqual(startup.lpAttributeList,{'handle_list':[123]})
        self.assertEqual(inherit.call_args_list[0].args,(123,True));self.assertEqual(inherit.call_args_list[-1].args,(123,False))
        args,kwargs=launch.call_args
        self.assertIn('claude_computer_use.worker_entry',args[0])
        self.assertEqual(kwargs['stdin'],subprocess.DEVNULL);self.assertEqual(kwargs['stdout'],subprocess.DEVNULL)
        self.assertTrue(kwargs['close_fds']);self.assertIsNone(kwargs['stderr'])
    def test_failed_launch_restores_handle_inheritance(self):
        child=Mock();child.fileno.return_value=123
        with patch.object(subprocess,'STARTUPINFO',return_value=Mock(),create=True),patch.object(subprocess,'CREATE_NO_WINDOW',0,create=True),patch('os.get_handle_inheritable',return_value=False,create=True),patch('os.set_handle_inheritable',create=True) as inherit,patch.object(subprocess,'Popen',side_effect=OSError('failed')):
            with self.assertRaises(OSError):launch_windows_worker(child,'capture',8)
        self.assertEqual(inherit.call_args_list[-1].args,(123,False))
    def test_existing_handle_inheritance_state_is_restored(self):
        child=Mock();child.fileno.return_value=123
        with patch.object(subprocess,'STARTUPINFO',return_value=Mock(),create=True),patch.object(subprocess,'CREATE_NO_WINDOW',0,create=True),patch('os.get_handle_inheritable',return_value=True,create=True),patch('os.set_handle_inheritable',create=True) as inherit,patch.object(subprocess,'Popen',return_value=Mock()):
            launch_windows_worker(child,'capture',8)
        self.assertEqual(inherit.call_args_list[-1].args,(123,True))

    def test_join_timeout_preserves_alive_process(self):
        process=Mock();process.poll.return_value=None;process.wait.side_effect=subprocess.TimeoutExpired('worker',.1)
        worker=SubprocessWorker(process);worker.join(.1)
        self.assertTrue(worker.is_alive());worker.kill();process.kill.assert_called_once()

@unittest.skipUnless(sys.platform=='win32','Native Windows inherited pipe test')
class NativeLaunchTests(unittest.TestCase):
    def test_minimal_entry_point_real_pipe_ping_and_cancel(self):
        client=WorkerClient(timeout=8)
        try:
            result=client.call('_worker_ping',{})
            import psutil
            root=psutil.Process(client._process.pid)
            owned=[root]+root.children(recursive=True)
            # A Windows venv Python launcher may forward to a descendant interpreter.
            self.assertIn(result['worker_pid'],{process.pid for process in owned})
            self.assertFalse(result['runtime_initialized'])
            self.assertIsInstance(client._process,SubprocessWorker)
            self.assertTrue(client.cancel());self.assertIsNone(client._process)
            _,alive=psutil.wait_procs(owned,timeout=.5)
            self.assertEqual(alive,[], 'Owned launcher/interpreter processes survived cancellation')
        finally:client.cancel()


class ParentWatchTests(unittest.TestCase):
    def test_parent_identity_change_or_access_failure_rejects(self):
        import psutil
        from claude_computer_use.worker_entry import parent_matches
        parent=Mock();parent.is_running.return_value=True;parent.create_time.return_value=123.5
        self.assertTrue(parent_matches(parent,123.5))
        self.assertFalse(parent_matches(parent,123.4))
        parent.create_time.side_effect=psutil.AccessDenied(123)
        self.assertFalse(parent_matches(parent,123.5))
        parent.create_time.side_effect=psutil.NoSuchProcess(123)
        self.assertFalse(parent_matches(parent,123.5))
