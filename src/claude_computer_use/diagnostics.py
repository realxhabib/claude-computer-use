"""Opt-in phase/stack diagnostics; never records tool arguments or editor content."""
import json
import os
import threading
import time
from pathlib import Path


def checkpoint(stage):
    directory=os.environ.get('CLAUDE_COMPUTER_DIAGNOSTICS_DIR')
    if not directory:return
    try:
        root=Path(directory);root.mkdir(parents=True,exist_ok=True)
        row={'stage':stage,'pid':os.getpid(),'thread':threading.get_native_id(),
             'monotonic':time.monotonic(),'wall_time':time.time()}
        with (root/f'phases-{os.getpid()}.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(row)+'\n')
    except OSError:
        pass  # Diagnostic output cannot enable or disrupt input.


def stack_watchdog(timeout):
    directory=os.environ.get('CLAUDE_COMPUTER_DIAGNOSTICS_DIR')
    if not directory:return None
    try:
        import faulthandler
        root=Path(directory);root.mkdir(parents=True,exist_ok=True)
        stream=(root/f'stacks-{os.getpid()}.log').open('a',encoding='utf-8')
        faulthandler.dump_traceback_later(max(.1,timeout*.6),file=stream)
        return stream
    except (OSError,RuntimeError):return None


def stop_watchdog(stream):
    if stream is not None:
        import faulthandler
        faulthandler.cancel_dump_traceback_later();stream.close()
