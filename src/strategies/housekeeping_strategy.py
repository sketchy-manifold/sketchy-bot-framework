import random
from datetime import datetime, timedelta
from typing import List, Optional

from src.models import Bet, Market
from src.strategies.base_strategy import BaseTradingStrategy
from src.strategies.strategy_result import StrategyResult
from src.logger import HousekeepingEvent, logger
from src.qualifiers.qualifiers import BaseQualifier
from config import HousekeepingConfig, APIConfig

class HousekeepingStrategy(BaseTradingStrategy):
    """Perform housekeeping actions like requesting loans, sending back excess balance, etc"""

    _STRATEGY_QUALIFIERS: List[BaseQualifier] = []

    # No base qualifiers needed for housekeeping
    BASE_QUALIFIERS: List[BaseQualifier] = []

    def __init__(self, client, balance_threshold: int, target_balance: int):
        super().__init__(client)
        self._last_run: Optional[datetime] = None
        self._last_loan_request: Optional[datetime] = None
        self.balance_threshold = balance_threshold
        self.target_balance = target_balance

    @property
    def qualifiers(self) -> List[BaseQualifier]:
        return self._STRATEGY_QUALIFIERS

    async def _check_remote_shutdown(self, now: datetime) -> Optional[HousekeepingEvent]:
        """Look for shutdown managrams and handle accordingly."""
        after_ms = int(
            (now - timedelta(minutes=HousekeepingConfig.SHUTDOWN_LOOKBACK_MINUTES)).timestamp() * 1000
        )
        txns = await self.client.get_transactions(
            to_id=APIConfig.USER_ID,
            after=after_ms,
            category="MANA_PAYMENT",
        )
        for txn in txns:
            message = ""
            if txn.data and isinstance(txn.data, dict):
                message = str(txn.data.get("message", ""))
            if HousekeepingConfig.KILLSWITCH_PHRASE in message:
                if txn.from_id == HousekeepingConfig.RECIPIENT_USER_ID:
                    kill_event = HousekeepingEvent(
                        message="Remote shutdown activated",
                        actions=["REMOTE_SHUTDOWN", "SEND_MANAGRAM"],
                        metadata={
                            'txn_id': txn.id,
                            'message': message,
                        },
                    )
                    logger.log(kill_event)
                    await self.client.send_managram(
                        to_ids=[txn.from_id],
                        amount=int(txn.amount),
                        message=HousekeepingConfig.KILLSWITCH_CONFIRMATION_MESSAGE,
                    )
                    raise SystemExit("Remote shutdown")
                else:
                    egg_event = HousekeepingEvent(
                        message="Unauthorized killswitch attempt",
                        actions=["EASTER_EGG", "SEND_MANAGRAM"],
                        metadata={
                            "txn_id": txn.id,
                            "from": txn.from_id,
                            "amount": txn.amount,
                            "message": message,
                        },
                    )
                    await self.client.send_managram(
                        to_ids=[HousekeepingConfig.RECIPIENT_USER_ID],
                        amount=int(txn.amount),
                        message=HousekeepingConfig.KILLSWITCH_EASTER_EGG_MESSAGE,
                    )
                    return egg_event
        return None

    async def _request_loan(self, now: datetime) -> Optional[HousekeepingEvent]:
        """Request the daily loan if it hasn't been received in the last 24 hours."""
        if (
            self._last_loan_request is None
            or now.date() != self._last_loan_request.date()
        ):
            try:
                result = await self.client.request_loan()
            except Exception as e:
                if "Already awarded loan today" in str(e):
                    self._last_loan_request = now
                    return HousekeepingEvent(
                        message=str(e),
                        actions=["ALREADY_REQUESTED_LOAN"],
                    )
                else:
                    return HousekeepingEvent(
                        message=str(e),
                        actions=["REQUEST_LOAN_FAIL"],
                    )
            self._last_loan_request = now
            
            payout = result["payout"]
            return HousekeepingEvent(
                message="Successfully requested loan",
                actions=["RECEIVED_LOAN"],
                metadata={
                    "payout": payout,
                }
            )
        return None

    async def _maybe_send_excess_balance(self, balance: int) -> Optional[HousekeepingEvent]:
        """Send a managram with excess balance if the threshold is exceeded."""
        if balance > self.balance_threshold:
            send_amount = int(balance - self.target_balance)
            emojis = "".join(random.sample(HousekeepingConfig.EMOJIS, k=3))
            message = f"{HousekeepingConfig.MESSAGE_BASE} {emojis}"
            await self.client.send_managram(
                to_ids=[HousekeepingConfig.RECIPIENT_USER_ID],
                amount=send_amount,
                message=message,
            )
            metadata = {
                "old_balance": balance,
                "sent_amount": send_amount,
                "new_balance": balance - send_amount
            }
            return HousekeepingEvent(
                actions=["TRANSFER_EXCESS_BALANCE"],
                message=message,
                metadata=metadata,
            )
        return None

    def _merge_housekeeping_events(
        self,
        events: List[HousekeepingEvent],
    ) -> HousekeepingEvent:
        """Merge two housekeeping events to keep track of all actions taken"""
        if len(events) == 0:
            return HousekeepingEvent(
                actions=[],
                message="No housekeeping actions taken",
            )

        merged_metadata = {}
        for e in events:
            if e.metadata:
                merged_metadata |= e.metadata

        return HousekeepingEvent(
            actions=[action for e in events for action in e.actions],
            message=";".join(e.message for e in events),
            metadata=merged_metadata,
        )

    async def propose_bet(
        self,
        triggering_bet: Bet,
        market: Market,
        market_bets: List[Bet],
        **kwargs,
    ) -> StrategyResult:
        now = datetime.now()
        if (
            self._last_run is not None
            and (now - self._last_run).total_seconds()
            < HousekeepingConfig.RUN_INTERVAL_MINUTES * 60
        ):
            return StrategyResult()

        self._last_run = now
        bot_user = await self.client.get_user_by_id(APIConfig.USER_ID)
        housekeeping_events = []

        shutdown_event = await self._check_remote_shutdown(now)
        if shutdown_event: housekeeping_events.append(shutdown_event)

        loan_event = await self._request_loan(now)
        if loan_event: housekeeping_events.append(loan_event)

        balance = bot_user.balance
        managram_event = await self._maybe_send_excess_balance(balance)
        if managram_event: housekeeping_events.append(managram_event)

        final_event = self._merge_housekeeping_events(housekeeping_events)
        return StrategyResult(event=final_event)
