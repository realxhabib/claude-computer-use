---
name: setup
description: Prepare or troubleshoot this plugin's local desktop server dependencies. Does not start computer control.
disable-model-invocation: true
---

Prepare this computer-use installation without launching the desktop server.

1. Check `uv --version`. If absent, explain that uv is the one prerequisite. On
   Windows use `winget install --id astral-sh.uv --exact`; on macOS with Homebrew
   use `brew install uv`. Follow the user's authorization for installation.
   Restart the terminal and Claude Code after installation to refresh PATH.
2. Run the following as an argument array if possible, preserving paths with spaces:

   `uv sync --project "${CLAUDE_PLUGIN_ROOT}" --python 3.12 --frozen --no-editable`

   Set the environment variable `UV_PROJECT_ENVIRONMENT` for that command only to
   `${CLAUDE_PLUGIN_DATA}/runtime-v0.4.1`. This must match the bundled .mcp.json.
   Do not sync the environment in the user's working project. Let downloads finish;
   report dependency errors honestly. This command does not start the GUI server.
3. Tell the user to reconnect the plugin's local-computer server using `/mcp` when
   they want to start computer use. Never reconnect automatically after Esc.
4. If an old manually registered local-computer server exists, explain how to remove
   that duplicate with `claude mcp remove local-computer` using its original scope.
   Keep the plugin's bundled server. Do not disable cursor ownership checks.

macOS needs Accessibility, Screen Recording and Input Monitoring permissions.
Windows needs an unlocked interactive desktop; WSL/service sessions aren't supported.
Do not claim this setup verifies native capture, input, cancellation or macOS support.

If `start_computer_use` fails, preserve its complete `Activity startup failed`
message: phase, child PID, exit code and any traceback. Do not summarize it as a
macOS permissions issue on Windows. Do not retry repeatedly or disable Esc.
A failure at `spawn_pending` can precede the reporting wrapper; collect this
plugin server's stderr from Claude's MCP/debug log in that case. Exclude unrelated
conversation/tool logs and secrets from any report.
