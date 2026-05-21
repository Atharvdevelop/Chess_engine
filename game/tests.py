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
        return self.client.post('/', {'move': uci})

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

