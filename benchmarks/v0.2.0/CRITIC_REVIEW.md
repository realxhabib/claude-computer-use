# Independent harsh-critic review

Review date: 2026-10-04. Scope: final local prototype revision, not desktop certification.

## Verdict

**PASS: local prototype correctness gate.**

**NOT VALIDATED: Windows/macOS release readiness.**

**NOT BENCHMARKED: ChatGPT/Codex comparison or parity.**

The initial review failed the prototype for two reproduced stale-reference defects and insufficient server-level evidence. Those defects are fixed. No remaining blocker to the explicitly limited local prototype gate was found. This does not justify marketing the product as reliable whole-computer automation or as equivalent to ChatGPT/Codex.

## Independently verified evidence

- Accessibility lifecycle: 9 tests passed.
- Native adapter contracts using doubles: 7 tests passed.
- Public server tools using injected desktop: 11 tests passed.
- Input validation: 2 tests passed.
- Python syntax compilation passed.
- Inspected implementation, tests, skill, README, benchmark protocol, fixture, results template, and local evidence artifact.
- Checked recorded implementation hashes against current source files.

These 29 independently rerun tests cover behavior in a Linux test environment. They do not execute native Windows/macOS desktop APIs, test Claude's decisions, or establish real task-completion performance.

The implementing agent captured one real MCP stdio smoke-test pass in 0.514 seconds and recorded wheel build/install evidence in `local-results.json`. I inspected its protocol test and artifact. My attempted independent transport rerun was interrupted while the permission tool was pending; it did not produce a test result. That recorded transport pass is attributed to the implementing agent, not my own execution. Wheel validation likewise uses the implementing agent's evidence.

## Findings resolved

1. `src/claude_computer_use/accessibility.py:179`: native dispatch invalidates references in `finally`, including partial execution followed by an exception.
2. `src/claude_computer_use/server.py:13`: every mutating desktop tool invalidates existing references on successful and failed attempts without initializing a native inspector unnecessarily.
3. Windows focus actions are gated by keyboard focusability; focused state is exposed where available.
4. Public labels/roles are bounded, while full-label fingerprints retain change detection beyond the displayed prefix.
5. Meaningful server and adapter-contract tests supplement the original pure validation/lifecycle tests.
6. Documentation distinguishes dispatch from outcome verification and explicitly describes unsupported native actions, unknown Mac visibility, native-call hangs, held-key risks, and absent policy enforcement.

## Remaining release blockers and limits

- Real Windows/macOS installation, permissions, capture, input, native actions, DPI mapping, cancellation, and app-recovery trials remain NOT RUN.
- Native OS calls can block indefinitely; node limits do not impose a wall-clock deadline. Unattended deployment needs isolated workers and supervision.
- Screenshot fallback is necessary for checked/selected state and field-content verification. Native actions cover Invoke/AXPress and focus, not full UI action patterns.
- Primary-display and ASCII limitations remain; window management is accomplished through GUI interaction/shortcuts rather than dedicated window APIs.
- Model adherence, prompt-injection resistance, wrong-target actions, and false completion claims have not been measured.
- No matching ChatGPT/Codex environment was tested. Internal competitor implementation is unknown; no numeric parity claim is defensible.

## Benchmark acceptance

The committed `PROTOCOL.md` provides repeatable tasks, independent outcome scoring, identical starting states, 20 trials per core task per OS, and a per-task 95% verified-completion gate. False completion and wrong-target consequential actions must remain zero. Unsupported or incomparable conditions must be recorded explicitly, not scored as wins. Results currently say NOT RUN, appropriately.

Passing this review means the prototype now has a defensible local correctness baseline and an honest validation plan. Public release and competitor-performance approval remain withheld pending actual host evidence.
