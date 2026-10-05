# Independent harsh-critic review — v0.3.3

Review date: 2026-10-04.

**PASS: local prototype gate for the wait-stop correction.**

**NOT ACCEPTED: complete native MCP integration, physical Escape/Resume, reliable text input, VM isolation, or ChatGPT/Codex parity.**

## Independent local evidence

Independently reran 87 default local tests without skips: Runtime 33, server proxies/stop gates 10, spawned worker 5, windows contracts 4, Unicode contracts 6, probe contracts 6, HTTP authentication 3, accessibility lifecycle 9, accessibility adapter contracts 6, validation 2, and activity contracts 3. Syntax compilation passed. No native Windows/macOS or transport/network test was run by this critic for this correction.

## Correction assessment

Previously, `wait()` bypassed the activity stop latch because it slept in the MCP process rather than using the native-call admission path. It now checks the companion and stop state at entry, including a zero-duration wait; checks again between sleep intervals of at most 50 ms; and captures/checks the worker cancellation generation under the activity lock. A completed stop/resume cycle between polls therefore invalidates the old wait instead of allowing it to complete successfully.

Three regressions cover stopped entry, stop during sleep, and a cancellation-generation change after apparent resume. These tests exercise the limited correction meaningfully. `cancel_pending()` intentionally remains available while stopped. A wait result is not proof of application readiness or native integration; app contents still require verification.

No new local blocker was found in this correction. Polling and check/return timing do not make events atomic; UI scheduling and physical stop delivery still require real-host tests.

## Host evidence and remaining failures

Delegated Windows v0.3.2 findings report 86 packaged tests passing, native banner/halo visibility through PrintWindow/window enumeration, and approximately 0.996-second direct-controller status. They also report repeated full-stdio native status/bind calls hitting eight-second deadlines. The faster direct-controller result does not explain or clear the MCP integration failure. This critic did not independently collect those Windows observations.

Physical Escape/Resume acceptance remains pending. Native visibility does not establish global key delivery, click-through behavior, nonactivating focus behavior, or successful resumption with discarded targets. Those outcomes need separate scoring. The cosmetic ShowWithoutActivating flag is an implementation choice, not measured proof.

Preserve v0.3.2 evidence and archive unchanged. Revalidate v0.3.3 stopped and resumed waits through actual MCP, then diagnose the repeated worker deadlines with session/launch/timing evidence. Do not declare the integration functional solely because the local suite passes or the overlay renders.

Prior limitations remain: batch text corruption, only one controlled paced success, no independent cursor on a shared desktop, no native Mac certification, and no controlled comparative benchmark. Local approval is limited to the code/test baseline and this wait-stop fix.
