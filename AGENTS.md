# Coding Agent Guide

This repository implements a trading bot for [Manifold Markets](https://manifold.markets). The project uses Python 3. Most logic lives under `src/` and tests live in `tests/`.

## Repository Layout

- `src/` – Core application modules
  - `core.py` – event loop and strategy orchestration
  - `manifold_client.py` – HTTP/WebSocket API client
  - `logger.py` – CSV-based logging system
  - `strategies/` – individual trading strategies
  - `qualifiers/` – reusable checks applied before proposing a trade
  - `models/` – data models used throughout the codebase
  - `utils/` – helper functions
  - `backtester.py` – log-based backtesting tool
- `config/` – configuration modules (`bet_config.py`, `api_config.py`, `log_config.py`)
- `tests/` – unit tests for strategies, qualifiers, logger and backtester
- `knowledge/` and other `*/knowledge.md` files – developer notes and best practices
- `main.py` – entry point which starts `Core`

## Development Tips

- **Run tests**: `python -m unittest discover tests`
- **Logging**: Logs are written to `logs/<domain>/<event>.csv`. Events derive from dataclasses in `src.logger`. Use `logger.log(event, domain)` to record actions.
- **Configuration**: `BetConfig` centralises thresholds. Values scale with aggressiveness settings. Adjust carefully and keep documentation in sync.
- **Data models**: All models inherit from `BaseModel`. They convert camelCase API fields to snake_case and timestamp numbers to `datetime` objects automatically.
- **Strategies**: Implement `BaseTradingStrategy` and override `qualifiers` plus `propose_bet`. `evaluate_and_propose` already runs qualifiers and handles logging.
- **Qualifiers**: See `src/qualifiers/qualifiers.py`. Each qualifier returns a `QualificationResult` (`PASS`/`FAIL`). Most are asynchronous as they may call `ManifoldClient`.

## ManifoldClient Gotchas

The API client manages both HTTP requests and a WebSocket connection. See `knowledge/manifold_client_logic.md` for details. Key points:

1. **Connection state** – rely on `self.connected` and existence of `self.ws`; do not check `self.ws.closed` or `self.ws.open`.
2. **Error recovery** – set `self.connected = False` on exceptions and use `_reconnect()` to restore the connection. Errors should be logged via `ErrorEvent`.
3. **Keepalive** – the WebSocket uses a manual ping task. Connection parameters are set through `websockets.connect`; use `ping_interval`/`ping_timeout` as shown in the knowledge doc.
4. **Subscriptions** – `self.subscriptions` stores topic->callback mappings. After reconnecting, `_send_subscribe` is called to resubscribe.

## Common Pitfalls

- **Multiple Choice markets** – many qualifiers require `answer_id` when `outcome_type == "MULTIPLE_CHOICE"`. Ensure bets include this field when needed.
- **Counterbet tracking** – `Core` tracks recent counterbets to avoid bidding wars. Pass `recent_counterbets` when qualifying strategies.
- **Logging domain names** – when using the logger, choose a domain string (e.g. `bets`, `errors`). New domains will create new folders under `logs/`.
- **Time handling** – API timestamps are milliseconds since epoch; models convert them to `datetime`. When constructing model instances manually in tests, use `datetime` objects.

## High-Level Flow

1. `Core.run()` connects to Manifold's WebSocket and subscribes to `global/new-bet`.
2. For each incoming bet, `on_bet` fetches the market and recent bets, then calls each strategy's `evaluate_and_propose` method.
3. Strategies run their qualifiers and may return proposed counter bets (`StrategyResult.bets`) or a log event explaining why no bet was placed.
4. If bets are proposed, `Core` places them through `ManifoldClient.place_bet` and logs `PlaceBetEvent`.
5. The logger writes structured CSV rows for later analysis or backtesting.

## Testing

The repository includes unit tests for strategies, qualifiers, the logger and the backtester. Run them with `pytest`. They rely only on the dependencies listed in `requirements.txt` 
