"""Backtesting framework for the trading bot.

This module reads historical `PlaceBetEvent` logs, fetches current or
resolved market data from Manifold, and computes the profitability of
each logged bet. The results are aggregated by strategy and written to a
markdown report.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.manifold_client import ManifoldClient
from src.models import Market, Bet
from config.api_config import APIConfig


@dataclass
class BetLog:
    id: Optional[str]
    timestamp: datetime
    strategies: List[str]
    contract_id: str
    amount: float
    shares: float
    outcome: str
    limit_prob: Optional[float]
    answer_id: Optional[str]
    ws_to_api_ms: Optional[int] = None


@dataclass
class BetResult:
    log: BetLog
    bet: Optional[Bet]
    profit: float
    profit_pct: float


class Backtester:
    """Load bet logs and evaluate their profitability."""

    def __init__(
        self,
        domains: List[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        log_dir: Path | str = "logs",
        report_path: Path | str = "backtest_report.md",
    ) -> None:
        self.domains = domains
        self.start = start
        self.end = end
        self.log_dir = Path(log_dir)
        self.report_path = Path(report_path)
        self.client = ManifoldClient()

    def _parse_event_row(self, row: Dict[str, str]) -> Optional[BetLog]:
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except Exception:
            return None
        if self.start and ts < self.start:
            return None
        if self.end and ts > self.end:
            return None
        strategy_field = row.get("strategy", "") or ""
        strategies = [s.strip() for s in strategy_field.split(",") if s.strip()]
        if not strategies:
            strategies = ["unknown"]
        return BetLog(
            id=row.get("id") or None,
            timestamp=ts,
            strategies=strategies,
            contract_id=row["contract_id"],
            amount=float(row["amount"]),
            shares=float(row.get("shares", 0)),
            outcome=row["outcome"],
            limit_prob=float(row["limit_prob"]) if row.get("limit_prob") else None,
            answer_id=row.get("answer_id") or None,
            ws_to_api_ms=int(row["ws_to_api_ms"]) if row.get("ws_to_api_ms") else None,
        )

    def load_bets(self) -> List[BetLog]:
        bets: List[BetLog] = []
        for domain in self.domains:
            csv_path = self.log_dir / domain / "placebetevent.csv"
            if not csv_path.exists():
                continue
            with open(csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    log = self._parse_event_row(row)
                    if log:
                        bets.append(log)
        return bets

    def load_api_bets(self) -> List[Bet]:
        after_ms = int(self.start.timestamp() * 1000) if self.start else None
        before_ms = int(self.end.timestamp() * 1000) if self.end else None
        return self.client.get_bets(
            user_id=APIConfig.USER_ID,
            after_time=after_ms,
            before_time=before_ms,
            limit=1000,
        )

    def _pair_logs_with_api_bets(self, logs: List[BetLog], bets: List[Bet]) -> List[Tuple[BetLog, Optional[Bet]]]:
        """Pair log entries with actual API bets.

        Matching first uses bet IDs when available. Otherwise it falls back to a
        heuristic based on contract, outcome, timestamp, amount and limit
        probability. This reduces incorrect pairings when multiple bets occur in
        the same market around the same time."""

        bets_by_id = {bet.id: bet for bet in bets if bet.id}
        unmatched = bets.copy()
        pairs: List[Tuple[BetLog, Optional[Bet]]] = []

        for log in logs:
            matched: Optional[Bet] = None
            if log.id and log.id in bets_by_id:
                matched = bets_by_id[log.id]
                if matched in unmatched:
                    unmatched.remove(matched)
            else:
                for bet in list(unmatched):
                    if bet.contract_id != log.contract_id or bet.outcome != log.outcome:
                        continue
                    if abs(bet.created_time.timestamp() - log.timestamp.timestamp()) > 1:
                        continue
                    if abs(bet.amount - log.amount) > 1e-6:
                        continue
                    if log.limit_prob is not None and bet.limit_prob is not None:
                        if abs(bet.limit_prob - log.limit_prob) > 1e-6:
                            continue
                    matched = bet
                    unmatched.remove(bet)
                    break
            pairs.append((log, matched))
        return pairs

    def _get_final_prob(self, market: Market, answer_id: Optional[str]) -> float:
        if market.is_resolved:
            if answer_id:
                ans = market.get_answer_by_id(answer_id)
                if ans and ans.resolution:
                    return 1.0 if ans.resolution == "YES" else 0.0
            if market.resolution_probability is not None:
                return market.resolution_probability
            if market.resolution == "YES":
                return 1.0
            if market.resolution == "NO":
                return 0.0
        if answer_id:
            prob = market.get_answer_probability(answer_id)
            return prob if prob is not None else 0.0
        return market.probability if market.probability is not None else 0.0

    def _evaluate_bet(self, log: BetLog, bet: Optional[Bet]) -> BetResult:
        market = self.client.get_market(log.contract_id)
        final_prob = self._get_final_prob(market, log.answer_id)
        amount = bet.amount if bet else log.amount
        shares = bet.shares if bet else log.shares
        outcome = bet.outcome if bet else log.outcome
        if outcome == "YES":
            value = shares * final_prob
        else:
            value = shares * (1 - final_prob)
        profit = value - amount
        profit_pct = profit / amount if amount else 0.0
        return BetResult(log=log, bet=bet, profit=profit, profit_pct=profit_pct)

    def run(self) -> List[BetResult]:
        logs = self.load_bets()
        if not logs:
            return []

        # Infer time range if not explicitly provided
        times = [log.timestamp for log in logs]
        if self.start is None:
            self.start = min(times)
        if self.end is None:
            self.end = max(times)

        api_bets = self.load_api_bets()
        paired = self._pair_logs_with_api_bets(logs, api_bets)
        results = [self._evaluate_bet(log, bet) for log, bet in paired]
        unpaired_logs = [log for log, bet in paired if bet is None]
        self._write_report(results, unpaired_logs)
        return results

    def _write_report(self, results: List[BetResult], unpaired_logs: List[BetLog]) -> None:
        strat_data: Dict[str, Dict[str, float]] = {}
        strat_counts: Dict[str, int] = {}
        strat_wins: Dict[str, int] = {}
        unpaired_counts: Dict[str, int] = {}

        for res in results:
            strategies = res.log.strategies or ["unknown"]
            for strat in strategies:
                data = strat_data.setdefault(strat, {"profit": 0.0, "investment": 0.0})
                data["profit"] += res.profit
                data["investment"] += res.log.amount
                strat_counts[strat] = strat_counts.get(strat, 0) + 1
                if res.profit > 0:
                    strat_wins[strat] = strat_wins.get(strat, 0) + 1

        for log in unpaired_logs:
            strategies = log.strategies or ["unknown"]
            for strat in strategies:
                unpaired_counts[strat] = unpaired_counts.get(strat, 0) + 1

        lines = ["# Backtesting Report", ""]
        if self.start or self.end:
            start = self.start.isoformat() if self.start else "?"
            end = self.end.isoformat() if self.end else "?"
            lines.append(f"Period: {start} to {end}")
            lines.append("")
        lines.append("| Strategy | Bets | Profit | ROI | Win Rate |")
        lines.append("|---|---:|---:|---:|---:|")
        for strat, data in strat_data.items():
            count = strat_counts.get(strat, 0)
            wins = strat_wins.get(strat, 0)
            roi = data["profit"] / data["investment"] if data["investment"] else 0.0
            win_rate = wins / count if count else 0.0
            lines.append(
                f"| {strat} | {count} | {data['profit']:.2f} | {roi:.2%} | {win_rate:.2%} |"
            )

        total_unpaired = len(unpaired_logs)
        lines.append("")
        lines.append(f"Unpaired log bets: {total_unpaired}")
        if total_unpaired:
            lines.append("| Strategy | Unpaired |")
            lines.append("|---|---:|")
            for strat, count in unpaired_counts.items():
                lines.append(f"| {strat} | {count} |")

        self.report_path.write_text("\n".join(lines))


if __name__ == "__main__":
    tester = Backtester(domains=["default"])
    tester.run()
