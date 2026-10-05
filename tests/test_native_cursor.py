import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.native_cursor import CursorLease,ARROW_ID

class CursorLeaseTests(unittest.TestCase):
    def api(self):
        api=Mock();api.snapshot.return_value='original';api.arrow.return_value='custom';api.copy.return_value='disposable-original'
        return api
    def test_restore_installs_copy_and_never_consumes_snapshot(self):
        api=self.api();lease=CursorLease(api);lease.capture();lease.activate();lease.restore();lease.close()
        self.assertEqual([x.args[0] for x in api.install.call_args_list],['custom','disposable-original'])
        api.copy.assert_called_once_with('original');api.destroy.assert_called_once_with('original')
    def test_partial_install_failure_restores_original(self):
        api=self.api();api.install.side_effect=[RuntimeError('partial'),None]
        lease=CursorLease(api);lease.capture()
        with self.assertRaises(RuntimeError):lease.activate()
        lease.close();self.assertFalse(lease.changed)
        self.assertEqual(api.install.call_args_list[-1].args,('disposable-original',))
    def test_repeated_cycles_preserve_one_original_snapshot(self):
        api=self.api();lease=CursorLease(api);lease.capture()
        for _ in range(3):lease.activate();lease.restore()
        lease.close();api.snapshot.assert_called_once();self.assertEqual(api.copy.call_count,3)
    def test_only_normal_arrow_slot_selected(self):self.assertEqual(ARROW_ID,32512)

class WindowsAPIContractTests(unittest.TestCase):
    def api(self):
        from claude_computer_use.native_cursor import WindowsCursor
        api=WindowsCursor.__new__(WindowsCursor);api.c=Mock();api.u=Mock();api.k=Mock();api.mutex=None
        return api
    def test_mutex_collision_does_not_change_cursor(self):
        api=self.api();api.k.CreateMutexW.return_value=123;api.c.get_last_error.return_value=183
        with self.assertRaisesRegex(RuntimeError,'Another'):api.acquire()
        api.k.CloseHandle.assert_called_once_with(123);api.u.SetSystemCursor.assert_not_called()
    def test_cursor_copy_does_not_return_shared_original(self):
        api=self.api();api.u.CopyImage.return_value=456
        self.assertEqual(api.copy(123),456)
        api.u.CopyImage.assert_called_once_with(123,2,0,0,0)
    def test_scheme_reload_failure_is_not_acknowledged(self):
        api=self.api();api.u.SystemParametersInfoW.return_value=False
        with self.assertRaises(RuntimeError):api.reload_scheme()

class RestorationEpochTests(unittest.TestCase):
    def test_old_restore_event_cannot_acknowledge_resumed_cycle(self):
        import threading
        from types import SimpleNamespace
        from claude_computer_use.native_cursor import NativeCursorGuard
        guard=NativeCursorGuard.__new__(NativeCursorGuard)
        guard.restored=threading.Event();guard.restored.set()
        guard.restored_epoch=SimpleNamespace(value=0)
        self.assertTrue(guard.restoration_matches(0))
        # Resume increments epoch; old stopped-cycle Event may remain set.
        self.assertFalse(guard.restoration_matches(1))
        # Restore from the current cycle, not a prior restore, enables acknowledgement.
        guard.restored_epoch.value=1
        self.assertTrue(guard.restoration_matches(1))

class GuardLifecycleTests(unittest.TestCase):
    def events(self):
        import threading
        from types import SimpleNamespace
        return [threading.Event() for _ in range(5)]+[SimpleNamespace(value=-1),SimpleNamespace(value=0)]
    def test_real_guard_loop_restores_across_resume_generations(self):
        from unittest.mock import patch
        from claude_computer_use.native_cursor import cursor_guard_main
        ready,restored,changed,stopped,shutdown,restored_epoch,epoch=self.events()
        api=Mock();api.snapshot.return_value='original';api.arrow.return_value='custom';api.copy.return_value='copy-original'
        iterations=[]
        def tick(_):
            iterations.append(1)
            if len(iterations)==1:stopped.set()
            elif len(iterations)==2:epoch.value+=1;stopped.clear()
            elif len(iterations)==3:stopped.set()
            else:shutdown.set()
        with patch('claude_computer_use.native_cursor.WindowsCursor',return_value=api),patch('psutil.Process'),patch('claude_computer_use.worker_entry.parent_matches',return_value=True),patch.object(shutdown,'wait',side_effect=tick):
            cursor_guard_main(ready,restored,restored_epoch,epoch,__import__("threading").Lock(),changed,stopped,shutdown,1,1,2,2)
        self.assertEqual([x.args[0] for x in api.install.call_args_list],['custom','copy-original','custom','copy-original'])
        self.assertEqual(restored_epoch.value,1);self.assertTrue(restored.is_set());self.assertFalse(changed.is_set())
        api.destroy.assert_called_once_with('original');api.release.assert_called_once()
    def test_partial_install_failure_restores_and_never_signals_ready(self):
        from unittest.mock import patch
        from claude_computer_use.native_cursor import cursor_guard_main
        ready,restored,changed,stopped,shutdown,restored_epoch,epoch=self.events()
        api=Mock();api.snapshot.return_value='original';api.arrow.return_value='custom';api.copy.return_value='copy-original'
        api.install.side_effect=[RuntimeError('partial'),None]
        with patch('claude_computer_use.native_cursor.WindowsCursor',return_value=api),patch('psutil.Process'),patch('claude_computer_use.worker_entry.parent_matches',return_value=True):
            cursor_guard_main(ready,restored,restored_epoch,epoch,__import__("threading").Lock(),changed,stopped,shutdown,1,1,2,2)
        self.assertFalse(ready.is_set());self.assertTrue(stopped.is_set());self.assertTrue(restored.is_set())
        self.assertEqual(api.install.call_args_list[-1].args,('copy-original',))


class CursorStateConcurrencyTests(unittest.TestCase):
    def test_guard_cannot_read_partial_resume_pair(self):
        import threading
        from claude_computer_use.native_cursor import resume_cursor,cursor_state
        entered=threading.Event();release=threading.Event();sampled=threading.Event()
        class Epoch:
            def __init__(self):self._value=0
            @property
            def value(self):return self._value
            @value.setter
            def value(self,value):
                self._value=value;entered.set();release.wait(2)
        epoch=Epoch();stopped=threading.Event();stopped.set();lock=threading.Lock();samples=[]
        resume=threading.Thread(target=resume_cursor,args=(lock,epoch,stopped));resume.start()
        self.assertTrue(entered.wait(1))
        def sample():samples.append(cursor_state(lock,epoch,stopped));sampled.set()
        guard=threading.Thread(target=sample);guard.start()
        try:
            self.assertFalse(sampled.wait(.05))
        finally:release.set();resume.join(1);guard.join(1)
        self.assertEqual(samples,[(1,False)])

class GuardTerminationTests(unittest.TestCase):
    def test_unconfirmed_root_termination_does_not_report_cleanup_success(self):
        import threading
        from unittest.mock import patch
        from claude_computer_use.native_cursor import NativeCursorGuard
        guard=NativeCursorGuard.__new__(NativeCursorGuard);guard.shutdown=threading.Event();guard.process=Mock();guard.process.pid=123
        guard.process.is_alive.return_value=True;guard.fallback=Mock()
        root=Mock();root.children.return_value=[]
        with patch('psutil.Process',return_value=root),patch('psutil.wait_procs',return_value=([],[])):
            with self.assertRaisesRegex(RuntimeError,'root termination not confirmed'):guard.close()
        guard.fallback.assert_not_called()
