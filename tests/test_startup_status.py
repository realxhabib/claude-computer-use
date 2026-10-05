import asyncio
import multiprocessing
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from claude_computer_use.startup_status import StartupStatus, run_startup_target


def failing_indicator(startup_status):
    startup_status.phase('qt_import')
    raise ImportError('synthetic missing Qt dependency')


def stalled_indicator(startup_status):
    startup_status.phase('listener_wait')
    time.sleep(60)


class StartupStatusTests(unittest.TestCase):
    def test_exception_phase_reaches_parent_when_spawned_from_async_thread(self):
        async def launch():
            ctx=multiprocessing.get_context('spawn');status=StartupStatus(ctx)
            process=ctx.Process(target=run_startup_target,args=(status,failing_indicator,()))
            await asyncio.to_thread(process.start)
            await asyncio.to_thread(process.join, 5)
            try:
                self.assertFalse(process.is_alive())
                detail=status.describe(process)
                self.assertIn('child exited before readiness',detail)
                self.assertIn('phase=qt_import',detail)
                self.assertIn('ImportError: synthetic missing Qt dependency',detail)
                self.assertIn('exitcode=1',detail)
            finally:
                if process.is_alive(): process.kill();process.join(2)
        asyncio.run(launch())

    def test_stall_report_keeps_original_phase_and_live_state_before_kill(self):
        ctx=multiprocessing.get_context('spawn');status=StartupStatus(ctx)
        process=ctx.Process(target=run_startup_target,args=(status,stalled_indicator,()))
        process.start()
        try:
            deadline=time.monotonic()+5
            while status.phase_bytes.value != b'listener_wait' and time.monotonic()<deadline:
                time.sleep(.01)
            detail=status.describe(process)
            self.assertIn('phase=listener_wait',detail)
            self.assertIn('readiness deadline expired',detail)
            self.assertIn('exitcode=None',detail)
        finally:
            if process.is_alive(): process.kill()
            process.join(2)

    def test_failure_before_entry_and_bounded_trace(self):
        ctx=multiprocessing.get_context('spawn');status=StartupStatus(ctx)
        process=Mock(pid=42,exitcode=1);process.is_alive.return_value=False
        self.assertIn('phase=spawn_pending',status.describe(process))
        try: raise RuntimeError('x'*10000)
        except RuntimeError: status.record_exception()
        self.assertLessEqual(len(status.error_bytes.value),4095)
