import chess
from typing import Optional

def classify_theme(board: chess.Board, ply: int, moved_piece_square: chess.Square, move: Optional[chess.Move] = None) -> str:
    """Classifies the theme of a move based on board state heuristics."""
    # 1. Opening: ply <= 12
    if ply <= 12:
        return "Opening"
        
    # 2. En Passant
    if move and board.is_en_passant(move):
        return "En Passant"

    # 3. Double Check / Check
    if board.is_check():
        if len(board.checkers()) > 1:
            return "Double Check"
        return "Check"
        
    # 4. Promotion & Underpromotion
    if move and move.promotion is not None:
        if move.promotion == chess.QUEEN:
            return "Promotion"
        return "Underpromotion"

    # 5. Pin: Check if the moved piece was pinned before moving
    if board.is_pinned(board.turn, moved_piece_square) or board.is_pinned(not board.turn, moved_piece_square):
        return "Pin"
        
    # 6. Fork Heuristic:
    moved_piece = board.piece_at(moved_piece_square)
    if moved_piece:
        attacks = board.attacks(moved_piece_square)
        attacked_targets = []
        opponent_color = not moved_piece.color
        
        for sq in attacks:
            target_piece = board.piece_at(sq)
            if target_piece and target_piece.color == opponent_color:
                if target_piece.piece_type in [chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
                    attacked_targets.append(target_piece)
                    
        has_king = any(p.piece_type == chess.KING for p in attacked_targets)
        if (has_king and len(attacked_targets) >= 2) or (len(attacked_targets) >= 2):
            return "Fork"

    # 7. Endgame Check
    material_count = 0
    for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
        material_count += len(board.pieces(piece_type, chess.WHITE))
        material_count += len(board.pieces(piece_type, chess.BLACK))
        
    if material_count <= 6:
        return "Endgame"
        
    # 8. Middlegame Tactics Default
    return "Tactics"
