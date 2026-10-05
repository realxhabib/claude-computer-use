"""Actual hard-killed process cannot orphan a ProcessSignal owner lock."""
import multiprocessing
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.signals import ProcessSignal


def wait_in_child(signal, ready):
    ready.set();signal.wait(60)


class SignalTests(unittest.TestCase):
    def test_set_clear_and_deadline(self):
        flag=ProcessSignal();self.assertFalse(flag.wait(.01))
        flag.set();self.assertTrue(flag.wait(0));flag.clear();self.assertFalse(flag.is_set())
    def test_hard_killed_waiter_does_not_block_parent_set(self):
        ctx=multiprocessing.get_context('spawn');signal=ProcessSignal(ctx);ready=ProcessSignal(ctx)
        child=ctx.Process(target=wait_in_child,args=(signal,ready));child.start()
        try:
            self.assertTrue(ready.wait(3));child.kill();child.join(2)
            self.assertFalse(child.is_alive())
            before=time.monotonic();signal.set()
            self.assertLess(time.monotonic()-before,.1);self.assertTrue(signal.is_set())
        finally:
            if child.is_alive():child.kill();child.join(2)


def hold_lock_in_child(lock,ready):
    with lock:
        ready.set();time.sleep(60)


class LockTests(unittest.TestCase):
    def test_dead_owner_has_bounded_failure(self):
        from claude_computer_use.signals import BoundedProcessLock
        ctx=multiprocessing.get_context('spawn');lock=BoundedProcessLock(ctx);ready=ProcessSignal(ctx)
        child=ctx.Process(target=hold_lock_in_child,args=(lock,ready));child.start()
        try:
            self.assertTrue(ready.wait(3));child.kill();child.join(2)
            before=time.monotonic()
            with self.assertRaisesRegex(RuntimeError,'coordination'):
                with lock:pass
            self.assertLess(time.monotonic()-before,.5)
        finally:
            if child.is_alive():child.kill();child.join(2)


class GuardCleanupTests(unittest.TestCase):
    def test_actual_guard_close_returns_after_waiter_killed(self):
        from claude_computer_use.native_cursor import NativeCursorGuard
        ctx=multiprocessing.get_context('spawn');signal=ProcessSignal(ctx);ready=ProcessSignal(ctx)
        child=ctx.Process(target=wait_in_child,args=(signal,ready));child.start()
        guard=NativeCursorGuard.__new__(NativeCursorGuard)
        guard.shutdown=signal;guard.changed=ProcessSignal(ctx);guard.process=child
        try:
            self.assertTrue(ready.wait(3));child.kill();child.join(2)
            before=time.monotonic();guard.close()
            self.assertLess(time.monotonic()-before,.5)
        finally:
            if child.is_alive():child.kill();child.join(2)


class ReadinessTests(unittest.TestCase):
    def test_dead_initializer_returns_without_ten_second_wait(self):
        from unittest.mock import Mock
        from claude_computer_use.signals import wait_for_process_ready
        ready=ProcessSignal();process=Mock();process.is_alive.return_value=False
        before=time.monotonic();self.assertFalse(wait_for_process_ready(ready,process,10))
        self.assertLess(time.monotonic()-before,.1)
