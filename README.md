# Computer use for Claude Code — v0.3.9

A desktop MCP server and Claude Code skill for Windows and macOS. v0.3.2 requires
explicit target-window binding, captures target-window pixels, and runs native
operations in a killable worker. This is a prototype with partially smoke-tested Windows v0.3 and unverified v0.3.2 native
behavior, not a measured ChatGPT/Codex equivalent. Current Windows builds temporarily enlarge the normal native arrow while active; macOS uses its native pointer plus glow.

## Which desktop does it control?

Local stdio controls the desktop of the user/session running this server. It
shares that desktop's real cursor, keyboard and foreground app. You cannot use
that same desktop freely while generic GUI automation continues unaffected.
There is no independent second cursor on a shared desktop in this package.

For simultaneous host use, run the server in a **dedicated interactive VM desktop**
and connect Claude Code to it. The VM has its own cursor/focus/apps; your host
remains independent. This package provides an authenticated loopback HTTP
transport for that setup; it does not create a VM or prove isolation. See
[ISOLATED_DESKTOP.md](ISOLATED_DESKTOP.md). Native AX/UIA actions can sometimes
work without moving a cursor, but this version still guards foreground state;
it does not promise background operation on your host's existing apps.

## Install locally

Use Windows 10/11 or a current Mac, Python 3.10+, and Claude Code. From the source:

```sh
python -m venv .venv
```

macOS:

```sh
.venv/bin/python -m pip install -e .
claude mcp add --transport stdio local-computer -- /ABSOLUTE/PATH/claude-computer-use/.venv/bin/claude-computer-use
claude --plugin-dir /ABSOLUTE/PATH/claude-computer-use
```

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -e .
claude mcp add --transport stdio local-computer -- C:\ABSOLUTE\PATH\claude-computer-use\.venv\Scripts\claude-computer-use.exe
claude --plugin-dir C:\ABSOLUTE\PATH\claude-computer-use
```

Replace absolute paths. Re-run install and restart Claude Code when upgrading.
Use `claude --help` / `claude mcp add --help` to check your installed CLI syntax.
The skill is loaded as a plugin; its MCP server is registered separately. Your
Claude Code authentication supplies the model; no additional model API key is used.

macOS: grant Accessibility and Screen Recording to the actual launcher/runtime
in System Settings → Privacy & Security and restart it as needed. Windows:
use an unlocked interactive user desktop, not a service/session-0 process.
An SSH-created Windows service session may not have access to the user's GUI.

## Target selection and recovery

1. Run `desktop_diagnostics`, `list_apps`, and `list_windows`.
2. `bind_window(window_id)` binds the exact window ID, owning PID and process
   birth time. Bind never implicitly activates or chooses a similarly named app.
3. `activate_window()` explicitly restores/raises that bound window and verifies
   foreground identity. OS foreground restrictions may refuse activation.
4. Capture `screenshot()` and inspect `inspect_ui()` / `find_elements()`.
5. Prefer supported native activation/focus. For mouse input use **window-local**
   coordinates from the screenshot, not primary-desktop coordinates.
6. After async maximize/minimize/restore, use `wait_for_window_state` for the expected OS state, then verify app/render contents with screenshot/inspection. Dispatch alone is not completion. If focus changes, input
   and capture reject; activate the bound window explicitly to recover.

Screenshots include provenance text (window ID, PID, frame, capture API, coordinate
space) and a PNG. Windows uses PrintWindow and crops invisible borders to DWM
visible bounds; macOS uses `screencapture -l` for the window ID. Neither path
falls back to a desktop screenshot. Before/after guards discard results if
before/after checks detect an identity, foreground, or frame change. A change
that returns to the original state between checks is not detected. Capture surfaces that render black or
incomplete images still require real host testing; do not infer success from
PrintWindow's return code alone. System-owned menus/dialogs may need their own
explicit binding. Mouse points must belong to the target; occluded points reject.
Every attempted mutation invalidates native refs and coordinate snapshots.
Capture again before each coordinate action; resize/movement requires a new shot.

Keyboard injection still uses OS foreground input. Checking focus and dispatch
cannot be atomic: a change in that small gap can misdirect input. Native Invoke
references address their exact bound controls; general input does not have an
OS-enforced background target. A dedicated VM/session is the way to avoid host
interference. Do not market foreground guards as independent-cursor isolation.

## New controls and limits

20 tools: app/window discovery; bind/activate; diagnostics/status; target capture;
click/hover/drag/scroll; Unicode input/chords; native inspect/search/read/act; wait;
state settlement, and cancellation. `list_apps` includes apps with enumerated windows, not all
installed/background apps. There is no launch/install-app tool.

Unicode uses Windows SendInput UTF-16 events or macOS Quartz Unicode events,
without replacing the clipboard. Windows smoke tests showed batch corruption of both Japanese and Latin text. Paced input matched exactly in one v0.3.1 probe, which does not establish reliability. v0.3.2 defaults to paced input, capped at 128 characters per call; explicit batch remains diagnostic. Complete Unicode support is **not established**. Responses include a hash of received text and native event-acceptance receipts; neither proves editor content. Invalid controls, lone surrogates and text over 10,000 characters
reject before typing. Focus and content must still be verified; don't enter
credentials. Some app/integrity boundaries may ignore or partially accept events.

Native actions remain Windows Invoke/macOS AXPress and focus. Native toggle,
selection, expansion, setting values and rich value/checked/selected verification
are not implemented. Focus is reported where supported; Mac visibility in the
accessibility tree is unknown. Use screenshots for other state checks. Names
are capped at 512 and roles at 128 characters; full labels are fingerprinted.
Native IDs expire after 30 seconds, any new inspection, and any attempted mutation.
External changes with identical identity/labels cannot be detected reliably.

Inspection defaults to 150 nodes/8 levels and reports truncation/errors. Search
accepts up to 500 nodes/20 levels; retry deeper when an empty result is truncated.
Mac AX-to-CG mapping uses public PID/title/geometry attributes and rejects
ambiguous or unavailable mapping. Titles may require Screen Recording permission.
Windows visible bounds use DWM, while captures retain/crop native bitmap offsets.
Only targets wholly on the primary display are supported. macOS capture temporarily writes a per-worker private directory on the runtime machine; normal completion or confirmed cancellation removes it. Supervisor crash or cleanup failure can leave data requiring manual removal. Captures have a
40-million-pixel geometry limit and a 16 MB encoded-size limit.

## Deadlines and cancellation

Native work runs in one spawned worker. Default request deadline is eight seconds;
set `CLAUDE_COMPUTER_TIMEOUT_SECONDS` to a value up to 30. `cancel_pending` kills
the worker and fences already queued calls. MCP request cancellation also kills
that generation. A timeout/cancel discards targets/refs; re-list, rebind and
inspect real state before resuming. Requests are never automatically replayed.
Termination may add up to one second for child/worker confirmation. The supervisor kills helper processes and removes its owned temporary capture directory after confirmed termination. Native calls can
still have partially dispatched input or queued work in an app; killing the
worker is not rollback or a guarantee an external app operation was cancelled.
If termination cannot be confirmed, stop automation. Modifier keys can remain
held after interrupted input; release them manually before continuing.

Mouse-corner failsafe remains enabled. Diagnostics separately report corner
position, desktop/session access and native exception/HRESULT. Cursor (0,0)
may indicate a sandbox/noninteractive session; it alone is not proof of a
user-triggered stop or of successful desktop access. UAC/secure desktop and
permission boundaries remain unsupported.

## Tests and evidence

```sh
python -m unittest discover -s tests -v
python -m compileall -q src
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

