from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal, Any, Set, Optional
import math
from datetime import datetime, timedelta
from src.models import Bet, Market, Answer
from src.manifold_client import ManifoldClient
from config import APIConfig, BetConfig
from src.utils.market_utils import FLIP_OUTCOME, logit_change

import numpy as np
import re

# Decision type for qualification
Decision = Literal["PASS", "FAIL"]

@dataclass
class QualificationResult:
    """
    Represents the outcome of a single qualification check.
    """
    decision: Decision
    reason: str  # Describes why the decision was made, e.g., "NON_BINARY_MARKET", "LIQUIDITY_TOO_LOW"
    details: Any = None # Optional additional details

class BaseQualifier(ABC):
    """
    Abstract base class for a single bet qualification check.
    Each qualifier checks a specific condition of a bet, market, or related data.
    """
    def __init__(self, **kwargs):
        """
        Initializes the qualifier with any necessary parameters.
        Subclasses can override this to accept specific configurations.
        """
        pass

    @abstractmethod
    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        # Potentially other context like ManifoldClient if a check needs to make API calls
        **kwargs 
    ) -> QualificationResult:
        """
        Performs the qualification check.

        Args:
            bet: The bet being evaluated.
            market: The market associated with the bet.
            market_bets: A list of recent bets in the market.
            **kwargs: Additional context or parameters needed for the check.

        Returns:
            QualificationResult: The outcome of the check.
        """
        pass

class MarketTypeQualifier(BaseQualifier):
    """Checks if the market is a support market type."""
    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs
    ) -> QualificationResult:
        if market.outcome_type != 'BINARY' and market.outcome_type != 'MULTIPLE_CHOICE':
            return QualificationResult(
                decision="FAIL",
                reason="UNSUPPORTED_MARKET_TYPE",
                details={"outcome_type": market.outcome_type}
            )
        return QualificationResult(decision="PASS", reason="SUPPORTED_MARKET_TYPE")

class LiquidityProvisionQualifier(BaseQualifier):
    """Checks if the bet is a liquidity provision."""
    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs
    ) -> QualificationResult:
        if bet.is_liquidity_provision:
            return QualificationResult(
                decision="FAIL",
                reason="LIQUIDITY_PROVISION",
                details={"bet_id": bet.id}
            )
        return QualificationResult(decision="PASS", reason="NOT_LIQUIDITY_PROVISION")

class MarketLiquidityQualifier(BaseQualifier):
    """Checks if the market has sufficient liquidity."""
    def __init__(self, min_liquidity: float):
        self.min_liquidity = min_liquidity

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs
    ) -> QualificationResult:
        # For MULTIPLE_CHOICE markets, check liquidity of the specific answer
        if market.outcome_type == "MULTIPLE_CHOICE" and not market.should_answers_sum_to_one:
            if not bet.answer_id:
                return QualificationResult(
                    decision="FAIL",
                    reason="MISSING_ANSWER_ID",
                    details={"bet_id": bet.id}
                )
            
            liquidity = market.get_answer_liquidity(bet.answer_id)
            if liquidity is None or liquidity < self.min_liquidity:
                return QualificationResult(
                    decision="FAIL",
                    reason="LOW_ANSWER_LIQUIDITY",
                    details={
                        "answer_id": bet.answer_id,
                        "liquidity": liquidity,
                        "min_liquidity": self.min_liquidity
                    }
                )
        else:  # BINARY market or dependent market
            if market.total_liquidity < self.min_liquidity:
                return QualificationResult(
                    decision="FAIL",
                    reason="LOW_LIQUIDITY",
                    details={
                        "total_liquidity": market.total_liquidity,
                        "min_liquidity": self.min_liquidity
                    }
                )
        return QualificationResult(decision="PASS", reason="SUFFICIENT_LIQUIDITY")


