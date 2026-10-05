# Handoff to Windows real-use testing thread

Intended collaborator: codex://threads/01a1077d-eaa4-7530-9df0-c1589af308f1.
The cloud authoring session has no callable tool to send messages to an unrelated
Codex thread. Incoming delegated evidence is preserved and can drive revisions.
Forward this revised package in that thread; no proactive message was sent.

The user now wants to keep using their host while the agent has its own cursor.
A shared desktop cannot provide generic independent foreground input. Test two
separate modes and do not claim independence from target-window guards:

1. Shared-host v0.3 regression: binding/activation, target pixels/provenance,
   frame/identity/occlusion rejection, Unicode, deadline cancellation, diagnostics,
   minimized/maximized windows and truncation. User interference is expected to
   trigger rejection/recovery. Never treat it as a controlled task failure rate.
2. Dedicated VM: run the authenticated loopback server inside an unlocked guest
   GUI, tunnel TCP, then test while user actively uses the host. See
   ISOLATED_DESKTOP.md. Provisioning a VM is not bundled; determine existing VM
   availability before making host configuration changes.

## v0.3.10 marketplace install acceptance (current)

Install uv and restart Claude Code so PATH is refreshed. Use the GitHub marketplace
flow in README, not an editable venv or separate `claude mcp add` registration.
The bundled launcher uses Python 3.12 and uv.lock; prior Python 3.14/other dependency
results do not certify this combination. Remove only the previous standalone
registration to avoid competing cursor owners.

Record Claude Code/uv versions, cold dependency setup duration and any MCP startup
timeout. If necessary, invoke `/computer-use:setup`, wait for completion and use
`/mcp` to reconnect explicitly. Verify the installed skill and bundled tools,
Calculator 96, target-scoped screenshot, and physical Esc terminal exit. Observe
whether Claude reconnects after Esc; it must not resume work without a new request.
Test paths containing spaces, restart/warm launch and plugin upgrade. macOS needs
its own permissions/input/capture/stop run. Linux packaging checks certify none of
these native behaviors.

## First Windows checks

- Verify revised ZIP SHA/version, create isolated venv; install dependencies,
  rerun packaged tests. Inspect Python 3.14 native dependency compatibility.
- `desktop_diagnostics`: capture real COM HRESULT/session failures separately
  from corner failsafe. Confirm correct interactive user desktop.
- `list_windows` → bind exact Calculator → activate → screenshot. Image must
  include provenance and only target pixels. Test normal/maximized/minimized.
- Native six-step 12×8 test; reinspection/96 and stale-ID rejection as before.
- Switch/occlude app before and during screenshot; no unrelated pixels may be
  returned. Check PrintWindow with hardware-accelerated/UWP surfaces for blank
  or incomplete images; no desktop fallback is allowed.
- Test window-local mouse mapping, including invisible maximized borders; fresh
  screenshot required after mutations/resize/movement.
- Disposable Notepad Unicode `café 日本語 😀\nsecond line\ttab`, exact result and
  unchanged clipboard. Test mid-input focus change and report the unavoidable
  foreground-input race rather than claiming atomic targeting.
- Test native-call hang, cancel_pending, MCP task cancellation and queued calls.
  Target must clear; no auto replay. Observe partial input/held keys and app-side
  work that may survive worker termination.
- Truncated depth8 search and deeper retry; compare error/truncation metadata.

## Real-use feedback

Record task intent, version/environment, elapsed model wall time, app initial
state, result independently observed, interruptions/recovery, false success,
wrong-target/capture leakage, human interventions and evidence references. Ask
whether host focus/cursor was disturbed, how recovery felt, and which apps fail.
Keep native harness timing separate from model timings; separate smoke evidence
from 20-trial controlled benchmark outcomes. Preserve previous v0.2 logs unchanged.

New native Windows/macOS behavior, VM isolation and HTTP-tunnel setup are not
certified by cloud tests. Return measured findings as another delegation so the
cloud session can revise code. Do not claim model parity from these smoke tests.

## Resolve the user's own-cursor observation

The user reports that ChatGPT/Codex computer use has a cursor. Do not infer that
it shares the physical OS cursor, or that it is a VM, from appearance alone.
While Codex operates existing native apps, have the user move the physical
mouse and type in a disposable host app. Record physical pointer position,
visible agent cursor location, host focus, keyboard destination, and target
app result concurrently. Determine whether both inputs actually work independently
in the same OS session. Document the exact product/tools. Current PyAutoGUI/
SendInput uses the runtime's shared OS input; a VM is an available isolation
option, not a claim about Codex's internals. Use measured results to choose a
future same-desktop background adapter if that is the behavior the user needs.

