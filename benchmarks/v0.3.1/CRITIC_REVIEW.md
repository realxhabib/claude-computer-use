# Independent harsh-critic review — v0.3.1

Review date: 2026-10-04.

**PASS: local prototype gate, including the controlled diagnostic probe.**

**UNRESOLVED: measured Windows Japanese character loss.** Accepted events, fingerprints, and paced mode do not establish correct editor text.

**NOT VALIDATED: v0.3.1 native Windows/Mac behavior, genuine hung-UIA recovery, interrupted held-key cleanup, VM isolation, or controlled ChatGPT/Codex parity.**

## Independent evidence

Independently reran 75 default local tests without skips: Runtime 31, server proxies 5, spawned worker 5, window contracts 4, Unicode contracts 5, controlled probe contracts 5, HTTP authentication 3, accessibility lifecycle 9, accessibility adapter contracts 6, and validation 2. Syntax compilation passed. No network/transport or native Windows/macOS test was executed by this critic for this revision.

## Issues found and resolved during review

- The new Windows placement field initially broke the window contract fixture. Its return tuple is now provided and the suite passes.
- Runtime previously interpreted injected window IDs differently depending on host OS, causing reported Windows fixture failures. Handle conversion now belongs to the Windows adapter, with Windows/Darwin/Linux simulation coverage.
- TextPattern alone did not establish a safe writable editor. The private probe now checks target ancestry, protected status, supported editor role, enabled/focusable state, and explicitly false read-only state before reading document text.
- Empty-state and focused-editor identity checks now occur again immediately before initial probe input.
- Batch input could continue into another same-window editor after Tab/Enter. The probe's pinned editor guard now runs before every native text piece and Tab/Enter dispatch. A regression demonstrates that a Tab-induced editor switch rejects the following text.

The focused-editor checks still have an unavoidable check/dispatch race. They are a mitigation, not atomic field targeting or a guarantee that another actor cannot alter document contents between checks.

## Scope and diagnostic honesty

The opt-in probe is Windows-only, uses a fixed ASCII-escaped synthetic payload, requires an explicitly confirmed empty disposable editor for mutation, executes through the regular killable worker, and is not exposed as an MCP tool. It reads editor content into its report; reports must contain synthetic data only. Protected/out-of-target fields are rejected before text retrieval in contract tests.

The probe reports caller/worker payload fingerprints and codepoints, expected UTF-16 units, native accepted-event counts, focused editor identity, actual DocumentRange text, and an exact comparison after newline normalization. Accepted-event counts are not an OS delivery trace or proof of text consumption. Paced mode remains an experimental diagnostic alternative.

The new window-state wait requires three consecutive stable OS-state observations and reports that app rendering/content verification is separate. It does not turn geometry settlement into a guarantee of app completion. Foreground activation refusal is surfaced with manual recovery guidance, rather than a bypass of OS rules.

## Measured history and remaining gates

The preserved v0.3 Windows summary reports native Calculator/capture/geometry successes, 22 fixture errors, Japanese loss despite unchanged clipboard, and injected-worker deadline/cancellation timings. Those tests are valuable partial evidence, not a controlled success-rate benchmark. The reported injected stalls do not establish genuine blocked UIA behavior or held-key recovery. This critic did not independently rerun the original Windows logs.

No root cause for the Japanese loss is established. Before claiming Unicode support, rerun the controlled batch and paced probes on the real Windows host and independently compare actual document content. A new Windows run must also confirm corrected packaged fixtures. Mac, DPI/session boundaries, real native hang/cancellation, and VM concurrent-host use remain required host-validation work.

The package still controls its runtime desktop's shared pointer/focus. The historical report says Codex also moved the physical pointer in that observed setup; that is not a universal product claim. No independent shared-host cursor or ChatGPT/Codex parity is established.
