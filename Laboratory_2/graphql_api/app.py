from ariadne import QueryType, MutationType, SubscriptionType, make_executable_schema, load_schema_from_path
from ariadne import ScalarType
from graphql import GraphQLError
import grpc
import uuid
import time
import json
import io
import csv
from generated import user_pb2, user_pb2_grpc, transaction_pb2, transaction_pb2_grpc, report_pb2, report_pb2_grpc
from collections import defaultdict
import asyncio

# Настройка gRPC соединений
user_channel = grpc.insecure_channel('localhost:50051')
transaction_channel = grpc.insecure_channel('localhost:50052')
report_channel = grpc.insecure_channel('localhost:50053')

user_stub = user_pb2_grpc.UserServiceStub(user_channel)
transaction_stub = transaction_pb2_grpc.TransactionServiceStub(transaction_channel)
report_stub = report_pb2_grpc.ReportServiceStub(report_channel)

# Инициализация типов Ariadne
query = QueryType()
mutation = MutationType()
subscription = SubscriptionType()

# Хранилище для подписок
transaction_subscribers = defaultdict(list)

@query.field("generateMonthlyReport")
def resolve_generate_monthly_report(_, info, userId, month):
    try:
        response = report_stub.GenerateMonthlyReport(
            report_pb2.MonthlyReportRequest(
                user_id=userId,
                month=month
            )
        )
        
        return {
            "userId": response.user_id,
            "month": response.month,
            "totalIncome": response.total_income,
            "totalExpenses": response.total_expenses,
            "balance": response.balance,
            "transactions": [
                {
                    "id": t.transaction_id,
                    "userId": t.user_id,
                    "amount": t.amount,
                    "category": t.category,
                    "type": t.type,
                    "date": t.date,
                    "description": t.description
                }
                for t in response.transactions
            ]
        }
    except grpc.RpcError as e:
        raise GraphQLError(f"Ошибка генерации отчета: {e.details()}")

@mutation.field("exportReport")
def resolve_export_report(_, info, userId, month, format):
    try:
        response = report_stub.ExportReport(
            report_pb2.ExportReportRequest(
                user_id=userId,
                month=month,
                format=format.lower()
            )
        )
        
        return {
            "fileContent": response.file_content.decode('utf-8'),
            "fileName": response.file_name
        }
    except grpc.RpcError as e:
        raise GraphQLError(f"Ошибка экспорта отчета: {e.details()}")

@subscription.source("transactionAdded")
async def source_transaction_added(_, info, userId):
    # Создаем очередь для данного пользователя
    print("TEST")
    queue = asyncio.Queue()
    transaction_subscribers[userId].append(queue)
    
    try:
        while True:
            # Ждем новые транзакции
            transaction = await queue.get()
            queue.task_done()
            yield transaction
    finally:
        # Удаляем очередь при отключении клиента
        transaction_subscribers[userId].remove(queue)

@subscription.field("transactionAdded")
def resolve_transaction_added(transaction, info, userId):
    print("TEST")
    return transaction

# Реализация резолверов
@query.field("getUser")
def resolve_get_user(_, info, id):
    try:
        response = user_stub.GetUser(user_pb2.GetUserRequest(user_id=id))
        return {
            "id": response.user_id,
            "username": response.username,
            "email": response.email,
            "createdAt": response.created_at
        }
    except grpc.RpcError as e:
        raise GraphQLError(f"Ошибка сервиса пользователей: {e.details()}")

@query.field("getTransactions")
def resolve_get_transactions(_, info, userId, startDate=None, endDate=None):
    try:
        response = transaction_stub.GetTransactions(
            transaction_pb2.GetTransactionsRequest(
                user_id=userId,
                start_date=startDate or "",
                end_date=endDate or ""
            )
        )
        return [
            {
                "id": t.transaction_id,
                "userId": t.user_id,
                "amount": t.amount,
                "category": t.category,
                "type": t.type,
                "date": t.date,
                "description": t.description
            }
            for t in response.transactions
        ]
    except grpc.RpcError as e:
        raise GraphQLError(f"Ошибка сервиса транзакций: {e.details()}")

@mutation.field("registerUser")
def resolve_register_user(_, info, username, email, password):
    try:
        response = user_stub.RegisterUser(
            user_pb2.RegisterRequest(
                username=username,
                email=email,
                password=password
            )
        )
        return {
            "id": response.user_id,
            "username": response.username,
            "email": response.email,
            "createdAt": response.created_at
        }
    except grpc.RpcError as e:
        raise GraphQLError(f"Ошибка регистрации: {e.details()}")

# Модифицируем мутацию addTransaction для поддержки подписок
@mutation.field("addTransaction")
async def resolve_add_transaction(_, info, userId, amount, category, type, description=None):
    try:
        # Создаем запрос к gRPC сервису транзакций
        response = transaction_stub.AddTransaction(
            transaction_pb2.AddTransactionRequest(
                user_id=userId,
                amount=float(amount),
                category=category,
                type=type,
                description=description or ""
            )
        )
        
        # Преобразуем ответ gRPC в формат GraphQL
        transaction_data = {
            "id": response.transaction.transaction_id,
            "userId": response.transaction.user_id,
            "amount": float(response.transaction.amount),
            "category": response.transaction.category,
            "type": response.transaction.type,
            "date": response.transaction.date,
            "description": response.transaction.description
        }
        
        # Уведомляем подписчиков
        for queue in transaction_subscribers.get(userId, []):
            await queue.put(transaction_data)
        
        return transaction_data
        
    except grpc.RpcError as e:
        error_msg = f"Ошибка при добавлении транзакции: {e.details()}"
        raise GraphQLError(error_msg)
    except Exception as e:
        raise GraphQLError(f"Неожиданная ошибка: {str(e)}")

# Загрузка схемы и создание исполняемой схемы
type_defs = load_schema_from_path("schema.graphql")
schema = make_executable_schema(
    type_defs,
    query,
    mutation,
    subscription
)