# Independent harsh-critic review — v0.3.2

Review date: 2026-10-04.

**PASS: local prototype gate for these limited revisions.**

**NOT ESTABLISHED: reliable generic paced text input, root cause of batch corruption, complete Unicode support, or ChatGPT/Codex parity.**

## Independent local evidence

After the activity-indicator revision, independently reran 84 default local tests without skips: Runtime 33, server proxies 7, spawned worker 5, windows contracts 4, Unicode contracts 6, probe contracts 6, HTTP authentication 3, accessibility lifecycle 9, accessibility adapter contracts 6, validation 2, and activity stop-state contracts 3. Syntax compilation passed. Independently checked that a 129-character default-paced MCP request rejects before proxy dispatch, while 128 characters forwards paced mode.

No native Windows/macOS, VM, MCP network transport, or comparative desktop benchmark was run by this critic for this revision. The recorded Windows v0.3.1 evidence is delegated host evidence, not this critic's execution.

## Assessment of changes

Defaulting to paced input is a reasonable experimental response to observed batch corruption. The 128-codepoint limit is enforced before input at both public proxy and runtime boundaries. It reduces predictable oversized requests; it is not a promise to finish within eight seconds. Slow OS/native checks can still consume the deadline, leaving partially typed content. Callers must inspect actual state rather than replay uncertain input.

The known test success was one controlled CLI probe, which pins the focused editor through UIA checks and uses a 12-second worker deadline. Generic MCP input checks target-window identity/foreground and normally uses an eight-second deadline; it does not pin editor identity. These paths have different checks and timing. A successful pinned probe cannot certify the generic path. The revised documentation and tester handoff distinguish them.

Synthetic probe cases now cover distinct/repeated Latin characters, CJK order/repeats, non-BMP emoji/repeats, and mixed newline/tab content. The caller and worker payload fingerprints are compared. Probe-only prepared scan units describe the INPUT array constructed before SendInput; accepted-event counts describe the API result. Neither is an OS delivery trace or verification of editor content. Exact observed DocumentRange content remains the outcome evidence.

The private probe retains opt-in empty-editor confirmation, protected/out-of-target refusal, writable-editor checks, per-dispatch editor pinning, and regular worker cancellation/deadlines. Reports contain explicit synthetic editor text and should not be collected from private documents. Same-window check/dispatch races remain possible.

## Limits and required follow-up

Delegated v0.3.1 Windows testing reports the packaged suite passed, batch input corrupted both Japanese and Latin repetitions, and one paced probe matched exactly. One exact sample is promising but provides no reliability estimate, causal diagnosis, or broad app/layout/version guarantee.

Run repeated independent trials of each synthetic case through both generic MCP paced input and pinned CLI probes, preserving their different deadlines/checks. Include empty-state resets, exact text scoring, clipboard integrity, focus changes, interruption, and partial-result evidence. Batch mode remains explicitly selectable for diagnosis and is known to have failed in measured trials; it must not be presented as dependable input.

Native v0.3.2 revalidation, Mac input/capture, VM concurrent-host operation, real hung-native cancellation, and controlled competitor comparisons remain pending. Local approval does not authorize claims of an independent cursor on a shared host or production-ready whole-computer reliability.

## Activity indicator and Escape-stop revision

The earlier local approval was superseded when the companion UI was added. Initial review found an admission/cancellation race, an own-halo occlusion issue on Mac, and shutdown ordering that could hide the indicator before stopping input. These are now addressed: admission captures the worker epoch under the same lock used for stop acknowledgement, own Mac halo exclusion requires both its actual process ID and exact title, and worker cancellation precedes indicator closure.

Independently checked Mac occlusion with injected window records: only the exact own halo is excluded; a different owner's identically titled window and the activity banner still occlude. Activity contracts verify stop latching, companion death, and cancellation failure leaving Resume unacknowledged. These are local logic tests, not execution of Qt or pynput on a desktop.

**PASS remains limited to the local prototype gate.** The banner, glow, focus behavior, click-through behavior, global Escape delivery, Input Monitoring permission handling, actual stop/resume races, and native companion startup still require Windows/Mac validation. The glowing halo decorates the shared system pointer; it is not an independent cursor.

Escape may be observed when synthesized by the agent, so ordinary menu dismissal can stop the session and require local Resume. This limitation is disclosed. Failure to confirm worker cancellation leaves Resume disabled. A dead companion requires server restart. The private tester-only Unicode CLI does not start this companion and must not be described as sharing the public server's indicator/Escape guarantees.

Native desktop startup is required by the public entry point; Linux transport tests that cannot launch the companion are not desktop validation. Any platform skip must remain separately reported, rather than included among passing evidence. No visual UI or native Escape success is claimed by this review.
