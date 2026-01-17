from typing import List, Optional
from config import BetConfig, APIConfig
from src.models import Bet, Market
import math

FLIP_OUTCOME = {"YES": "NO", "NO": "YES"}

def get_moving_average_market_val(
    bets: List[Bet],
    window_size: int = 25,
    answer_id: Optional[str] = None,
) -> float:
    """Calculate the moving average of market values based on historical bets."""
    if answer_id:
        bets = [bet for bet in bets if bet.answer_id == answer_id]

    bets = [bet for bet in bets if bet.user_id != APIConfig.USER_ID]
    sorted_bets = sorted(bets, key=lambda bet: bet.created_time)
    recent_bets = sorted_bets[-window_size:]
    if not recent_bets:
        return 0.0
    moving_average = sum(bet.prob_after for bet in recent_bets) / len(recent_bets)
    return max(0.0, min(1.0, moving_average))

def logit(p: float):
    return math.log(p / (1-p))

def inv_logit(logit: float):
    return 1 / (1 + math.exp(-logit))

def logit_change(p1, p2) -> float:
    return abs(logit(p1) - logit(p2))

def logit_reversion(
    prob_before: float, 
    prob_after: float, 
    reversion_factor: float
) -> float:
    logit_after = logit(prob_after)
    logit_before = logit(prob_before)
    logit_diff = logit_after - logit_before

    # Revert 1/3 of the user's move (in logit space)
    logit_target = logit_after - logit_diff * reversion_factor
    return inv_logit(logit_target)