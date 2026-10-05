"""Minimal Windows worker entry point: no MCP server or inherited stdio input."""
import argparse


def parent_matches(parent, expected_birth):
    import psutil
    try:return parent.is_running() and parent.create_time()==expected_birth
    except psutil.Error:return False


def main():
    from .diagnostics import checkpoint
    checkpoint('worker.entry')
    from multiprocessing.connection import PipeConnection
    from .worker import bootstrap, worker_main
    parser=argparse.ArgumentParser()
    parser.add_argument('--pipe-handle',type=int,required=True)
    parser.add_argument('--capture-dir',required=True)
    parser.add_argument('--timeout',type=float,required=True)
    parser.add_argument('--parent-pid',type=int,required=True)
    parser.add_argument('--parent-birth',type=float,required=True)
    args=parser.parse_args()
    import os, threading, psutil
    try:parent=psutil.Process(args.parent_pid)
    except psutil.Error:os._exit(1)
    if not parent_matches(parent,args.parent_birth):os._exit(1)
    def watch_parent():
        tick=threading.Event()
        while not tick.wait(.25):
            if not parent_matches(parent,args.parent_birth):os._exit(1)
    threading.Thread(target=watch_parent,daemon=True).start()
    bootstrap(PipeConnection(args.pipe_handle),args.capture_dir,worker_main,args.timeout)


if __name__=='__main__':main()
