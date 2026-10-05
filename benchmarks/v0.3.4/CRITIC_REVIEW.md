# Independent harsh-critic review — v0.3.4

Review date: 2026-10-04.

**PASS: local prototype gate for the dedicated-worker launch, diagnostics, and reference-style UI changes.**

**UNVERIFIED: resolution of measured Windows full-MCP deadlines, real private-handle inheritance, native appearance/focus/click-through, physical Escape/Resume, and reliable text input.**

## Independent evidence

Independently reran the default local suites: **96 passed and one native Windows launch test explicitly skipped** on Linux. The passed suites include real spawned Linux worker cancellation/helper cleanup, mocked Windows launch contracts, parent identity/error contracts, diagnostics, UI geometry, runtime controls, and activity stop-state behavior. Syntax compilation passed.

The skipped test checks actual Windows private-pipe ping/cancellation. It is not a success. Native stdio/HTTP desktop tests were not executed by this critic. The strengthened stdio test now requires worker-backed computer_status, which is a useful acceptance check but remains native-host unrun here.

## Launch and lifecycle assessment

The production Windows path now invokes a dedicated minimal worker module through subprocess, supplies an explicit private pipe handle list, detaches stdin/stdout, and avoids reimporting the MCP main module. This is a plausible architectural improvement over the previous spawn path. It does not establish which part of prior startup caused the eight-second timeouts, nor prove their resolution.

Reviewed launch contracts preserve prior handle-inheritance state on success/failure. The child verifies the launcher's supplied PID and birth time before serving requests, and its parent watcher fails closed on process identity mismatch or psutil errors. These address review findings that attaching to a parent PID after launch could accept a reused process and that monitor errors could silently defeat orphan protection.

Cancellation still fences queued calls, discards target state, and uses the process wrapper for termination. Process creation and synchronous send are not independently preempted; only the response-wait path has the existing deadline enforcement. That scope is now disclosed. Native Windows handle lifetime, interactive desktop/session behavior, process-tree termination, and parent-death behavior need real host validation.

## Diagnostic assessment

Optional phase checkpoints separate parent spawn/send/receive from worker entry/import/construction/dispatch/send. Logs omit request argument values and editor text. Timed stacks begin after worker request receipt and cannot diagnose a stall that prevents worker entry; external startup/stack capture may still be needed. Diagnostics provide evidence, not a causal conclusion. Logging does not justify raising the unchanged production timeout and declaring the integration fixed.

## Visual assessment

The implemented top-center rounded blue banner, Claude wording, cancellation control, and black arrow with white outline/soft blue glow are a reasonable reference-based interpretation. Geometry tests verify positioning and that the arrow tip tracks the actual pointer hotspot. Nonactivating and input-transparent cursor-overlay flags are retained; local Resume and stop acknowledgement are preserved.

No rendered native comparison was performed. The supplied photograph is not a pixel-exact specification. The system pointer remains and may overlap the overlay; the arrow path itself is 23 device-independent pixels tall while the glow occupies a larger area. Actual perceived size, native overlap, scaling, visual similarity, and focus/click-through must be judged from host captures. The banner intentionally receives clicks and can occlude underlying controls. Its screen follows the pointer, while target automation remains limited to the primary display.

## Required acceptance

Preserve earlier failing Windows evidence. Test both installed console and module MCP launchers with the same environment, private ping, worker-backed status/bind, phase logs, and the unchanged eight-second native deadline. Successful discovery or a fast direct harness does not clear actual MCP failures.

Collect native screenshots and independently verify target capture, arrow hotspot/scaling, banner appearance, clicking, physical/injected Escape, local Resume, companion death, cancellation, and parent death. Text corruption and generic paced reliability remain separate unresolved work. No independent cursor, VM isolation, or ChatGPT/Codex parity is established by this local approval.