## v0.3.1 follow-up

Retest all Windows fixtures: Runtime now leaves ID interpretation to its injected
adapter, while Windows.record owns int conversion. The cloud simulates Windows,
Mac and Linux with opaque fake IDs; real Windows suite still needs a rerun.

Use exact previously enumerated IDs, not ambiguous Calculator titles. After
Invoke maximize/minimize/restore, wait_for_window_state then screenshot; keep
settled geometry success separate from the one SetForegroundWindow refusal.
The refusal now instructs manual taskbar/Dock/Alt-Tab selection without bypass.

For Japanese input, run the README's controlled ASCII-source batch/ paced
probes in fresh synthetic empty Notepad editors. Capture editor identity,
fixed payload and received hashes/UTF16 units, accepted events, actual
DocumentRange/codepoints and strict newline-normalized equality. Record failed
probes honestly. No root cause or paced remedy has been proven; do not certify
Unicode from accented/emoji success or unchanged clipboard alone. Keep original
v0.3 evidence unchanged and send measured v0.3.1 findings back by delegation.

## v0.3.2 follow-up

Preserve v0.3.1's 77-test pass and both text results separately. Run 20 trials per mode/case with fresh preflight-confirmed empty synthetic editors, exact window IDs and exact normalized content checks. Cases: mixed, ascii-distinct, ascii-repeat, cjk, emoji. Record successes, failures, duration, focus changes and receipts; do not replay into failed nonempty documents. Prepared scan units are not OS delivery evidence.

Run a separate 20-trial mixed-text series through public `type_text` with its new default paced mode, then read-only `unicode_probe --mode observe --case mixed`. The CLI mutation probe additionally pins the editor before dispatch and can change timing. Do not pool these series. Paced calls now reject more than 128 characters before dispatch. Neither one paced success nor all accepted events establishes reliable typing. Root cause remains unresolved.

Record the different deadlines: public MCP defaults to 8 seconds; CLI probe uses 12. The 128-character cap does not guarantee completion on slow hosts. Cancellation can leave partial text.

## Activity companion acceptance checks (new, native untested)

Verify the banner remains visible, halo follows physical pointer without stealing focus/clicks, and capture/occlusion guards still behave correctly. Press physical Escape during paced typing, native stall, and between calls: worker must cancel and subsequent model calls reject. Resume must remain disabled until cancellation completes; only a local user click resumes, with discarded target requiring rebind. Kill the companion and confirm fail-closed behavior. Test repeated stop/resume, multi-monitor/DPI, Windows focus and macOS Input Monitoring denial. Record visual screenshots using synthetic windows only. Shared system cursor remains shared.

Also test agent-injected Escape: it may trigger the same stop latch. Do not describe the current listener as physical-key-only.

## v0.3.3 stop gate and integration diagnosis

`wait(0)` must reject while stopped; a pending wait must reject after stop, including stop+resume before its next poll. `cancel_pending` remains available. Keep testing physical Esc/local Resume separately from timeout errors.

For the full-stdio 8-second worker deadlines, retain each exact error/method and launcher command. Compare the installed console entry point against `python -m claude_computer_use.server` using the same venv, interactive desktop, environment and default deadline; isolate status then bind in a clean session. Capture process startup/exit timing and stderr without unrelated editor content or credentials. Compare direct controller vs actual stdio in separate trials. Do not infer an Escape stop or raise the production timeout to declare success. Submit logs before assigning a cause.

## v0.3.4 Windows acceptance

Run native private-pipe test in `test_worker_launch.py`, then both actual MCP launchers at unchanged eight-second deadline. Status and bind must return successfully; preserve module/console outcomes separately. Run with `CLAUDE_COMPUTER_DIAGNOSTICS_DIR` set to a fresh directory and return phases/stack logs if anything stalls. Worker entry no longer reimports the MCP main module and inherits only its private pipe HANDLE; this is a candidate startup correction, not a measured fix. Check worker cleanup after parent termination and native cancellation.

