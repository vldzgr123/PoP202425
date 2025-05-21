from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLTransportWSHandler, GraphQLHTTPHandler
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from .app import schema

# Настройка CORS
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
]

# Создание ASGI приложения
app = Starlette(
    middleware=middleware,
    debug=True,
)

# Настройка GraphQL эндпоинта
app.mount("/graphql", GraphQL(
    schema,
    debug=True,
    http_handler=GraphQLHTTPHandler(),
    websocket_handler=GraphQLTransportWSHandler()
))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)