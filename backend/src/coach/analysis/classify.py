from typing import Tuple
from config.settings import Settings
from coach.schemas.models import Severity

def calculate_cpl_and_label(
    best_uci: str,
    played_uci: str,
    score_before: int,
    score_after: int,
    settings: Settings
) -> Tuple[int, Severity]:
    """Calculates the centipawn loss and assigns a severity label."""
    if best_uci == played_uci:
        return 0, "ok"
        
    S_best = score_before
    # Negate score_after because the opponent's POV turn flipped
    S_played = -score_after
    
    cpl = max(0, S_best - S_played)
    
    if cpl < settings.inaccuracy_cp:
        label: Severity = "ok"
    elif cpl < settings.mistake_cp:
        label = "inaccuracy"
    elif cpl < settings.blunder_cp:
        label = "mistake"
    else:
        label = "blunder"
        
    return cpl, label