class ExtremeMarketProbQualifier(BaseQualifier):
    """Fails markets where the probability is already near-certain."""

    def __init__(self, threshold_percent: int):
        self.threshold_percent = threshold_percent
        self.lower_bound = threshold_percent / 100
        self.upper_bound = 1 - self.lower_bound

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs,
    ) -> QualificationResult:
        if market.outcome_type == "MULTIPLE_CHOICE":
            if not bet.answer_id:
                return QualificationResult(
                    decision="FAIL",
                    reason="MISSING_ANSWER_ID",
                    details={"market_id": market.id},
                )
            prob = market.get_answer_probability(bet.answer_id)
        else:
            prob = market.probability

        if prob is None:
            return QualificationResult(
                decision="FAIL",
                reason="UNKNOWN_MARKET_PROBABILITY",
                details={"market_id": market.id, "answer_id": bet.answer_id},
            )

        if prob < self.lower_bound or prob > self.upper_bound:
            return QualificationResult(
                decision="FAIL",
                reason="EXTREME_MARKET_PROBABILITY",
                details={
                    "probability": prob,
                    "threshold_percent": self.threshold_percent,
                },
            )

        return QualificationResult(decision="PASS", reason="MARKET_PROBABILITY_WITHIN_RANGE")

class BetAmountQualifier(BaseQualifier):
    """Checks if the bet amount is sufficient."""
    def __init__(self, min_amount: float):
        self.min_amount = min_amount

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs
    ) -> QualificationResult:
        if abs(bet.amount) < self.min_amount:
            return QualificationResult(
                decision="FAIL",
                reason="SMALL_BET",
                details={
                    "bet_amount": bet.amount,
                    "min_amount": self.min_amount
                }
            )
        return QualificationResult(decision="PASS", reason="SUFFICIENT_BET_AMOUNT")
    
class CreatorIsBettorQualifier(BaseQualifier):
    """Checks if the bet is coming from the market creator"""
    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs
    ) -> QualificationResult:
        if bet.user_id == market.creator_id:
            return QualificationResult(
                decision="FAIL",
                reason="MARKET_CREATOR_IS_BETTOR",
                details={
                    "user_id": bet.user_id,
                }
            )
        
        if bet.answer_id is not None:
            answer = market.get_answer_by_id(bet.answer_id)
            if answer and bet.user_id == answer.user_id:
                return QualificationResult(
                decision="FAIL",
                reason="ANSWER_CREATOR_IS_BETTOR",
                details={
                    "user_id": bet.user_id,
                }
            )

        return QualificationResult(decision="PASS", reason="BETTOR_NOT_CREATOR")

class OverinvestedQualifier(BaseQualifier):
    """Checks if a bet would exceed the maximum position limit."""
    def __init__(self, max_position: float, invert_outcome: bool=False):
        self.max_position = max_position
        self.invert_outcome = invert_outcome

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        client: ManifoldClient,
        **kwargs
    ) -> QualificationResult:
        # Get current positions (filtered by answer_id if MULTIPLE_CHOICE)
        current_positions = await client.get_market_positions(
            market.id,
            user_id=APIConfig.USER_ID, # me
            answer_id=bet.answer_id
        )

        if not current_positions:
            return QualificationResult(decision="PASS", reason="NO_CURRENT_POSITION")

        position = current_positions[0]
        curr_position_dir = position['maxSharesOutcome']
        curr_prob = await client.get_market_probability(market.id, answer_id=bet.answer_id)

        if 'totalShares' not in position or curr_position_dir not in position['totalShares']:
            return QualificationResult(decision="PASS", reason="NO_CURRENT_POSITION")

        # Calculate current position value
        curr_position_value = position['totalShares'][curr_position_dir] * (curr_prob if curr_position_dir == 'YES' else (1-curr_prob))
        
        # Normally we assume we're counterbetting the incoming bet
        proposed_bet_outcome = FLIP_OUTCOME[bet.outcome]
        if self.invert_outcome:
            proposed_bet_outcome = FLIP_OUTCOME[proposed_bet_outcome]

        # If we're profitable, keeping going (to a point)
        if 'profit' in position:
            profit_adjusted_max_position = max(self.max_position * min(1 + position['profit'] / self.max_position, 2), self.max_position / 5)
        else:
            profit_adjusted_max_position = self.max_position

        # If would be betting in same direction as current position
        if curr_position_dir == proposed_bet_outcome and curr_position_value >= profit_adjusted_max_position:
            return QualificationResult(
                decision="FAIL",
                reason="MAX_POSITION_EXCEEDED",
                details={
                    "current_position": curr_position_value,
                    "max_position": self.max_position
                }
            )

        return QualificationResult(decision="PASS", reason="POSITION_WITHIN_LIMITS")
    
    
