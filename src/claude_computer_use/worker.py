"""Serialized desktop worker with hard local deadlines and explicit cancellation."""
import multiprocessing
import threading
import queue
import os
import shutil
import tempfile
import time
from .diagnostics import checkpoint, stack_watchdog, stop_watchdog


def bootstrap(connection, capture_dir, entrypoint, timeout=8):
    os.environ['CLAUDE_COMPUTER_CAPTURE_DIR'] = capture_dir
    if os.name != 'nt': os.setsid()
    checkpoint("worker.bootstrap")
    os.environ["CLAUDE_COMPUTER_WORKER_TIMEOUT"] = str(timeout)
    entrypoint(connection)


def worker_main(connection):
    runtime = None
    try:
        while True:
            checkpoint("worker.wait_request")
            method, arguments = connection.recv()
            checkpoint("worker.request_received")
            watchdog=stack_watchdog(float(os.environ.get("CLAUDE_COMPUTER_WORKER_TIMEOUT", "8")))
            try:
                if method == '_worker_ping':
                    connection.send(('ok', {'worker_pid': os.getpid(), 'runtime_initialized': runtime is not None}))
                    continue
                if runtime is None:
                    checkpoint("worker.runtime_import_begin")
                    from .runtime import Runtime
                    checkpoint("worker.runtime_import_end")
                    runtime = Runtime()
                    checkpoint("worker.runtime_constructed")
                checkpoint("worker.dispatch_begin")
                result = runtime.dispatch(method, arguments)
                checkpoint("worker.dispatch_end")
                checkpoint("worker.send_begin")
                connection.send(('ok', result))
                checkpoint('worker.send_end')
            except Exception as error:
                checkpoint('worker.exception')
                connection.send(('error', f'{type(error).__name__}: {str(error)[:1024]}'))
            finally:
                stop_watchdog(watchdog)
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        connection.close()


class SubprocessWorker:
    """Process interface used by cancellation, backed by a detached-stdio child."""
    def __init__(self, process):self.process=process;self.pid=process.pid
    def is_alive(self):return self.process.poll() is None
    def kill(self):self.process.kill()
    def join(self, timeout=None):
        import subprocess
        try:self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:pass


