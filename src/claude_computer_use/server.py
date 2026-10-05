"""Local stdio MCP proxy. Native calls execute in a killable worker process."""
import asyncio
import argparse
import atexit
import multiprocessing
import os
import json
from mcp.server.fastmcp import FastMCP, Image
from mcp.types import TextContent, ImageContent
from .validation import bounded
from .unicode_input import validate_text
from .worker import WorkerClient

mcp = FastMCP('local-computer')
_worker = None
_activity = None


def worker():
    global _worker
    if _worker is None:
        _worker = WorkerClient(timeout=float(os.environ.get('CLAUDE_COMPUTER_TIMEOUT_SECONDS', '8')))
    return _worker


async def call(method, **arguments):
    client = worker()
    epoch = client.epoch()  # Capture before checks; stop cancellation fences this request.
    if _activity is not None:
        _activity.check()
        with _activity.lock:
            _activity.check()
    try:
        return await asyncio.to_thread(client.call, method, arguments, epoch=epoch)
    except asyncio.CancelledError:
        # Conservatively cancel all native requests in this generation. Do not
        # kill a newer generation that has already restarted after another cancel.
        await asyncio.shield(asyncio.to_thread(client.cancel, epoch=epoch))
        raise


@mcp.tool()
async def list_apps() -> dict:
    """List applications with visible/on-screen windows. No target required."""
    return await call('list_apps')


@mcp.tool()
async def list_windows() -> dict:
    """List window IDs, owning PID, app, title and bounds. Select an exact target explicitly."""
    return await call('list_windows')


@mcp.tool()
async def bind_window(window_id: str) -> dict:
    """Bind an enumerated window ID, PID and process birth. Required before capture/input.
    Does not activate. Rebinding invalidates all native element references.
    """
    return await call('bind_window', window_id=window_id)


@mcp.tool()
async def activate_window() -> dict:
    """Explicitly restore/activate the bound window and verify foreground identity.
    Use to recover from another app taking focus. Never switches targets implicitly.
    """
    return await call('activate_window')


@mcp.tool()
async def wait_for_window_state(state: str = 'stable', timeout: float = 3) -> dict:
    """Wait for bound-window OS state after async native dispatch. States: stable, visible,
    minimized, maximized (Windows), foreground. Samples stable metadata before returning;
    this does not verify editor contents or render completion. Never scores dispatch alone.
    """
    return await call('wait_for_window_state', state=state, timeout=timeout)


@mcp.tool()
async def computer_status() -> dict:
    """Get OS, cursor, foreground ID, bound target and window-local coordinate convention."""
    return await call('computer_status')


@mcp.tool()
async def desktop_diagnostics() -> dict:
    """Diagnose interactive-session/permission/native-provider access separately from corner failsafe.
    Reports native exception/HRESULT without treating cursor (0,0) as proof of desktop access.
    """
    return await call('desktop_diagnostics')


@mcp.tool()
async def screenshot() -> list[TextContent | ImageContent]:
    """Capture ONLY the bound foreground window via PrintWindow/macOS window capture.
    Never falls back to a desktop screenshot. Rejects focus/identity/frame changes before
    returning pixels. Image coordinates are local to the bound window, not the desktop.
    On unsupported capture surfaces, report failure rather than capturing unrelated apps.
    """
    result = await call('screenshot')
    return [TextContent(type='text', text=json.dumps(result['provenance'])),
            Image(data=result['png'], format='png').to_image_content()]


@mcp.tool()
async def click(x: int, y: int, button: str = 'left', clicks: int = 1) -> dict:
    """Click window-local coordinates after target/foreground/point-occlusion checks."""
    return await call('click', x=x, y=y, button=button, clicks=clicks)


@mcp.tool()
async def move_mouse(x: int, y: int) -> dict:
    """Hover at window-local coordinates after target and occlusion checks."""
    return await call('move_mouse', x=x, y=y)


@mcp.tool()
async def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> dict:
    """Drag inside the bound window using local coordinates. Both endpoints must be unoccluded."""
    return await call('drag', start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y, duration=duration)


@mcp.tool()
async def type_text(text: str, input_mode: str = 'paced') -> dict:
    """Dispatch experimental Unicode input without changing the clipboard; verify exact content.
    Batch CJK and Latin corruption was measured in Windows Notepad. Default paced mode
    passed one smoke trial, not a certified fix; paced requests are limited to 128 characters; never infer successful text from accepted input events.
    Rechecks target between short chunks. Rejects invalid Unicode/control characters before
    any typing. Verify field and resulting content; never use for credentials.
    """
    validate_text(text)
    if input_mode not in {'batch','paced'}:raise ValueError('input_mode must be batch or paced')
    if input_mode=='paced' and len(text)>128:raise ValueError('Paced input accepts at most 128 characters per call; split and verify chunks')
    return await call('type_text', text=text, input_mode=input_mode)


