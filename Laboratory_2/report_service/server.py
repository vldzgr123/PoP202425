import io
import csv
import json
import time
from concurrent import futures
from datetime import datetime

import grpc
from generated import report_pb2, report_pb2_grpc, transaction_pb2, transaction_pb2_grpc
import msgpack
from graphql_api.auth import AuthService
from fastapi import FastAPI
from .auth_middleware import jwt_middleware

app = FastAPI()
app.middleware('http')(jwt_middleware)

class ReportService(report_pb2_grpc.ReportServiceServicer):
    def __init__(self):
        self.transaction_channel = grpc.insecure_channel('localhost:50052')
        self.transaction_stub = transaction_pb2_grpc.TransactionServiceStub(self.transaction_channel)

    def GenerateMonthlyReport(self, request, context):
        try:
            metadata = dict(context.invocation_metadata())
            token = metadata.get('authorization', '').replace('Bearer ', '')
            
            if not AuthService.verify_token(token, "report_service"):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            
            user_id = request.user_id
            month = request.month
            
            if '-' not in month:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Month format should be YYYY-MM")
                return report_pb2.MonthlyReportResponse()
            
            request_data = {
                'user_id': user_id,
                'start_date': f"{month}-01",
                'end_date': f"{month}-31"
            }
            
            msgpack_request = msgpack.packb(request_data)
            

            unpacked = msgpack.unpackb(msgpack_request, raw=False) 
            
            # Получаем транзакции через gRPC
            transactions_response = self.transaction_service_stub.GetTransactions(
                transaction_pb2.GetTransactionsRequest(
                    user_id=str(unpacked['user_id']),  # Преобразуем в str
                    start_date=str(unpacked['start_date']),
                    end_date=str(unpacked['end_date'])
                )
            )
            
            # Рассчитываем итоги
            total_income = sum(t.amount for t in transactions_response.transactions if t.type == 'income')
            total_expenses = sum(t.amount for t in transactions_response.transactions if t.type == 'expense')
            balance = total_income - total_expenses
            
            # Формируем ответ
            response = report_pb2.MonthlyReportResponse(
                user_id=user_id,
                month=month,
                total_income=total_income,
                total_expenses=total_expenses,
                balance=balance
            )
            
            # Добавляем транзакции
            response.transactions.extend(transactions_response.transactions)
            
            return response
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error generating report: {str(e)}")
            return report_pb2.MonthlyReportResponse()

    def ExportReport(self, request, context):
        try:
            metadata = dict(context.invocation_metadata())
            token = metadata.get('authorization', '').replace('Bearer ', '')
            
            if not AuthService.verify_token(token, "report_service"):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            # Генерируем отчет
            report = self.GenerateMonthlyReport(
                report_pb2.MonthlyReportRequest(
                    user_id=request.user_id,
                    month=request.month
                ),
                context
            )
            
            # Экспорт в разных форматах
            if request.format == 'json':
                report_dict = {
                    'user_id': report.user_id,
                    'month': report.month,
                    'total_income': report.total_income,
                    'total_expenses': report.total_expenses,
                    'balance': report.balance,
                    'transactions': [
                        {
                            'transaction_id': t.transaction_id,
                            'amount': t.amount,
                            'category': t.category,
                            'type': t.type,
                            'date': t.date,
                            'description': t.description
                        } for t in report.transactions
                    ]
                }
                file_content = json.dumps(report_dict, indent=2).encode('utf-8')
                file_name = f"report_{report.user_id}_{report.month}.json"
                
            elif request.format == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Заголовки
                writer.writerow([
                    "Transaction ID", "Amount", "Category", 
                    "Type", "Date", "Description"
                ])
                
                # Данные
                for t in report.transactions:
                    writer.writerow([
                        t.transaction_id, t.amount, t.category,
                        t.type, t.date, t.description
                    ])
                
                # Итоги
                writer.writerow([])
                writer.writerow(["Total Income", report.total_income])
                writer.writerow(["Total Expenses", report.total_expenses])
                writer.writerow(["Balance", report.balance])
                
                file_content = output.getvalue().encode('utf-8')
                file_name = f"report_{report.user_id}_{report.month}.csv"
                
            else:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('Unsupported export format')
                return report_pb2.ExportReportResponse()
            
            return report_pb2.ExportReportResponse(
                file_content=file_content,
                file_name=file_name
            )
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f'Export error: {str(e)}')
            return report_pb2.ExportReportResponse()

def serve():
    with open('finance_pki/certs/report_service/report_service.key', 'rb') as f:
        private_key = f.read()
    with open('finance_pki/certs/report_service/report_service.crt', 'rb') as f:
        certificate = f.read()
    with open('finance_pki/intermediate/intermediateCA.crt', 'rb') as f:
        ca_cert = f.read()
    
    server_credentials = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(private_key, certificate)],
        root_certificates=ca_cert,
        require_client_auth=True
    )
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    report_pb2_grpc.add_ReportServiceServicer_to_server(ReportService(), server)
    server.add_secure_port('[::]:50052', server_credentials)
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()