"""Actual spawned processes: hanging call, cancellation, crash and restart."""
import sys
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.worker import WorkerClient


def fake_worker(connection):
    try:
        while True:
            method,args=connection.recv()
            if method=='child':
                import os,subprocess
                child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
                from pathlib import Path
                Path(os.environ['CLAUDE_COMPUTER_CAPTURE_DIR'],'sensitive.png').write_bytes(b'test')
                connection.send(('ok',{'child_pid':child.pid,'capture_dir':os.environ['CLAUDE_COMPUTER_CAPTURE_DIR']}))
            elif method=='hang':time.sleep(60)
            elif method=='crash':return
            elif method=='large':connection.send(('ok',b'x'*2_000_000))
            elif method=='error':connection.send(('error','mock error'))
            else:connection.send(('ok',{'target':None,'method':method}))
    except (EOFError,OSError):pass
    finally:connection.close()


class WorkerTests(unittest.TestCase):
    def test_hard_deadline_kills_and_next_request_starts_unbound(self):
        client=WorkerClient(timeout=0.5,entrypoint=fake_worker)
        try:
            started=time.monotonic()
            with self.assertRaisesRegex(TimeoutError,'worker killed'):client.call('hang',{})
            self.assertLess(time.monotonic()-started,2)
            self.assertIsNone(client._process)
            self.assertIsNone(client.call('status',{})['target'])
        finally:client.cancel()

    def test_cancel_can_interrupt_concurrent_call(self):
        client=WorkerClient(timeout=10,entrypoint=fake_worker);errors=[]
        def call():
            try:client.call('hang',{})
            except Exception as error:errors.append(error)
        thread=threading.Thread(target=call);thread.start()
        try:
            deadline=time.monotonic()+2
            while client._process is None and time.monotonic()<deadline:time.sleep(0.01)
            self.assertTrue(client.cancel());thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual(len(errors),1)
            self.assertIsNone(client.call('status',{})['target'])
        finally:client.cancel();thread.join(timeout=2)

    def test_crash_clears_state_and_errors_do_not_replay(self):
        client=WorkerClient(timeout=2,entrypoint=fake_worker)
        try:
            with self.assertRaisesRegex(RuntimeError,'outcome uncertain'):client.call('crash',{})
            self.assertIsNone(client._process)
            with self.assertRaisesRegex(RuntimeError,'mock error'):client.call('error',{})
            self.assertEqual(len(client.call('large',{})),2_000_000)
        finally:client.cancel()

    def test_cancel_fences_already_queued_requests_and_idle_requests(self):
        client=WorkerClient(timeout=2,entrypoint=fake_worker)
        epoch=client.epoch();errors=[]
        client._serial.acquire()
        def queued():
            try:client.call('bind_window',{},epoch=epoch)
            except Exception as error:errors.append(error)
        thread=threading.Thread(target=queued);thread.start()
        try:
            client.cancel()
            client._serial.release()
            thread.join(timeout=2)
            self.assertEqual(len(errors),1)
            self.assertIn('cancelled before dispatch',str(errors[0]))
            self.assertIsNone(client._process)
            self.assertIsNone(client.call('status',{})['target'])
            newer=client._process
            self.assertFalse(client.cancel(epoch=epoch))
            self.assertIs(client._process,newer)
        finally:client.cancel();thread.join(timeout=2)

    def test_cancel_stops_helper_and_removes_parent_owned_capture_directory(self):
        import psutil
        client=WorkerClient(timeout=2,entrypoint=fake_worker)
        result=client.call('child',{})
        try:
            child=psutil.Process(result['child_pid'])
            self.assertTrue(Path(result['capture_dir'],'sensitive.png').exists())
            client.cancel()
            self.assertFalse(Path(result['capture_dir']).exists())
            deadline=time.monotonic()+1
            while child.is_running() and child.status()!=psutil.STATUS_ZOMBIE and time.monotonic()<deadline:time.sleep(0.01)
            self.assertTrue(not child.is_running() or child.status()==psutil.STATUS_ZOMBIE)
        finally:client.cancel()