Compare native banner/cursor captures against user's supplied photo. Banner: top-center blue rounded bar, white “Claude is using your computer” and “Esc to cancel”. Cursor: dark arrow, white outline, diffuse blue glow, true pointer-tip anchor. Test click-through, focus, primary/secondary/DPI behavior and native pointer layering. Banner is interactive and deliberately occludes underlying controls. Test local cancel button as well as physical Escape and Resume. Confirm resumed tasks rebind and old pending calls fail.

## v0.3.5 native process-tree regression

Rerun suite including native private-pipe test: ping PID must belong to tracked launcher's descendant tree; sampled launcher/interpreter processes must all exit within 0.5s of cancellation. Preserve actual runtime PID, launcher PID and tree separately. This changes the test's incorrect PID equality assumption; production launcher remains the measured v0.3.4 implementation.

Repeat actual MCP status/bind at default eight seconds to detect regressions. Physical Escape and human Resume remain separate acceptance checks; discard the earlier tester `capture_window` typo result. Do not score unconfirmed physical key source or invalid postResume command as acceptance.

## v0.3.6 single visible pointer

Verify that moving over buttons, editor text and resize borders shows exactly the native pointer plus soft blue glow, with no second arrow. Native pointer shape follows OS/app settings. Verify click/drag pass-through and companion termination leaves the native cursor visible without restoration. Banner is unchanged.

Preserve physical Escape/local Resume feedback and successful discarded-target/rebind harness separately from the unresolved longer-hold result. Before cleanup in future stop/hold failures, snapshot companion is_alive/exitcode, stopped/acknowledged and timestamps. Test repeated cycles, physical Escape during paced typing and local cancel button separately.

## v0.3.7 Windows native arrow replacement

New Windows-only guard replaces OCR_NORMAL with a 48-pixel arrow while active; I-beam, resize, busy and custom app cursors remain native. Confirm one pointer over buttons/text/borders. Compare native active arrow and blue glow to reference. Capture original pointer before enabling and verify restoration after physical Escape, cancel button, clean server exit, companion kill and parent kill. Repeat Resume cycles: restoration must complete before Resume acknowledgement, then replacement reapplies while active.

Test guard-process termination separately: surviving parent must block calls and reload configured scheme. Test a second simultaneous server: mutex ownership collision must refuse startup without modifying the first server's cursor. Simulate native installation/restore failures where feasible. Native replacement, restoration, DPI and guard failures are unvalidated in cloud. Forced death of both controller and guard may require manual scheme reload; preserve cursor-shape evidence, not just successful API return.

## v0.3.8 forced-guard shutdown and transition latency

Kill only the guard as in the measured v0.3.7 repro, join it, then call server cleanup. Require a bounded return, exact cursor restoration, and no surviving owned processes. Shared event/epoch synchronization has changed; retest physical Escape/Resume cycles and both actual MCP launchers at the original eight-second deadline. Bounded state locks must reject without hanging if their owning process dies. Verify fail-fast ownership collision leaves the first session's arrow unchanged.

User-visible lag is not localized. Clarify whether it is initial activation, Escape restoration, Resume reapplication or banner update. With diagnostics enabled, compare activity.escape_received/resume_click against cursor.install/restore begin/end and activity.stop_acknowledged. Record physical click/key-to-visible-frame time separately; synthetic 21–28 ms bitmap restore is not user-perceived end-to-end latency. Preserve traces before cleanup.

## v0.3.9 terminal Escape policy (supersedes Resume tests)

Physical Escape and banner Cancel must end the session completely. Verify native worker cancellation, exact cursor restore, disappearance of banner/glow/companions, MCP server exit/disconnection and no sampled owned processes remaining. Claude Code host remains open. No Resume button and no silent automatic relaunch. Native API cleanup must complete before server exit. A failed restore/cleanup must block input and must not fire the exit callback. Test pending native work and idle sessions through BOTH actual MCP launchers.

After explicit user request to continue, launch a fresh server, check unbound state, bind target and verify any partial app-side result. Preserve v0.3.8 physical Resume callback timing as historical evidence, not terminal-exit acceptance. Current global listener can also react to injected Escape; report that behavior separately.

Measure Esc-to-banner/halo-disappearance, cursor restoration and MCP EOF separately. Observe Claude Code for at least ten seconds after EOF: detect any host-driven restart or model retry. The server does not relaunch itself; host reconnection behavior must be validated rather than assumed. There must be no visible paused/Resume state.
