import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, CallbackContext,
    MessageHandler, Filters
)
from database import Database
from game_logic import XOGame
from admin import AdminPanel
from payment import PaymentProcessor
import config
from typing import Optional, Dict, List

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class XOBot:
    def __init__(self, token: str, db: Database):
        self.updater = Updater(token, use_context=True)
        self.db = db
        self.payment_processor = PaymentProcessor(db)
        self.admin_panel = AdminPanel(db)
        self.active_games = {}  # {game_id: XOGame instance}
        
        # Register handlers
        dp = self.updater.dispatcher
        
        # User commands
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("play", self.play))
        dp.add_handler(CommandHandler("play_bot", self.play_bot))
        dp.add_handler(CommandHandler("stats", self.stats))
        dp.add_handler(CommandHandler("deposit", self.deposit))
        dp.add_handler(CommandHandler("withdraw", self.withdraw))
        dp.add_handler(CommandHandler("leaderboard", self.leaderboard))
        dp.add_handler(CommandHandler("menu", self.show_main_menu))
        
        # Admin commands
        dp.add_handler(CommandHandler("admin", self.admin_menu))
        
        # Callback queries
        dp.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Messages
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))

    def start(self, update: Update, context: CallbackContext):
        """Send welcome message when command /start is issued."""
        user = update.effective_user
        self.db.create_user_if_not_exists(
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or ""
        )
        
        # Check if this is a game invitation
        if context.args and context.args[0].startswith('game_'):
            try:
                game_id = int(context.args[0][5:])
                self.join_game(update, game_id)
                return
            except (ValueError, IndexError):
                pass
                
        self.show_main_menu(update)

    def show_main_menu(self, update: Update, context: CallbackContext = None):
        """Show the main menu with all available options"""
        user = update.effective_user
        user_points = self.db.get_user_points(user.id) or 0
        
        keyboard = [
            [InlineKeyboardButton("🎮 Play vs Friend", callback_data="menu_play")],
            [InlineKeyboardButton("🤖 Play vs Bot", callback_data="menu_play_bot")],
            [InlineKeyboardButton("📊 My Stats", callback_data="menu_stats")],
            [InlineKeyboardButton("💰 Deposit Points", callback_data="menu_deposit")],
            [InlineKeyboardButton("💸 Withdraw Points", callback_data="menu_withdraw")],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")]
        ]
        
        # Add admin button if user is admin
        if self.db.is_admin(user.id):
            keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="menu_admin")])
        
        message_text = (
            f"👋 Welcome back, {user.first_name}!\n\n"
            f"💰 Your points: <b>{user_points}</b>\n\n"
            "What would you like to do?"
        )
        
        if update.callback_query:
            update.callback_query.edit_message_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            update.message.reply_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

    def play(self, update: Update, context: CallbackContext):
        """Initiate a game with another player"""
        user = update.effective_user
        
        # Validate bet amount
        if not context.args:
            update.message.reply_text(
                "Please specify a bet amount between {}-{} points.\n"
                "Example: /play 100".format(config.MIN_BET, config.MAX_BET)
            )
            return
            
        try:
            bet_amount = int(context.args[0])
            if not (config.MIN_BET <= bet_amount <= config.MAX_BET):
                raise ValueError
        except (ValueError, IndexError):
            update.message.reply_text(
                "Invalid bet amount. Please specify between {}-{} points.".format(
                    config.MIN_BET, config.MAX_BET
                )
            )
            return
            
        # Check user balance
        user_points = self.db.get_user_points(user.id)
        if user_points is None or user_points < bet_amount:
            update.message.reply_text(
                "You don't have enough points for this bet!\n"
                "Your balance: {} points".format(user_points or 0)
            )
            return
            
        # Create a new game
        game_id = self.db.create_game(player1_id=user.id, bet_amount=bet_amount)
        if not game_id:
            update.message.reply_text("Failed to create game. Please try again.")
            return
            
        self.active_games[game_id] = XOGame(
            player1_id=user.id,
            bet_amount=bet_amount
        )
        
        # Generate share link
        share_url = f"https://t.me/{config.BOT_USERNAME}?start=game_{game_id}"
        
        keyboard = [
            [InlineKeyboardButton("📤 Share Game", url=f"https://t.me/share/url?url={share_url}")],
            [InlineKeyboardButton("❌ Cancel Game", callback_data=f"cancel_{game_id}")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        
        update.message.reply_text(
            "🎮 <b>Game created!</b> 🎮\n"
            "💰 Bet amount: <b>{} points</b>\n\n"
            "Share this game with a friend or cancel it:".format(bet_amount),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    def play_bot(self, update: Update, context: CallbackContext):
        """Start a game against the AI bot"""
        user = update.effective_user
        
        # Validate bet amount
        if not context.args:
            update.message.reply_text(
                "Please specify a bet amount between {}-{} points.\n"
                "Example: /play_bot 100".format(config.MIN_BET, config.MAX_BET)
            )
            return
            
        try:
            bet_amount = int(context.args[0])
            if not (config.MIN_BET <= bet_amount <= config.MAX_BET):
                raise ValueError
        except (ValueError, IndexError):
            update.message.reply_text(
                "Invalid bet amount. Please specify between {}-{} points.".format(
                    config.MIN_BET, config.MAX_BET
                )
            )
            return
            
        # Check user balance
        user_points = self.db.get_user_points(user.id)
        if user_points is None or user_points < bet_amount:
            update.message.reply_text(
                "You don't have enough points for this bet!\n"
                "Your balance: {} points".format(user_points or 0)
            )
            return
            
        # Create a new game against bot
        game_id = self.db.create_game(player1_id=user.id, bet_amount=bet_amount)
        if not game_id:
            update.message.reply_text("Failed to create game. Please try again.")
            return
            
        self.active_games[game_id] = XOGame(
            player1_id=user.id,
            bet_amount=bet_amount,
            against_bot=True
        )
        
        # Show the game board
        self.show_game_board(update, game_id)

    def show_game_board(self, update: Update, game_id: int, show_menu_button: bool = False):
        """Display the current game board"""
        if game_id not in self.active_games:
            return
            
        game = self.active_games[game_id]
        board = game.get_board_for_display()
        
        # Create inline keyboard for the board
        keyboard = []
        for i in range(0, 9, 3):
            row = []
            for j in range(3):
                pos = i + j
                row.append(InlineKeyboardButton(
                    board[pos],
                    callback_data=f"move_{game_id}_{pos}"
                ))
            keyboard.append(row)
            
        # Add action buttons
        action_buttons = []
        if not game.game_over:
            if game.player2_id is None and not game.against_bot:
                action_buttons.append(InlineKeyboardButton("❌ Cancel Game", callback_data=f"cancel_{game_id}"))
        else:
            # Game over - show menu button
            action_buttons.append(InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"))
            
        if action_buttons:
            keyboard.append(action_buttons)
            
        # Determine status message
        if game.game_over:
            if game.winner == 'X':
                status = "🎉 Player X wins!"
            elif game.winner == 'O':
                status = "🎉 Player O wins!"
            else:
                status = "🤝 It's a draw!"
        else:
            if game.player2_id is None and not game.against_bot:
                status = "⏳ Waiting for player 2..."
            else:
                status = "Current turn: {}".format(
                    "Player X" if game.current_turn == 'X' else "Player O"
                )
        
        # Create message text
        message_text = (
            "🎮 <b>XO Game</b> 🎮\n"
            "💰 Bet: <b>{} points</b>\n\n"
            "{} | {} | {}\n"
            "-----------\n"
            "{} | {} | {}\n"
            "-----------\n"
            "{} | {} | {}\n\n"
            "{}".format(
                game.bet_amount,
                board[0], board[1], board[2],
                board[3], board[4], board[5],
                board[6], board[7], board[8],
                status
            )
        )
        
        # Send or update the message
        if update.callback_query:
            update.callback_query.edit_message_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            update.message.reply_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

    def handle_game_over(self, game_id: int, update: Update = None):
        """Handle game completion and return to main menu"""
        if game_id not in self.active_games:
            return
            
        game = self.active_games[game_id]
        
        # Update database with game results
        self.db.complete_game(game_id, game.winner)
        
        # Process points transfer if there was a winner
        if game.winner == 'X':
            winner_id = game.player1_id
            loser_id = game.player2_id if not game.against_bot else None
        elif game.winner == 'O':
            winner_id = game.player2_id if not game.against_bot else None
            loser_id = game.player1_id
        else:  # Draw
            winner_id = None
            loser_id = None
            
        if winner_id and loser_id:
            self.db.transfer_points(loser_id, winner_id, game.bet_amount)
            
        # Remove game from active games
        del self.active_games[game_id]
        
        # Show the final game board with menu option
        if update:
            self.show_game_board(update, game_id, show_menu_button=True)

    def button_callback(self, update: Update, context: CallbackContext):
        """Handle button callbacks"""
        query = update.callback_query
        query.answer()
        
        data = query.data
        
        if data == "menu_main":
            self.show_main_menu(update)
        elif data == "menu_play":
            query.edit_message_text(
                "To start a game with a friend, use the command:\n"
                "<code>/play [amount]</code>\n\n"
                "Example: <code>/play 100</code>",
                parse_mode='HTML'
            )
        elif data == "menu_play_bot":
            query.edit_message_text(
                "To start a game against our AI bot, use the command:\n"
                "<code>/play_bot [amount]</code>\n\n"
                "Example: <code>/play_bot 100</code>",
                parse_mode='HTML'
            )
        elif data == "menu_stats":
            self.stats(query)
        elif data == "menu_deposit":
            query.edit_message_text(
                "To deposit points, use the command:\n"
                "<code>/deposit [amount]</code>\n\n"
                "Example: <code>/deposit 500</code>",
                parse_mode='HTML'
            )
        elif data == "menu_withdraw":
            query.edit_message_text(
                "To withdraw points, use the command:\n"
                "<code>/withdraw [amount]</code>\n\n"
                "Example: <code>/withdraw 500</code>",
                parse_mode='HTML'
            )
        elif data == "menu_leaderboard":
            self.leaderboard(query)
        elif data == "menu_admin":
            self.admin_menu(query)
        elif data.startswith("move_"):
            parts = data.split("_")
            if len(parts) == 3:
                try:
                    game_id = int(parts[1])
                    position = int(parts[2])
                    self.handle_move(query, game_id, position)
                except (ValueError, IndexError):
                    pass
        elif data.startswith("cancel_"):
            try:
                game_id = int(data.split("_")[1])
                self.handle_cancel(query, game_id)
            except (ValueError, IndexError):
                pass
        elif data.startswith("admin_"):
            self.admin_panel.handle_admin_callback(query, data)

    def stats(self, update: Update, context: CallbackContext = None):
        """Show user statistics"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            update.message.reply_text("User data not found!")
            return
            
        message = (
            "📊 <b>Your Statistics:</b>\n\n"
            f"🏆 Wins: {user_data['wins']}\n"
            f"💔 Losses: {user_data['losses']}\n"
            f"🤝 Draws: {user_data['draws']}\n"
            f"💰 Points: {user_data['points']}\n\n"
            f"🆔 User ID: <code>{user.id}</code>"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        
        if update.callback_query:
            update.callback_query.edit_message_text(
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            update.message.reply_text(
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

    def leaderboard(self, update: Update, context: CallbackContext = None):
        """Show the leaderboard"""
        top_players = self.db.get_top_players(10)
        
        if not top_players:
            message = "No players found on the leaderboard yet!"
        else:
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
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        
        if update.callback_query:
            update.callback_query.edit_message_text(
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            update.message.reply_text(
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

    def deposit(self, update: Update, context: CallbackContext):
        """Handle deposit command"""
        user = update.effective_user
        
        if not context.args:
            update.message.reply_text(
                "Please specify an amount to deposit.\n"
                "Example: /deposit 500"
            )
            return
            
        try:
            amount = int(context.args[0])
            if amount <= 0:
                raise ValueError
        except (ValueError, IndexError):
            update.message.reply_text("Please enter a valid positive amount.")
            return
            
        payment_methods = self.payment_processor.get_payment_methods()
        keyboard = [
            [InlineKeyboardButton(method, callback_data=f"deposit_{method.lower()}_{amount}")]
            for method in payment_methods.values()
        ]
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="menu_main")])
        
        update.message.reply_text(
            f"Select payment method for depositing {amount} points:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def withdraw(self, update: Update, context: CallbackContext):
        """Handle withdrawal command"""
        user = update.effective_user
        user_points = self.db.get_user_points(user.id) or 0
        
        if not context.args:
            update.message.reply_text(
                "Please specify an amount to withdraw.\n"
                "Example: /withdraw 500"
            )
            return
            
        try:
            amount = int(context.args[0])
            if amount <= 0:
                raise ValueError
        except (ValueError, IndexError):
            update.message.reply_text("Please enter a valid positive amount.")
            return
            
        if user_points < amount:
            update.message.reply_text(
                f"You don't have enough points! Your balance: {user_points}"
            )
            return
            
        payment_methods = self.payment_processor.get_payment_methods()
        keyboard = [
            [InlineKeyboardButton(method, callback_data=f"withdraw_{method.lower()}_{amount}")]
            for method in payment_methods.values()
        ]
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="menu_main")])
        
        fee = int(amount * (config.TRANSACTION_FEE / 100))
        net_amount = amount - fee
        
        update.message.reply_text(
            f"Select payment method for withdrawing {amount} points:\n"
            f"⚠️ Fee: {fee} points ({config.TRANSACTION_FEE}%)\n"
            f"💰 You'll receive: {net_amount} points",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def admin_menu(self, update: Update, context: CallbackContext = None):
        """Show admin control panel"""
        self.admin_panel.admin_menu(update, context)

    def handle_message(self, update: Update, context: CallbackContext):
        """Handle regular text messages"""
        update.message.reply_text(
            "I didn't understand that command. Use /menu to see available options."
        )

def main():
    # Load configuration
    db = Database(config.DB_HOST, config.DB_USER, config.DB_PASSWORD, config.DB_NAME)
    
    # Create and start the bot
    bot = XOBot(config.BOT_TOKEN, db)
    bot.updater.start_polling()
    bot.updater.idle()

if __name__ == '__main__':
    main()