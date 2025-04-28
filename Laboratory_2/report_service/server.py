import io
import csv
import json
from concurrent import futures
import grpc
from generated import report_pb2, report_pb2_grpc
from generated import transaction_pb2, transaction_pb2_grpc

class ReportService(report_pb2_grpc.ReportServiceServicer):
    def __init__(self, transaction_channel):
        self.transaction_stub = transaction_pb2_grpc.TransactionServiceStub(transaction_channel)

    def GenerateMonthlyReport(self, request, context):
        try:
            # Проверяем формат месяца
            if '-' not in request.month:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Month format should be YYYY-MM")
                return report_pb2.MonthlyReportResponse()
            
            year, month = request.month.split('-')
            start_date = f"{year}-{month}-01"
            end_date = f"{year}-{month}-31"
            
            # Получаем транзакции
            try:
                transactions_response = self.transaction_stub.GetTransactions(
                    transaction_pb2.GetTransactionsRequest(
                        user_id=request.user_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                )
            except grpc.RpcError as e:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Failed to get transactions: {e.details()}")
                return report_pb2.MonthlyReportResponse()
            
            # Если транзакций нет
            if not transactions_response.transactions:
                return report_pb2.MonthlyReportResponse(
                    user_id=request.user_id,
                    month=request.month,
                    total_income=0,
                    total_expenses=0,
                    balance=0
                )
            
            # Рассчитываем суммы
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
            context.set_details(f"Internal server error: {str(e)}")
            return report_pb2.MonthlyReportResponse()
    def ExportReport(self, request, context):
        try:
            # Сначала получаем отчет
            report = self.GenerateMonthlyReport(
                report_pb2.MonthlyReportRequest(
                    user_id=request.user_id,
                    month=request.month
                ),
                context
            )

            # Готовим данные для экспорта
            if request.format == 'json':
                report_data = {
                    'user_id': report.user_id,
                    'month': report.month,
                    'total_income': report.total_income,
                    'total_expenses': report.total_expenses,
                    'balance': report.balance,
                    'transactions': [
                        {
                            'id': t.transaction_id,
                            'date': t.date,
                            'amount': t.amount,
                            'category': t.category,
                            'type': t.type,
                            'description': t.description
                        } for t in report.transactions
                    ]
                }
                file_content = json.dumps(report_data, indent=2).encode('utf-8')
                file_name = f"report_{report.user_id}_{report.month}.json"

            elif request.format == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Заголовки
                writer.writerow([
                    "Transaction ID", "Date", "Amount", 
                    "Category", "Type", "Description"
                ])
                
                # Данные транзакций
                for t in report.transactions:
                    writer.writerow([
                        t.transaction_id, t.date, t.amount,
                        t.category, t.type, t.description
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
                context.set_details("Unsupported export format")
                return report_pb2.ExportReportResponse()

            return report_pb2.ExportReportResponse(
                file_content=file_content,
                file_name=file_name
            )

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Export error: {str(e)}")
            return report_pb2.ExportReportResponse()

def serve():
    transaction_channel = grpc.insecure_channel('localhost:50052')
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    report_pb2_grpc.add_ReportServiceServicer_to_server(
        ReportService(transaction_channel), server)
    server.add_insecure_port('[::]:50053')
    server.start()
    print("Report Service running on port 50053")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()