@mcp.tool()
async def press_keys(keys: list[str]) -> dict:
    """Press a chord only when the bound target is foreground. macOS command / Windows ctrl.
    A chord may move focus; subsequent input/capture then rejects until explicit recovery.
    """
    return await call('press_keys', keys=keys)


@mcp.tool()
async def scroll(amount: int, x: int, y: int) -> dict:
    """Scroll at an unoccluded window-local point; positive up, negative down."""
    return await call('scroll', amount=amount, x=x, y=y)


@mcp.tool()
async def wait(seconds: float = 0.5) -> dict:
    """Wait briefly; reject local stop and abort if stop/resume occurs during the wait."""
    bounded(seconds, 0, 3)
    if _activity is None:
        await asyncio.sleep(seconds)
    else:
        client = worker()
        epoch = client.epoch()
        _activity.check()
        with _activity.lock:
            _activity.check()
        remaining = seconds
        while True:
            with _activity.lock:
                _activity.check()
                if client.epoch() != epoch:
                    raise RuntimeError('Wait cancelled; worker generation changed during wait')
            if remaining <= 0:
                break
            interval = min(remaining, 0.05)
            await asyncio.sleep(interval)
            remaining -= interval
    return {'waited': seconds}


@mcp.tool()
async def inspect_ui(max_nodes: int = 150, max_depth: int = 8) -> dict:
    """Inspect native controls only while the bound target is foreground. Reports truncation.
    Increase bounds (up to 500 nodes/20 levels) if a maximized app has a deeper tree.
    IDs expire after 30 seconds, another inspection, or any attempted mutation.
    """
    return await call('inspect_ui', max_nodes=max_nodes, max_depth=max_depth)


@mcp.tool()
async def find_elements(name: str = '', role: str = '', exact: bool = False,
                        max_nodes: int = 150, max_depth: int = 8) -> dict:
    """Search fresh target UI by name/role. Returns all matches and truncation.
    Can increase tree limits when default depth omits controls; an empty truncated result
    does not prove absence. Roles are OS native names.
    """
    if not name and not role: raise ValueError('Provide a name or role')
    return await call('find_elements', name=name, role=role, exact=exact,
                      max_nodes=max_nodes, max_depth=max_depth)


@mcp.tool()
async def read_element(element_id: str) -> dict:
    """Recheck target identity and an existing native reference's state."""
    return await call('read_element', element_id=element_id)


@mcp.tool()
async def act_on_element(element_id: str, action: str = 'activate') -> dict:
    """Native activate/focus in the bound foreground target. Dispatch is not verification.
    Every attempted mutation invalidates native references, even after partial failure.
    """
    return await call('act_on_element', element_id=element_id, action=action)


@mcp.tool()
async def cancel_pending() -> dict:
    """Kill the native worker, discard bound target/references, and stop any local pending call.
    Cannot undo input already dispatched or cancel an operation already queued by an app.
    Never automatically retries. Re-list/rebind and inspect actual state before continuing.
    """
    stopped = await asyncio.to_thread(worker().cancel)
    return {'worker_stopped': stopped, 'target_discarded': True, 'outcome': 'May be partially executed; verify before resuming'}


def cleanup():
    if _worker is not None: _worker.cancel()
    if _activity is not None: _activity.close()


def exit_session():
    # Activity has cancelled native work, restored the cursor and closed both
    # companions before invoking this. End the MCP connection, keeping Claude open.
    os._exit(0)


def main():
    global _activity
    parser=argparse.ArgumentParser(description='Desktop MCP: local stdio, or authenticated loopback HTTP inside a dedicated VM')
    parser.add_argument('--transport',choices=['stdio','http'],default='stdio')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not 1024 <= args.port <= 65535: parser.error('port must be 1024..65535')
    token=os.environ.get('CLAUDE_COMPUTER_HTTP_TOKEN','')
    if args.transport=='http' and len(token)<32:
        parser.error('HTTP requires CLAUDE_COMPUTER_HTTP_TOKEN with at least 32 random characters')
    multiprocessing.freeze_support()
    atexit.register(cleanup)
    from .activity import Activity
    _activity = Activity(lambda: _worker.cancel() if _worker is not None else None, on_exit=exit_session)
    try:
        if args.transport=='stdio':mcp.run(transport='stdio')
        else:
            from .http_transport import serve
            serve(mcp,args.port,token)
    finally:cleanup()


if __name__ == '__main__': main()
