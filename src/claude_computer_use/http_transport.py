"""Loopback-only authenticated transport for a dedicated interactive VM desktop."""
import hmac


class BearerGate:
    def __init__(self, app, token):
        if len(token) < 32: raise ValueError('HTTP token must contain at least 32 characters')
        self.app, self.token = app, ('Bearer '+token).encode('utf-8')

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            authorization = [value for name,value in scope.get('headers',[]) if name.lower()==b'authorization']
            if len(authorization)!=1 or not hmac.compare_digest(authorization[0],self.token):
                await send({'type':'http.response.start','status':401,
                            'headers':[(b'content-type',b'application/json')]})
                await send({'type':'http.response.body','body':b'{"error":"Unauthorized"}'})
                return
        await self.app(scope,receive,send)


def serve(mcp, port, token):
    import uvicorn
    mcp.settings.host='127.0.0.1'
    mcp.settings.port=port
    uvicorn.run(BearerGate(mcp.streamable_http_app(),token),host='127.0.0.1',port=port)
