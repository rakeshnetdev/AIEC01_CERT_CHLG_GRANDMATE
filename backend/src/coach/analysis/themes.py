import chess

def classify_theme(board: chess.Board, ply: int, moved_piece_square: chess.Square) -> str:
    """Classifies the theme of a move based on board state heuristics."""
    # 1. Opening: ply <= 12
    if ply <= 12:
        return "Opening"
        
    # 2. Pin: Check if the moved piece was pinned before moving
    # The side whose turn it is/was is board.turn.
    # Note: If this is called on board_before, board.turn is the active player.
    # If called on board_after, board.turn is the opponent.
    # To be safe, we check both the board's current turn and its inverse.
    # If the moved_piece_square had a pinned piece for the side whose king was targeted:
    if board.is_pinned(board.turn, moved_piece_square) or board.is_pinned(not board.turn, moved_piece_square):
        return "Pin"
        
    # 3. Check: If the current position has the side-to-move's king in check
    if board.is_check():
        return "Check"
        
    # 4. Endgame: If total non-pawn material is small
    material_count = 0
    for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
        material_count += len(board.pieces(piece_type, chess.WHITE))
        material_count += len(board.pieces(piece_type, chess.BLACK))
        
    if material_count <= 6:
        return "Endgame"
        
    # 5. Middlegame Tactics: Default
    return "Tactics"