def launch_windows_worker(child, capture_dir, timeout):
    # A dedicated module avoids reimporting the MCP __main__ during Windows spawn.
    # Inherit only the private Pipe HANDLE, never MCP stdin/stdout. The worker
    # remains in the same interactive desktop/session; this does not create a VM.
    import subprocess
    import sys
    import psutil
    parent_birth=psutil.Process(os.getpid()).create_time()
    handle=child.fileno()
    inherited_before=os.get_handle_inheritable(handle)
    startup=subprocess.STARTUPINFO()
    startup.lpAttributeList={'handle_list':[handle]}
    os.set_handle_inheritable(handle,True)
    try:
        process=subprocess.Popen([sys.executable,'-m','claude_computer_use.worker_entry',
            '--pipe-handle',str(handle),'--capture-dir',capture_dir,'--timeout',str(timeout),
            '--parent-pid',str(os.getpid()),'--parent-birth',str(parent_birth)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=None,
            startupinfo=startup,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
    finally:os.set_handle_inheritable(handle,inherited_before)
    return SubprocessWorker(process)


class WorkerClient:
    def __init__(self, timeout=8, entrypoint=worker_main):
        from .validation import bounded
        self.timeout = bounded(timeout, 0.1, 30)
        self.entrypoint = entrypoint
        self._serial = threading.Lock()
        self._lifecycle = threading.RLock()
        self._epoch = 0
        self._process = self._connection = None
        self._capture_dir = None

    def epoch(self):
        with self._lifecycle: return self._epoch

    def _start(self, epoch):
        with self._lifecycle:
            if epoch != self._epoch:
                raise RuntimeError('Request cancelled before dispatch; rebind target before resuming')
            if self._process is not None:
                if self._process.is_alive(): return self._process, self._connection
                self.cancel(expected=self._process)
                raise RuntimeError('Worker exited while idle; target discarded. Re-list and rebind before continuing.')
            ctx = multiprocessing.get_context('spawn')
            parent, child = ctx.Pipe()
            capture_dir = tempfile.mkdtemp(prefix='claude-capture-worker-')
            checkpoint("parent.spawn_begin")
            try:
                if os.name == 'nt' and self.entrypoint is worker_main:
                    process=launch_windows_worker(child,capture_dir,self.timeout)
                else:
                    process = ctx.Process(target=bootstrap, args=(child,capture_dir,self.entrypoint,self.timeout), daemon=True)
                    process.start()
            except BaseException:
                parent.close(); child.close(); shutil.rmtree(capture_dir)
                raise
            checkpoint("parent.spawn_end")
            child.close()
            self._process, self._connection = process, parent
            self._capture_dir = capture_dir
            return process, parent

    def cancel(self, expected=None, epoch=None):
        with self._lifecycle:
            process = self._process
            if expected is not None and process is not expected: return False
            if epoch is not None and epoch != self._epoch: return False
            self._epoch += 1  # Fence queued requests, including cancellation while idle.
            if process is None: return False
            connection = self._connection
            # On POSIX the worker owns a session/process group; kill every
            # helper (including screencapture), not only the Python parent.
            if os.name != 'nt':
                import signal
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    # If bootstrap has not created the group yet, no native
                    # helpers can have started; terminate the Python worker.
                    if process.is_alive(): process.kill()
            elif process.is_alive():
                import psutil
                try:
                    parent = psutil.Process(process.pid)
                    parent.suspend()  # Prevent new descendants during enumeration.
                    descendants = parent.children(recursive=True)
                    for child in reversed(descendants):
                        try: child.kill()
                        except psutil.NoSuchProcess: pass
                    process.kill()
                    _, alive = psutil.wait_procs(descendants, timeout=0.5)
                    if alive: raise RuntimeError('Child termination not confirmed; stop automation')
                except psutil.NoSuchProcess:
                    pass
            process.join(timeout=0.5)
            if process.is_alive():
                raise RuntimeError('Worker termination not confirmed; do not resume automation')
            self._process = self._connection = None
            connection.close()
            if self._capture_dir:
                shutil.rmtree(self._capture_dir)
                self._capture_dir = None
            return True

    def call(self, method, arguments, epoch=None):
        epoch = self.epoch() if epoch is None else epoch
        checkpoint("parent.call_begin")
        deadline = time.monotonic() + self.timeout
        if not self._serial.acquire(timeout=self.timeout):
            raise TimeoutError('Desktop worker is busy; request was not dispatched')
        process = None
        try:
            process, connection = self._start(epoch)
            checkpoint("parent.send_begin")
            connection.send((method, arguments))
            checkpoint("parent.send_end")
            incoming = queue.Queue(maxsize=1)
            def receive():
                try: incoming.put(('response', connection.recv()))
                except (EOFError, OSError) as error: incoming.put(('failure', error))
            reader = threading.Thread(target=receive, daemon=True)
            reader.start()
            try:
                checkpoint("parent.receive_begin")
                kind, response = incoming.get(timeout=max(0, deadline-time.monotonic()))
                checkpoint("parent.receive_end")
            except queue.Empty:
                checkpoint("parent.deadline")
                self.cancel(expected=process)
                reader.join(timeout=0.5)
                raise TimeoutError('Native deadline exceeded; worker killed, target/references discarded. Input may have partially executed. Inspect state, rebind, and never replay automatically.')
            if kind == 'failure': raise response
            status, result = response
            if status == 'error': raise RuntimeError(result)
            return result
        except (EOFError, BrokenPipeError, OSError) as error:
            # TimeoutError subclasses OSError: preserve informative deadline result.
            if isinstance(error, TimeoutError): raise
            if process is not None: self.cancel(expected=process)
            raise RuntimeError('Desktop worker exited/cancelled; outcome uncertain, target discarded. Rebind before further actions.') from error
        finally:
            self._serial.release()
