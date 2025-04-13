from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from typing import Dict, List, Optional
from database import Database
import logging

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AdminPanel:
    def __init__(self, db: Database):
        self.db = db
        
    def admin_menu(self, update: Update, context: CallbackContext):
        """Show admin control panel"""
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            update.message.reply_text("⛔ You don't have admin privileges!")
            return
            
        keyboard = [
            [InlineKeyboardButton("📝 Pending Withdrawals", callback_data="admin_pending_wd")],
            [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
            [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📊 System Stats", callback_data="admin_stats")]
        ]
        
        update.message.reply_text(
            "🛠️ <b>Admin Control Panel</b> 🛠️",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    def handle_admin_callback(self, query, data: str):
        """Handle admin callback queries"""
        if data == "admin_pending_wd":
            self.show_pending_withdrawals(query)
        elif data == "admin_users":
            self.show_user_management(query)
        elif data == "admin_back":
            self.admin_menu(query)
        elif data.startswith("admin_approve_"):
            transaction_id = int(data.split("_")[2])
            self.approve_withdrawal(query, transaction_id)
        elif data.startswith("admin_reject_"):
            transaction_id = int(data.split("_")[2])
            self.reject_withdrawal(query, transaction_id)
        # Add more handlers as needed
        
    def show_pending_withdrawals(self, query):
        """Show list of pending withdrawals for approval"""
        pending = self.db.get_pending_withdrawals()
        
        if not pending:
            query.edit_message_text("✅ No pending withdrawals.")
            return
            
        message = "🔄 <b>Pending Withdrawals:</b>\n\n"
        keyboard = []
        
        for wd in pending:
            message += (
                f"📌 <b>ID:</b> {wd['transaction_id']}\n"
                f"👤 <b>User:</b> {wd['first_name']} (@{wd['username']})\n"
                f"💰 <b>Amount:</b> {wd['amount']} points\n"
                f"🏦 <b>Method:</b> {wd['payment_method']}\n\n"
            )
            
            keyboard.append([
                InlineKeyboardButton(f"✅ Approve #{wd['transaction_id']}", 
                                  callback_data=f"admin_approve_{wd['transaction_id']}"),
                InlineKeyboardButton(f"❌ Reject #{wd['transaction_id']}", 
                                  callback_data=f"admin_reject_{wd['transaction_id']}")
            ])
            
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        
        query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    def approve_withdrawal(self, query, transaction_id: int):
        """Approve a withdrawal request"""
        if self.db.approve_withdrawal(transaction_id):
            query.answer("Withdrawal approved successfully!")
        else:
            query.answer("Failed to approve withdrawal!")
            
        self.show_pending_withdrawals(query)
        
    def reject_withdrawal(self, query, transaction_id: int):
        """Reject a withdrawal request"""
        if self.db.reject_withdrawal(transaction_id):
            query.answer("Withdrawal rejected and funds returned!")
        else:
            query.answer("Failed to reject withdrawal!")
            
        self.show_pending_withdrawals(query)
        
    def show_user_management(self, query):
        """Show user management options"""
        keyboard = [
            [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user")],
            [InlineKeyboardButton("📊 Top Players", callback_data="admin_top_players")],
            [InlineKeyboardButton("🚫 Banned Users", callback_data="admin_banned_users")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]
        
        query.edit_message_text(
            "👥 <b>User Management</b> 👥",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    def show_top_players(self, query, limit: int = 10):
        """Show top players by points"""
        top_players = self.db.get_top_players(limit)
        
        if not top_players:
            query.edit_message_text("No players found!")
            return
            
        message = "🏆 <b>Top Players:</b>\n\n"
        
        for i, player in enumerate(top_players, 1):
            message += (
                f"{i}. {player['first_name']} (@{player['username']})\n"
                f"   Points: {player['points']} | "
                f"W: {player['wins']} | "
                f"L: {player['losses']} | "
                f"D: {player['draws']}\n\n"
            )
            
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="admin_users")]
        ]
        
        query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )