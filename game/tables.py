# game/tables.py
# Piece-Square Tables (PST): positional bonus/penalty for each square.
# Indexed from a8 (index 0) to h1 (index 63) for White.
# For Black pieces, the board is mirrored via chess.square_mirror().

PAWN_TABLE = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 40, 40, 20, 10, 10,
     5,  5, 10, 35, 35, 10,  5,  5,
     0,  0,  0, 30, 30,  0,  0,  0,
     5, -5,-10,  5,  5,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
]

KNIGHT_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

BISHOP_TABLE = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]

# Rooks love open files, connected rooks on the 7th rank, and central columns (d/e).
# Strong penalty for corner/edge trapping. Bonus for 7th rank invasion.
ROOK_TABLE = [
     0,  0,  5, 10, 10,  5,  0,  0,   # 8th rank: small bonus for d/e files
    10, 15, 15, 20, 20, 15, 15, 10,   # 7th rank: strong invasion bonus
     0,  0,  5, 10, 10,  5,  0,  0,
    -5,  0,  5, 10, 10,  5,  0, -5,
    -5,  0,  5, 10, 10,  5,  0, -5,
    -5,  0,  0,  5,  5,  0,  0, -5,
    -10, -5,  0,  0,  0,  0, -5,-10,  # 2nd rank: slightly passive
    -10,  0,  0,  5,  5,  0,  0,-10   # 1st rank: penalty for staying home
]

# Queens prefer eventual central control but are strongly penalised for
# developing too early (low-index = opponent's side = early aggression trap).
# Worst squares are the very early development squares (rows 5-6 from white's view).
QUEEN_TABLE = [
    -20,-10,-10, -5, -5,-10,-10,-20,   # 8th rank: fine for endgame centralisation
    -10,  0,  5,  0,  0,  0,  0,-10,
    -10,  5,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,   # 3rd rank: early exposure warning
    -30,-20,-10, -5, -5,-10,-20,-30    # 2nd rank: heavy penalty — stay home early!
]

# ==========================================================================
# KING SAFETY — two separate tables for middlegame vs endgame
# ==========================================================================

# MIDDLEGAME: King should hide in the corner after castling (g1/c1 for white).
# Strong penalties for marching forward into the open board.
KING_MG_TABLE = [
    -80,-70,-70,-70,-70,-70,-70,-80,   # opponent's back rank — disastrous
    -60,-60,-60,-60,-60,-60,-60,-60,
    -40,-50,-50,-60,-60,-50,-50,-40,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,-10,-10,  0, 20, 20,   # stay near castled g1/b1 corner
     30, 40, 20,  0,  0, 10, 40, 30    # g1 and b1 are safest castled squares
]

# ENDGAME: Queen has traded off, so the king must centralise and help pawns promote.
# Corners are now dangerous (can get mated or trapped); centre is king.
KING_EG_TABLE = [
    -50,-30,-20,-10,-10,-20,-30,-50,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -40,-30,-20,-10,-10,-20,-30,-40,
    -50,-40,-30,-20,-20,-30,-40,-50
]