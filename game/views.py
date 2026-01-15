from django.shortcuts import render, redirect
import chess
import chess.svg
import random  # This fixes the red line under 'random.choice'



def evaluate_board(board):
    # Basic material counting: P=100, N/B=300, R=500, Q=900
    if board.is_checkmate():
        return -9999 if board.turn else 9999
    
    wp = len(board.pieces(chess.PAWN, chess.WHITE))
    bp = len(board.pieces(chess.PAWN, chess.BLACK))
    wn = len(board.pieces(chess.KNIGHT, chess.WHITE))
    bn = len(board.pieces(chess.KNIGHT, chess.BLACK))
    wb = len(board.pieces(chess.BISHOP, chess.WHITE))
    bb = len(board.pieces(chess.BISHOP, chess.BLACK))
    wr = len(board.pieces(chess.ROOK, chess.WHITE))
    br = len(board.pieces(chess.ROOK, chess.BLACK))
    wq = len(board.pieces(chess.QUEEN, chess.WHITE))
    bq = len(board.pieces(chess.QUEEN, chess.BLACK))
    
    return 100*(wp-bp) + 300*(wn-bn + wb-bb) + 500*(wr-br) + 900*(wq-bq)

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


