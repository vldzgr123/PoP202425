from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLTransportWSHandler
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute, Route
from starlette.websockets import WebSocket
from starlette.responses import PlainTextResponse
import uvicorn

from .app import schema

# Принудительно используем legacy протокол
class LegacyWSHandler(GraphQLTransportWSHandler):
    async def handle(self, websocket: WebSocket, context_value):
        # Добавляем поддержку legacy протокола
        async def send(message: str):
            await websocket.send_text(message)
        
        async def receive():
            return await websocket.receive_text()
        
        await super().handle(send=send, receive=receive, context_value=context_value)

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    handler = LegacyWSHandler()
    try:
        await handler.handle(websocket, {"websocket": websocket})
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

app = Starlette(
    debug=True,
    routes=[
        Route("/graphql", GraphQL(schema, debug=True)),
        WebSocketRoute("/subscriptions", websocket_endpoint),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)