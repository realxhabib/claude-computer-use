# Independent harsh-critic review — v0.3.0

Review date: 2026-10-04.

**PASS: local prototype gate.** No remaining blocker to that limited gate was found after revision and re-review.

**NOT VALIDATED: native Windows/macOS v0.3.0 operation and VM concurrent-host isolation.**

**NOT BENCHMARKED: controlled ChatGPT/Codex comparison or parity.**

## Independent local evidence

Independently executed 60 tests, all passing, with no skips in these suites: runtime 22, MCP server proxies 5, spawned workers 5, window adapter contracts 4, Unicode contracts 4, HTTP authentication 3, native accessibility lifecycle 9, accessibility adapter contracts 6, and validation 2. Syntax compilation also passed.

The worker tests execute real spawned Linux processes. They demonstrate deadlines, queued-request fencing, explicit cancellation, crash recovery, helper-process termination, and deletion of a parent-owned sensitive capture directory. Other desktop/native tests use injected doubles and do not certify OS APIs. This review did not rerun MCP transport/network tests or Windows/macOS native operations.

## Review failures addressed

- Queued requests previously could dispatch after cancellation. Cancellation generations now fence requests before executor/serial dispatch, including idle cancellation.
- MCP task cancellation previously left the native worker running. The async proxy now cancels the matching generation; an old cancellation cannot kill a newer generation.
- Windows maximized invisible resize borders could cause false off-screen rejection. DWM visible bounds and explicit PrintWindow crop offsets now have contract/regression tests.
- Native Unicode paths lacked evidence. Tests now cover Windows INPUT ABI, UTF-16 surrogate pairs, partial SendInput failures, and Quartz UTF-16 lengths/key-down/up.
- macOS capture helpers and temporary PNGs could survive worker cancellation. POSIX process-group termination and parent-owned private capture-directory cleanup address that concern; a real helper-process regression passed. Windows process-tree cleanup remains native-host unverified.
- Coordinate actions now require a new successful target capture after each attempted mutation or frame change.

## Privacy and isolation assessment

The code uses bound-window capture APIs, not desktop capture fallback. Before/after identity, foreground, and geometry checks discard detected mismatches. Provenance accompanies returned pixels. This is a defensible improvement over v0.2 full-primary-display capture, but actual PrintWindow/screencapture behavior must be tested on supported hosts. Black/incomplete surfaces, window-ID reuse, and changes that occur and reverse between checks remain important host-test cases.

Foreground input guards cannot make check/dispatch atomic. This server still shares its runtime desktop's physical cursor, keyboard, and focus. A separate VM is a proposed deployment arrangement, not a provisioned or empirically validated second cursor.

HTTP authentication rejects missing, wrong, and duplicate bearer headers; configuration binds loopback and documentation specifies an authenticated encrypted tunnel, one controller per instance, and shared target state. Authentication middleware is locally tested; actual HTTP/SSH/VM connectivity and isolation are not verified here. It is not a multi-tenant service.

macOS capture writes a private temporary PNG locally. Confirmed ordinary cancellation cleans it, but supervisor crashes or cleanup failures can retain sensitive data. Cancellation cannot roll back input or app-side operations already dispatched, and interrupted chords can leave modifier keys held. These limits are disclosed.

## Historical evidence and comparison

The v0.2 Windows smoke summary preserves user/testing-thread reports: a preopened calculator native harness reached 96 with six stale-reference rejections; two Claude trials were interrupted and did not perform mutation tools; full-desktop capture exposed unrelated content. Their scopes and timings are explicitly separated. This critic did not independently rerun those historical Windows results.

Observed Codex behavior in that report is useful motivation, not a controlled performance benchmark or proof of independent-cursor/target-pixel isolation. Current v0.3 release approval still requires real-host capture, Unicode, DPI, permissions, cancellation, foreground-race, deep-tree, and VM isolation trials. No success-rate, speed, or parity claim is defensible without matching controlled comparative runs.
