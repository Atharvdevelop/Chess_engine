from django.shortcuts import render, redirect
import chess
import chess.svg

# =========================
# PIECE-SQUARE TABLES
# =========================

pawn_table = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0
]

knight_table = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

bishop_table = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]

king_table = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20
]

# =========================
# EVALUATION (WHITE POV ONLY)
# =========================

def evaluate_board(board):
    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0   # ← THIS WAS MISSING

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue

        idx = square if piece.color == chess.WHITE else chess.square_mirror(square)   
        val = 0

        if piece.piece_type == chess.PAWN:
            val = 100 + pawn_table[idx]
        elif piece.piece_type == chess.KNIGHT:
            val = 320 + knight_table[idx]
        elif piece.piece_type == chess.BISHOP:
            val = 330 + bishop_table[idx]
        elif piece.piece_type == chess.ROOK:
            val = 500
        elif piece.piece_type == chess.QUEEN:
            val = 900
        elif piece.piece_type == chess.KING:
            val = 20000 + king_table[idx]

        score += val if piece.color == chess.WHITE else -val

    return score

# =========================
# MINIMAX + ALPHA BETA
# =========================

def minimax(board, depth, alpha, beta, maximizing):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)

    if maximizing:
        max_eval = -99999
        for move in board.legal_moves:
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
        for move in board.legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break
        return min_eval

# =========================
# BEST MOVE SELECTION
# =========================

def get_best_move(board, depth):
    best_move = None
    maximizing = board.turn == chess.WHITE
    best_value = -99999 if maximizing else 99999

    for move in board.legal_moves:
        board.push(move)
        value = minimax(board, depth - 1, -100000, 100000, not maximizing)
        board.pop()

        if maximizing and value > best_value:
            best_value = value
            best_move = move
        elif not maximizing and value < best_value:
            best_value = value
            best_move = move

    return best_move

# =========================
# DJANGO VIEW
# =========================

def board_view(request):
    fen = request.session.get('board_fen', 'start')
    board = chess.Board() if fen == 'start' else chess.Board(fen)

    if request.method == "POST":
        move_uci = request.POST.get('move')
        try:
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                board.push(move)

                if not board.is_game_over():
                    engine_move = get_best_move(board, depth=4)
                    if engine_move:
                        board.push(engine_move)

                request.session['board_fen'] = board.fen()
        except:
            pass

        return redirect('/')

    return render(request, 'game/board.html', {'fen': board.fen()})

def reset_game(request):
    request.session.pop('board_fen', None)
    return redirect('/')
