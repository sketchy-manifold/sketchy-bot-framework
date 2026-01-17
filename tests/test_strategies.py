# Read tests/knowledge.md in this directory for how to run tests.
import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.models import Bet, Market, Txn, PortfolioMetrics
from src.strategies.housekeeping_strategy import HousekeepingStrategy
from config import APIConfig, HousekeepingConfig

class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        # Convert client methods used in strategies to AsyncMock
        async_methods = [
            'place_bet', 'get_market_probability', 'get_market_positions',
            'get_user_portfolio', 'get_transactions', 'get_bets', 'get_market',
            'send_managram', 'request_loan', 'get_user_by_id'
        ]
        for method in async_methods:
            setattr(self.client, method, AsyncMock())
        self.client.get_user_by_id.return_value = MagicMock(balance=0)
        self.now = datetime.now()
        self.market = Market(
            id="m1",
            creator_id="u1",
            question="Binary?",
            created_time=self.now,
            volume=1000.0,
            mechanism="cpmm-1",
            outcome_type="BINARY",
            is_resolved=False,
            total_liquidity=500.0,
        )

    def create_bet(self, **kwargs):
        default = dict(
            amount=50.0,
            shares=20.0,
            outcome="YES",
            contract_id=self.market.id,
            created_time=self.now,
            prob_before=0.4,
            prob_after=0.6,
            user_id="u2",
        )
        default.update(kwargs)
        return Bet(**default)

    def create_housekeeping_strategy(self):
        return HousekeepingStrategy(
            self.client,
            HousekeepingConfig.BALANCE_THRESHOLD,
            HousekeepingConfig.TARGET_BALANCE,
        )

    def test_housekeeping_sends_managram(self):
        strat = self.create_housekeeping_strategy()
        bet = self.create_bet()
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=3100,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
        )
        self.client.get_user_portfolio.return_value = metrics
        self.client.get_user_by_id.return_value = MagicMock(balance=metrics.balance)
        with patch("random.sample", return_value=["💰", "💵"]):
            result = asyncio.run(strat.propose_bet(bet, self.market, []))
        self.client.send_managram.assert_called_once()
        self.client.request_loan.assert_called_once()
        self.assertIsNotNone(result.event)
        self.assertIn("TRANSFER_EXCESS_BALANCE", result.event.actions)
        self.assertEqual(result.event.metadata["sent_amount"], metrics.balance - HousekeepingConfig.TARGET_BALANCE)

    def test_housekeeping_no_event_when_below_threshold(self):
        strat = self.create_housekeeping_strategy()
        bet = self.create_bet()
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=1000,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
        )
        self.client.get_user_portfolio.return_value = metrics
        self.client.get_user_by_id.return_value = MagicMock(balance=metrics.balance)
        result = asyncio.run(strat.propose_bet(bet, self.market, []))
        self.client.send_managram.assert_not_called()
        self.client.request_loan.assert_called_once()
        self.assertIsNotNone(result.event)
        self.assertIn("RECEIVED_LOAN", result.event.actions)
        self.assertIn("Successfully requested loan", result.event.message)

    def test_housekeeping_remote_shutdown(self):
        strat = self.create_housekeeping_strategy()
        bet = self.create_bet()
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=1000,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
        )
        self.client.get_user_portfolio.return_value = metrics
        self.client.get_user_by_id.return_value = MagicMock(balance=metrics.balance)
        txn = Txn(
            id="t1",
            data={"message": "hello <ACTIVATE_KILLSWITCH> there"},
            to_id=APIConfig.USER_ID,
            token="M$",
            amount=1,
            from_id=HousekeepingConfig.RECIPIENT_USER_ID,
            to_type="USER",
            category="MANA_PAYMENT",
            from_type="USER",
            created_time=self.now,
            description="test",
        )
        self.client.get_transactions.return_value = [txn]
        with self.assertRaises(SystemExit):
            asyncio.run(strat.propose_bet(bet, self.market, []))
        self.client.send_managram.assert_called_once_with(
            to_ids=[HousekeepingConfig.RECIPIENT_USER_ID],
            amount=int(txn.amount),
            message=HousekeepingConfig.KILLSWITCH_CONFIRMATION_MESSAGE,
        )
        self.client.request_loan.assert_not_called()

    def test_housekeeping_easter_egg_on_bad_killswitch(self):
        strat = self.create_housekeeping_strategy()
        bet = self.create_bet()
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=1000,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
        )
        self.client.get_user_portfolio.return_value = metrics
        self.client.get_user_by_id.return_value = MagicMock(balance=metrics.balance)
        txn = Txn(
            id="t2",
            data={"message": "pls <ACTIVATE_KILLSWITCH>"},
            to_id=APIConfig.USER_ID,
            token="M$",
            amount=2,
            from_id="other_user",
            to_type="USER",
            category="MANA_PAYMENT",
            from_type="USER",
            created_time=self.now,
            description="test",
        )
        self.client.get_transactions.return_value = [txn]
        result = asyncio.run(strat.propose_bet(bet, self.market, []))
        self.client.send_managram.assert_called_once_with(
            to_ids=[HousekeepingConfig.RECIPIENT_USER_ID],
            amount=int(txn.amount),
            message=HousekeepingConfig.KILLSWITCH_EASTER_EGG_MESSAGE,
        )
        self.assertIsNotNone(result.event)
        self.assertIn("EASTER_EGG", result.event.actions)

    def test_housekeeping_skips_when_run_too_recently(self):
        strat = self.create_housekeeping_strategy()
        bet = self.create_bet()
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=3100,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
        )
        self.client.get_user_portfolio.return_value = metrics
        self.client.get_user_by_id.return_value = MagicMock(balance=metrics.balance)
        with patch("random.sample", return_value=["💰", "💵"]):
            result1 = asyncio.run(strat.propose_bet(bet, self.market, []))
        self.assertIsNotNone(result1.event)
        self.client.send_managram.assert_called_once()
        self.client.request_loan.assert_called_once()

        with patch("random.sample", return_value=["💰", "💵"]):
            result2 = asyncio.run(strat.propose_bet(bet, self.market, []))
        self.assertIsNone(result2.event)
        self.client.send_managram.assert_called_once()
        self.client.request_loan.assert_called_once()

    def test_housekeeping_requests_loan_only_once_per_day(self):
        strat = self.create_housekeeping_strategy()
        bet = self.create_bet()
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=1000,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
        )
        self.client.get_user_portfolio.return_value = metrics
        self.client.get_user_by_id.return_value = MagicMock(balance=metrics.balance)
        asyncio.run(strat.propose_bet(bet, self.market, []))
        self.assertEqual(self.client.request_loan.call_count, 1)

        strat._last_run -= timedelta(minutes=HousekeepingConfig.RUN_INTERVAL_MINUTES + 1)
        strat._last_loan_request -= timedelta(minutes=1)
        asyncio.run(strat.propose_bet(bet, self.market, []))
        self.assertEqual(self.client.request_loan.call_count, 1)

        strat._last_run -= timedelta(minutes=HousekeepingConfig.RUN_INTERVAL_MINUTES + 1)
        strat._last_loan_request -= timedelta(hours=25)
        asyncio.run(strat.propose_bet(bet, self.market, []))
        self.assertEqual(self.client.request_loan.call_count, 2)

    def test_housekeeping_handles_duplicate_loan_error(self):
        strat = self.create_housekeeping_strategy()
        bet = self.create_bet()
        metrics = PortfolioMetrics(
            investment_value=0,
            cash_investment_value=0,
            balance=1000,
            cash_balance=0,
            spice_balance=0,
            total_deposits=0,
            total_cash_deposits=0,
            loan_total=0,
            timestamp=self.now,
        )
        self.client.get_user_portfolio.return_value = metrics
        self.client.get_user_by_id.return_value = MagicMock(balance=metrics.balance)
        self.client.request_loan.side_effect = Exception(
            'API error (400): {"message":"Already awarded loan today"}'
        )
        result = asyncio.run(strat.propose_bet(bet, self.market, []))
        self.client.request_loan.assert_called_once()
        self.assertIsNotNone(strat._last_loan_request)
        self.assertIsNotNone(result.event)
        self.assertIn("REQUEST_LOAN_FAIL", result.event.actions)
        self.assertIn("Already awarded loan today", result.event.message)

if __name__ == "__main__":
    unittest.main()
