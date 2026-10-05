"""Real authenticated loopback MCP handshake. Does not control a desktop."""
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path


@unittest.skipIf(sys.platform not in {"win32","darwin"}, "Desktop companion needs native GUI host")
@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ['mcp','httpx','uvicorn']), 'Install project dependencies')
class HttpProtocolTests(unittest.TestCase):
    def test_authenticated_loopback_initialize_and_tool_discovery(self):
        import httpx
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
        root=Path(__file__).resolve().parents[1]
        token='test-only-'+('x'*64)
        env=dict(os.environ,PYTHONPATH=str(root/'src'),CLAUDE_COMPUTER_HTTP_TOKEN=token)
        process=subprocess.Popen([sys.executable,'-m','claude_computer_use.server',
            '--transport','http','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        url=f'http://127.0.0.1:{port}/mcp'
        try:
            with httpx.Client(timeout=3,trust_env=False) as client:
                deadline=time.monotonic()+5
                while True:
                    try:
                        response=client.get(url)
                        if response.status_code==401:break
                    except httpx.TransportError:pass
                    if time.monotonic()>deadline:self.fail('Loopback server did not become ready')
                    time.sleep(0.05)
                headers={'Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream'}
                body={'jsonrpc':'2.0','id':1,'method':'initialize','params':{
                    'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'http-smoke','version':'1'}}}
                init=client.post(url,headers=headers,json=body)
                self.assertEqual(init.status_code,200,init.text)
                def message(response):
                    if response.headers.get('content-type','').startswith('application/json'):return response.json()
                    return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith('data: ')))
                self.assertIn('serverInfo',message(init)['result'])
                headers['Mcp-Session-Id']=init.headers['mcp-session-id']
                headers['MCP-Protocol-Version']='2024-11-05'
                notify=client.post(url,headers=headers,json={'jsonrpc':'2.0','method':'notifications/initialized'})
                self.assertEqual(notify.status_code,202,notify.text)
                listing=client.post(url,headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
                self.assertEqual(listing.status_code,200,listing.text)
                self.assertEqual(len(message(listing)['result']['tools']),20)
                # Session ID alone is insufficient without its bearer token.
                denial=client.post(url,headers={'Mcp-Session-Id':headers['Mcp-Session-Id']},json=body)
                self.assertEqual(denial.status_code,401)
        finally:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
