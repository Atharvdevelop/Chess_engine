from django.shortcuts import render, redirect
import chess
import chess.svg
from .tables import PAWN_TABLE, KNIGHT_TABLE, BISHOP_TABLE, KING_TABLE

# (Keep your pawn_table, knight_table, bishop_table, and king_table exactly as they are)

# =========================
# EVALUATION (STAYS THE SAME)
# =========================
def evaluate_board(board):
    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
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
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)

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
                break # Prune branch
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
                break # Prune branch
        return min_eval

# =========================
# BEST MOVE SELECTION (DEPTH 4)
# =========================
def get_best_move(board, depth):
    best_move = None
    maximizing = board.turn == chess.WHITE
    best_value = -100000 if maximizing else 100000
    
    alpha = -100000
    beta = 100000

    for move in order_moves(board):
        board.push(move)
        value = minimax(board, depth - 1, alpha, beta, not maximizing)
        board.pop()

        if maximizing:
            if value > best_value:
                best_value = value
                best_move = move
            alpha = max(alpha, value)
        else:
            if value < best_value:
                best_value = value
                best_move = move
            beta = min(beta, value)

    return best_move

# =========================
# DJANGO VIEW (UPDATED TO DEPTH 4)
# =========================

def board_view(request):
    # 1. Get or set User Preference (Default to White)
    user_color = request.session.get('user_color', 'white')
    fen = request.session.get('board_fen', 'start')
    board = chess.Board() if fen == 'start' else chess.Board(fen)

    # 2. Handle Side Selection via GET request
    if request.method == "GET" and 'choose_color' in request.GET:
        selected = request.GET.get('choose_color')
        request.session['user_color'] = selected
        request.session['board_fen'] = 'start'  # Reset board for new side
        return redirect('/')

    # 3. AI Automatic Move Logic
    # The AI moves if it is the AI's turn based on your chosen color
    ai_turn = (user_color == 'white' and board.turn == chess.BLACK) or \
              (user_color == 'black' and board.turn == chess.WHITE)

    if ai_turn and not board.is_game_over():
        engine_move = get_best_move(board, depth=4)
        if engine_move:
            board.push(engine_move)
            request.session['board_fen'] = board.fen()
            return redirect('/')

    # 4. Handle Player Move
    if request.method == "POST":
        move_uci = request.POST.get('move')
        try:
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                board.push(move)
                request.session['board_fen'] = board.fen()
        except:
            pass
        return redirect('/')

    return render(request, 'game/board.html', {
        'fen': board.fen(),
        'user_color': user_color
    })

def reset_game(request):
    # This now clears the board but KEEPS your color preference
    request.session['board_fen'] = 'start'
    return redirect('/')

