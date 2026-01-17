from dataclasses import dataclass
from typing import Optional, List, Tuple

@dataclass
class ArbitragePair:
    """
    Represents a pair of markets that can be arbitraged against each other.
    
    For binary markets:
    - If inverted=False: market1 YES = market2 YES
    - If inverted=True: market1 YES = market2 NO
    
    For multiple choice markets:
    - answer_pairs maps equivalent answers between markets
    - inverted applies to each answer pair
    """
    market1_id: str
    market2_id: str
    inverted: bool  # If True, market2's YES is equivalent to market1's NO
    min_spread: float  # Minimum price difference to trigger arbitrage (e.g. 0.02 for 2%)
    margin: float  # How much of the spread to capture (e.g. 0.5 for 50%)
    max_position: float  # Maximum position size in M$
    # For MULTIPLE_CHOICE markets:
    answer_pairs: Optional[List[Tuple[str, str]]] = None  # [(market1_answer_id, market2_answer_id)]

    def __post_init__(self):
        # Validate inputs
        if not 0 < self.min_spread < 1:
            raise ValueError("min_spread must be between 0 and 1")
        if not 0 < self.margin < 1:
            raise ValueError("margin must be between 0 and 1")
        if self.max_position <= 0:
            raise ValueError("max_position must be positive")
        
    def get_paired_answer(self, market_id: str, answer_id: str) -> Optional[str]:
        """Get the corresponding answer_id in the other market."""
        if not self.answer_pairs:
            return None
            
        for m1_aid, m2_aid in self.answer_pairs:
            if market_id == self.market1_id and answer_id == m1_aid:
                return m2_aid
            if market_id == self.market2_id and answer_id == m2_aid:
                return m1_aid
        return None

    def contains_market(self, market_id: str) -> bool:
        """Check if this pair contains the given market."""
        return market_id in (self.market1_id, self.market2_id)

    def get_other_market_id(self, market_id: str) -> Optional[str]:
        """Get the ID of the other market in the pair."""
        if market_id == self.market1_id:
            return self.market2_id
        if market_id == self.market2_id:
            return self.market1_id
        return None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            market1_id=data["market1_id"],
            market2_id=data["market2_id"],
            inverted=data["inverted"],
            min_spread=data["min_spread"],
            margin=data["margin"],
            max_position=data["max_position"],
            answer_pairs=data["answer_pairs"],
        )