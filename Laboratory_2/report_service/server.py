import os
import csv
import json
import time
from concurrent import futures
from datetime import datetime

import grpc
from generated import report_pb2, report_pb2_grpc, transaction_pb2, transaction_pb2_grpc
import msgpack

class ReportService(report_pb2_grpc.ReportServiceServicer):
    def __init__(self, transaction_service_stub):
        self.transaction_service_stub = transaction_service_stub

    def GenerateMonthlyReport(self, request, context):
        # Using MessagePack for alternative communication
        try:
            # Get transactions via MessagePack (simulated)
            msgpack_request = msgpack.packb({
                'user_id': request.user_id,
                'start_date': f"{request.month}-01",
                'end_date': f"{request.month}-31"
            })
            
            # In a real implementation, we would send this to a MessagePack endpoint
            # For demo, we'll just unpack it and use gRPC
            unpacked = msgpack.unpackb(msgpack_request)
            
            # Still using gRPC for actual communication in this demo
            transactions_response = self.transaction_service_stub.GetTransactions(
                transaction_pb2.GetTransactionsRequest(
                    user_id=unpacked[b'user_id'].decode(),
                    start_date=unpacked[b'start_date'].decode(),
                    end_date=unpacked[b'end_date'].decode()
                )
            )
        finally:
            pass
            
            transactions = transactions_response.transactions
        
        # Calculate totals
        total_income = sum(t.amount for t in transactions if t.type == 'income')
        total_expenses = sum(t.amount for t in transactions if t.type == 'expense')
        balance = total_income - total_expenses
        
        return report_pb2.MonthlyReportResponse(
            user_id=request.user_id,
            month=request.month,
            total_income=total_income,
            total_expenses=total_expenses,
            balance=balance,
            transactions=transactions
        )

    def ExportReport(self, request, context):
        # First generate the report
        report = self.GenerateMonthlyReport(
            report_pb2.MonthlyReportRequest(
                user_id=request.user_id,
                month=request.month
            ),
            context
        )
        
        # Export based on format
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
            output = []
            # Header
            output.append([
                "Transaction ID", "Amount", "Category", "Type", 
                "Date", "Description"
            ])
            
            for t in report.transactions:
                output.append([
                    t.transaction_id, t.amount, t.category, t.type,
                    t.date, t.description
                ])
            
            # Summary
            output.append([])
            output.append(["Total Income", report.total_income])
            output.append(["Total Expenses", report.total_expenses])
            output.append(["Balance", report.balance])
            
            # Convert to CSV
            file_content = ""
            with io.StringIO() as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(output)
                file_content = csvfile.getvalue().encode('utf-8')
            
            file_name = f"report_{report.user_id}_{report.month}.csv"
        else:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Unsupported export format')
            return report_pb2.ExportReportResponse()
        
        return report_pb2.ExportReportResponse(
            file_content=file_content,
            file_name=file_name
        )

def serve():
    # Setup connection to Transaction Service
    transaction_channel = grpc.insecure_channel('localhost:50052')
    transaction_stub = transaction_pb2_grpc.TransactionServiceStub(transaction_channel)
    
    # Start Report Service
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    report_pb2_grpc.add_ReportServiceServicer_to_server(
        ReportService(transaction_stub), server)
    server.add_insecure_port('[::]:50053')
    server.start()
    print("Report Service running on port 50053")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()