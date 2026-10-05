# Independent harsh-critic review — v0.3.7

Review date: 2026-10-04.

**PASS: local prototype gate for Windows native-arrow replacement and restoration coordination.**

**NOT VALIDATED: real Windows cursor replacement/restoration, repeated physical stop/resume cycles, native failure recovery, DPI/accessibility scaling, or macOS replacement.**

## Independent evidence

Independently reran the default local suites: 110 passed and one native Windows worker-launch test skipped on Linux. Syntax compilation passed. Native-cursor tests comprise lease ownership, API call contracts, stale-epoch rejection, an explicitly interleaved Resume/state-read regression, and execution of the actual guard loop with a fake API. Activity tests cover cancellation-before-restoration, restoration failure, and disabled acknowledgement. These tests do not execute Win32 cursor APIs, bitmap rendering, Qt, or physical input.

## Review failures resolved

Initial review found that a stale restoration Event could acknowledge a new Resume cycle, and that a fallback exception could prevent cancellation of already-running native work. The latter was independently reproduced with zero worker cancellation attempts after fallback failure.

Cancellation now precedes restoration/fallback; failed restoration leaves Resume unacknowledged. Restoration acknowledgements carry a generation, and the guard snapshots generation/paused state under the same dedicated lock used for atomic local Resume. A forced-interleave test blocks the guard during Resume's partial update and confirms it reads the completed pair, eliminating the inconsistent new-generation/old-pause acknowledgement found in re-review. The monitor does not hold that cursor-state lock while awaiting restoration.

## Design assessment

Replacement is limited to OCR_NORMAL. Text, resize, busy, and application-defined cursor semantics are preserved. The larger arrow uses a fixed 48-physical-pixel black/white bitmap; the overlay paints glow only, avoiding a second arrow. This is Windows-only. Mac retains its native pointer with glow.

The guard holds a private copied original and supplies disposable handles to SetSystemCursor, which consumes installed handles. CopyImage contracts avoid shared/copy-return-original flags. Partial install failure triggers restoration, readiness follows successful install or paused restoration, and repeated loop tests preserve one original snapshot across cycles.

A session-local named mutex rejects another owner. Parent and companion PID/birth identities are monitored. Guard death blocks public calls; surviving-parent fallback reloads the configured cursor scheme. That fallback may differ from a preexisting temporary cursor override. Simultaneous forced termination cannot guarantee restoration, and the manual scheme-reload recovery is documented.

No further local implementation blocker was found. Approval is for the local code/test baseline, not a guarantee that every native resource, process termination, or system preference interaction behaves correctly.

## Required native acceptance

On real Windows, measure original/replacement/restored arrow identity, shape, hotspot, dimensions, and resource lifetimes. Test normal startup/shutdown, partial install and restore failure, repeated physical Escape/Resume, companion loss, parent loss, guard-only loss, mutex collision, and forced cleanup. Confirm worker cancellation precedes restoration acknowledgement and no input resumes when restoration fails.

Test installed-console and module MCP launchers, scaling/accessibility configurations, app-defined cursors, click-through glow, and preserved text/resize cursor roles. Preserve custom original cursor settings and verify fallback limitations honestly. Existing historical human feedback on prior versions does not validate this newly introduced system-cursor replacement.

Reliable Unicode, native Mac operation, VM isolation, independent cursor behavior, and controlled ChatGPT/Codex parity remain unestablished. Mac native replacement is explicitly unsupported in this version.
