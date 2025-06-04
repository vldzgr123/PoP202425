import unittest
import grpc
from generated import (
    user_pb2, user_pb2_grpc,
    report_pb2, report_pb2_grpc,
    transaction_pb2, transaction_pb2_grpc
)
from graphql_api.auth import AuthService

class TestFinanceServices(unittest.TestCase):
    def setUp(self):
        # Загрузка сертификатов
        with open('finance_pki/intermediate/intermediateCA.crt', 'rb') as f:
            self.ca_cert = f.read()
        with open('finance_pki/certs/report_service/report_service.key', 'rb') as f:
            self.private_key = f.read()
        with open('finance_pki/certs/report_service/report_service.crt', 'rb') as f:
            self.certificate = f.read()

        self.channel_credentials = grpc.ssl_channel_credentials(
            root_certificates=self.ca_cert,
            private_key=self.private_key,
            certificate_chain=self.certificate
        )
        
        # Настройка каналов для всех сервисов
        self.setup_user_service_channel()
        self.setup_report_service_channel()
        self.setup_transaction_service_channel()
        
        # Создаем тестовые данные
        self.create_test_user()
        self.create_test_transaction()

    def setup_user_service_channel(self):
        channel = grpc.secure_channel(
            'localhost:50051',
            self.channel_credentials,
            options=[
                ('grpc.ssl_target_name_override', 'user_service'),
                ('grpc.default_authority', 'user_service')
            ]
        )
        self.user_stub = user_pb2_grpc.UserServiceStub(channel)

    def setup_report_service_channel(self):
        channel = grpc.secure_channel(
            'localhost:50052',
            self.channel_credentials,
            options=[
                ('grpc.ssl_target_name_override', 'report_service'),
                ('grpc.default_authority', 'report_service')
            ]
        )
        self.report_stub = report_pb2_grpc.ReportServiceStub(channel)

    def setup_transaction_service_channel(self):
        channel = grpc.secure_channel(
            'localhost:50053',
            self.channel_credentials,
            options=[
                ('grpc.ssl_target_name_override', 'transaction_service'),
                ('grpc.default_authority', 'transaction_service')
            ]
        )
        self.transaction_stub = transaction_pb2_grpc.TransactionServiceStub(channel)

    def create_test_user(self):
        token = AuthService.create_service_token(
            "test_client",
            "user_service",
            ["write"]
        )
        
        try:
            response = self.user_stub.RegisterUser(
                user_pb2.RegisterRequest(
                    username="testuser",
                    email="test@example.com",
                    password="testpassword"
                ),
                metadata=[('authorization', f'Bearer {token}')]
            )
            self.test_user_id = response.user_id
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.ALREADY_EXISTS:
                raise
            login_response = self.user_stub.LoginUser(
                user_pb2.LoginRequest(
                    email="test@example.com",
                    password="testpassword"
                ),
                metadata=[('authorization', f'Bearer {token}')]
            )
            self.test_user_id = login_response.user_id

    def create_test_transaction(self):
        token = AuthService.create_service_token(
            "test_client",
            "transaction_service",
            ["write"]
        )
        
        response = self.transaction_stub.AddTransaction(
            transaction_pb2.AddTransactionRequest(
                user_id=self.test_user_id,
                amount=100.0,
                category="test",
                type='test',
                description="Initial deposit"
            ),
            metadata=[('authorization', f'Bearer {token}')]
        )
        self.test_transaction_id = response.transaction.transaction_id

    # Тесты для UserService
    def test_user_registration_and_login(self):
        token = AuthService.create_service_token(
            "test_client",
            "user_service",
            ["write"]
        )
        
        # Тест регистрации
        register_response = self.user_stub.RegisterUser(
            user_pb2.RegisterRequest(
                username="newuser",
                email="new@example.com",
                password="newpassword"
            ),
            metadata=[('authorization', f'Bearer {token}')]
        )
        self.assertIsNotNone(register_response.user_id)
        
        # Тест авторизации
        login_response = self.user_stub.LoginUser(
            user_pb2.LoginRequest(
                email="new@example.com",
                password="newpassword"
            ),
            metadata=[('authorization', f'Bearer {token}')]
        )
        self.assertEqual(login_response.email, "new@example.com")

    def test_get_user_info(self):
        token = AuthService.create_service_token(
            "report_service",
            "user_service",
            ["read"]
        )
        
        response = self.user_stub.GetUser(
            user_pb2.GetUserRequest(user_id=self.test_user_id),
            metadata=[('authorization', f'Bearer {token}')]
        )
        
        self.assertEqual(response.user_id, self.test_user_id)
        self.assertEqual(response.email, "test@example.com")

    def test_create_transaction(self):
        token = AuthService.create_service_token(
            "test_client",
            "transaction_service",
            ["write"]
        )
        
        response = self.transaction_stub.AddTransaction(
            transaction_pb2.AddTransactionRequest(
                user_id=self.test_user_id,
                amount=50.0,
                category="test",
                type="test",
                description="Test transaction"
            ),
            metadata=[('authorization', f'Bearer {token}')]
        )
        
        self.assertIsNotNone(response.transaction.transaction_id)

if __name__ == '__main__':
    unittest.main()