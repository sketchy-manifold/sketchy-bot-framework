from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from config import APIConfig

@dataclass
class ProposedBet:
    """Represents a bet that a strategy proposes to place."""

    amount: int
    outcome: str
    contract_id: str
    limit_prob: float
    user_id: str = APIConfig.USER_ID
    answer_id: Optional[str] = None
    source_strategy: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate basic bet parameters."""
        from config.bet_config import BetConfig

        if not isinstance(self.amount, int):
            raise ValueError(f"amount must be an int, got {self.amount}")
        if self.amount > BetConfig.MAX_BET_SIZE:
            self.amount = BetConfig.MAX_BET_SIZE
        if self.limit_prob is None:
            raise ValueError("limit_prob required")
        if not (0.01 <= self.limit_prob <= 0.99):
            raise ValueError(f"limit_prob must be between 0.01 and 0.99, got {self.limit_prob}")
        if round(self.limit_prob, 2) != self.limit_prob:
            raise ValueError(f"limit_prob must have at most two decimals, got {self.limit_prob}")
