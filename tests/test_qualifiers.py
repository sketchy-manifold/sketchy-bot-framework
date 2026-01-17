# Read tests/knowledge.md in this directory for how to run tests.
import sys
import unittest
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

# Ensure the src package is importable when tests are run directly
ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_PATH))

from src.qualifiers.qualifiers import (
    MarketTypeQualifier,
    LiquidityProvisionQualifier,
    MarketLiquidityQualifier,
    BetAmountQualifier,
    ProbabilityChangeQualifier,
    CreatorIsBettorQualifier,
    SmartUserQualifier,
    ProfitableUserQualifier,
    OverinvestedQualifier,
    RecentlyCounterbetUserQualifier,
    NoBotsQualifier,
    CanTakeProfitQualifier,
    NoSellsQualifier,
    NoBetsOnOwnMarketsQualifier,
    AnswerMentionsCurrentDayQualifier,
)
from src.qualifiers.arbitrage_qualifiers import ArbitrageableMarketQualifier
from src.models.arbitrage_pair import ArbitragePair
from src.models import Bet, Market, Answer, User, PortfolioMetrics
from config import BetConfig


class QualifierTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now()
        self.market_binary = Market(
            id="m1",
            creator_id="u1",
            question="Binary?",
            created_time=self.now - timedelta(days=10),
            volume=1000.0,
            mechanism="cpmm-1",
            outcome_type="BINARY",
            is_resolved=False,
            total_liquidity=150.0,
        )
        self.market_multi = Market(
            id="m2",
            creator_id="u1",
            question="Multi?",
            created_time=self.now - timedelta(days=5),
            volume=1000.0,
            mechanism="cpmm-multi-1",
            outcome_type="MULTIPLE_CHOICE",
            is_resolved=False,
            should_answers_sum_to_one=False,
            answers=[
                Answer(
                    id="a1",
                    index=0,
                    contract_id="m2",
                    created_time=int(self.now.timestamp() * 1000),
                    user_id="u2",
                    text="A1",
                    probability=0.5,
                    is_other=False,
                    total_liquidity=40.0,
                ),
                Answer(
                    id="a2",
                    index=1,
                    contract_id="m2",
                    created_time=int(self.now.timestamp() * 1000),
                    user_id="u3",
                    text="A2",
                    probability=0.5,
                    is_other=False,
                    total_liquidity=60.0,
                ),
            ],
        )

        self.bet_binary = Bet(
            amount=50.0,
            shares=20.0,
            outcome="YES",
            contract_id="m1",
            created_time=self.now,
            prob_before=0.4,
            prob_after=0.5,
            user_id="u2",
        )
        self.bet_multi = Bet(
            amount=30.0,
            shares=10.0,
            outcome="YES",
            contract_id="m2",
            answer_id="a1",
            created_time=self.now,
            prob_before=0.4,
            prob_after=0.5,
            user_id="u4",
        )

        self.mock_client = MagicMock()
        async_methods = [
            'get_market_probability', 'get_market_positions',
            'get_user_by_id', 'get_user_portfolio_history', 'get_market'
        ]
        for method in async_methods:
            setattr(self.mock_client, method, AsyncMock())
        self.mock_client.get_market_probability.return_value = 0.7
        self.mock_client.get_market_positions.return_value = [
            {
                "maxSharesOutcome": "YES",
                "totalShares": {"YES": 100.0},
                "profitPercent": 50,
            }
        ]
        self.mock_client.get_market.return_value = self.market_binary
        user = User(id="u4", username="tester", name="Tester", avatar_url="", created_time=self.now - timedelta(days=60))
        self.mock_client.get_user_by_id.return_value = user
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=0,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
            profit=10,
        )
        self.mock_client.get_user_portfolio_history.return_value = [metrics]

    def test_market_type(self):
        q = MarketTypeQualifier()
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, []))
        self.assertEqual(res.decision, "PASS")
        bad_market = self.market_binary
        bad_market.outcome_type = "FREE_RESPONSE"
        res = asyncio.run(q.qualify(self.bet_binary, bad_market, []))
        self.assertEqual(res.decision, "FAIL")

    def test_liquidity_provision(self):
        q = LiquidityProvisionQualifier()
        bet = self.bet_binary
        bet.is_liquidity_provision = True
        res = asyncio.run(q.qualify(bet, self.market_binary, []))
        self.assertEqual(res.decision, "FAIL")
        bet.is_liquidity_provision = False
        res = asyncio.run(q.qualify(bet, self.market_binary, []))
        self.assertEqual(res.decision, "PASS")

    def test_market_liquidity_binary(self):
        q = MarketLiquidityQualifier(min_liquidity=200)
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, []))
        self.assertEqual(res.decision, "FAIL")
        self.market_binary.total_liquidity = 250
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, []))
        self.assertEqual(res.decision, "PASS")

    def test_market_liquidity_multiple_choice(self):
        q = MarketLiquidityQualifier(min_liquidity=30)
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, []))
        self.assertEqual(res.decision, "PASS")
        self.market_multi.answers[0].total_liquidity = 10
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, []))
        self.assertEqual(res.decision, "FAIL")

    def test_bet_amount(self):
        q = BetAmountQualifier(min_amount=40)
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, []))
        self.assertEqual(res.decision, "PASS")
        self.bet_binary.amount = 20
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, []))
        self.assertEqual(res.decision, "FAIL")

    def test_probability_change(self):
        q = ProbabilityChangeQualifier(min_change=0.2, max_change=0.6)
        bet = self.bet_binary
        bet.prob_before = 0.5
        bet.prob_after = 0.55
        res = asyncio.run(q.qualify(bet, self.market_binary, []))
        self.assertEqual(res.decision, "FAIL")

        # Exceed maximum change
        q = ProbabilityChangeQualifier(max_change=0.2)
        bet.prob_after = 0.8
        res = asyncio.run(q.qualify(bet, self.market_binary, []))
        self.assertEqual(res.decision, "FAIL")

        # Acceptable change
        q = ProbabilityChangeQualifier(min_change=0.1, max_change=0.6)
        bet.prob_after = 0.7
        res = asyncio.run(q.qualify(bet, self.market_binary, []))
        self.assertEqual(res.decision, "PASS")

    def test_creator_is_bettor(self):
        q = CreatorIsBettorQualifier()
        bet = self.bet_binary
        bet.user_id = self.market_binary.creator_id
        res = asyncio.run(q.qualify(bet, self.market_binary, []))
        self.assertEqual(res.decision, "FAIL")
        bet.user_id = "u2"
        res = asyncio.run(q.qualify(bet, self.market_binary, []))
        self.assertEqual(res.decision, "PASS")
        bet_mc = self.bet_multi
        bet_mc.user_id = "u2"  # creator of answer a1
        res = asyncio.run(q.qualify(bet_mc, self.market_multi, []))
        self.assertEqual(res.decision, "FAIL")

    def test_smart_user_blocklist_and_profit(self):
        q = SmartUserQualifier({"u4"}, max_profit=100)
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        q = SmartUserQualifier(set(), max_profit=5)
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        q = SmartUserQualifier(set(), max_profit=200)
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")

    def test_profitable_user(self):
        q = ProfitableUserQualifier(min_profit=5)
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")
        q = ProfitableUserQualifier(min_profit=20)
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")

    def test_overinvested(self):
        q = OverinvestedQualifier(max_position=50)
        # Bet opposite to current position direction to trigger failure
        self.bet_binary.outcome = "NO"
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        q = OverinvestedQualifier(max_position=200)
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")

    def test_recently_counterbet(self):
        q = RecentlyCounterbetUserQualifier(minutes=10)
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")
        history = [
            (
                Bet(amount=10, shares=5, outcome="YES", contract_id="m1", created_time=self.now, prob_before=0.4, prob_after=0.5, user_id="u2"),
                Bet(amount=10, shares=5, outcome="NO", contract_id="m1", created_time=self.now, prob_before=0.5, prob_after=0.4, user_id="u0"),
                self.now,
            )
        ]
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client, recent_counterbets=history))
        self.assertEqual(res.decision, "PASS")

        # Still under the 3 counterbet limit for not-smart users
        history.append(
            (
                Bet(amount=10, shares=5, outcome="YES", contract_id="m1", created_time=self.now, prob_before=0.4, prob_after=0.5, user_id="u2"),
                Bet(amount=10, shares=5, outcome="NO", contract_id="m1", created_time=self.now, prob_before=0.5, prob_after=0.4, user_id="u0"),
                self.now,
            )
        )
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client, recent_counterbets=history))
        self.assertEqual(res.decision, "PASS")

        # Exceed the limit with a third recent counterbet
        history.append(
            (
                Bet(amount=10, shares=5, outcome="YES", contract_id="m1", created_time=self.now, prob_before=0.4, prob_after=0.5, user_id="u2"),
                Bet(amount=10, shares=5, outcome="NO", contract_id="m1", created_time=self.now, prob_before=0.5, prob_after=0.4, user_id="u0"),
                self.now,
            )
        )
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client, recent_counterbets=history))
        self.assertEqual(res.decision, "FAIL")

    def test_no_bots(self):
        q = NoBotsQualifier()
        bet = self.bet_binary
        bet.is_api = True
        res = asyncio.run(q.qualify(bet, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        bet.is_api = False
        res = asyncio.run(q.qualify(bet, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")

    def test_can_take_profit(self):
        q = CanTakeProfitQualifier(min_profit_percent=40)
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")
        q = CanTakeProfitQualifier(min_profit_percent=60)
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        # Wrong direction
        bet = self.bet_binary
        bet.outcome = "NO"
        q = CanTakeProfitQualifier(min_profit_percent=40)
        res = asyncio.run(q.qualify(bet, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")

    def test_no_sells(self):
        q = NoSellsQualifier()
        bet = self.bet_binary
        bet.amount = -5
        res = asyncio.run(q.qualify(bet, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        bet.amount = 5
        res = asyncio.run(q.qualify(bet, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")

    def test_no_bets_on_own_markets(self):
        q = NoBetsOnOwnMarketsQualifier()
        # Fail when the market creator matches the configured ID
        self.market_binary.creator_id = BetConfig.SELF_ID
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        # Pass otherwise
        self.market_binary.creator_id = "other_user"
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")

    def test_answer_mentions_current_day(self):
        q = AnswerMentionsCurrentDayQualifier()
        today = datetime.now()
        self.market_multi.answers[0].text = f"Event on {today.strftime('%B')} {today.day}?"
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, []))
        self.assertEqual(res.decision, "FAIL")

        self.market_multi.answers[0].text = "No date here"
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, []))
        self.assertEqual(res.decision, "PASS")

    def test_arbitrage_market_closed(self):
        other = Market(
            id="m3",
            creator_id="u5",
            question="Other",
            created_time=self.now,
            volume=1000.0,
            mechanism="cpmm-1",
            outcome_type="BINARY",
            is_resolved=False,
            close_time=self.now - timedelta(days=1),
            probability=0.5,
        )
        pair = ArbitragePair(
            market1_id="m1",
            market2_id="m3",
            inverted=False,
            min_spread=0.02,
            margin=0.5,
            max_position=100,
        )
        self.mock_client.get_market.return_value = other
        q = ArbitrageableMarketQualifier([pair])
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        self.assertEqual(res.reason, "PAIR_MARKET_CLOSED")

    def test_arbitrage_probability_range(self):
        other = Market(
            id="m3",
            creator_id="u5",
            question="Other",
            created_time=self.now,
            volume=1000.0,
            mechanism="cpmm-1",
            outcome_type="BINARY",
            is_resolved=False,
            probability=0.5,
        )
        pair = ArbitragePair(
            market1_id="m1",
            market2_id="m3",
            inverted=False,
            min_spread=0.02,
            margin=0.5,
            max_position=100,
        )
        self.mock_client.get_market.return_value = other
        self.mock_client.get_market_probability.side_effect = [0.0, 0.5]
        q = ArbitrageableMarketQualifier([pair])
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        self.assertEqual(res.reason, "PROBABILITY_OUT_OF_RANGE")
        self.mock_client.get_market_probability.side_effect = None

    def test_arbitrage_answer_resolved(self):
        other = Market(
            id="m3",
            creator_id="u5",
            question="Other MC",
            created_time=self.now,
            volume=1000.0,
            mechanism="cpmm-multi-1",
            outcome_type="MULTIPLE_CHOICE",
            is_resolved=False,
            answers=[
                Answer(
                    id="b1",
                    index=0,
                    contract_id="m3",
                    created_time=int(self.now.timestamp() * 1000),
                    user_id="u6",
                    text="B1",
                    probability=0.5,
                    is_other=False,
                    total_liquidity=40.0,
                ),
                Answer(
                    id="b2",
                    index=1,
                    contract_id="m3",
                    created_time=int(self.now.timestamp() * 1000),
                    user_id="u7",
                    text="B2",
                    probability=0.5,
                    is_other=False,
                    total_liquidity=60.0,
                ),
            ],
        )
        pair = ArbitragePair(
            market1_id="m2",
            market2_id="m3",
            inverted=False,
            min_spread=0.02,
            margin=0.5,
            max_position=100,
            answer_pairs=[("a1", "b1"), ("a2", "b2")],
        )
        self.mock_client.get_market.return_value = other
        self.market_multi.answers[0].resolution = "YES"
        q = ArbitrageableMarketQualifier([pair])
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        self.assertEqual(res.reason, "MARKET_CLOSED")

    def test_arbitrage_pair_answer_resolved(self):
        other = Market(
            id="m3",
            creator_id="u5",
            question="Other MC",
            created_time=self.now,
            volume=1000.0,
            mechanism="cpmm-multi-1",
            outcome_type="MULTIPLE_CHOICE",
            is_resolved=False,
            answers=[
                Answer(
                    id="b1",
                    index=0,
                    contract_id="m3",
                    created_time=int(self.now.timestamp() * 1000),
                    user_id="u6",
                    text="B1",
                    probability=0.5,
                    is_other=False,
                    total_liquidity=40.0,
                    resolution="YES",
                ),
                Answer(
                    id="b2",
                    index=1,
                    contract_id="m3",
                    created_time=int(self.now.timestamp() * 1000),
                    user_id="u7",
                    text="B2",
                    probability=0.5,
                    is_other=False,
                    total_liquidity=60.0,
                ),
            ],
        )
        pair = ArbitragePair(
            market1_id="m2",
            market2_id="m3",
            inverted=False,
            min_spread=0.02,
            margin=0.5,
            max_position=100,
            answer_pairs=[("a1", "b1"), ("a2", "b2")],
        )
        self.mock_client.get_market.return_value = other
        q = ArbitrageableMarketQualifier([pair])
        res = asyncio.run(q.qualify(self.bet_multi, self.market_multi, [], client=self.mock_client))
        self.assertEqual(res.decision, "FAIL")
        self.assertEqual(res.reason, "PAIR_MARKET_CLOSED")

    def test_arbitrage_passes(self):
        other = Market(
            id="m3",
            creator_id="u5",
            question="Other",
            created_time=self.now,
            volume=1000.0,
            mechanism="cpmm-1",
            outcome_type="BINARY",
            is_resolved=False,
            probability=0.6,
        )
        pair = ArbitragePair(
            market1_id="m1",
            market2_id="m3",
            inverted=False,
            min_spread=0.02,
            margin=0.5,
            max_position=100,
        )
        self.mock_client.get_market.return_value = other
        self.mock_client.get_market_probability.side_effect = [0.5, 0.6]
        q = ArbitrageableMarketQualifier([pair])
        res = asyncio.run(q.qualify(self.bet_binary, self.market_binary, [], client=self.mock_client))
        self.assertEqual(res.decision, "PASS")
        self.assertEqual(res.reason, "ARBITRAGEABLE")
        self.mock_client.get_market_probability.side_effect = None


if __name__ == "__main__":
    unittest.main()
