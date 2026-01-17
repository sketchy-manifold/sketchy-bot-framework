# Sketchy's Manifold Bot Framework

This is a bot framework for [Manifold](https://manifold.markets), a play-money prediction market platform. The framework makes it simpler to create a trading bot by providing a few basic features:

1. A **Manifold API client** that handles WebSocket connections and API requests.
2. **Classes that abstract core Manifold concepts** (Bet, Market, etc), and add a few helper functions
3. **A strategy framework** that allows you to define custom trading strategies.
4. A **core event loop** that runs the strategy logic and manages the WebSocket connection.

## Manifold API Client
The async client in `src/manifold_client.py` wraps both the REST API and the WebSocket feed behind one interface. It centralizes auth and request configuration from `APIConfig`, lazily creates an `aiohttp.ClientSession`, and maps API payloads into model objects (`User`, `Market`, `Bet`, and more) so callers work with typed data instead of raw dicts.

Key behaviors:
- `_make_request` handles GET/POST, timeouts, retries, and a TTL cache keyed by endpoint plus params, with per-endpoint overrides from `APIConfig`.
- WebSocket lifecycle (`connect`, `listen`, `subscribe`) includes a manual ping loop, ack handling, callback routing by topic, and exponential backoff in `_reconnect`.


## Manifold Objects
Domain models live in `src/models` as dataclasses that inherit from `BaseModel`. `BaseModel.from_dict` normalizes Manifold JSON by converting camelCase to snake_case, converting `*Time` fields to `datetime`, and logging unexpected keys via `ErrorEvent` so schema drift is visible.

Notable behaviors:
- `Market` and `Answer` capture multiple-choice structure, parse nested answers, and expose helper methods like `get_answer_probability` and `get_answer_liquidity`.
- `Bet`, `Comment`, `User`, `LiteUser`, `PortfolioMetrics`, and `Txn` provide typed access to common entities; `Bet` reconciles `bet_id` to `id`.
- `ProposedBet` validates order parameters against `BetConfig`, while `ArbitragePair` encodes cross-market relationships for arbitrage logic.


## Strategy Framework
Strategies implement `BaseTradingStrategy` (`src/strategies/base_strategy.py`), which defines a qualifier pipeline and a single `propose_bet` hook. `evaluate_and_propose` runs base qualifiers plus strategy-specific qualifiers (async), returns a `StrategyResult` containing either proposed bets or a log event, and stamps strategy names for downstream logging.

Framework components:
- Qualifiers in `src/qualifiers/qualifiers.py` provide reusable PASS/FAIL checks (market type, bot/creator restrictions, opt-out, liquidity provisions, etc.) and can call `ManifoldClient` when needed.
- `HousekeepingStrategy` (`src/strategies/housekeeping_strategy.py`) uses the same interface for non-trading maintenance: daily loan requests, balance transfers via managrams, and a killswitch triggered by inbound transactions.
- Proposed orders are represented by `ProposedBet`, and housekeeping thresholds/recipients are configured via `config/housekeeping_config.py` and `config/api_config.py`.


## Core Event Loop
The event loop in `src/core.py` is the runtime coordinator. `Core.run` connects the WebSocket, subscribes to `global/new-bet`, and hands each message to `on_bet`, which fetches market context, evaluates all strategies concurrently, and places resulting bets through `ManifoldClient`. Errors and placed bets are logged via the CSV logger in `src/logger.py`.

Flow at a glance:
- Parse each incoming bet batch into `Bet` objects, then load the market and recent bet history.
- Call each strategy's `evaluate_and_propose` with `recent_counterbets`, merge overlapping proposals by contract/answer/outcome, and compute latency for logging.
- Enforce multiple-choice `answer_id` requirements, place limit orders with `BetConfig` settings, log `PlaceBetEvent`, and prune stale counterbet records.


## Installation

1. Clone the repository:
```bash
git clone https://github.com/danstoyell/manifold-dagonet.git
cd manifold-dagonet
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your API key:
```bash
cp config/api_config.template.py config/api_config.py
```
Then edit `config/api_config.py` and add your API key from https://manifold.markets/profile

4. Set up test configuration:
```bash
cp tests/test_config.template.py tests/test_config.py
```
Then edit `test_config.py` and add your test user/market IDs.

## Running Tests

```bash
python -m unittest discover tests
```

## Logging

The bot uses a domain-based logging system that writes events to CSV files. Logs are organized by domain (e.g., bets, markets, errors) and event type.

Log files are stored in the `logs` directory with the following structure:
```
logs/
  bets/
    betevent.csv
  markets/
    marketevent.csv
  errors/
    errorevent.csv
```

Each event type has a predefined schema and all events are automatically timestamped.

Logging can be disabled entirely by setting the environment variable
`DAGONET_ENABLE_LOGGING=0`. This is useful when running the unit tests
so no log files are created.

## Contributing

This is a personal project, but discussion is welcome! I take no responsibility if you lose all your mana.


## Known Jankiness
- Not sure why I implemented a custom logger. I think just because it was so easy with vibe coding.
- The way the client converts the API response to a class is ~"strongly typed" in the sense that it'll break if Manifold fields to their response. I think this is a feature, not a bug - it means I have to go figure out what they mucked with. But YMMV.
- If any of the way configs, environments, or any "setup" stuff is handled seems hacky, I blame working at BigCo and not having to deal with this stuff regularly.