Tests cover target mismatch/capture races, provenance, coordinate mapping,
occlusion, process identity reuse, truncation, Unicode contracts, public MCP
proxies, actual spawned-worker hangs/cancellation/restart, and real stdio
protocol discovery. Adapter tests use doubles and do not certify native APIs.
The MCP SDK requires working local IPC; a sandbox may block its async runtime.
Do not count skipped tests or unavailable native environments as successes.

[Historical v0.2.0 evidence](benchmarks/v0.2.0/windows-smoke-summary.json)
preserves the real Windows findings supplied by the testing thread. Those are
smoke results, not a controlled benchmark. The [v0.3 Windows summary](benchmarks/v0.3.0/windows-smoke-summary.json) preserves native capture/window/cancellation successes and the Unicode/fixture failures. Those are partial smoke evidence, not release validation. The delegated v0.3.1 Windows suite passed 77 tests; batch text failed and one paced probe passed. v0.3.2 native behavior, Mac operation, VM isolation and controlled parity remain unvalidated. See
[benchmark protocol](benchmarks/PROTOCOL.md) and [tester handoff](TESTER_HANDOFF.md).

## v0.3.2 Windows Unicode investigation

The known failure is exact editor text, not merely a screenshot/font issue: UIA
DocumentRange reported spaces instead of Japanese. We have not established
whether payload transport, Windows event delivery, input services, timing or
editor handling caused it. The existing correct UTF-16 event contract is now
tested with the exact Japanese units, but cloud tests cannot prove consumption.
Do not silently replace the clipboard or claim that paced input fixes the defect.

Use a disposable EMPTY Notepad document, an exact enumerated window ID, and the
interactive-session testing shell (without switching focus to a console). Run:

