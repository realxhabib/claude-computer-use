"""Real stdio MCP stays connected while desktop use is inactive."""
import asyncio
import os
import sys
import unittest
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class IdleProtocolTests(unittest.TestCase):
    def test_one_connection_survives_idle_end_and_rejected_desktop_calls(self):
        async def run():
            root = Path(__file__).resolve().parents[1]
            params = StdioServerParameters(command=sys.executable,
                args=['-m', 'claude_computer_use.server'],
                env=dict(os.environ, PYTHONPATH=str(root / 'src')), cwd=root)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    names = {t.name for t in (await client.list_tools()).tools}
                    self.assertTrue({'start_computer_use', 'end_computer_use', 'computer_session_status'} <= names)
                    for _ in range(3):
                        status = await client.call_tool('computer_session_status', {})
                        self.assertFalse(status.isError)
                        self.assertIn('idle', str(status.content))
                        rejected = await client.call_tool('list_windows', {})
                        self.assertTrue(rejected.isError)
                        self.assertIn('not active', str(rejected.content))
                        self.assertFalse((await client.call_tool('end_computer_use', {})).isError)
                    # Unsupported native startup returns an error, not a dead transport.
                    if sys.platform not in {'win32', 'darwin'}:
                        self.assertTrue((await client.call_tool('start_computer_use', {})).isError)
                        self.assertFalse((await client.call_tool('computer_session_status', {})).isError)
        asyncio.run(run())
