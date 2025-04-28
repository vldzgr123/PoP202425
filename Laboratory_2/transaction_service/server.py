import os
import time
import uuid
from concurrent import futures

import grpc
from generated import transaction_pb2_grpc, transaction_pb2
import msgpack

class TransactionService(transaction_pb2_grpc.TransactionServiceServicer):
    def __init__(self):
        self.transactions = {}  # user_id -> list of transactions

    def AddTransaction(self, request, context):
        transaction_id = str(uuid.uuid4())
        transaction_date = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        
        transaction = {
            'transaction_id': transaction_id,
            'user_id': request.user_id,
            'amount': request.amount,
            'category': request.category,
            'type': request.type,
            'date': transaction_date,
            'description': request.description
        }
        
        if request.user_id not in self.transactions:
            self.transactions[request.user_id] = []
        
        self.transactions[request.user_id].append(transaction)
        
        return transaction_pb2.TransactionResponse(
            transaction=transaction_pb2.Transaction(
                transaction_id=transaction_id,
                user_id=request.user_id,
                amount=request.amount,
                category=request.category,
                type=request.type,
                date=transaction_date,
                description=request.description
            )
        )

    def GetTransactions(self, request, context):
        user_transactions = self.transactions.get(request.user_id, [])
        
        # Filter by date range if provided
        filtered_transactions = []
        for t in user_transactions:
            if (not request.start_date or t['date'] >= request.start_date) and \
               (not request.end_date or t['date'] <= request.end_date):
                filtered_transactions.append(t)
        
        return transaction_pb2.TransactionsResponse(
            transactions=[transaction_pb2.Transaction(
                transaction_id=t['transaction_id'],
                user_id=t['user_id'],
                amount=t['amount'],
                category=t['category'],
                type=t['type'],
                date=t['date'],
                description=t['description']
            ) for t in filtered_transactions]
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    transaction_pb2_grpc.add_TransactionServiceServicer_to_server(TransactionService(), server)
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Transaction Service running on port 50052")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()