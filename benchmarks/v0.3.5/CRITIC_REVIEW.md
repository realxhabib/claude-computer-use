# Independent harsh-critic review — v0.3.5

Review date: 2026-10-04.

**PASS: local gate for the limited native process-tree test correction.**

**NOT YET VERIFIED: corrected native Windows suite, physical Escape/human Resume, reliable Unicode, Mac behavior, VM isolation, or ChatGPT/Codex parity.**

## Independent evidence

Independently reran the default local suites: 96 passed and one native Windows launch test skipped on Linux. Syntax compilation passed. No native Windows or transport test was executed by this critic for this revision.

## Test correction

The previous native test required the responding interpreter PID to equal the subprocess launcher's PID. Delegated Windows observations showed a venv launcher process with descendant interpreters, including the actual responding worker. Equality therefore encoded an inappropriate assumption about the platform launch topology.

The corrected test requires the ping responder to belong to the tracked root-plus-descendant process tree, retains the uninitialized-runtime and subprocess-wrapper assertions, then checks that every sampled owned process exits after cancellation. It does not simply remove identity or cleanup assertions. This is a defensible correction based on observed process relationships.

No production launch or cancellation change is introduced by this revision. Sampled-tree verification establishes cleanup of the sampled processes; it is not a universal proof that no descendant could escape or be created later. The native corrected test remains skipped here and must pass on the host before declaring the corrected Windows suite clean.

## Delegated host evidence

Preserved v0.3.4 evidence reports 98 packaged tests passed and one native PID assertion failed. Separate cleanup observations identified launcher PID 45060, children 1396/30368, responder 30368, cancellation around 15 ms, and no sampled process alive after 0.5 seconds. The separate cleanup success does not retroactively turn the failed packaged suite into a pass.

Both actual MCP launchers passed status/bind within the unchanged eight-second native deadline in those host observations: module 0.536/0.010 seconds, console 0.550/0.014 seconds. This is concrete evidence that the previously measured startup failures were absent in these trials; it is not an established root-cause diagnosis or a repeated reliability benchmark.

The same report describes Calculator result 96 with stale-reference rejection, injected-Escape rejection of pending waits/subsequent calls, and native visual captures. Physical source attribution and a valid human Resume/rebind/capture acceptance run remain unverified. An earlier post-Resume command typo is invalid evidence and must not be scored as product failure or success.

Local approval is limited to the corrected process-tree test and preserved evidence. Do not infer independent-cursor operation, Unicode reliability, complete physical stop/resume behavior, or competitor parity from it.
