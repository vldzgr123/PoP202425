import os
import time
import hashlib
from concurrent import futures

import grpc
from generated import user_pb2, user_pb2_grpc
from graphql_api.auth import AuthService
from fastapi import FastAPI
from .auth_middleware import jwt_middleware

app = FastAPI()
app.middleware('http')(jwt_middleware)

class UserService(user_pb2_grpc.UserServiceServicer):
    def __init__(self):
        self.users = {}  # In-memory storage for demo purposes

    def RegisterUser(self, request, context):
        metadata = dict(context.invocation_metadata())
        if 'authorization' not in metadata:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token required")
        
        token = metadata['authorization'].replace('Bearer ', '')
        payload = AuthService.verify_token(token, "user_service")
        if not payload:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Invalid token")
        if request.email in [u['email'] for u in self.users.values()]:
            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            context.set_details('User with this email already exists')
            return user_pb2.UserResponse()

        user_id = hashlib.sha256(request.email.encode()).hexdigest()[:16]
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        
        user = {
            'user_id': user_id,
            'username': request.username,
            'email': request.email,
            'password_hash': password_hash,
            'created_at': time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        }
        
        self.users[user_id] = user
        
        return user_pb2.UserResponse(
            user_id=user_id,
            username=user['username'],
            email=user['email'],
            created_at=user['created_at']
        )

    def LoginUser(self, request, context):
        metadata = dict(context.invocation_metadata())
        if 'authorization' not in metadata:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token required")
        
        token = metadata['authorization'].replace('Bearer ', '')
        payload = AuthService.verify_token(token, "user_service")
        if not payload:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Invalid token")
        user = next((u for u in self.users.values() if u['email'] == request.email), None)
        
        if not user or user['password_hash'] != hashlib.sha256(request.password.encode()).hexdigest():
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details('Invalid email or password')
            return user_pb2.UserResponse()
            
        return user_pb2.UserResponse(
            user_id=user['user_id'],
            username=user['username'],
            email=user['email'],
            created_at=user['created_at']
        )

    def GetUser(self, request, context):
        metadata = dict(context.invocation_metadata())
        if 'authorization' not in metadata:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token required")
        
        token = metadata['authorization'].replace('Bearer ', '')
        payload = AuthService.verify_token(token, "user_service")
        if not payload:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Invalid token")
        user = self.users.get(request.user_id)
        if not user:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details('User not found')
            return user_pb2.UserResponse()
            
        return user_pb2.UserResponse(
            user_id=user['user_id'],
            username=user['username'],
            email=user['email'],
            created_at=user['created_at']
        )

def serve():
    # Чтение сертификатов в бинарном режиме ('rb')
    with open('finance_pki/certs/user_service/user_service.key', 'rb') as f:
        private_key = f.read()
    with open('finance_pki/certs/user_service/user_service.crt', 'rb') as f:
        certificate = f.read()
    with open('finance_pki/intermediate/intermediateCA.crt', 'rb') as f:
        ca_cert = f.read()
    
    # Настройка mTLS с правильными типами данных
    server_credentials = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(private_key, certificate)],
        root_certificates=ca_cert,
        require_client_auth=True
    )
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_secure_port('[::]:50051', server_credentials)
    server.start()
    print("User Service running on port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()