"""Minimal Windows companion entry. No MCP/main reimport or inherited stdin."""
import argparse
import os


def main():
    from .diagnostics import checkpoint
    checkpoint("companion.private_entry")
    from multiprocessing.connection import PipeConnection
    from multiprocessing.reduction import ForkingPickler
    parser = argparse.ArgumentParser()
    parser.add_argument('--pipe-handle', type=int, required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--parent-birth', type=float, required=True)
    args = parser.parse_args()
    import threading
    import psutil
    from .worker_entry import parent_matches
    try: parent = psutil.Process(args.parent_pid)
    except psutil.NoSuchProcess: return
    if not parent_matches(parent, args.parent_birth): return
    state = {'shutdown': None, 'restores_cursor': False}
    state_lock = threading.Lock()
    def watch_parent():
        tick = threading.Event()
        while not tick.wait(.25):
            if not parent_matches(parent, args.parent_birth):
                with state_lock:
                    signal = state['shutdown']
                    restores_cursor = state['restores_cursor']
                    if signal is not None: signal.set()
                    if restores_cursor: return  # Guard must restore, never bypass its finally.
                # Indicator has no cursor lease. Allow its Qt loop to quit first.
                tick.wait(1)
                os._exit(1)
    threading.Thread(target=watch_parent, daemon=True).start()
    # Return the actual interpreter PID, not necessarily its venv launcher's PID.
    connection = PipeConnection(args.pipe_handle)
    try:
        connection.send({'pid': os.getpid()})
        payload = connection.recv_bytes(4096)
    finally:
        connection.close()
    target, target_args, shutdown, restores_cursor = ForkingPickler.loads(payload)
    with state_lock:
        # If the parent vanished before transfer, don't acquire the desktop.
        if not parent_matches(parent, args.parent_birth): return
        state.update(shutdown=shutdown, restores_cursor=restores_cursor)
    checkpoint("companion.payload_loaded")
    target(*target_args)


def probe(ready, shutdown, pid_value, lock):
    """Private native test: exercise transferred signals, raw values and a lock."""
    with lock: pid_value.value = os.getpid()
    ready.set()
    shutdown.wait(30)


if __name__ == '__main__':
    main()
