import asyncio
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use.http_transport import BearerGate


class HttpTests(unittest.TestCase):
    def test_missing_wrong_duplicate_bearer_rejected_without_calling_app(self):
        for headers in [[],[(b'authorization',b'Bearer wrong')],
                        [(b'authorization',b'Bearer '+b'x'*32)]*2]:
            invoked=[];responses=[]
            async def app(scope,receive,send):invoked.append(True)
            async def send(value):responses.append(value)
            asyncio.run(BearerGate(app,'x'*32)({'type':'http','headers':headers},None,send))
            self.assertEqual(invoked,[])
            self.assertEqual(responses[0]['status'],401)

    def test_authorized_request_and_lifespan_pass_through(self):
        invoked=[]
        async def app(scope,receive,send):invoked.append(scope['type'])
        gate=BearerGate(app,'x'*32)
        asyncio.run(gate({'type':'http','headers':[(b'authorization',b'Bearer '+b'x'*32)]},None,None))
        asyncio.run(gate({'type':'lifespan'},None,None))
        self.assertEqual(invoked,['http','lifespan'])

    def test_short_token_rejected(self):
        with self.assertRaises(ValueError):BearerGate(None,'weak')
