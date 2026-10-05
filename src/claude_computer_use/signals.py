"""Single-byte process flags without owner-held locks vulnerable to hard termination."""
import multiprocessing
import time


class ProcessSignal:
    def __init__(self, context=None):
        ctx=context or multiprocessing.get_context('spawn')
        self.flag=ctx.RawValue('b',0)
    def is_set(self):return bool(self.flag.value)
    def set(self):self.flag.value=1
    def clear(self):self.flag.value=0
    def wait(self, timeout=None):
        deadline=None if timeout is None else time.monotonic()+timeout
        while not self.is_set():
            if deadline is not None:
                remaining=deadline-time.monotonic()
                if remaining<=0:return False
                time.sleep(min(.01,remaining))
            else:time.sleep(.01)
        return True


class BoundedProcessLock:
    """A dead owner fails the operation instead of hanging UI or MCP admission."""
    def __init__(self, context=None, timeout=.1):
        ctx=context or multiprocessing.get_context('spawn')
        self.lock=ctx.Lock();self.timeout=timeout
    def __enter__(self):
        if not self.lock.acquire(timeout=self.timeout):
            raise RuntimeError('Computer-use coordination lock unavailable; stop and restart the server')
        return self
    def __exit__(self,*_):self.lock.release()


def wait_for_process_ready(ready, process, timeout=10):
    """Fail promptly if initialization exits; do not wait the full readiness budget."""
    deadline=time.monotonic()+timeout
    while not ready.is_set():
        if not process.is_alive():return False
        remaining=deadline-time.monotonic()
        if remaining<=0:return False
        ready.wait(min(.01,remaining))
    return process.is_alive()
