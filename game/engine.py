# pyrefly: ignore [missing-import]
import chess
from .tables import (
    PAWN_TABLE, KNIGHT_TABLE, BISHOP_TABLE,
    ROOK_TABLE, QUEEN_TABLE,
    KING_MG_TABLE, KING_EG_TABLE,
)

# ==========================================================
# 0. GAME PHASE DETECTION: Middlegame ya Endgame?
# ==========================================================
# Queen material weight used to decide phase.
# If both queens are off the board we call it endgame.
_QUEEN_VALUE = 900

def _is_endgame(board):
    """
    Returns True when the position is classified as an endgame.
    Heuristic: total queen material on the board is less than one queen's value
    (i.e. at most one queen remains, OR both queens are gone).
    """
    queen_material = sum(
        _QUEEN_VALUE
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) and p.piece_type == chess.QUEEN
    )
    return queen_material < _QUEEN_VALUE  # fewer than 1 queen equivalent remaining

# ==========================================================
# 1. EVALUATION LOGIC: Board ki quality check karta hai
# ==========================================================
def evaluate_board(board, depth_left=0):
    # Checkmate handling: Agar game khatam hai toh max points do
    if board.is_checkmate():
        # Shorter paths to mate get a higher bonus (+depth_left)
        mate_score = 30000 + depth_left
        return -mate_score if board.turn == chess.WHITE else mate_score

    # Draw handling: Repetition ya stalemate hone par 0 score (Neutral)
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    # Choose king table based on game phase
    king_table = KING_EG_TABLE if _is_endgame(board) else KING_MG_TABLE

    score = 0
    # Har square ko scan karke pieces ki value aur position check karna
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue

        # White ke liye normal, Black ke liye mirrored table use karna
        idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
        val = 0

        # Piece Value + Positional Table Bonus
        if piece.piece_type == chess.PAWN:
            val = 100 + PAWN_TABLE[idx]
        elif piece.piece_type == chess.KNIGHT:
            val = 320 + KNIGHT_TABLE[idx]
        elif piece.piece_type == chess.BISHOP:
            val = 330 + BISHOP_TABLE[idx]
        elif piece.piece_type == chess.ROOK:
            val = 500 + ROOK_TABLE[idx]
        elif piece.piece_type == chess.QUEEN:
            val = 900 + QUEEN_TABLE[idx]
        elif piece.piece_type == chess.KING:
            val = 20000 + king_table[idx]

        # White ke points add honge aur Black ke subtract
        score += val if piece.color == chess.WHITE else -val
    return score

# ==========================================================
# 2. SEARCH OPTIMIZATION: Captures ko pehle check karna
# ==========================================================
def order_moves(board):
    moves = list(board.legal_moves)
    # Move sorting captures first makes Alpha-Beta pruning much faster
    moves.sort(key=lambda move: board.is_capture(move), reverse=True)
    return moves

# ==========================================================
# 3. MINIMAX ALGORITHM: Future moves simulate karna
# ==========================================================
def minimax(board, depth, alpha, beta, maximizing):
    # Draw Aversion: Same position repeat hone par 0 return karna
    if board.is_repetition(2):
        return 0

    # Base Case: Jab depth khatam ho ya game over, board evaluate karo
    if depth == 0 or board.is_game_over():
        return evaluate_board(board, depth)

    ordered_moves = order_moves(board)

    if maximizing:
        max_eval = -99999
        for move in ordered_moves:
            board.push(move)  # Move trial start
            eval = minimax(board, depth - 1, alpha, beta, False)  # Recursive call
            board.pop()  # Move trial end (Undo)
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)  # Best found so far
            if beta <= alpha:
                break  # Pruning: branch discard karna
        return max_eval
    else:
        min_eval = 99999
        for move in ordered_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break
        return min_eval

# ==========================================================
# 4. BEST MOVE SELECTION: Root level move selection
# ==========================================================
def get_best_move(board, depth):
    best_move = None
    maximizing = board.turn == chess.WHITE
    best_value = -100000 if maximizing else 100000
    alpha, beta = -100000, 100000

    for move in order_moves(board):
        board.push(move)
        # Minimax se current move ka future result check karna
        value = minimax(board, depth - 1, alpha, beta, not maximizing)
        board.pop()

        # Score update karke best move choose karna
        if maximizing:
            if value > best_value:
                best_value, best_move = value, move
            alpha = max(alpha, value)
        else:
            if value < best_value:
                best_value, best_move = value, move
            beta = min(beta, value)
    return best_move