class NoBotsQualifier(BaseQualifier):
    """Checks if the bet is from the API"""
    def __init__(self):
        pass

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        client: ManifoldClient,
        **kwargs
    ) -> QualificationResult:
        if bet.is_api:
            return QualificationResult(
                    decision="FAIL",
                    reason="API_BET",
                    details={}
                )

        return QualificationResult(decision="PASS", reason="NOT_API_BET")


class NoSellsQualifier(BaseQualifier):
    """Checks if the bet is a sell order, which there's a lot of bugs for"""
    def __init__(self):
        pass

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        client: ManifoldClient,
        **kwargs
    ) -> QualificationResult:
        if bet.amount < 0:
            return QualificationResult(
                    decision="FAIL",
                    reason="SKIPPING_SELL_BET",
                    details={
                        "amount": bet.amount,
                    }
                )

        return QualificationResult(decision="PASS", reason="NOT_SELL")


class NoBetsOnOwnMarketsQualifier(BaseQualifier):
    """Fail when the market was created by this bot's owner."""

    def __init__(self):
        pass

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        client: ManifoldClient,
        **kwargs,
    ) -> QualificationResult:
        if market.creator_id == BetConfig.SELF_ID:
            return QualificationResult(
                decision="FAIL",
                reason="SELF_CREATED_MARKET",
                details={"question": market.question},
            )

        return QualificationResult(decision="PASS", reason="NOT_OWN_MARKET")


class OtherQualifier(BaseQualifier):
    """Fail when betting on an 'Other' answer in MULTIPLE_CHOICE markets."""

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs,
    ) -> QualificationResult:
        if not bet.answer_id:
            return QualificationResult(decision="PASS", reason="NOT_MULTICHOICE")

        answer = market.get_answer_by_id(bet.answer_id)
        if not answer or not answer.text:
            return QualificationResult(decision="PASS", reason="NO_ANSWER_TEXT")

        if answer.text.strip().lower() == "other":
            return QualificationResult(
                decision="FAIL",
                reason="OTHER_ANSWER",
                details={"answer_id": bet.answer_id},
            )

        return QualificationResult(decision="PASS", reason="ANSWER_NOT_OTHER")


class OptOutQualifier(BaseQualifier):
    """Fail when the market description contains an explicit no-bot opt-out tag."""

    TAG = "#no-bots"

    async def qualify(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs,
    ) -> QualificationResult:
        description_text = self._description_text(market.description).lower()
        if self.TAG in description_text:
            return QualificationResult(
                decision="FAIL",
                reason="MARKET_OPTED_OUT",
                details={"tag": self.TAG},
            )

        return QualificationResult(decision="PASS", reason="MARKET_HAS_NOT_OPTED_OUT")

    def _description_text(self, description) -> str:
        if not description:
            return ""
        if isinstance(description, str):
            return description
        return self._extract_text(description)

    def _extract_text(self, node) -> str:
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return "".join(self._extract_text(child) for child in node if child is not None)
        if isinstance(node, dict):
            text_parts = []
            text_value = node.get("text")
            if isinstance(text_value, str):
                text_parts.append(text_value)
            content = node.get("content")
            if isinstance(content, list):
                for child in content:
                    text_parts.append(self._extract_text(child))
            return "".join(text_parts)
        return ""
