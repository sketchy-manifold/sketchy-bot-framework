from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from .base_model import BaseModel
from .answer import Answer

@dataclass
class Market(BaseModel):
    """Represents a Manifold market."""
    
    # Required fields
    id: str
    creator_id: str
    question: str
    created_time: datetime
    volume: float
    mechanism: str  # 'cpmm-1', 'cpmm-multi-1', or 'dpm-2'
    outcome_type: str  # 'BINARY', 'MULTIPLE_CHOICE', etc.
    is_resolved: bool
    
    # Optional fields
    min: Optional[float] = None
    max: Optional[float] = None
    value: Optional[str] = None
    sibling_contract_id: Optional[str] = None
    resolver_id: Optional[str] = None
    close_time: Optional[datetime] = None
    token: Optional[str] = None
    last_comment_time: Optional[datetime] = None
    description: Optional[str] = None
    text_description: Optional[str] = None
    cover_image_url: Optional[str] = None
    group_slugs: Optional[List[str]] = None
    creator_username: Optional[str] = None
    creator_avatar_url: Optional[str] = None
    creator_name: Optional[str] = None
    creator_bio: Optional[str] = None
    creator_website: Optional[str] = None
    creator_banner_url: Optional[str] = None
    creator_discord_handle: Optional[str] = None
    creator_twitter_handle: Optional[str] = None
    creator_balance: Optional[float] = None
    creator_total_deposited: Optional[float] = None
    creator_total_withdrawn: Optional[float] = None
    creator_total_profit: Optional[float] = None
    creator_total_trades: Optional[int] = None
    creator_total_profit_percentage: Optional[float] = None
    creator_total_profit_percentage_rank: Optional[int] = None
    creator_total_profit_rank: Optional[int] = None
    creator_total_trades_rank: Optional[int] = None
    creator_total_deposited_rank: Optional[int] = None
    creator_total_withdrawn_rank: Optional[int] = None
    
    # Resolution related fields
    resolution: Optional[str] = None
    resolution_time: Optional[datetime] = None
    resolution_probability: Optional[float] = None
    
    # Pool and probability related fields
    pool: Optional[Dict[str, Any]] = None  # For MULTIPLE_CHOICE: Dict[answerId, float] or Dict[answerId, Dict[outcome, float]]
    probability: Optional[float] = None  # For BINARY only
    p: Optional[float] = None  # For CPMM markets
    
    # Multiple choice specific fields
    answers: Optional[List[Answer]] = None  # List of Answer objects for MULTIPLE_CHOICE markets
    should_answers_sum_to_one: Optional[bool] = None  # Whether answers are dependent
    add_answers_mode: Optional[str] = None  # 'ANYONE', 'ONLY_CREATOR', or 'DISABLED'
    
    # Timestamps
    last_bet_time: Optional[datetime] = None
    last_updated_time: Optional[datetime] = None
    
    # Other optional fields
    slug: Optional[str] = None
    url: Optional[str] = None
    total_liquidity: Optional[float] = None  # For BINARY markets
    volume24_hours: Optional[float] = None
    unique_bettor_count: Optional[int] = None
    is_cancelled: Optional[bool] = None
    is_favorited: Optional[bool] = None
    is_scheduled: Optional[bool] = None
    is_disputed: Optional[bool] = None
    is_sold_out: Optional[bool] = None
    is_active: Optional[bool] = None
    is_stonk: Optional[bool] = None
    is_binary: Optional[bool] = None
    is_numeric: Optional[bool] = None
    is_free_response: Optional[bool] = None
    is_multiple_choice: Optional[bool] = None
    is_range: Optional[bool] = None
    is_moneyline: Optional[bool] = None
    is_pool: Optional[bool] = None
    is_log_scale: Optional[bool] = None

    # Liquidity pool fields
    is_liquidity_pool: Optional[bool] = None
    is_liquidity_pool_v2: Optional[bool] = None
    is_liquidity_pool_v3: Optional[bool] = None
    is_liquidity_pool_v4: Optional[bool] = None
    is_liquidity_pool_v5: Optional[bool] = None
    is_liquidity_pool_v6: Optional[bool] = None
    is_liquidity_pool_v7: Optional[bool] = None
    is_liquidity_pool_v8: Optional[bool] = None
    is_liquidity_pool_v9: Optional[bool] = None
    is_liquidity_pool_v10: Optional[bool] = None

    def __str__(self):
        if self.outcome_type == "MULTIPLE_CHOICE":
            answer_count = len(self.answers) if self.answers else 0
            return f"question={self.question}, type=MULTIPLE_CHOICE, answers={answer_count}, slug={self.slug}, url={self.url}"
        return f"question={self.question}, prob={self.probability}, slug={self.slug}, url={self.url}"

    @classmethod
    def from_dict(cls, data: dict):
        """Convert API response to Market object."""
        # Handle answers for MULTIPLE_CHOICE markets
        if 'answers' in data and data['answers'] is not None:
            data['answers'] = [Answer.from_dict(ans) for ans in data['answers']]
        return super().from_dict(data)

    def get_answer_by_id(self, answer_id: str) -> Optional[Answer]:
        """Get an answer by its ID."""
        if self.answers:
            for answer in self.answers:
                if answer.id == answer_id:
                    return answer
        return None

    def get_answer_probability(self, answer_id: str) -> Optional[float]:
        """Get the probability for a specific answer."""
        if self.outcome_type != "MULTIPLE_CHOICE":
            return None

        # First check the answer object itself
        answer = self.get_answer_by_id(answer_id)
        if answer and answer.probability is not None:
            return answer.probability

        # For cpmm-multi-1, probability might be in the pool data
        if isinstance(self.pool, dict) and answer_id in self.pool:
            pool_data = self.pool[answer_id]
            if isinstance(pool_data, dict) and 'probability' in pool_data:
                return pool_data['probability']

        return None

    def get_answer_liquidity(self, answer_id: str) -> Optional[float]:
        """Get the liquidity for a specific answer."""
        if self.outcome_type != "MULTIPLE_CHOICE":
            return None

        # First check the answer object itself
        answer = self.get_answer_by_id(answer_id)
        if answer:
            if answer.total_liquidity is not None:
                return answer.total_liquidity
            if answer.pool is not None:  # For dpm-2
                return answer.pool

        # For cpmm-multi-1, liquidity might be in the pool data
        if isinstance(self.pool, dict) and answer_id in self.pool:
            pool_data = self.pool[answer_id]
            if isinstance(pool_data, (int, float)):  # Direct liquidity value
                return float(pool_data)
            if isinstance(pool_data, dict):
                # If it has YES/NO pools, sum them
                if 'YES' in pool_data and 'NO' in pool_data:
                    return float(pool_data['YES']) + float(pool_data['NO'])
                # If it has a total_liquidity field
                if 'total_liquidity' in pool_data:
                    return float(pool_data['total_liquidity'])

        return None
    
    def get_liquidity(self, answer_id: Optional[str] = None) -> Optional[float]:
        """Get the liquidity for a specific market, or answer on market"""
        assert(answer_id is None or self.outcome_type == 'MULTIPLE_CHOICE')

        if answer_id:
            return self.get_answer_liquidity(answer_id)
        else:
            return self.total_liquidity