from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .base_model import BaseModel

@dataclass
class Answer(BaseModel):
    """
    Represents an answer in a MULTIPLE_CHOICE market.
    
    For cpmm-multi-1 markets:
    - Each answer effectively acts like a mini binary market.
    - The answer has its own YES/NO pools and probability.
    - Total liquidity is specific to this answer.
    
    For dpm-2 markets:
    - Answers have individual probabilities.
    - The 'pool' represents mana invested in this answer.
    """
    id: str
    index: int # Order of the answer, starting from 0
    contract_id: str  # Parent market ID
    created_time: int  # Unix timestamp ms
    user_id: str  # Creator of the answer
    text: str  # Text of the answer
    probability: float  # Current probability of this answer
    is_other: bool

    # Optional fields that might be present
    name: Optional[str] = None  # Display name of the answer creator
    username: Optional[str] = None  # Username of the answer creator
    volume: Optional[int] = None
    avatar_url: Optional[str] = None
    prob_changes: Optional[any] = None
    resolution: Optional[str] = None
    color: Optional[str] = None
    resolver_id: Optional[str] = None
    resolution_time: Optional[int] = None
    resolution_probability: Optional[float] = None
    text_fts: Optional[str] = None
    fs_updated_time: Optional[datetime] = None
    prob_change_day: Optional[float] = None
    prob_change_week: Optional[float] = None
    prob_change_month: Optional[float] = None
    midpoint: Optional[float] = None


    # Fields specific to cpmm-multi-1
    pool_yes: Optional[float] = field(default=None)  # Shares in YES pool for this answer
    pool_no: Optional[float] = field(default=None)  # Shares in NO pool for this answer
    total_liquidity: Optional[float] = field(default=None)  # Total liquidity for this answer
    subsidy_pool: Optional[float] = field(default=None)  # Liquidity subsidy for this answer

    # Field for dpm-2 style pool (mana invested in this answer)
    pool: Optional[float] = field(default=None)