```powershell
.venv\Scripts\claude-computer-unicode-probe.exe --window-id HWND --mode batch --confirm-empty-editor > batch-report.json
```

Clear/replace the disposable document manually and focus its editor before the
paced trial; never auto-replay into the nonempty result:

```powershell
.venv\Scripts\claude-computer-unicode-probe.exe --window-id HWND --mode paced --confirm-empty-editor > paced-report.json
```

Default `--mode observe` is read-only and requires no mutation confirmation.
The probe explicitly reads editor text into its report; use synthetic data only.
It checks the focused editor belongs to the exact target, refuses protected or
nonempty editors before mutation, uses the regular killable worker, and emits
ASCII JSON. The fixed payload is ASCII-escaped in Python source so console
encoding cannot replace its Japanese literals. Reports show separately generated fixed caller/worker payload codepoints and
UTF-16 units, plus accepted input-event counts (not a captured OS-delivery trace), received text hash,
actual DocumentRange text/codepoints, editor identity, and exact matching after
newline normalization. Read-only observation does not diagnose the root cause.

If batch and paced both fail with identical received hashes/units, retain that
failure and investigate editor/input-service handling next; do not declare a
fix. Keyboard-event acceptance is not text-content verification.

The controlled probe pins the focused editor before each input dispatch (including Tab/Enter). These checks cannot be atomic with OS input; same-window field changes in that gap remain possible. Use an idle, empty synthetic editor for diagnosis.

The probe supports `--case mixed`, `ascii-distinct`, `ascii-repeat`, `cjk`, and `emoji`. Its optional prepared scan-unit receipts describe the array before SendInput, not delivered OS events. Repeat both modes in fresh empty editors. Also test the public `type_text` default separately: the controlled probe adds focused-editor checks that may change timing. Use read-only `--mode observe --case mixed` after public typing to check exact content.

Generic MCP calls use an 8-second worker deadline; the diagnostic CLI uses 12 seconds. Even a paced call within the 128-character cap can exceed its deadline on a slow host. Partial input can remain after cancellation; never automatically retry.

## Visible activity and local stop

The desktop server now starts a separate companion showing “Claude is using your computer — Esc to cancel” and a soft blue glow around the native system pointer. The halo does not provide an independent cursor. Escape ends the session: the worker is cancelled, the original cursor restored, the banner and glow closed, and the MCP server exited. There is no Resume button. Start a fresh server session and verify partially executed actions before continuing. The indicator stays visible between calls while computer use is enabled.

This new UI requires PySide6 and pynput. macOS requires Input Monitoring permission for the global Escape listener, alongside existing Accessibility permissions. Startup refuses to proceed if the companion fails to initialize; companion loss blocks subsequent calls. Native appearance, click-through behavior, global Escape delivery and permissions still require real Windows/macOS testing. Escape cannot undo input already sent or prevent a queued OS event. A killed/failed companion cannot be resumed; restart the server.

The private diagnostic Unicode CLI is tester-only and does not start the activity companion; its controlled empty-editor runs are separate from the user-facing MCP server.

The global listener may also observe an Escape injected by the agent; using Escape to dismiss a menu can therefore exit the session. It is not a physical-key-only detector.

### v0.3.3 stop-gate correction

`wait()` now obeys the local stop latch, polls during a pending wait and rejects a worker-generation change even if the user resumes before the next poll. `cancel_pending()` remains available while stopped. Delegated v0.3.2 Windows evidence confirms the native banner/halo and 86 packaged tests; repeated full-MCP native deadlines and physical Escape/Resume remain separate unresolved acceptance checks.

### v0.3.4 reference styling and Windows startup revision

The indicator now follows the supplied photo's style: top-center rounded blue bar, “Claude is using your computer”, “Esc to cancel”, and a dark arrow with white outline and soft blue glow. Dimensions use device-independent pixels. This is a reference-based reproduction, not a pixel-exact certification from a perspective photo. The native system cursor remains; we do not globally replace it. The indicator's own arrow tip tracks QCursor. The banner intentionally receives clicks and can occlude a control beneath it.

Production Windows workers now launch a minimal dedicated module with only the private pipe handle inherited, stdin/stdout detached, and no MCP main-module reimport. This addresses an architectural difference between direct-harness and full-MCP startup. Native timeout resolution is unverified until both actual launchers pass the unchanged eight-second deadline. Worker parent monitoring prevents indefinite orphan execution after parent death; cancellation still discards target state. Non-Windows and injected test entry points retain the existing spawn path.

Set `CLAUDE_COMPUTER_DIAGNOSTICS_DIR` to a dedicated local directory before server startup to collect phase timestamps and timed worker stacks. Logs contain no tool argument values or editor text; stacks include source paths. Logging is off by default. The worker stack watchdog starts after request receipt, so a stall before worker entry may require an external stack capture. The response wait is deadline-bounded; process creation and synchronous pipe send are not independently preempted.

