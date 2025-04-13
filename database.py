import mysql.connector
from mysql.connector import Error
import logging
from typing import Optional, Dict, List

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, host: str, user: str, password: str, database: str):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = self._create_connection()
        
    def _create_connection(self):
        """Create a database connection"""
        try:
            connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=False
            )
            logger.info("MySQL Database connection successful")
            return connection
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise
            
    def _execute_query(self, query: str, params: tuple = None, fetch_one: bool = False):
        """Execute a SQL query and return results"""
        cursor = None
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if fetch_one:
                result = cursor.fetchone()
            else:
                result = cursor.fetchall()
                
            self.connection.commit()
            return result
        except Error as e:
            self.connection.rollback()
            logger.error(f"Query execution error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
                
    def initialize_tables(self):
        """Initialize all required database tables"""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                points INT DEFAULT 100,
                wins INT DEFAULT 0,
                losses INT DEFAULT 0,
                draws INT DEFAULT 0,
                banned BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS games (
                game_id INT AUTO_INCREMENT PRIMARY KEY,
                player1_id BIGINT,
                player2_id BIGINT,
                bet_amount INT,
                winner_id BIGINT,
                status ENUM('pending', 'active', 'completed', 'abandoned') DEFAULT 'pending',
                board_state VARCHAR(9) DEFAULT '         ',
                current_turn ENUM('X', 'O') DEFAULT 'X',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (player1_id) REFERENCES users(user_id) ON DELETE SET NULL,
                FOREIGN KEY (player2_id) REFERENCES users(user_id) ON DELETE SET NULL,
                FOREIGN KEY (winner_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                amount INT,
                type ENUM('deposit', 'withdrawal', 'bet', 'win', 'loss', 'transfer', 'fee', 'adjustment'),
                status ENUM('pending', 'completed', 'rejected') DEFAULT 'pending',
                payment_method VARCHAR(100),
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                message_text TEXT,
                is_broadcast BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
            """
        ]
        
        for query in queries:
            self._execute_query(query)
            
    def create_user_if_not_exists(self, user_id: int, username: str, first_name: str, last_name: str) -> bool:
        """Create a new user if they don't exist"""
        query = """
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        username = VALUES(username),
        first_name = VALUES(first_name),
        last_name = VALUES(last_name),
        last_active = CURRENT_TIMESTAMP
        """
        try:
            self._execute_query(query, (user_id, username, first_name, last_name))
            return True
        except Error:
            return False
            
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user details"""
        query = "SELECT * FROM users WHERE user_id = %s"
        return self._execute_query(query, (user_id,), fetch_one=True)
        
    def get_user_points(self, user_id: int) -> Optional[int]:
        """Get user's points balance"""
        query = "SELECT points FROM users WHERE user_id = %s"
        result = self._execute_query(query, (user_id,), fetch_one=True)
        return result['points'] if result else None
        
    def update_user_points(self, user_id: int, amount: int) -> bool:
        """Update user's points balance"""
        query = "UPDATE users SET points = points + %s WHERE user_id = %s"
        try:
            self._execute_query(query, (amount, user_id))
            return True
        except Error:
            return False
            
    def create_game(self, player1_id: int, bet_amount: int) -> Optional[int]:
        """Create a new game and return game ID"""
        query = """
        INSERT INTO games (player1_id, bet_amount)
        VALUES (%s, %s)
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (player1_id, bet_amount))
            game_id = cursor.lastrowid
            self.connection.commit()
            cursor.close()
            return game_id
        except Error as e:
            logger.error(f"Error creating game: {e}")
            return None
            
    def complete_game(self, game_id: int, winner: Optional[str]) -> bool:
        """Mark a game as completed and set the winner"""
        query = """
        UPDATE games 
        SET status = 'completed', 
            completed_at = CURRENT_TIMESTAMP,
            winner_id = CASE %s 
                WHEN 'X' THEN player1_id 
                WHEN 'O' THEN player2_id 
                ELSE NULL 
            END
        WHERE game_id = %s
        """
        try:
            self._execute_query(query, (winner, game_id))
            
            # Update player statistics
            game = self.get_game(game_id)
            if not game:
                return False
                
            if winner == 'X':
                self._execute_query(
                    "UPDATE users SET wins = wins + 1 WHERE user_id = %s",
                    (game['player1_id'],)
                )
                self._execute_query(
                    "UPDATE users SET losses = losses + 1 WHERE user_id = %s",
                    (game['player2_id'],)
                )
            elif winner == 'O':
                self._execute_query(
                    "UPDATE users SET wins = wins + 1 WHERE user_id = %s",
                    (game['player2_id'],)
                )
                self._execute_query(
                    "UPDATE users SET losses = losses + 1 WHERE user_id = %s",
                    (game['player1_id'],)
                )
            else:  # Draw
                self._execute_query(
                    "UPDATE users SET draws = draws + 1 WHERE user_id IN (%s, %s)",
                    (game['player1_id'], game['player2_id'])
                )
                
            return True
        except Error as e:
            logger.error(f"Error completing game: {e}")
            return False
            
    def get_game(self, game_id: int) -> Optional[Dict]:
        """Get game details"""
        query = "SELECT * FROM games WHERE game_id = %s"
        return self._execute_query(query, (game_id,), fetch_one=True)
        
    def record_transaction(self, user_id: int, amount: int, 
                         transaction_type: str, status: str, 
                         payment_method: str = None, details: str = None) -> Optional[int]:
        """Record a financial transaction"""
        query = """
        INSERT INTO transactions 
        (user_id, amount, type, status, payment_method, details)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (user_id, amount, transaction_type, status, payment_method, details))
            transaction_id = cursor.lastrowid
            self.connection.commit()
            cursor.close()
            return transaction_id
        except Error as e:
            logger.error(f"Error recording transaction: {e}")
            return None
            
    def get_pending_withdrawals(self) -> List[Dict]:
        """Get all pending withdrawal requests"""
        query = """
        SELECT t.*, u.username, u.first_name 
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.type = 'withdrawal' AND t.status = 'pending'
        """
        return self._execute_query(query)
        
    def update_transaction_status(self, transaction_id: int, status: str) -> bool:
        """Update transaction status"""
        query = "UPDATE transactions SET status = %s, processed_at = CURRENT_TIMESTAMP WHERE transaction_id = %s"
        try:
            self._execute_query(query, (status, transaction_id))
            return True
        except Error:
            return False
            
    def get_top_players(self, limit: int = 10) -> List[Dict]:
        """Get top players by points"""
        query = """
        SELECT user_id, username, first_name, last_name, points, wins, losses, draws
        FROM users
        WHERE banned = FALSE
        ORDER BY points DESC
        LIMIT %s
        """
        return self._execute_query(query, (limit,))
        
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        query = "SELECT is_admin FROM users WHERE user_id = %s"
        result = self._execute_query(query, (user_id,), fetch_one=True)
        return result['is_admin'] if result else False