from django.shortcuts import render
import chess
import chess.svg

def board_view(request):
    # Initialize a standard chess board
    board = chess.Board()
    
    # Generate the SVG image of the board
    board_svg = chess.svg.board(board=board, size=400)
    
    return render(request, 'game/board.html', {'board_svg': board_svg})