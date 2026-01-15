from django.shortcuts import render, redirect
import chess
import chess.svg
import random  # This fixes the red line under 'random.choice'

# Positive values for White, we will flip them for Black
pawn_table = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
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


def evaluate_board(board):
    if board.is_checkmate():
        return -9999 if board.turn else 9999
    
    total_evaluation = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        
        # Base material values
        val = 0
        if piece.piece_type == chess.PAWN: val = 100 + pawn_table[square if piece.color == chess.WHITE else chess.square_mirror(square)]
        elif piece.piece_type == chess.KNIGHT: val = 320 + knight_table[square if piece.color == chess.WHITE else chess.square_mirror(square)]
        elif piece.piece_type == chess.BISHOP: val = 330 + bishop_table[square if piece.color == chess.WHITE else chess.square_mirror(square)]
        elif piece.piece_type == chess.ROOK: val = 500
        elif piece.piece_type == chess.QUEEN: val = 900
        elif piece.piece_type == chess.KING: val = 20000 + king_table[square if piece.color == chess.WHITE else chess.square_mirror(square)]
        
        if piece.color == chess.WHITE:
            total_evaluation += val
        else:
            total_evaluation -= val
            
    return total_evaluation



def minimax(board, depth, alpha, beta, maximizing_player):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)

    if maximizing_player:
        max_eval = -99999
        for move in board.legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha: break
        return max_eval
    else:
        min_eval = 99999
        for move in board.legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha: break
        return min_eval

def get_best_move(board, depth):
    best_move = None
    best_value = -99999
    for move in board.legal_moves:
        board.push(move)
        board_value = -minimax(board, depth - 1, -100000, 100000, not board.turn)
        board.pop()
        if board_value > best_value:
            best_value = board_value
            best_move = move
    return best_move

def board_view(request):
    fen = request.session.get('board_fen', 'start')
    board = chess.Board(fen) if fen != 'start' else chess.Board()

    if request.method == "POST":
        move_uci = request.POST.get('move')
        try:
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                board.push(move)
                
                # Engine Move (Random)
                if not board.is_game_over():
                    engine_move = get_best_move(board, depth=5) # depth 3 looks 3 turns ahead
                    if engine_move:
                        board.push(engine_move)
                
                request.session['board_fen'] = board.fen()
        except:
            pass
        return redirect('/')

    # Send the 'fen' string to the template instead of the SVG
    return render(request, 'game/board.html', {'fen': board.fen()})


def reset_game(request):
    # This clears the board memory from the database
    if 'board_fen' in request.session:
        del request.session['board_fen']
    return redirect('/')


