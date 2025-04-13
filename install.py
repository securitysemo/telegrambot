import mysql.connector
from mysql.connector import Error
import getpass
import configparser
import os
import re

def validate_bot_token(token):
    """Validate Telegram bot token format"""
    return re.match(r'^\d+:[a-zA-Z0-9_-]+$', token) is not None

def validate_user_id(user_id):
    """Validate Telegram user ID"""
    return user_id.isdigit()

def run_installation():
    print("=== XO Game Bot Installation ===")
    print("This script will guide you through the setup process.\n")
    
    # Database Configuration
    print("\n[Database Configuration]")
    db_host = input("Database host (default: localhost): ").strip() or "localhost"
    db_user = input("Database username: ").strip()
    if not db_user:
        print("Error: Database username is required!")
        return
        
    db_password = getpass.getpass("Database password (leave empty if none): ").strip() or ""
    db_name = input("Database name (will be created if not exists): ").strip()
    if not db_name:
        print("Error: Database name is required!")
        return
    
    # Telegram Configuration
    print("\n[Telegram Bot Configuration]")
    while True:
        bot_token = input("Telegram bot token (from @BotFather): ").strip()
        if validate_bot_token(bot_token):
            break
        print("Invalid bot token format. Please enter a valid token (format: 123456789:ABCdefGHIJKlmNoPQRsTUVwxyZ)")
    
    while True:
        admin_id = input("Admin Telegram user ID (get it from @userinfobot): ").strip()
        if validate_user_id(admin_id):
            admin_id = int(admin_id)
            break
        print("Invalid user ID. Please enter a numeric ID.")
    
    # Payment Configuration
    print("\n[Payment Configuration]")
    transaction_fee = 5
    try:
        fee_input = input("Transaction fee percentage (default: 5): ").strip()
        if fee_input:
            transaction_fee = max(0, min(100, int(fee_input)))
    except ValueError:
        print("Using default transaction fee of 5%")
    
    initial_points = 100
    try:
        points_input = input("Initial points for new users (default: 100): ").strip()
        if points_input:
            initial_points = max(0, int(points_input))
    except ValueError:
        print("Using default initial points of 100")
    
    # Game Configuration
    print("\n[Game Configuration]")
    min_bet = 10
    max_bet = 5000
    try:
        min_input = input("Minimum bet amount (default: 10): ").strip()
        if min_input:
            min_bet = max(1, int(min_input))
        
        max_input = input("Maximum bet amount (default: 5000): ").strip()
        if max_input:
            max_bet = max(min_bet, int(max_input))
    except ValueError:
        print("Using default bet limits (10-5000)")
    
    print("\nStarting installation...")
    
    try:
        # Connect to MySQL server
        connection = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password
        )
        
        # Create database if not exists
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.close()
        
        # Create config file
        config = configparser.ConfigParser()
        
        config['DATABASE'] = {
            'host': db_host,
            'user': db_user,
            'password': db_password,
            'database': db_name
        }
        
        config['TELEGRAM'] = {
            'bot_token': bot_token,
            'admin_id': str(admin_id),
            'bot_username': bot_token.split(':')[0]
        }
        
        config['SETTINGS'] = {
            'transaction_fee': str(transaction_fee),
            'initial_points': str(initial_points),
            'min_bet': str(min_bet),
            'max_bet': str(max_bet)
        }
        
        config['PAYMENT'] = {
            'methods': 'paypal,vodafone,bank'
        }
        
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
            
        print("\nConfiguration saved to config.ini")
        
        # Initialize database tables
        from database import Database
        db = Database(db_host, db_user, db_password, db_name)
        db.initialize_tables()
        
        # Create admin user
        cursor = db.connection.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, points, is_admin) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "username=VALUES(username), "
            "first_name=VALUES(first_name), "
            "last_name=VALUES(last_name), "
            "points=VALUES(points), "
            "is_admin=VALUES(is_admin)",
            (admin_id, 'admin', 'Admin', 'User', 10000, True)
        )
        db.connection.commit()
        cursor.close()
        
        print("\n=== Installation Completed Successfully ===")
        print("\nNext steps:")
        print("1. Install requirements: pip install -r requirements.txt")
        print("2. Start the bot: python bot.py")
        print("\nFor production use, consider running the bot with:")
        print("nohup python bot.py > bot.log 2>&1 &")
        
    except Error as e:
        print(f"\nError during installation: {e}")
        if 'connection' in locals() and connection.is_connected():
            connection.close()
    except Exception as e:
        print(f"\nUnexpected error: {e}")

if __name__ == '__main__':
    run_installation()