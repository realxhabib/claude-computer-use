"""Bounded, lock-free startup diagnostics shared with a desktop child process.

Only bootstrap phases and exception traces are recorded, never screen contents
or tool arguments. Diagnostic readers tolerate an interrupted child write.
"""
import traceback


class StartupStatus:
    def __init__(self, context):
        self.phase_bytes = context.RawArray('c', 128)
        self.error_bytes = context.RawArray('c', 4096)
        self.phase('spawn_pending')

    def phase(self, name):
        self.phase_bytes.value = name.encode('utf-8')[:127]

    def record_exception(self):
        self.error_bytes.value = traceback.format_exc().encode('utf-8')[:4095]

    def describe(self, process):
        phase = self.phase_bytes.value.decode('utf-8', errors='replace')
        error = self.error_bytes.value.decode('utf-8', errors='replace')
        # Sample before cleanup so our own termination isn't called a crash.
        alive = process.is_alive()
        state = 'readiness deadline expired' if alive else 'child exited before readiness'
        detail = f'{state}; phase={phase}; child_pid={process.pid}; exitcode={process.exitcode}'
        if error: detail += '\n' + error
        return detail


def run_startup_target(status, target, args):
    status.phase('child_entered')
    try:
        target(*args, startup_status=status)
    except BaseException:
        status.record_exception()
        raise
