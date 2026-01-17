from typing import Optional
from dataclasses import dataclass
from .base_model import BaseModel

@dataclass
class Comment(BaseModel):
    """Represents a Manifold comment."""
    
    id: str
    text: str
    user_id: str
    user_name: str
    contract_id: str
    visibility: str
    comment_type: str
    created_time: int
    contract_slug: str
    user_username: str
    user_avatar_url: str
    contract_question: str
    commenter_position_prob: float
    commenter_position_shares: float
    commenter_position_outcome: str
    likes: int
    dislikes: int

    # Optional fields
    bet_id: Optional[str] = None
    bet_amount: Optional[float] = None
    bet_outcome: Optional[str] = None
