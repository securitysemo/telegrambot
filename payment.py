from typing import Optional, Dict
from database import Database
import config
import logging

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, db: Database):
        self.db = db
        self.fee_percentage = config.TRANSACTION_FEE
        
    def process_deposit(self, user_id: int, amount: int, method: str) -> Optional[int]:
        """Process a deposit request"""
        if amount <= 0:
            return None
            
        # Record transaction
        transaction_id = self.db.record_transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='deposit',
            status='completed',
            payment_method=method,
            details=f"Deposit of {amount} points via {method}"
        )
        
        if not transaction_id:
            return None
            
        # Update user balance
        if not self.db.update_user_points(user_id, amount):
            return None
            
        return transaction_id
        
    def process_withdrawal(self, user_id: int, amount: int, method: str) -> Optional[int]:
        """Process a withdrawal request"""
        if amount <= 0:
            return None
            
        # Validate user balance
        user_points = self.db.get_user_points(user_id)
        if user_points is None or user_points < amount:
            return None
            
        # Calculate fee and net amount
        fee = int(amount * (self.fee_percentage / 100))
        net_amount = amount - fee
        
        # Record transaction
        transaction_id = self.db.record_transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='withdrawal',
            status='pending',
            payment_method=method,
            details=f"Withdrawal request for {amount} points ({net_amount} after {fee} fee) via {method}"
        )
        
        if not transaction_id:
            return None
            
        # Hold the funds (deduct from balance)
        if not self.db.update_user_points(user_id, -amount):
            return None
            
        return transaction_id
        
    def approve_withdrawal(self, transaction_id: int) -> bool:
        """Admin approves a withdrawal"""
        transaction = self.db.get_transaction(transaction_id)
        if not transaction or transaction['type'] != 'withdrawal' or transaction['status'] != 'pending':
            return False
            
        # Record fee transaction
        fee = int(transaction['amount'] * (self.fee_percentage / 100))
        self.db.record_transaction(
            user_id=transaction['user_id'],
            amount=fee,
            transaction_type='fee',
            status='completed',
            payment_method=transaction['payment_method'],
            details=f"Transaction fee for withdrawal #{transaction_id}"
        )
        
        # Update withdrawal status
        return self.db.update_transaction_status(transaction_id, 'completed')
        
    def reject_withdrawal(self, transaction_id: int) -> bool:
        """Admin rejects a withdrawal - refund points"""
        transaction = self.db.get_transaction(transaction_id)
        if not transaction or transaction['type'] != 'withdrawal' or transaction['status'] != 'pending':
            return False
            
        # Refund points to user
        if not self.db.update_user_points(transaction['user_id'], transaction['amount']):
            return False
            
        # Update withdrawal status
        return self.db.update_transaction_status(transaction_id, 'rejected')
        
    def get_payment_methods(self) -> Dict[str, str]:
        """Get available payment methods"""
        return {
            'paypal': 'PayPal',
            'vodafone': 'Vodafone Cash',
            'bank': 'Bank Transfer'
        }