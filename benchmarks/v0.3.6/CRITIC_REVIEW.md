# Independent harsh-critic review — v0.3.6

Review date: 2026-10-04.

**PASS: limited local gate for removing the duplicate drawn pointer.**

**PENDING: native glow appearance/hit-testing and repeated physical stop/resume stability.**

## Independent evidence

Independently reran the default local suites: 96 passed and one native Windows launch test skipped on Linux. Syntax compilation passed. Style geometry, activity stop state, server admission/wait gates, worker lifecycle, and launch contracts pass locally. No Qt native rendering, physical keyboard input, or Windows/macOS integration test was executed by this critic for v0.3.6.

## Change assessment

The companion no longer draws a second arrow. It paints only a diffuse blue glow centered at the native cursor position. The arrow path and its painter logic are removed; the system pointer is neither hidden nor replaced. This directly addresses reported overlapping pointers without introducing a crash-sensitive global cursor-restoration mechanism.

The banner, local Resume acknowledgement, stop latch, nonactivating window flags, input-transparent halo flags, and exact own-halo identity remain. The native OS controls pointer shape and size, so this revision does not guarantee the photographed arrow's appearance or a larger pointer. Local geometry tests establish centering arithmetic, not visual quality or native hit-testing. The filled glow's transparency differs from a hollow ring and should be tested while clicking near/at the pointer.

No new code blocker was found in this limited change. The v0.3.5 process-tree test correction remains included; its Windows-specific test is still skipped here.

## Host evidence and interpretation

Reported v0.3.4 human feedback identifies the duplicate native/drawn cursor, observes physical Escape changing the banner, and observes local Resume working. A corrected harness reports stopped-wait rejection, no target bound after Resume, and successful explicit rebind. These support those specific observed outcomes; they do not establish long-run cycle reliability.

A longer hold probe ended without sufficient recorded state to determine why. It must not be labelled a crash or a successful stability run. Later user feedback that the setup worked does not resolve that missing evidence. Separate parent-death observations report all four sampled descendants gone after one second; that is sampled cleanup evidence, not a universal lifecycle proof.

Preserve those observations separately from v0.3.6 results. Obtain current native captures, verify exactly one visible pointer, glow tracking/contrast/scaling, click-through and occlusion checks, physical Escape, acknowledged Resume, discarded targets/rebind, and repeated idle/active cycles with precleanup process/stop state recorded.

Reliable Unicode, Mac validation, VM isolation, independent cursor operation, and controlled ChatGPT/Codex parity remain unestablished. This approval is for the local implementation baseline and duplicate-pointer correction only.
