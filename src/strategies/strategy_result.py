from dataclasses import dataclass
from typing import Optional, List
from src.models import ProposedBet
from src.logger import StratLogEvent

@dataclass
class StrategyResult:
    """Represents the outcome of a strategy evaluation.

    Exactly one of ``bets`` or ``event`` should be provided.
    """
    bets: Optional[List[ProposedBet]] = None
    event: Optional[StratLogEvent] = None
    strategy: Optional[str] = None
