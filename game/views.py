from django.shortcuts import render, redirect
from django.http import JsonResponse
# pyrefly: ignore [missing-import]
import chess
import json
from .tables import PAWN_TABLE, KNIGHT_TABLE, BISHOP_TABLE, KING_TABLE

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

    score = 0
    # Har square ko scan karke pieces ki value aur position check karna
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece: continue

        # White ke liye normal, Black ke liye mirrored table use karna
        idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
        val = 0
        
        # Piece Value + Positional Table Bonus (Tables humein tables.py se milte hain)
        if piece.piece_type == chess.PAWN: val = 100 + PAWN_TABLE[idx]
        elif piece.piece_type == chess.KNIGHT: val = 320 + KNIGHT_TABLE[idx]
        elif piece.piece_type == chess.BISHOP: val = 330 + BISHOP_TABLE[idx]
        elif piece.piece_type == chess.ROOK: val = 500
        elif piece.piece_type == chess.QUEEN: val = 900
        elif piece.piece_type == chess.KING: val = 20000 + KING_TABLE[idx]

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
    if board.is_repetition(2): return 0

    # Base Case: Jab depth khatam ho ya game over, board evaluate karo
    if depth == 0 or board.is_game_over():
        return evaluate_board(board, depth)

    ordered_moves = order_moves(board)

    if maximizing:
        max_eval = -99999
        for move in ordered_moves:
            board.push(move) # Move trial start
            eval = minimax(board, depth - 1, alpha, beta, False) # Recursive call
            board.pop() # Move trial end (Undo)
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval) # Best found so far
            if beta <= alpha: break # Pruning: branch discard karna
        return max_eval
    else:
        min_eval = 99999
        for move in ordered_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha: break
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

# ==========================================================
# 5. DJANGO VIEWS: User requests aur UI interaction handle karna
# ==========================================================
def board_view(request):
    # Session se purana data load karna (FEN string, Color, History)
    user_color = request.session.get('user_color', 'white')
    fen = request.session.get('board_fen', 'start')
    move_history = request.session.get('move_history', []) 
    
    board = chess.Board() if fen == 'start' else chess.Board(fen)

    # User ke color choice ke according game reset karna
    if request.method == "GET" and 'choose_color' in request.GET:
        user_color = request.GET.get('choose_color')
        request.session['user_color'] = user_color
        request.session['board_fen'], request.session['move_history'] = 'start', []
        board = chess.Board()

    # Custom Position logic: FEN input validate karke load karna
    if request.method == "GET" and 'set_fen' in request.GET:
        custom_fen = request.GET.get('set_fen')
        try:
            chess.Board(custom_fen) 
            request.session['board_fen'], request.session['move_history'] = custom_fen, []
            board = chess.Board(custom_fen)
        except ValueError:
            pass

    # AI Turn logic for initial/GET load (e.g., if user plays black and game just starts/resets)
    ai_turn = (user_color == 'white' and board.turn == chess.BLACK) or \
              (user_color == 'black' and board.turn == chess.WHITE)

    if request.method == "GET":
        if ai_turn and not board.is_game_over():
            engine_move = get_best_move(board, depth=4)
            if engine_move:
                move_history.append(board.san(engine_move)) 
                board.push(engine_move)
                request.session['board_fen'], request.session['move_history'] = board.fen(), move_history
        
        # Template render karna context ke saath
        return render(request, 'game/board.html', {
            'fen': board.fen(), 'user_color': user_color, 'move_history': move_history 
        })

    # Player Move logic: Frontend se POST (AJAX/JSON) request handle karna
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            move_uci = data.get('move')
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({'success': False, 'error': 'Invalid JSON body'}, status=400)

        if not move_uci:
            return JsonResponse({'success': False, 'error': 'No move provided'}, status=400)
            
        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid move format'}, status=400)

        if move not in board.legal_moves:
            return JsonResponse({'success': False, 'error': 'Illegal move'}, status=400)

        # Apply player's move
        player_san = board.san(move)
        move_history.append(player_san) 
        board.push(move)
        
        # Save player's move to session
        request.session['board_fen'] = board.fen()
        request.session['move_history'] = move_history
        
        ai_played = False
        ai_move_san = None
        
        # Check if it's the AI's turn next
        ai_turn = (user_color == 'white' and board.turn == chess.BLACK) or \
                  (user_color == 'black' and board.turn == chess.WHITE)
                  
        if ai_turn and not board.is_game_over():
            engine_move = get_best_move(board, depth=4)
            if engine_move:
                ai_move_san = board.san(engine_move)
                move_history.append(ai_move_san)
                board.push(engine_move)
                ai_played = True
                
                # Save AI's move to session
                request.session['board_fen'] = board.fen()
                request.session['move_history'] = move_history

        # Determine if the game is over and get the reason
        is_game_over = board.is_game_over()
        game_over_reason = None
        if is_game_over:
            if board.is_checkmate():
                game_over_reason = "Checkmate"
            elif board.is_stalemate():
                game_over_reason = "Stalemate"
            elif board.is_insufficient_material():
                game_over_reason = "Insufficient Material"
            elif board.is_fivefold_repetition() or board.is_repetition(3):
                game_over_reason = "Repetition"
            elif board.is_seventyfive_moves() or board.is_fifty_moves():
                game_over_reason = "Fifty-move rule"
            else:
                game_over_reason = "Draw"

        return JsonResponse({
            'success': True,
            'board_fen': board.fen(),
            'ai_played': ai_played,
            'ai_move': ai_move_san,
            'move_history': move_history,
            'is_game_over': is_game_over,
            'game_over_reason': game_over_reason
        })

