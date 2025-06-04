import jwt
from datetime import datetime, timedelta
from typing import Optional, List

# Общие настройки для всех сервисов
JWT_SECRET = "finance_super_secret_key_123!"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 30

class AuthService:
    @staticmethod
    def create_service_token(
        service_name: str, 
        target_service: str, 
        scopes: List[str]
    ) -> str:
        payload = {
            "iss": "finance-auth",
            "sub": service_name,
            "aud": target_service,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
            "scope": scopes,
            "service_id": f"{service_name}_uuid"
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str, expected_audience: str) -> Optional[dict]:
        try:
            return jwt.decode(
                token, 
                JWT_SECRET, 
                algorithms=[JWT_ALGORITHM],
                audience=expected_audience
            )
        except jwt.PyJWTError:
            return None