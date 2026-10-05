# Independent harsh-critic review — v0.3.8

Review date: 2026-10-04.

**PASS: local prototype gate for dead-guard cleanup and coordination changes.**

**PENDING: real Windows v0.3.8 forced-guard cleanup, timing/stability, and native stop/resume revalidation.**

## Independent evidence

Independently reran the default local suites: 117 passed and one native Windows worker-launch test skipped on Linux. Syntax compilation passed. Tests include actual spawned-process hard kills, bounded failure after a killed lock owner, ProcessSignal operations, and actual NativeCursorGuard.close against a killed polling waiter, alongside cursor guard lifecycle and coordination contracts.

Earlier in this review I independently reproduced the failure class: kill a spawned process deliberately holding multiprocessing.Event's condition, then a surviving Event.set remains blocked. That established the vulnerability class. Subsequent delegated Windows stack evidence specifically located the measured cleanup stall in Event.set/Condition notification; that host evidence is separately attributed and was not collected by this critic.

## Changes assessed

Activity and cursor-guard flags now use single-byte RawValue polling signals without owner-held Event condition locks. Cursor generation fields also use raw values, avoiding synchronized-Value locks in fallback/cleanup. Remaining admission and cursor-state locks have bounded acquisition and fail closed. Process readiness checks detect dead initializers without consuming the full ten-second budget.

Cleanup no longer sets an Event that can retain a killed guard's internal lock. NativeCursorGuard.close is exercised with a real killed child in local testing. This is useful regression evidence, but it does not certify Windows API fallback, venv process-tree cleanup, or actual desktop shutdown.

Worker cancellation occurs before coordination/restoration attempts, so orphaned coordination cannot prevent the initial stop attempt. The observer still requires restored cursor state before enabling local Resume. Cursor state pairs retain shared bounded locking; failed acquisition rejects work instead of admitting it.

## Regression found and resolved

Moving cancellation outside the activity lock initially reopened an admission race: a request checked running state, cancellation advanced the worker generation, and the request then captured that new generation and dispatched while stopped. I reproduced that through the actual async server.call with a generation-fenced client.

The server now captures the worker generation at entry before any activity check or admission lock and never refreshes it. A later cancellation invalidates that original token. The wait path uses the same capture ordering. The forced-interleave regression invokes cancellation after the successful admission check and confirms the request is fenced before native dispatch. No remaining local blocker was found in this revision.

## Host evidence and limits

Delegated v0.3.7 evidence reports a passing native suite, 32-to-48-pixel arrow replacement, exact synthetic restoration, rejection of a second cursor owner, both MCP launchers working, physical Escape/Resume, and a ten-second stable observation. It also reports forced-guard cleanup hanging twice despite fallback restoration and fail-closed status. Those earlier successes do not certify the new cleanup implementation.

Reported synthetic restoration/acknowledgement timings are useful specific measurements, not identification of the user's perceived slow transition. Optional phase checkpoints now distinguish Escape receipt, cancellation, Resume, and cursor install/restore. Measure the actual slow transition before claiming its latency fixed.

Single-byte polling and bounded locks trade unbounded owner-lock hangs for polling latency and explicit operation failure. They are not robust-lock recovery or universal crashproofness. Native cursor API calls and other process-start/send paths retain documented limitations. Simultaneous forced loss of controller and guard still cannot guarantee exact cursor restoration.

Revalidate real forced-guard cleanup, both MCP launchers, physical and injected stop, acknowledged Resume, cursor identity, repeated cycles, second-owner failure, parent/companion death, and precleanup process state. Mac, reliable Unicode, independent cursor/VM operation, and ChatGPT/Codex parity remain separately unestablished.
