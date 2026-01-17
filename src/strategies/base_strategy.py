from abc import ABC, abstractmethod
from typing import List, Optional
from src.models import Bet, Market
from src.qualifiers.qualifiers import (
    BaseQualifier,
    QualificationResult,
    NoBetsOnOwnMarketsQualifier,
    NoSellsQualifier,
    MarketTypeQualifier,
    LiquidityProvisionQualifier,
    NoBotsQualifier,
    CreatorIsBettorQualifier,
    OptOutQualifier,
)
from src.manifold_client import ManifoldClient
from src.logger import QualificationFailEvent, LogEvent
from .strategy_result import StrategyResult

class BaseTradingStrategy(ABC):
    """
    Abstract base class for a trading strategy.
    A strategy consists of a set of qualifiers and betting logic.
    Subclasses must implement the 'qualifiers' property to define their list of qualifiers.
    """

    #: Qualifiers that are run for every strategy prior to strategy-specific ones
    BASE_QUALIFIERS: List[BaseQualifier] = [
        MarketTypeQualifier(),
        NoBetsOnOwnMarketsQualifier(),
        NoBotsQualifier(),
        NoSellsQualifier(),
        CreatorIsBettorQualifier(),
        OptOutQualifier(),
        LiquidityProvisionQualifier(),
    ]

    @property
    def base_qualifiers(self) -> List[BaseQualifier]:
        """Return qualifiers that apply to all strategies."""
        return self.BASE_QUALIFIERS

    @property
    @abstractmethod
    def qualifiers(self) -> List[BaseQualifier]:
        """
        A list of BaseQualifier instances that should be run before proposing a bet.
        This should be implemented by subclasses.
        Example:
            _my_qualifiers = [MarketTypeQualifier(), LiquidityQualifier(min_liquidity=100)]

            @property
            def qualifiers(self) -> List[BaseQualifier]:
                return self._my_qualifiers
        """
        pass

    def __init__(self, client: ManifoldClient):
        """
        Initializes the trading strategy.

        Args:
            client: The Manifold API client.
        """
        self.client = client

    async def _run_qualifiers(
        self,
        bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs
    ) -> Optional[QualificationResult]:
        """
        Runs all configured qualifiers for the given bet and market context.

        Returns:
            Optional[LogEvent]: Log event for the first failing qualifier, or None if all pass.
        """
        for qualifier_instance in self.base_qualifiers + self.qualifiers:
            result = await qualifier_instance.qualify(
                bet,
                market,
                market_bets,
                client=self.client,
                **kwargs
            )
            if result.decision == "FAIL":
                return result
                
        return None

    @abstractmethod
    async def propose_bet(
        self,
        triggering_bet: Bet,  # The bet that triggered this strategy evaluation
        market: Market,
        market_bets: List[Bet]
    ) -> StrategyResult:
        """
        Evaluates the market conditions and proposes a bet based on the strategy's logic.
        This method is called only if all qualifiers pass.

        Args:
            triggering_bet: The incoming bet that initiated the evaluation.
            market: The market in which the triggering_bet occurred.
            market_bets: A list of recent bets in the market.

        Returns:
            StrategyResult: Result representing proposed trades or a a log event
        """
        pass

    async def evaluate_and_propose(
        self,
        triggering_bets: List[Bet],
        market: Market,
        market_bets: List[Bet],
        **kwargs
    ) -> StrategyResult:
        """
        First runs qualifiers, then if all pass, runs the strategy's bet proposal logic.
        """
        # Validate inputs (basic check, can be expanded)
        if not triggering_bets or len(triggering_bets) == 0 or not market:
            return None
        
        # We only care about the first bet, regardless of market type
        triggering_bet = triggering_bets[0]

        # Run qualifiers
        fail_result = await self._run_qualifiers(triggering_bet, market, market_bets, **kwargs)
        if fail_result:
            event = QualificationFailEvent.from_bet(
                    triggering_bet,
                    market,
                    fail_result.reason,
                    metadata=str(fail_result.details),
                )
            event.strategy = type(self).__name__
            return StrategyResult(event=event)

        # If all qualifiers passed, proceed to propose a bet
        result =  await self.propose_bet(triggering_bet, market, market_bets, **kwargs)
        result.strategy = type(self).__name__
        if result.bets:
            for b in result.bets:
                b.source_strategy = type(self).__name__
        if result.event:
            result.event.strategy = type(self).__name__

        return result
