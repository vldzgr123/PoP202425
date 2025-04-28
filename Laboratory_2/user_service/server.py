from concurrent import futures
import grpc
import time
from generated import report_pb2, report_pb2_grpc
from generated import transaction_pb2, transaction_pb2_grpc

class ReportService(report_pb2_grpc.ReportServiceServicer):
    def __init__(self, transaction_channel):
        self.transaction_stub = transaction_pb2_grpc.TransactionServiceStub(transaction_channel)

    def GenerateMonthlyReport(self, request, context):
        try:
            # Получаем транзакции за указанный месяц
            year_month = request.month.split('-')
            start_date = f"{year_month[0]}-{year_month[1]}-01"
            end_date = f"{year_month[0]}-{year_month[1]}-31"
            
            # Получаем транзакции через gRPC
            transactions_response = self.transaction_stub.GetTransactions(
                transaction_pb2.GetTransactionsRequest(
                    user_id=request.user_id,
                    start_date=start_date,
                    end_date=end_date
                )
            )
            
            # Рассчитываем итоги
            total_income = sum(t.amount for t in transactions_response.transactions if t.type == 'income')
            total_expenses = sum(t.amount for t in transactions_response.transactions if t.type == 'expense')
            balance = total_income - total_expenses
            
            return report_pb2.MonthlyReportResponse(
                user_id=request.user_id,
                month=request.month,
                total_income=total_income,
                total_expenses=total_expenses,
                balance=balance,
                transactions=transactions_response.transactions
            )
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error generating report: {str(e)}")
            return report_pb2.MonthlyReportResponse()

def serve():
    # Настраиваем соединение с сервисом транзакций
    transaction_channel = grpc.insecure_channel('localhost:50052')
    
    # Создаем сервер
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    report_pb2_grpc.add_ReportServiceServicer_to_server(
        ReportService(transaction_channel), server)
    server.add_insecure_port('[::]:50053')
    server.start()
    print("Report Service running on port 50053")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()