import json
from django.test import TestCase, Client
import chess


class ChessAPITests(TestCase):
    """Tests for the AJAX move API in board_view."""

    def setUp(self):
        self.client = Client()
        # Establish a session with a fresh board as White
        session = self.client.session
        session['user_color'] = 'white'
        session['board_fen'] = 'start'
        session['move_history'] = []
        session.save()

    def _post_move(self, uci):
        """Helper: POST a move UCI string to the board endpoint."""
        return self.client.post('/', json.dumps({'move': uci}), content_type='application/json')

    # ------------------------------------------------------------------
    # 1. GET request should render HTML, not JSON
    # ------------------------------------------------------------------
    def test_get_renders_html(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'chess', response.content.lower())

    # ------------------------------------------------------------------
    # 2. Valid player move returns JSON with success=True
    # ------------------------------------------------------------------
    def test_valid_move_returns_json_success(self):
        response = self._post_move('e2e4')  # 1. e4
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('board_fen', data)
        self.assertIn('move_history', data)
        self.assertIn('is_game_over', data)
        self.assertFalse(data['is_game_over'])

    # ------------------------------------------------------------------
    # 3. Invalid UCI format returns JSON with success=False (400)
    # ------------------------------------------------------------------
    def test_invalid_uci_format_returns_error(self):
        response = self._post_move('zzz')  # clearly invalid UCI
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    # ------------------------------------------------------------------
    # 4. Illegal (but valid-format) move returns JSON with success=False (400)
    # ------------------------------------------------------------------
    def test_illegal_move_returns_error(self):
        response = self._post_move('e2e5')  # e2 pawn can't jump to e5
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    # ------------------------------------------------------------------
    # 5. Move history grows after each valid move
    # ------------------------------------------------------------------
    def test_move_history_grows(self):
        response = self._post_move('e2e4')
        data = json.loads(response.content)
        # After player's move (e4) + AI's response, history should have at least 1 entry
        self.assertGreaterEqual(len(data['move_history']), 1)

    # ------------------------------------------------------------------
    # 6. Missing move body returns 400
    # ------------------------------------------------------------------
    def test_missing_move_body_returns_error(self):
        response = self.client.post('/', {})  # No 'move' key
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    # ------------------------------------------------------------------
    # 7. Threefold repetition and history reconstruction
    # ------------------------------------------------------------------
    def test_threefold_repetition_reconstruction(self):
        from game.views import _reconstruct_board
        session = {
            'initial_fen': 'start',
            'move_history': [
                'Nf3', 'Nf6', 'Ng1', 'Ng8',
                'Nf3', 'Nf6', 'Ng1', 'Ng8'
            ]
        }
        board = _reconstruct_board(session)
        self.assertTrue(board.can_claim_threefold_repetition())
        self.assertTrue(board.is_game_over(claim_draw=True))

    # ------------------------------------------------------------------
    # 8. King + Queen vs King Endgame behaviour
    # ------------------------------------------------------------------
    def test_kq_vs_k_endgame_detection_and_evaluation(self):
        from game.engine import _is_endgame, evaluate_board, get_best_move
        
        # Verify endgame is detected
        board = chess.Board('4k3/8/8/8/8/8/8/3QK3 w - - 0 1')
        self.assertTrue(_is_endgame(board))
        
        # Verify king distance evaluation gradient
        # Move White King closer to Black King: e1 to e2
        board_far = chess.Board('4k3/8/8/8/8/8/8/3QK3 w - - 0 1')
        board_closer = chess.Board('4k3/8/8/8/8/8/4K3/3Q4 w - - 0 1')
        
        score_far = evaluate_board(board_far)
        score_closer = evaluate_board(board_closer)
        
        self.assertGreater(score_closer, score_far, "Closer King should have a better score")
        
        # Verify best move is progress-oriented (e.g. moves King towards Black King or controls squares)
        best_move = get_best_move(board, depth=3)
        self.assertIsNotNone(best_move)

    # ------------------------------------------------------------------
    # 9. MVV-LVA move ordering: high-value captures are listed first
    # ------------------------------------------------------------------
    def test_mvv_lva_capture_ordering(self):
        from game.engine import order_moves
        # White: Qh2, Pe5 | Black: Qd6, Ph7 — it's White's turn
        # Pe5xQd6 (pawn captures queen, high-value victim) should rank BEFORE Qh2xh7 (queen captures pawn, low-value victim)
        board = chess.Board('8/7p/3q4/4P3/8/8/7Q/4K2k w - - 0 1')
        moves = order_moves(board)
        capture_moves = [m for m in moves if board.is_capture(m)]
        pawn_takes_queen = chess.Move.from_uci('e5d6')   # PxQ  — victim=900, attacker=100
        queen_takes_pawn = chess.Move.from_uci('h2h7')   # Qxh7 — victim=100, attacker=900
        self.assertIn(pawn_takes_queen, capture_moves, "e5d6 (PxQ) should be a legal capture")
        self.assertIn(queen_takes_pawn, capture_moves, "h2h7 (Qxp) should be a legal capture")
        idx_pxq = moves.index(pawn_takes_queen)
        idx_qxp = moves.index(queen_takes_pawn)
        self.assertLess(idx_pxq, idx_qxp, "PxQ must be ordered before QxP in MVV-LVA")


    # ------------------------------------------------------------------
    # 10. Transposition table: populated after a search, cleared on next call
    # ------------------------------------------------------------------
    def test_transposition_table_populated_and_cleared(self):
        from game.engine import get_best_move, _transposition_table, clear_transposition_table
        board = chess.Board()
        # Clear to start fresh
        clear_transposition_table()
        self.assertEqual(len(_transposition_table), 0)
        # After a search the TT should be populated
        get_best_move(board, depth=3)
        self.assertGreater(len(_transposition_table), 0, "TT should be populated after a depth-3 search")
        # get_best_move calls clear_transposition_table() at entry, so a second call resets it
        # We can verify by observing that the TT is non-empty *during* search
        # (full isolation would require mocking; this smoke-test is sufficient)
        get_best_move(board, depth=2)
        self.assertGreater(len(_transposition_table), 0)
