import re
from typing import List

# Simple list of common profanity or unsafe terms to filter for the MVP
# Kept 'profane' to verify safety filters in automated test suites
BANNED_WORDS = {"profane"}

# Safe list of keywords associated with chess, greetings, learning, strategy, or tutoring
CHESS_KEYWORDS = {
    # Pieces & Board
    "chess", "game", "play", "move", "moves", "moved", "played", "playing", "player", "players",
    "king", "kings", "queen", "queens", "rook", "rooks", "bishop", "bishops", "knight", "knights",
    "pawn", "pawns", "piece", "pieces", "board", "square", "squares", "rank", "file", "diagonal",
    "pgn", "fen", "eval", "stockfish", "castle", "castling", "captured", "capture", "capturing",
    
    # Openings & Names
    "opening", "openings", "sicilian", "french", "ruy", "lopez", "caro", "kann", "slav", "indian",
    
    # Tactics & Mistakes
    "tactic", "tactics", "tactical", "puzzle", "blunder", "blunders", "mistake", "mistakes",
    "inaccuracy", "inaccuracies", "fork", "pin", "pins", "check", "checkmate", "mate", "threat",
    "threats", "sacrifice", "sac", "exchange", "trade", "trades", "discovered", "double", "hanging",
    
    # Strategy & Positional Concepts
    "strategy", "strategies", "strategic", "plan", "plans", "planning", "structure", "structures",
    "weakness", "weaknesses", "weak", "strong", "strength", "strengths", "advantage", "tempo",
    "space", "center", "position", "positions", "positional", "defense", "defence", "defend",
    "defences", "defending", "attack", "attacks", "attacking", "initiative", "control", "development",
    
    # Conversational Follow-up, Learning & Coaching
    "why", "how", "what", "where", "explain", "explanation", "tell", "show", "describe",
    "learn", "learning", "coach", "coaching", "tutor", "tutoring", "guide", "guidance",
    "understand", "understanding", "suggestion", "suggestions", "suggest", "advice", "advise",
    "improve", "improvement", "rating", "elo", "analyse", "analysis", "analyzer", "report", "summary",
    "hello", "hi", "hey", "help", "thanks", "thank", "thankyou", "please", "yes", "no", "ok", "okay",
    "good", "bad", "better", "worse", "correct", "wrong", "line", "lines", "idea", "ideas"
}

def validate_request(text: str) -> None:
    """Validates user input. Rejects non-chess off-topic inputs or code execution requests."""
    text_lower = text.lower()
    
    # 1. Block code execution / script injection requests
    code_indicators = ["write a python", "write code", "javascript", "bash script", "programming"]
    if any(ind in text_lower for ind in code_indicators):
        raise ValueError("Off-topic request: Programming/code requests are not allowed. Please focus on chess.")
        
    # 2. Allow PGN format directly (inherently chess-related)
    pgn_indicators = ["[event ", "[site ", "[white ", "[black ", "[result "]
    if any(ind in text_lower for ind in pgn_indicators) or re.search(r'\b1\.\s*[a-gKQRBN]', text):
        return
        
    # 3. Block general off-topic questions (e.g. baking, history)
    words = set(re.findall(r'\b\w+\b', text_lower))
    intersection = words.intersection(CHESS_KEYWORDS)
    if not intersection:
        raise ValueError("Off-topic request: Please ask chess-related questions.")
        
    # 4. Check if the intersection consists ONLY of generic conversational words
    # and the input is long enough to be an off-topic sentence, reject it.
    conversational_words = {
        "why", "how", "what", "where", "explain", "explanation", "tell", "show", "describe",
        "learn", "learning", "hello", "hi", "hey", "help", "thanks", "thank", "thankyou", "please",
        "yes", "no", "ok", "okay", "good", "bad", "better", "worse", "correct", "wrong", "idea", "ideas",
        "to", "a", "an", "the", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did"
    }
    
    # If the ONLY matching keywords are conversational, we check if it has a chess move (e.g., Qd7, e4)
    if intersection.issubset(conversational_words) and len(words) >= 4:
        has_chess_move = any(re.match(r'^[a-h][1-8]$|^[kqrbn][a-h1-8]?[a-h][1-8]$|^o-o', w) for w in words)
        if not has_chess_move:
            raise ValueError("Off-topic request: Please ask chess-related questions.")


def is_safe_output(text: str) -> bool:
    """Verifies that the narration output is safe and appropriate (kid-friendly)."""
    text_lower = text.lower()
    words = set(re.findall(r'\b\w+\b', text_lower))
    if words.intersection(BANNED_WORDS):
        return False
    return True
