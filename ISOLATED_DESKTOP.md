# Independent cursor: dedicated VM desktop

An agent operating generic apps needs a separate GUI session to avoid stealing
the host's focus and cursor. This package connects to such a desktop; it does
not provision it. A VM owns its cursor, keyboard state, apps and display. Sharing
selected files is a separate filesystem arrangement; native host apps aren't
inside that VM. macOS guests require a suitable Mac virtualization setup.

## VM-side server

Create/start a Windows or macOS VM, log into its desktop, install Python and the
package there, and open a terminal **inside that interactive GUI session**.
Starting the GUI worker through Windows SSH/service session 0 does not substitute
for that session. Keep the guest logged in/unlocked and avoid manually manipulating
the guest cursor while the agent works. You can use the host freely.

Generate a random secret into `CLAUDE_COMPUTER_HTTP_TOKEN` without committing it.
For example in Windows PowerShell inside the VM:

```powershell
$env:CLAUDE_COMPUTER_HTTP_TOKEN = (.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))")
.venv\Scripts\claude-computer-use.exe --transport http --port 8765
```

The HTTP endpoint is `http://127.0.0.1:8765/mcp` in the VM. It only binds loopback
and requires one matching `Authorization: Bearer ...` header. Treat the server as
one-controller-per-instance; multiple clients would share target state. Do not
expose it directly to the LAN or Internet. HTTP is for the encrypted tunnel below,
not a public deployment. The VM/transport configuration is not tested in this
Linux session; verify on the guest before relying on it.

## Host connection

Use the VM's already-configured authenticated SSH connection only as a TCP tunnel:

```sh
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 vm-user@vm-host
```

The GUI server remains running in the logged-in VM desktop. SSH is not launching
its GUI worker. Configure Claude Code on the host with an HTTP MCP server URL
`http://127.0.0.1:8765/mcp` and Authorization header containing the VM token.
Consult your Claude Code version's `mcp add --help` for HTTP/header flags, or use
its MCP JSON configuration UI. Avoid committing the credential to a project or
passing it in visible process arguments; store it in a private user configuration.
Load the skill plugin on the host too.

## Verify isolation before ordinary use

1. `computer_status.runtime_machine` must identify the VM, not the host.
2. `list_windows` must show guest apps only. Bind the guest calculator and capture it.
3. Record host cursor/focus, then perform guest calculation while moving the host
   mouse and typing in a disposable host text editor. Guest result must be 96;
   host cursor/focus/text must not be changed by guest automation.
4. Repeat while switching host apps. Collect guest provenance, host observations,
   task result and cancellation behavior. A tester independently scores the result.
5. Disconnect the tunnel and cancel the server: failure must be reported without
   falling back to controlling the host desktop.

Until these tests pass on a real VM setup, independent-cursor operation is an
architecture/setup option, not a certified behavior. On a shared desktop the
plugin continues to use the one OS cursor and must stop/recover on focus changes.
