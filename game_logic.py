from typing import List, Optional
import random

class XOGame:
    def __init__(self, player1_id: int, player2_id: Optional[int] = None, 
                 bet_amount: int = 0, against_bot: bool = False):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.bet_amount = bet_amount
        self.against_bot = against_bot
        self.board = [' ' for _ in range(9)]  # 3x3 board
        self.current_turn = 'X'  # Player X starts first
        self.winner = None
        self.game_over = False
        
    def make_move(self, position: int, symbol: str) -> bool:
        """Make a move on the board"""
        if self.game_over or not (0 <= position < 9) or self.board[position] != ' ' or symbol != self.current_turn:
            return False
            
        self.board[position] = symbol
        self.current_turn = 'O' if symbol == 'X' else 'X'
        
        # Check for winner or draw
        self.winner = self.check_winner()
        if self.winner or self.is_board_full():
            self.game_over = True
            
        return True
        
    def check_winner(self) -> Optional[str]:
        """Check if there's a winner"""
        # Check rows
        for i in range(0, 9, 3):
            if self.board[i] == self.board[i+1] == self.board[i+2] != ' ':
                return self.board[i]
                
        # Check columns
        for i in range(3):
            if self.board[i] == self.board[i+3] == self.board[i+6] != ' ':
                return self.board[i]
                
        # Check diagonals
        if self.board[0] == self.board[4] == self.board[8] != ' ':
            return self.board[0]
        if self.board[2] == self.board[4] == self.board[6] != ' ':
            return self.board[2]
            
        return None
        
    def is_board_full(self) -> bool:
        """Check if the board is full (draw)"""
        return ' ' not in self.board
        
    def get_board_for_display(self) -> List[str]:
        """Get the board with positions for empty cells"""
        return [self.board[i] if self.board[i] != ' ' else str(i+1) for i in range(9)]
        
    def bot_move(self) -> Optional[int]:
        """AI bot makes a move using minimax algorithm"""
        if not self.against_bot or self.current_turn != 'O' or self.game_over:
            return None
            
        # For the first move, sometimes make a random move for variety
        if self.board.count(' ') >= 8 and random.random() < 0.3:
            empty_positions = [i for i, cell in enumerate(self.board) if cell == ' ']
            return random.choice(empty_positions)
            
        best_score = -float('inf')
        best_move = None
        
        for i in range(9):
            if self.board[i] == ' ':
                self.board[i] = 'O'
                score = self.minimax(self.board, 0, False)
                self.board[i] = ' '
                
                if score > best_score:
                    best_score = score
                    best_move = i
                    
        if best_move is not None:
            self.make_move(best_move, 'O')
            return best_move
            
        return None
        
    def minimax(self, board: List[str], depth: int, is_maximizing: bool) -> int:
        """Minimax algorithm implementation"""
        # Create a temporary game to check winner
        temp_game = XOGame(0)
        temp_game.board = board.copy()
        
        winner = temp_game.check_winner()
        
        if winner == 'O':
            return 10 - depth
        elif winner == 'X':
            return depth - 10
        elif temp_game.is_board_full():
            return 0
            
        if is_maximizing:
            best_score = -float('inf')
            for i in range(9):
                if board[i] == ' ':
                    board[i] = 'O'
                    score = self.minimax(board, depth + 1, False)
                    board[i] = ' '
                    best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for i in range(9):
                if board[i] == ' ':
                    board[i] = 'X'
                    score = self.minimax(board, depth + 1, True)
                    board[i] = ' '
                    best_score = min(score, best_score)
            return best_score
            
    def get_game_state(self) -> dict:
        """Return current game state"""
        return {
            'board': self.board,
            'current_turn': self.current_turn,
            'winner': self.winner,
            'game_over': self.game_over,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'bet_amount': self.bet_amount,
            'against_bot': self.against_bot
        }