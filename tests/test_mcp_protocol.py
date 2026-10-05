"""Actual native desktop MCP stdio: discovery plus worker-backed status."""
import asyncio
import os
import sys
import unittest
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = None


@unittest.skipIf(sys.platform not in {"win32","darwin"}, "Desktop companion needs native GUI host")
@unittest.skipIf(ClientSession is None, 'Install project dependencies to exercise MCP')
class ProtocolTests(unittest.TestCase):
    def test_startup_tool_discovery_and_errors(self):
        async def check():
            root = Path(__file__).resolve().parents[1]
            env = dict(os.environ, PYTHONPATH=str(root / 'src'))
            params = StdioServerParameters(command=sys.executable,
                args=['-m', 'claude_computer_use.server'], env=env, cwd=root)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    discovered = await session.list_tools()
                    names = {tool.name for tool in discovered.tools}
                    self.assertTrue({'inspect_ui', 'find_elements', 'read_element',
                                     'act_on_element', 'screenshot', 'click',
                                     'press_keys', 'computer_status'} <= names)
                    error = await session.call_tool('find_elements', {'name': '', 'role': ''})
                    self.assertTrue(error.isError)
                    self.assertIn('Provide a name or role', str(error.content))
                    error = await session.call_tool('wait', {'seconds': -1})
                    self.assertTrue(error.isError)
                    self.assertIn('between', str(error.content))
                    started = await session.call_tool('start_computer_use', {})
                    self.assertFalse(started.isError, str(started.content))
                    ok = await session.call_tool('wait', {'seconds': 0})
                    self.assertFalse(ok.isError)
                    # Discovery alone missed measured Windows worker timeouts.
                    status = await asyncio.wait_for(session.call_tool('computer_status', {}), timeout=12)
                    self.assertFalse(status.isError, str(status.content))
                    ended = await session.call_tool('end_computer_use', {})
                    self.assertFalse(ended.isError, str(ended.content))
                    inactive = await session.call_tool('wait', {'seconds': 0})
                    self.assertTrue(inactive.isError)
                    restarted = await session.call_tool('start_computer_use', {})
                    self.assertFalse(restarted.isError, str(restarted.content))
                    unbound = await session.call_tool('screenshot', {})
                    self.assertTrue(unbound.isError)
                    self.assertIn('No target bound', str(unbound.content))
                    self.assertFalse((await session.call_tool('end_computer_use', {})).isError)
        asyncio.run(check())
