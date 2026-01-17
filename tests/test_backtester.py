# Read tests/knowledge.md in this directory for how to run tests.
import unittest
from datetime import datetime, timedelta

from src.backtester import Backtester, BetLog, BetResult
from src.models import Bet

class TestPairing(unittest.TestCase):
    def test_pair_logs_with_api_bets(self):
        bt = Backtester(domains=[])
        ts = datetime.now()
        logs = [BetLog(id="bet1", timestamp=ts, strategies=["s"], contract_id="c1", amount=10.0, shares=5.0, outcome="YES", limit_prob=0.5, answer_id=None)]
        bets = [Bet(amount=10.0, shares=5.0, outcome="YES", contract_id="c1", created_time=ts)]
        paired = bt._pair_logs_with_api_bets(logs, bets)
        self.assertEqual(paired[0][1], bets[0])

    def test_pair_with_time_tolerance(self):
        bt = Backtester(domains=[])
        ts_log = datetime.now()
        ts_bet = ts_log + timedelta(seconds=1)
        logs = [BetLog(id=None, timestamp=ts_log, strategies=["s"], contract_id="c1", amount=10.0, shares=5.0, outcome="NO", limit_prob=0.4, answer_id=None)]
        bets = [Bet(amount=10.0, shares=5.0, outcome="NO", contract_id="c1", created_time=ts_bet)]
        paired = bt._pair_logs_with_api_bets(logs, bets)
        self.assertIsNotNone(paired[0][1])

    def test_pair_by_amount_and_limit_prob(self):
        bt = Backtester(domains=[])
        now = datetime.now()
        logs = [
            BetLog(id=None, timestamp=now, strategies=["a"], contract_id="c", amount=10.0, shares=1.0, outcome="YES", limit_prob=0.6, answer_id=None),
            BetLog(id=None, timestamp=now + timedelta(seconds=0.5), strategies=["b"], contract_id="c", amount=5.0, shares=1.0, outcome="YES", limit_prob=0.7, answer_id=None),
        ]
        bets = [
            Bet(amount=5.0, shares=1.0, outcome="YES", contract_id="c", created_time=now + timedelta(seconds=0.5), limit_prob=0.7),
            Bet(amount=10.0, shares=1.0, outcome="YES", contract_id="c", created_time=now, limit_prob=0.6),
        ]
        paired = bt._pair_logs_with_api_bets(logs, bets)
        self.assertEqual(paired[0][1], bets[1])
        self.assertEqual(paired[1][1], bets[0])

if __name__ == "__main__":
    unittest.main()
