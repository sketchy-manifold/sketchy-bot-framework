import asyncio
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from src.models import Bet, ProposedBet
from src.logger import ErrorEvent, PlaceBetEvent, logger
from src import ManifoldClient, WebSocketMessage
from src.strategies import (
    HousekeepingStrategy,
    StrategyResult,
)
from config import BetConfig, HousekeepingConfig

class Core:
    def __init__(self, persona: str = "dagonet"):
        self.client = ManifoldClient()
        self.persona = persona
        self.strategies = [
            HousekeepingStrategy(
                self.client,
                HousekeepingConfig.BALANCE_THRESHOLD,
                HousekeepingConfig.TARGET_BALANCE,
            ),
            # Your strategies here!
        ]

    async def run(self):
        """Run the core application.
        
        Connects to WebSocket and subscribes to bet updates.
        """
        await self.client.connect()
        await self.client.subscribe('global/new-bet', self.on_bet)
        await self.client.listen()

    async def on_bet(self, message: WebSocketMessage):
        """Handle incoming bet update message.
        
        Args:
            message: WebSocket message containing bet data
        """
        try:
            await self.on_bet_impl(message)
        except Exception as e:
            logger.log(ErrorEvent(
                error_type=type(e),
                message=str(e),
                source=__class__,
            ))

    async def on_bet_impl(self, message: WebSocketMessage):
        start_time = datetime.now()
        bet_data_list = message['data'].get('bets', [])
        bets = [Bet.from_dict(bet_data) for bet_data in bet_data_list]
        
        mkt = await self.client.get_market(bets[0].contract_id)
        mkt_bets = await self.client.get_bets(
            contract_id=mkt.id,
            limit=1000
        )
        proposed_result = await self.get_proposed_response_result(bets, mkt, mkt_bets)

        if not proposed_result:
            return

        for proposed_bet in proposed_result.bets:
            amount = max(proposed_bet.amount, 1)

            if mkt.outcome_type == "MULTIPLE_CHOICE" and not proposed_bet.answer_id:
                logger.log(ErrorEvent(
                    error_type=ValueError,
                    message="Missing answer_id for MULTIPLE_CHOICE bet",
                    source=__class__
                ))
                continue

            ws_to_api_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            result_bet = await self.client.place_bet(
                amount=amount,
                contractId=proposed_bet.contract_id,
                outcome=proposed_bet.outcome,
                limitProb=proposed_bet.limit_prob,
                expiresMillisAfter=BetConfig.LIMIT_DURATION * 1000,
                dryRun=BetConfig.DRY_RUN,
                answerId=proposed_bet.answer_id,
            )

            event = PlaceBetEvent(
                id=f"trigger_{bets[0].id}_on_market_{proposed_bet.contract_id}",
                user_id=proposed_bet.user_id,
                amount=amount,
                filled_amount=result_bet.amount,
                outcome=proposed_bet.outcome,
                contract_id=proposed_bet.contract_id,
                limit_prob=proposed_bet.limit_prob,
                answer_id=proposed_bet.answer_id,
                ws_to_api_ms=ws_to_api_ms,
                extra_data=str(proposed_bet.extra_data) if proposed_bet.extra_data else None,
            )

            event.strategy = proposed_bet.source_strategy
            logger.log(event)

    async def get_proposed_response_result(self, bet_list, mkt, mkt_bets) -> Optional[StrategyResult]:
        """Return the first non-empty strategy result."""
        tasks = [
            strategy.evaluate_and_propose(
                bet_list,
                mkt,
                mkt_bets,
            )
            for strategy in self.strategies
        ]
        results = await asyncio.gather(*tasks)

        bet_results = []
        for strat_response in results:
            if strat_response.event:
                pass # (Skipping failed qualification events for now - just too expensive to log)
                # logger.log(strat_response.event)
            elif strat_response.bets:
                bet_results.append(strat_response)
        
        if len(bet_results) == 0:
            return None
        if len(bet_results) == 1:
            return bet_results[0]
        
        return self.combine_strat_results(bet_results)
    
    def combine_strat_results(self, results: List[StrategyResult]) -> StrategyResult:
        bets = []

        for result in results:
            for bet in result.bets:
                contract_id = bet.contract_id
                answer_id = bet.answer_id
                outcome = bet.outcome

                matching_bets = [b for b in bets if b.contract_id == contract_id and b.answer_id == answer_id and b.outcome == outcome]
                if len(matching_bets) == 0:
                    bets.append(bet)
                elif len(matching_bets) == 1:
                    finalized_bet = matching_bets[0]
                    finalized_bet.amount = max(bet.amount, finalized_bet.amount)
                    if finalized_bet.outcome == "YES":
                        finalized_bet.limit_prob = max(bet.limit_prob, finalized_bet.limit_prob)
                    else:
                        finalized_bet.limit_prob = min(bet.limit_prob, finalized_bet.limit_prob)
                    finalized_bet.source_strategy += "," + bet.source_strategy
                    finalized_bet.extra_data.update(bet.extra_data)
                else:
                    raise Exception("Invariant broken, more than one finalized bet with same contract/answer id!")
                
        return StrategyResult(bets=bets)
                



if __name__ == "__main__":
    core = Core()
    asyncio.run(core.run())
