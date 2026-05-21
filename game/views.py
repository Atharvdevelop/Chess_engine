from django.shortcuts import render, redirect
from django.http import JsonResponse
# pyrefly: ignore [missing-import]
import chess
import json
from .engine import get_best_move

def _reconstruct_board(session):
    """
    Reconstructs the chess.Board with full move history from the session.
    This is critical for detecting threefold repetition.
    """
    initial_fen = session.get('initial_fen', 'start')
    move_history = session.get('move_history', [])
    board = chess.Board() if initial_fen == 'start' else chess.Board(initial_fen)
    for move_san in move_history:
        try:
            board.push_san(move_san)
        except ValueError:
            pass
    return board

# ==========================================================
# DJANGO VIEWS: User requests aur UI interaction handle karna
# ==========================================================

def board_view(request):
    # Session se purana data load karna (FEN string, Color, History)
    user_color = request.session.get('user_color', 'white')
    fen = request.session.get('board_fen', 'start')
    move_history = request.session.get('move_history', [])

    if 'initial_fen' not in request.session:
        request.session['initial_fen'] = 'start'

    board = _reconstruct_board(request.session)

    # User ke color choice ke according game reset karna
    if request.method == "GET" and 'choose_color' in request.GET:
        user_color = request.GET.get('choose_color')
        request.session['user_color'] = user_color
        request.session['board_fen'], request.session['move_history'] = 'start', []
        request.session['initial_fen'] = 'start'
        board = chess.Board()

    # Custom Position logic: FEN input validate karke load karna
    if request.method == "GET" and 'set_fen' in request.GET:
        custom_fen = request.GET.get('set_fen')
        try:
            chess.Board(custom_fen)
            request.session['board_fen'], request.session['move_history'] = custom_fen, []
            request.session['initial_fen'] = custom_fen
            board = chess.Board(custom_fen)
        except ValueError:
            pass  # Invalid FEN: silently ignore and keep the current board

    # AI Turn logic for initial/GET load (e.g., if user plays black and game just starts/resets)
    ai_turn = (user_color == 'white' and board.turn == chess.BLACK) or \
              (user_color == 'black' and board.turn == chess.WHITE)

    if request.method == "GET":
        if ai_turn and not board.is_game_over(claim_draw=True):
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

        if ai_turn and not board.is_game_over(claim_draw=True):
            engine_move = get_best_move(board, depth=4)
            if engine_move:
                ai_move_san = board.san(engine_move)
                move_history.append(ai_move_san)
                board.push(engine_move)
                ai_played = True

                # Save AI's move to session
                request.session['board_fen'] = board.fen()
                request.session['move_history'] = move_history

        return JsonResponse({
            'success': True,
            'board_fen': board.fen(),
            'ai_played': ai_played,
            'ai_move': ai_move_san,
            'move_history': move_history,
            'is_game_over': board.is_game_over(claim_draw=True),
            'game_over_reason': _get_game_over_reason(board),
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
    move_history = request.session.get('move_history', [])
    if 'initial_fen' not in request.session:
        request.session['initial_fen'] = 'start'
    board = _reconstruct_board(request.session)

    # Parse SAN → validate as a legal move
    try:
        move = board.parse_san(move_san)
    except ValueError:
        return JsonResponse(
            {'success': False, 'error': f'Invalid or illegal SAN move: {move_san}'},
            status=400
        )

    if move not in board.legal_moves:
        return JsonResponse({'success': False, 'error': 'Illegal move'}, status=400)

    # Apply player's move
    player_san = board.san(move)
    move_history.append(player_san)
    board.push(move)
    request.session['board_fen']    = board.fen()
    request.session['move_history'] = move_history

    ai_played   = False
    ai_move_san = None

    # AI's turn?
    ai_turn = (user_color == 'white' and board.turn == chess.BLACK) or \
              (user_color == 'black' and board.turn == chess.WHITE)

    if ai_turn and not board.is_game_over(claim_draw=True):
        engine_move = get_best_move(board, depth=4)
        if engine_move:
            ai_move_san = board.san(engine_move)
            move_history.append(ai_move_san)
            board.push(engine_move)
            ai_played = True
            request.session['board_fen']    = board.fen()
            request.session['move_history'] = move_history

    return JsonResponse({
        'success':          True,
        'board_fen':        board.fen(),
        'ai_played':        ai_played,
        'ai_move':          ai_move_san,
        'move_history':     move_history,
        'is_game_over':     board.is_game_over(claim_draw=True),
        'game_over_reason': _get_game_over_reason(board),
    })


def reset_game(request):
    # Session variables ko clear karke game restart karna
    request.session['board_fen'], request.session['move_history'] = 'start', []
    request.session['initial_fen'] = 'start'
    return redirect('/')


# ==========================================================
# PRIVATE HELPER: Game-over reason detect karna
# ==========================================================
def _get_game_over_reason(board):
    """Returns a human-readable reason string, or None if game is still in progress."""
    if not board.is_game_over(claim_draw=True):
        return None
    if board.is_checkmate():
        return 'Checkmate'
    if board.is_stalemate():
        return 'Stalemate'
    if board.is_insufficient_material():
        return 'Insufficient Material'
    if board.is_fivefold_repetition() or board.is_repetition(3):
        return 'Repetition'
    if board.is_seventyfive_moves() or board.is_fifty_moves():
        return 'Fifty-move rule'
    return 'Draw'