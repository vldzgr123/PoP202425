from fastapi import Request, HTTPException
from graphql_api.auth import AuthService

async def jwt_middleware(request: Request, call_next):
    if request.url.path.startswith('/graphql'):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        token = auth_header.split(' ')[1]
        # Для user_service ожидаем аудиторию 'user_service'
        payload = AuthService.verify_token(token, "user_service")
        if not payload:
            raise HTTPException(status_code=403, detail="Invalid token")
        
        request.state.service_id = payload.get('service_id')
        request.state.scopes = payload.get('scope', [])
    
    response = await call_next(request)
    return response