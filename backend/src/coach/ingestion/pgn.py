import io
import hashlib
from typing import Iterator, Tuple
import chess
import chess.pgn
from coach.schemas.models import Game, Source

def parse_pgn(pgn: str, source: Source, username: str) -> Game:
    """Parses a PGN string into a normalized Game model."""
    pgn_io = io.StringIO(pgn.strip())
    game_node = chess.pgn.read_game(pgn_io)
    if game_node is None:
        raise ValueError("Invalid PGN: Could not parse any chess game.")
    
    headers = game_node.headers
    white = headers.get("White", "Unknown")
    black = headers.get("Black", "Unknown")
    result = headers.get("Result", "*")
    
    # Parse ratings
    white_rating = None
    if "WhiteElo" in headers:
        try:
            white_rating = int(headers["WhiteElo"])
        except ValueError:
            pass
            
    black_rating = None
    if "BlackElo" in headers:
        try:
            black_rating = int(headers["BlackElo"])
        except ValueError:
            pass
            
    time_control = headers.get("TimeControl", None)
    opening_name = headers.get("Opening", None)
    
    # Infer user color
    user_color = "white"
    if black.lower() == username.lower():
        user_color = "black"
    elif white.lower() == username.lower():
        user_color = "white"
    else:
        # Default fallback
        user_color = "white"
        
    # Generate stable game_id if not present
    game_id = headers.get("Link") or headers.get("Site")
    if not game_id:
        # Hash the moves/pgn to get a unique identifier
        game_id = "uploaded_" + hashlib.md5(pgn.encode("utf-8")).hexdigest()[:12]
    else:
        # Clean URL if it's a link
        game_id = game_id.split("/")[-1]
        
    # Re-export clean PGN format
    exporter = chess.pgn.StringExporter(headers=True, comments=True, variations=True)
    clean_pgn = game_node.accept(exporter)
    
    return Game(
        game_id=game_id,
        source=source,
        pgn=clean_pgn,
        white=white,
        black=black,
        white_rating=white_rating,
        black_rating=black_rating,
        result=result,
        time_control=time_control,
        user_color=user_color,
        opening_name=opening_name
    )


def iter_positions(game: Game) -> Iterator[Tuple[int, chess.Board, chess.Move]]:
    """Yields (ply, board_before, move) for each move in the game."""
    pgn_io = io.StringIO(game.pgn)
    game_node = chess.pgn.read_game(pgn_io)
    if game_node is None:
        return
        
    board = game_node.board()
    for ply, move in enumerate(game_node.mainline_moves(), start=1):
        yield ply, board.copy(), move
        board.push(move)
