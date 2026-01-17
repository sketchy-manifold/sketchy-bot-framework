from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from .base_model import BaseModel
from config import APIConfig

@dataclass
class Bet(BaseModel):
    """Represents a Manifold bet."""
    
    # Required fields
    amount: float
    shares: float
    outcome: str  # "YES" or "NO" (even for MULTIPLE_CHOICE, represents buying or selling shares of that answer)
    contract_id: str  # Parent market ID
    created_time: datetime
    
    id: Optional[str] = None  # pseudo-optional, sometimes passed in as bet_id
    user_id: Optional[str] = None

    # Multiple choice specific fields
    answer_id: Optional[str] = None  # The specific answer being bet on in a MULTIPLE_CHOICE market

    # Optional fields
    bet_group_id: Optional[str] = None
    order_amount: Optional[float] = None
    limit_prob: Optional[float] = None
    is_cancelled: Optional[bool] = None
    is_filled: Optional[bool] = None
    fills: Optional[List[Dict]] = None
    prob_before: Optional[float] = None  # For MULTIPLE_CHOICE, this is the probability of the specific answer
    prob_after: Optional[float] = None   # For MULTIPLE_CHOICE, this is the probability of the specific answer
    is_api: Optional[bool] = None
    is_redemption: Optional[bool] = None
    visibility: Optional[str] = None
    expires_at: Optional[datetime] = None
    bet_id: Optional[str] = None
    updated_time: Optional[datetime] = None
    fees: Optional[Dict[str, float]] = None
    silent: Optional[bool] = None
    reply_to_comment_id: Optional[str] = None
    is_ante: Optional[bool] = None
    loan_amount: Optional[float] = None
    user_name: Optional[str] = None
    user_username: Optional[str] = None
    user_avatar_url: Optional[str] = None
    dpm_shares: Optional[float] = None
    dpm_weight: Optional[float] = None
    is_challenge: Optional[bool] = None
    prob_average: Optional[float] = None
    sale: Optional[bool] = None
    is_sold: Optional[bool] = None
    comment: Optional[Dict[str, Any]] = None
    source_strategy: Optional[str] = None
    is_liquidity_provision: bool = False
    is_interest_claim: Optional[bool] = False

    def __str__(self):
        base = f"amount={self.amount}, outcome={self.outcome}, probBefore={round(self.prob_before * 100, 1)}, probAfter={round(self.prob_after * 100, 2)}, contract_id={self.contract_id}, user_id={self.user_id}"
        if self.answer_id:
            base += f", answer_id={self.answer_id}"
        return base
    
    def __post_init__(self):
        if self.id is None and self.bet_id is not None:
            self.id = self.bet_id