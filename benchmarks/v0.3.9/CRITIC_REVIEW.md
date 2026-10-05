# Independent harsh-critic review — v0.3.9

Review date: 2026-10-04.

**PASS: local prototype gate for terminal Escape semantics.**

**PENDING: real Windows/Mac Escape-to-disconnect, process/cursor cleanup, and Claude host reconnect behavior.**

## Independent local evidence

Independently reran the default local suites: 123 passed and one native Windows worker-launch test skipped on Linux. Syntax compilation passed. Activity tests cover terminal ordering, running-state behavior, cleanup failure, actual nonterminating companion rejection, and idempotent serialized closure. Native cursor contracts reject unconfirmed root termination. No native terminal-Escape or MCP disconnect test was run by this critic.

## Terminal behavior assessment

The user-facing companion has no Resume control. Escape/cancel latches stop, blocks admission, cancels native work, confirms cursor restoration, closes guard and indicator, and only then invokes the server's terminal exit callback. The banner/glow are hidden on the next UI timer frame after stop. The actual MCP entry point exits its own server process after completed cleanup; it does not deliberately terminate Claude Code or the host application.

The direct testing harness uses no exit callback by default, allowing it to inspect cleanup after the companions close. That harness behavior is intentionally distinct from the production MCP exit and must not be mistaken for native EOF validation.

## Review finding resolved

Initial teardown methods killed/joined processes without confirming their roots were dead, allowing the terminal callback after unconfirmed cleanup. I reproduced Activity.close returning while a process double remained alive.

Both guard and companion now reject unconfirmed root termination. Activity closure is parent-thread serialized and idempotent. The actual terminal path is tested with a nonterminating companion and does not invoke exit. Cleanup/restoration failures remain explicit failures rather than a false successful session end.

No further local blocker was found in this limited semantic change. Historical generation/Resume helpers retained for tests do not provide a user-facing resume path.

## Required native acceptance and boundaries

Verify physical and injected Escape through real MCP: pending calls reject/disconnect, original cursor identity is restored, guard/worker/companion roots and sampled descendants exit, no Resume control remains, and Claude stays open. Test idle and in-flight requests, restoration/termination failure, and a fresh deliberately started session afterward.

The server can close its connection; it does not control whether a Claude client automatically reconnects or restarts a configured MCP server. That behavior must be observed and handled explicitly before promising a terminal user-visible computer-use session. Do not infer it from a direct Activity harness or a mocked exit callback.

Historical v0.3.8 callback/API timings and user reports of instant transitions apply to that earlier policy. They do not validate v0.3.9 end-to-end terminal latency. Cursor restoration and cleanup still occur before exit, so visible UI removal is not proof that all cleanup has finished.

Reliable Unicode, Mac replacement, independent-cursor/VM behavior, and controlled ChatGPT/Codex parity remain separately unestablished. This approval covers the local terminal-stop implementation baseline only.
