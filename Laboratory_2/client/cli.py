import grpc
import argparse
import msgpack
from datetime import datetime
import json
import os
from generated import user_pb2, user_pb2_grpc
from generated import transaction_pb2, transaction_pb2_grpc
from generated import report_pb2, report_pb2_grpc

class FinanceCLI:
    def __init__(self):
        # Setup gRPC channels
        self.user_channel = grpc.insecure_channel('localhost:50051')
        self.user_stub = user_pb2_grpc.UserServiceStub(self.user_channel)
        
        self.transaction_channel = grpc.insecure_channel('localhost:50052')
        self.transaction_stub = transaction_pb2_grpc.TransactionServiceStub(self.transaction_channel)
        
        self.report_channel = grpc.insecure_channel('localhost:50053')
        self.report_stub = report_pb2_grpc.ReportServiceStub(self.report_channel)
        
        self.session_file = "finance_cli_session.json"
        self.current_user = self._load_session()

    def _load_session(self):
        if os.path.exists(self.session_file):
            with open(self.session_file, 'r') as f:
                return json.load(f)
        return None
    
    def _save_session(self):
        with open(self.session_file, 'w') as f:
            json.dump(self.current_user, f)

    def register(self, username, email, password):
        response = self.user_stub.RegisterUser(
            user_pb2.RegisterRequest(
                username=username,
                email=email,
                password=password
            )
        )
        if response.user_id:
            print(f"User registered successfully! User ID: {response.user_id}")
            return True
        return False

    def login(self, email, password):
        response = self.user_stub.LoginUser(
            user_pb2.LoginRequest(email=email, password=password)
        )
        if response.user_id:
            self.current_user = {
                'user_id': response.user_id,
                'username': response.username,
                'email': response.email
            }
            self._save_session()
            print(f"Logged in as {response.username} (ID: {response.user_id})")
            return True
        print("Login failed. Invalid email or password.")
        return False

    def add_transaction(self, amount, category, type, description):
        if not self.current_user:
            print("Please login first")
            return
            
        response = self.transaction_stub.AddTransaction(
            transaction_pb2.AddTransactionRequest(
                user_id=self.current_user['user_id'],
                amount=amount,
                category=category,
                type=type,
                description=description
            )
        )
        
        if response.transaction.transaction_id:
            print(f"Transaction added: {response.transaction}")
            return True
        return False

    def get_transactions(self, start_date=None, end_date=None):
        if not self.current_user:
            print("Please login first")
            return
            
        response = self.transaction_stub.GetTransactions(
            transaction_pb2.GetTransactionsRequest(
                user_id=self.current_user['user_id'],
                start_date=start_date,
                end_date=end_date
            )
        )
        
        print(f"Transactions for {self.current_user['username']}:")
        for t in response.transactions:
            print(f"{t.date} - {t.type.upper()}: {t.amount} ({t.category}) - {t.description}")

    def generate_report(self, month=None):
        if not self.current_user:
            print("Please login first")
            return
            
        if not month:
            month = datetime.now().strftime("%Y-%m")
            
        response = self.report_stub.GenerateMonthlyReport(
            report_pb2.MonthlyReportRequest(
                user_id=self.current_user['user_id'],
                month=month
            )
        )
        
        print(f"\nMonthly Report for {month}:")
        print(f"Income: {response.total_income}")
        print(f"Expenses: {response.total_expenses}")
        print(f"Balance: {response.balance}")
        
        print("\nTransactions:")
        for t in response.transactions:
            print(f"{t.date} - {t.type.upper()}: {t.amount} ({t.category}) - {t.description}")

    def export_report(self, month=None, format='json'):
        if not self.current_user:
            print("Please login first")
            return
            
        if not month:
            month = datetime.now().strftime("%Y-%m")
            
        response = self.report_stub.ExportReport(
            report_pb2.ExportReportRequest(
                user_id=self.current_user['user_id'],
                month=month,
                format=format
            )
        )
        
        with open(response.file_name, 'wb') as f:
            f.write(response.file_content)
            
        print(f"Report exported to {response.file_name}")

def main():
    cli = FinanceCLI()
    
    parser = argparse.ArgumentParser(description="Personal Finance Manager CLI")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Register command
    register_parser = subparsers.add_parser('register')
    register_parser.add_argument('--username', required=True)
    register_parser.add_argument('--email', required=True)
    register_parser.add_argument('--password', required=True)
    
    # Login command
    login_parser = subparsers.add_parser('login')
    login_parser.add_argument('--email', required=True)
    login_parser.add_argument('--password', required=True)
    
    # Add transaction command
    transaction_parser = subparsers.add_parser('add-transaction')
    transaction_parser.add_argument('--amount', type=float, required=True)
    transaction_parser.add_argument('--category', required=True)
    transaction_parser.add_argument('--type', choices=['income', 'expense'], required=True)
    transaction_parser.add_argument('--description', default="")
    
    # Get transactions command
    get_transactions_parser = subparsers.add_parser('get-transactions')
    get_transactions_parser.add_argument('--start-date', required=False)
    get_transactions_parser.add_argument('--end-date', required=False)
    
    # Generate report command
    report_parser = subparsers.add_parser('generate-report')
    report_parser.add_argument('--month', required=False)
    
    # Export report command
    export_parser = subparsers.add_parser('export-report')
    export_parser.add_argument('--month', required=False)
    export_parser.add_argument('--format', choices=['json', 'csv'], default='json')
    
    args = parser.parse_args()
    
    if args.command == 'register':
        cli.register(args.username, args.email, args.password)
    elif args.command == 'login':
        cli.login(args.email, args.password)
    elif args.command == 'add-transaction':
        cli.add_transaction(args.amount, args.category, args.type, args.description)
    elif args.command == 'get-transactions':
        cli.get_transactions(args.start_date, args.end_date)
    elif args.command == 'generate-report':
        cli.generate_report(args.month)
    elif args.command == 'export-report':
        cli.export_report(args.month, args.format)

if __name__ == '__main__':
    main()