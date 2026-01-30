from django.shortcuts import render, redirect
import chess
import chess.svg
from .tables import PAWN_TABLE, KNIGHT_TABLE, BISHOP_TABLE, KING_TABLE

# (Keep your pawn_table, knight_table, bishop_table, and king_table exactly as they are)

# =========================
# EVALUATION (STAYS THE SAME)
# =========================
def evaluate_board(board, depth_left=0):
    # 1. Checkmate handling
    if board.is_checkmate():
        mate_score = 30000 + depth_left 
        return -mate_score if board.turn == chess.WHITE else mate_score

    # 2. Draw handling - Fixed the attribute error here
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_threefold_repetition():
        return 0

    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue

        idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
        val = 0

        if piece.piece_type == chess.PAWN:
            val = 100 + PAWN_TABLE[idx]
        elif piece.piece_type == chess.KNIGHT:
            val = 320 + KNIGHT_TABLE[idx]
        elif piece.piece_type == chess.BISHOP:
            val = 330 + BISHOP_TABLE[idx]
        elif piece.piece_type == chess.ROOK:
            val = 500
        elif piece.piece_type == chess.QUEEN:
            val = 900
        elif piece.piece_type == chess.KING:
            val = 20000 + KING_TABLE[idx]

        score += val if piece.color == chess.WHITE else -val
    return score

# =========================
# NEW: MOVE ORDERING (SPEED BOOST)
# =========================
def order_moves(board):
    """Sorts moves to check captures first, making Alpha-Beta much faster."""
    moves = list(board.legal_moves)
    # Checks captures first because they are most likely to cause pruning
    moves.sort(key=lambda move: board.is_capture(move), reverse=True)
    return moves

# =========================
# OPTIMIZED MINIMAX + ALPHA BETA
# =========================
def minimax(board, depth, alpha, beta, maximizing):
    # Only check for repetition if there are few pieces left (Endgame)
    # This restores speed in the opening/middle game.
    if len(board.piece_map()) < 10: 
        if board.is_repetition(2): 
            return 0

    if depth == 0 or board.is_game_over():
        # Always pass depth to ensure the "fast mate" bonus works
        return evaluate_board(board, depth)

    ordered_moves = order_moves(board)

    if maximizing:
        max_eval = -99999
        for move in ordered_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha: 
                break 
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
    
# =========================
# BEST MOVE SELECTION (DEPTH 4)
# =========================

def get_best_move(board, depth):
    best_move = None
    maximizing = board.turn == chess.WHITE
    best_value = -100000 if maximizing else 100000
    alpha, beta = -100000, 100000

    for move in order_moves(board):
        board.push(move)
        # Pass the depth to minimax so evaluate_board can use it
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

# =========================
# DJANGO VIEW (UPDATED TO DEPTH 4)
# =========================

def board_view(request):
    # 1. Get current data from session
    user_color = request.session.get('user_color', 'white')
    fen = request.session.get('board_fen', 'start')
    move_history = request.session.get('move_history', []) 
    
    board = chess.Board() if fen == 'start' else chess.Board(fen)

    # 2. Handle Side Selection
    if request.method == "GET" and 'choose_color' in request.GET:
        request.session['user_color'] = request.GET.get('choose_color')
        request.session['board_fen'] = 'start'
        request.session['move_history'] = [] 
        return redirect('/')

    # --- NEW: Handle Custom FEN Position ---
    if request.method == "GET" and 'set_fen' in request.GET:
        custom_fen = request.GET.get('set_fen')
        try:
            # Validate if it is a real FEN string
            chess.Board(custom_fen) 
            request.session['board_fen'] = custom_fen
            request.session['move_history'] = [] # New position, new history
            return redirect('/')
        except ValueError:
            # If FEN is invalid, ignore it and continue
            pass

    # 3. AI Automatic Move Logic
    ai_turn = (user_color == 'white' and board.turn == chess.BLACK) or \
              (user_color == 'black' and board.turn == chess.WHITE)

    if ai_turn and not board.is_game_over():
        engine_move = get_best_move(board, depth=4)
        if engine_move:
            move_history.append(board.san(engine_move)) 
            board.push(engine_move)
            request.session['board_fen'] = board.fen()
            request.session['move_history'] = move_history
            return redirect('/')

    # 4. Handle Player Move
    if request.method == "POST":
        move_uci = request.POST.get('move')
        try:
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                move_history.append(board.san(move)) 
                board.push(move)
                request.session['board_fen'] = board.fen()
                request.session['move_history'] = move_history
        except:
            pass
        return redirect('/')

    return render(request, 'game/board.html', {
        'fen': board.fen(),
        'user_color': user_color,
        'move_history': move_history 
    })


def reset_game(request):
    request.session['board_fen'] = 'start'
    request.session['move_history'] = [] # Clean everything on reset
    return redirect('/')