### v0.3.5 Windows process-tree test correction

The native private-pipe test now requires the responding worker PID to belong to the tracked launcher process tree, and verifies that the whole sampled tree exits after cancellation. Windows venv launchers can run the interpreter as a descendant; PID equality with the launcher is not required. No production launch/cancellation behavior changed in this correction.

Delegated v0.3.4 evidence: both actual MCP launchers now pass the unchanged eight-second deadline (module status 0.536s/bind 0.010s; console status 0.550s/bind 0.014s). The packaged suite recorded 98 passes/one PID-test failure. A separate sampled-tree cancellation probe passed; this does not retroactively make that suite pass. Calculator produced 96 with stale-reference rejection, and injected Escape stopped pending waits and blocked subsequent calls. Human Resume and physical Escape attribution remain unverified.

### v0.3.6 single visible pointer

Real Windows feedback confirmed that v0.3.4's drawn arrow overlapped the normal Windows cursor. The companion now draws only the diffuse blue glow centered on the native pointer. It never hides or replaces the system cursor; companion termination removes the glow without requiring cursor restoration. Pointer shape/size follow the user's OS settings. This avoids duplicates, but the native pointer shape is not forced to match the reference. The top-centered banner remains unchanged.

User feedback confirms physical Escape changes the banner and local Resume works. A corrected harness confirms wait rejection while stopped, a discarded target after Resume, and successful explicit rebind. A longer hold probe stopped without enough precleanup state to establish why; repeated-cycle stability is not established. Separate parent-death evidence found all four sampled descendants gone after one second.

### v0.3.7 native Windows arrow while active

Windows now uses a 48-pixel dark arrow with white outline in the normal system arrow slot while enabled, plus the soft blue glow. The overlay draws no arrow, so there is one pointer. Text, resize, busy and application-defined cursors retain their native behavior. Fixed physical dimensions are not DPI-certified. macOS currently retains its native cursor plus glow; native replacement is Windows-only.

An independent guard captures a private original arrow snapshot, supplies disposable handles to SetSystemCursor, and restores the original on Escape, companion failure, parent exit or clean shutdown. Resume acknowledgement requires both worker cancellation and cursor restoration. A session-local mutex permits one cursor owner. Installation failure restores the original before input is admitted. This is newly implemented, not native-validated.

If the guard is killed, the surviving controller reloads the configured Windows cursor scheme; that fallback may differ from a temporary preexisting cursor override. Simultaneous forced termination of guard and controller cannot guarantee restoration. Recovery: Windows Settings → Bluetooth & devices → Mouse → Additional mouse settings → Pointers → Apply reloads the selected scheme. No registry or persistent cursor settings are changed.

### v0.3.8 forced-guard shutdown correction

The v0.3.7 Windows suite passed all 113 tests and native pointer/physical Escape/Resume checks succeeded, but forced guard death left cleanup stuck in multiprocessing.Event.set. Shared flags now use lock-free byte polling; cursor counters are raw shared values, and the remaining state locks have bounded acquisition. Cancellation precedes coordination/restoration work. Cleanup never acquires the cursor state lock. A hard-killed waiter and actual guard-close regression cover the failure class locally; native forced-guard shutdown retesting is still required.

Initialization now notices an exited child promptly instead of consuming the entire ten-second readiness timeout. Opt-in diagnostics add Escape receipt, Resume click, worker-cancellation, acknowledgment and native cursor install/restore timestamps. Three synthetic Windows stop trials restored cursor pixels in 20.7–27.8 ms and acknowledged in 34.8–44.3 ms; these exclude physical key and local click latency and do not explain the user's perceived transition lag.

### v0.3.9 Escape ends the session

Escape and the banner's cancel button now stop pending native work, restore the cursor, close the companions and terminate the MCP server connection. Claude Code itself remains open. There is no paused mode or Resume button. A fresh computer-use session must start a new server and bind a target again; the old target/references are discarded. This supersedes the earlier Resume-based instructions and tests.

The exit callback runs only after cleanup returns successfully. If restoration/cleanup fails, input stays blocked rather than exiting and abandoning an unconfirmed cursor state. Calls already dispatched can have partial app-side effects; inspect actual state after restarting. Native terminal-Escape acceptance is pending; historical v0.3.8 physical Escape/Resume results do not prove the new exit behavior.

On Esc the overlay hides its banner and glow on its next UI frame while teardown finishes. A failed teardown leaves the controller blocked for manual recovery. The server never relaunches itself; Claude Code connection restart policy must be checked in the native acceptance run.
