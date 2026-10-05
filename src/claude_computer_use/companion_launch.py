"""Windows desktop companions launched without multiprocessing's main bootstrap.

Shared ctypes and semaphore transfer use CPython multiprocessing's reducers.
The receiving PID comes from the private inherited pipe and must belong to the
launched process tree (venv launchers may have an interpreter child).
"""
import multiprocessing
import os
import subprocess
import sys
import time


class CompanionProcess:
    owns_process_tree = True
    def __init__(self, process):
        import psutil
        self.process = process
        self.root = psutil.Process(process.pid)
        self.actual = None

    @property
    def pid(self):
        return self.actual.pid if self.actual is not None else self.process.pid

    @property
    def exitcode(self):
        return self.process.poll()

    def is_alive(self):
        return self.process.poll() is None or (self.actual is not None and self.actual.is_running())

    def attach(self, pid):
        owned = [self.root] + self.root.children(recursive=True)
        found = next((p for p in owned if p.pid == pid), None)
        if found is None or not found.is_running():
            raise RuntimeError('Companion handshake PID is not in the launched process tree')
        found.create_time()  # Cache process identity before later PID reuse.
        self.actual = found

    def kill(self):
        import psutil
        owned = []
        try:
            if self.root.is_running():
                self.root.suspend()
                owned = self.root.children(recursive=True)
        except psutil.NoSuchProcess:
            pass
        if self.actual is not None and self.actual not in owned:
            owned.append(self.actual)
        for child in reversed(owned):
            try: child.kill()
            except psutil.NoSuchProcess: pass
        if self.process.poll() is None: self.process.kill()
        _, alive = psutil.wait_procs(owned, timeout=1)
        if alive: raise RuntimeError('Companion descendant termination not confirmed')

    def join(self, timeout=None):
        import psutil
        deadline = None if timeout is None else time.monotonic() + timeout
        try: self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired: return
        if self.actual is not None:
            remaining = None if deadline is None else max(0, deadline - time.monotonic())
            try: self.actual.wait(timeout=remaining)
            except psutil.TimeoutExpired: pass


class HandleTransfer:
    def __init__(self, pid):
        import _winapi
        self.handle = _winapi.OpenProcess(_winapi.PROCESS_DUP_HANDLE, False, pid)

    def duplicate_for_child(self, handle):
        from multiprocessing.reduction import duplicate
        return duplicate(handle, self.handle)

    def close(self):
        import _winapi
        _winapi.CloseHandle(self.handle)


def serialize_arguments(target, args, actual_pid, shutdown=None, restores_cursor=False):
    from multiprocessing import context, reduction
    transfer = HandleTransfer(actual_pid)
    previous = context.get_spawning_popen()
    context.set_spawning_popen(transfer)  # Thread-local; no global spawn monkeypatch.
    try:
        payload = bytes(reduction.ForkingPickler.dumps((target, args, shutdown, restores_cursor)))
        if len(payload) > 4096:
            raise RuntimeError('Companion bootstrap exceeds private-pipe payload limit')
        return payload
    finally:
        context.set_spawning_popen(previous)
        transfer.close()


def launch_windows_companion(target, args, timeout=10, shutdown=None, restores_cursor=False):
    import psutil
    parent, child = multiprocessing.get_context('spawn').Pipe()
    process = None
    raw = None
    deadline = time.monotonic() + timeout
    handle = child.fileno()
    inherited_before = os.get_handle_inheritable(handle)
    try:
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {'handle_list': [handle]}
        os.set_handle_inheritable(handle, True)
        try:
            raw = subprocess.Popen([sys.executable, '-m', 'claude_computer_use.companion_entry',
                '--pipe-handle', str(handle), '--parent-pid', str(os.getpid()),
                '--parent-birth', str(psutil.Process(os.getpid()).create_time())],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=None,
                startupinfo=startup, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
        finally:
            os.set_handle_inheritable(handle, inherited_before)
        process = CompanionProcess(raw)
        child.close()
        if not parent.poll(max(0, deadline - time.monotonic())):
            raise RuntimeError('Companion private-entry handshake timed out before argument transfer')
        hello = parent.recv()
        if not isinstance(hello, dict) or type(hello.get('pid')) is not int:
            raise RuntimeError('Invalid companion private-entry handshake')
        process.attach(hello['pid'])
        payload = serialize_arguments(target, args, process.pid, shutdown, restores_cursor)
        parent.send_bytes(payload)
        return process
    except BaseException:
        if process is not None:
            process.kill(); process.join(1)
        elif raw is not None:
            raw.kill(); raw.wait(timeout=1)
        raise
    finally:
        parent.close(); child.close()


def start_companion(ctx, target, args, timeout=10, shutdown=None, restores_cursor=False):
    if sys.platform == 'win32':
        return launch_windows_companion(target, args, timeout, shutdown, restores_cursor)
    process = ctx.Process(target=target, args=args, daemon=True)
    process.start()
    return process
