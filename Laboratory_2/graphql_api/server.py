from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLTransportWSHandler, GraphQLHTTPHandler
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from graphql_api.auth import AuthService
from fastapi import FastAPI, Request, HTTPException
import uvicorn

from .app import schema

class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith('/graphql'):
            auth = request.headers.get('Authorization')
            if not auth or not auth.startswith('Bearer '):
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            token = auth.split(' ')[1]
            if not AuthService.verify_token(token, "user_service"):
                raise HTTPException(status_code=403, detail="Invalid token")
        
        return await call_next(request)

app = FastAPI()
# Настройка GraphQL эндпоинта
app.mount("/graphql", GraphQL(
    schema,
    debug=True,
    http_handler=GraphQLHTTPHandler(),
    websocket_handler=GraphQLTransportWSHandler()
))

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)