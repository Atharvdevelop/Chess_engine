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
_QUEEN_VALUE = 900

def _is_endgame(board):
    """
    Returns True when the position is classified as an endgame.
    Heuristic: if both queens are gone, OR if there is a queen but the total
    non-king, non-pawn material on the board is less than or equal to 12 points.
    (This ensures K+Q vs K is correctly classified as an endgame).
    """
    queens = [
        sq for sq in chess.SQUARES
        if (p := board.piece_at(sq)) and p.piece_type == chess.QUEEN
    ]
    if not queens:
        return True

    # Standard values: Q=9, R=5, B=3, N=3
    non_pawn_weight = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type not in (chess.KING, chess.PAWN):
            if p.piece_type == chess.QUEEN:
                non_pawn_weight += 9
            elif p.piece_type == chess.ROOK:
                non_pawn_weight += 5
            elif p.piece_type in (chess.BISHOP, chess.KNIGHT):
                non_pawn_weight += 3

    return non_pawn_weight <= 12

# ==========================================================
# 1. EVALUATION LOGIC: Board ki quality check karta hai
# ==========================================================
def evaluate_board(board, depth_left=0):
    # Checkmate handling: shorter paths get a higher bonus (+depth_left)
    if board.is_checkmate():
        mate_score = 30000 + depth_left
        return -mate_score if board.turn == chess.WHITE else mate_score

    # Draw: stalemate, repetition, insufficient material
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    # Choose king table based on game phase
    king_table = KING_EG_TABLE if _is_endgame(board) else KING_MG_TABLE

    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue

        # White = normal index, Black = mirrored index
        idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
        val = 0

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

        score += val if piece.color == chess.WHITE else -val

    # Lone-king / cornering heuristics
    white_pieces = board.occupied_co[chess.WHITE]
    black_pieces = board.occupied_co[chess.BLACK]

    if chess.popcount(black_pieces) == 1 and chess.popcount(white_pieces) > 1:
        # White is winning: close in and push Black King to a corner
        wk = board.king(chess.WHITE)
        bk = board.king(chess.BLACK)
        if wk is not None and bk is not None:
            score -= chess.square_distance(wk, bk) * 10
            b_file = chess.square_file(bk)
            b_rank = chess.square_rank(bk)
            score += int((abs(b_file - 3.5) + abs(b_rank - 3.5)) * 20)

    elif chess.popcount(white_pieces) == 1 and chess.popcount(black_pieces) > 1:
        # Black is winning: close in and push White King to a corner
        wk = board.king(chess.WHITE)
        bk = board.king(chess.BLACK)
        if wk is not None and bk is not None:
            score += chess.square_distance(wk, bk) * 10
            w_file = chess.square_file(wk)
            w_rank = chess.square_rank(wk)
            score -= int((abs(w_file - 3.5) + abs(w_rank - 3.5)) * 20)

    return score

# ==========================================================
# 2. PIECE VALUES (used by MVV-LVA move ordering)
# ==========================================================
_PIECE_VALUES = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:  20000,
}

def _get_piece_value(piece_type: int) -> int:
    """Return the centipawn value of a piece type."""
    return _PIECE_VALUES.get(piece_type, 0)

# ==========================================================
# 3. MOVE ORDERING: MVV-LVA + check bonus + promotions
# ==========================================================
def order_moves(board):
    """
    Order moves to maximise alpha-beta pruning efficiency.
    Priority (highest first):
      1. Captures scored by MVV-LVA  (victim_value * 10 - attacker_value)
      2. Promotions (queen)
      3. Moves that give check
      4. Quiet moves
    """
    moves = list(board.legal_moves)

    def move_score(move):
        score = 0
        # MVV-LVA: captures
        if board.is_capture(move):
            victim_sq = move.to_square
            victim    = board.piece_at(victim_sq)
            attacker  = board.piece_at(move.from_square)
            if victim and attacker:
                score += _get_piece_value(victim.piece_type) * 10 \
                       - _get_piece_value(attacker.piece_type)
            else:
                # En-passant: attacker is pawn, victim is pawn
                score += 100 * 10 - 100
        # Promotions (queen)
        if move.promotion == chess.QUEEN:
            score += 800
        # Check bonus (relatively cheap: board does not need to push the move)
        if board.gives_check(move):
            score += 50
        return score

    moves.sort(key=move_score, reverse=True)
    return moves

# ==========================================================
# 4. TRANSPOSITION TABLE
# ==========================================================
# Flag constants
TT_EXACT      = 0   # Exact score stored
TT_LOWERBOUND = 1   # Score is at least this (alpha cutoff occurred)
TT_UPPERBOUND = 2   # Score is at most this (beta cutoff occurred)

# The table maps board._transposition_key() → (depth, flag, score)
_transposition_table: dict = {}

def clear_transposition_table():
    """Empty the TT at the start of each root search to avoid stale entries."""
    _transposition_table.clear()

# ==========================================================
# 5. MINIMAX WITH ALPHA-BETA + TRANSPOSITION TABLE
# ==========================================================
def minimax(board, depth, alpha, beta, maximizing):
    # Draw aversion: repeated position returns 0
    if board.is_repetition(2):
        return 0

    # --- Transposition Table lookup ---
    tt_key = board._transposition_key()
    tt_entry = _transposition_table.get(tt_key)
    if tt_entry is not None:
        cached_depth, cached_flag, cached_score = tt_entry
        if cached_depth >= depth:
            if cached_flag == TT_EXACT:
                return cached_score
            elif cached_flag == TT_LOWERBOUND:
                alpha = max(alpha, cached_score)
            elif cached_flag == TT_UPPERBOUND:
                beta = min(beta, cached_score)
            if alpha >= beta:
                return cached_score

    # Base case: leaf node or game over
    if depth == 0 or board.is_game_over():
        return evaluate_board(board, depth)

    ordered_moves = order_moves(board)
    original_alpha = alpha

    if maximizing:
        max_eval = -99999
        for move in ordered_moves:
            board.push(move)
            val = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, val)
            alpha    = max(alpha, val)
            if beta <= alpha:
                break  # Beta cutoff — prune remaining branches

        # Store result in TT
        flag = TT_EXACT if original_alpha < max_eval < beta else \
               (TT_LOWERBOUND if max_eval >= beta else TT_UPPERBOUND)
        _transposition_table[tt_key] = (depth, flag, max_eval)
        return max_eval

    else:
        min_eval = 99999
        for move in ordered_moves:
            board.push(move)
            val = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, val)
            beta     = min(beta, val)
            if beta <= alpha:
                break  # Alpha cutoff — prune remaining branches

        flag = TT_EXACT if alpha < min_eval < beta else \
               (TT_UPPERBOUND if min_eval <= alpha else TT_LOWERBOUND)
        _transposition_table[tt_key] = (depth, flag, min_eval)
        return min_eval

# ==========================================================
# 6. BEST MOVE SELECTION: Root-level search
# ==========================================================
def get_best_move(board, depth):
    # Clear TT each time so a fresh search produces accurate results
    clear_transposition_table()

    best_move   = None
    maximizing  = board.turn == chess.WHITE
    best_value  = -100000 if maximizing else 100000
    alpha, beta = -100000, 100000

    for move in order_moves(board):
        board.push(move)
        value = minimax(board, depth - 1, alpha, beta, not maximizing)
        board.pop()

        if maximizing:
            if value > best_value:
                best_value, best_move = value, move
            alpha = max(alpha, value)
        else:
            if value < best_value:
                best_value, best_move = value, move
            beta = min(beta, value)

    return best_move