def make_move_api(request):
    """
    Dedicated JSON API endpoint: POST /make-move-api/
    Accepts: { "move": "<SAN string>" }  e.g. { "move": "e4" }
    Returns: JSON with updated FEN, move history, and game-over state.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        move_san = data.get('move', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON body'}, status=400)

    if not move_san:
        return JsonResponse({'success': False, 'error': 'No move provided'}, status=400)

    # Rebuild board from session
    user_color   = request.session.get('user_color', 'white')
    fen          = request.session.get('board_fen', 'start')
    move_history = request.session.get('move_history', [])
    board = chess.Board() if fen == 'start' else chess.Board(fen)

    # Parse SAN → validate as a legal move
    try:
        move = board.parse_san(move_san)
    except ValueError:
        return JsonResponse({'success': False, 'error': f'Invalid or illegal SAN move: {move_san}'}, status=400)

    if move not in board.legal_moves:
        return JsonResponse({'success': False, 'error': 'Illegal move'}, status=400)

    # Apply player's move
    player_san = board.san(move)
    move_history.append(player_san)
    board.push(move)
    request.session['board_fen']      = board.fen()
    request.session['move_history']   = move_history

    ai_played    = False
    ai_move_san  = None

    # AI's turn?
    ai_turn = (user_color == 'white' and board.turn == chess.BLACK) or \
              (user_color == 'black' and board.turn == chess.WHITE)

    if ai_turn and not board.is_game_over():
        engine_move = get_best_move(board, depth=4)
        if engine_move:
            ai_move_san = board.san(engine_move)
            move_history.append(ai_move_san)
            board.push(engine_move)
            ai_played = True
            request.session['board_fen']    = board.fen()
            request.session['move_history'] = move_history

    # Game-over detection
    is_game_over    = board.is_game_over()
    game_over_reason = None
    if is_game_over:
        if board.is_checkmate():
            game_over_reason = 'Checkmate'
        elif board.is_stalemate():
            game_over_reason = 'Stalemate'
        elif board.is_insufficient_material():
            game_over_reason = 'Insufficient Material'
        elif board.is_fivefold_repetition() or board.is_repetition(3):
            game_over_reason = 'Repetition'
        elif board.is_seventyfive_moves() or board.is_fifty_moves():
            game_over_reason = 'Fifty-move rule'
        else:
            game_over_reason = 'Draw'

    return JsonResponse({
        'success':          True,
        'board_fen':        board.fen(),
        'ai_played':        ai_played,
        'ai_move':          ai_move_san,
        'move_history':     move_history,
        'is_game_over':     is_game_over,
        'game_over_reason': game_over_reason,
    })


def reset_game(request):
    # Session variables ko clear karke game restart karna
    request.session['board_fen'], request.session['move_history'] = 'start', []
    return redirect('/')