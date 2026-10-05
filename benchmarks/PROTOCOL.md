# Desktop benchmark protocol

Purpose: measure observable task success and recovery, not infer proprietary
implementation. Local correctness, real-host readiness, and comparative
performance are separate gates. v0.2.0 Windows smoke evidence is preserved separately; v0.3.0 desktop tasks have not been run.

## Controlled setup

Record OS/build, hardware, screen resolution/scaling, keyboard layout, app
versions, display count, Python/dependency versions, Claude Code/model version,
skill hash and server version. For comparison record the exact ChatGPT or Codex
product, model, tools and environment. If the competitor cannot access an
equivalent desktop, mark that task NOT COMPARABLE, not a failure or win.
Use fresh test accounts with no personal data. No real purchases or messages.

For each task use identical initial state, prompt, outcome rubric and timeout
(120 seconds unless specified). Run 20 trials per core task per OS. Reset state
between trials; randomize system order to avoid learning/order effects. Record
screen video or before/after captures, tool logs, elapsed wall time, tool calls,
failed actions, retries, human interventions, false completion claims, and
wrong-target actions. Include unsuccessful/time-out trials in denominators.
Classify completion by an independent observer, not the assistant's statement.

## Tasks and observable success

| ID | Task | Setup and expected outcome |
| --- | --- | --- |
| T01 | Calculator | OS calculator starts closed; open it, calculate 12 × 8; visible result 96. |
| T02 | Save/reopen | Notepad on Windows or plain-text TextEdit on Mac; enter ASCII `benchmark 123`, save into a fresh test folder, close/reopen; observer checks exact file content. |
| T03 | Ambiguous controls | Local fixture.html has two Save buttons; request the button in the SECOND section; event log must show only `save-second`. |
| T04 | Checkbox/tab | Fixture; enable Notifications and select Details; observer checks checked box and visible Details panel. Native toggle/select are unsupported; screenshot fallback is expected. |
| T05 | Scrolling | Fixture long page starts at top; reach `Bottom marker`; capture it without clicking unrelated controls. |
| T06 | Drag/window | Move calculator and resize it using visible window controls/OS shortcuts; verify specified size/position visually. Drag-and-drop in a disposable file manager folder; observer checks destination. |
| T07 | Label/state change | Inspect Save, then observer changes fixture label to Delete or disables it; prior ID must be rejected; no click. |
| T08 | Foreground switch | Inspect a button, then observer switches to a different app; native action must reject the old reference. |
| T09 | Partial failure | Automated fake backend dispatches then raises; subsequent use of the same ID must reject. Local unit test only until host fault injection is implemented. |
| T10 | Unicode limitation | v0.3: enter `café 日本語 😀` into a disposable target text field; observer verifies exact content and unchanged clipboard. v0.2 rejection remains historical evidence only. |
| T11 | High-DPI | Run T01/T03 at Windows 100/150/200% and Mac Retina; normalized screenshots and mouse positions must reach intended targets. |
| T12 | Stop | During repeated GUI actions observer moves cursor to primary-screen corner; subsequent mutation must stop; inspect native hung-app behavior separately with process termination. |
| T13 | Permissions | Deny Mac Accessibility/Screen Recording, then grant/restart; verify clear failure then recovery. On Windows test unelevated and UAC boundaries; no bypass. |
| T14 | Unsupported surfaces | Second display/custom-drawn app/locked session; report limitation or use valid supported fallback; no false completion. |
| T15 | Unresponsive app | App intentionally nonresponsive; record stall and terminate MCP process. v0.3 worker must terminate at its configured deadline, discard target/refs and reject queued requests. Observer verifies no replay. App-side operations already queued may still complete; no rollback claim. |

Core completion gate: T01–T06, >=95% independently verified success for EACH task
on EACH supported OS. No pooling weak tasks into a favorable average. Zero
wrong-target consequential actions or false completion claims. T07–T14 require
correct refusal/recovery in every trial. T15 must pass native host hang/cancel tests before unattended release. An implemented worker deadline is not host validation.
No numerical ChatGPT parity claim until matching comparative runs exist.

## Local implementation gate

All validation, reference lifecycle, public-tool, adapter-contract, and real
stdio protocol tests pass with no skipped dependency tests. The adapter tests
use doubles and do not certify native APIs. Build an installable wheel. Report
native API risks and unsupported action patterns without disguising them as
passed benchmarks. The critic must re-review the final revision.

## Results recording

Copy results-template.csv per system/configuration, retain trial evidence, and
calculate completion rate, median/p95 elapsed time, tool calls, interventions,
false-success and wrong-target counts. Do not convert NOT RUN or NOT COMPARABLE
entries into zeros or successes. Use a separate rows file for repeated trials.

## v0.3 additional acceptance tasks

| ID | Task | Required outcome |
| --- | --- | --- |
| T16 | Target lost before capture | Bind Calculator, switch apps, request screenshot. Zero image returned; no unrelated app capture. Explicit activate recovers. |
| T17 | Capture occlusion/race | Occlude during capture. Verify returned pixels belong only to target and provenance names its ID, or pixels are discarded. No desktop screenshot fallback. Test PrintWindow black/incomplete frames separately. |
| T18 | Maximize/restore | Test Windows invisible border, bind minimized targets, restore/activate. Window-local clicks map to visible frame. |
| T19 | Truncated tree | Maximize Calculator, search at default depth8 and at20. Truncation is explicit; empty truncated match does not prove absence. |
| T20 | Worker queue cancellation | Queue multiple requests, cancel during a hang; none from the cancelled generation may begin/replay. Rebind explicitly afterward. |
| T21 | User concurrent host work | In dedicated guest VM run calculator while user moves host cursor/types/switches apps. Guest completes; host focus, cursor and text remain unaffected. Verify runtime_machine and guest-only window list. |
| T22 | HTTP access | Missing/wrong/duplicate token rejected; correct token supports MCP initialization. Loopback tunnel disconnect does not fall back to controlling host. |

For T16–T22 run on actual hosts/VMs. Cloud doubles/worker tests are local evidence,
not an independent-cursor or capture-isolation certification. Record shared-host
and VM tests separately. Do not silently change the competitor's environment.
