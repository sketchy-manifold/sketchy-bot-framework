import aiohttp
from typing import Optional, List, Dict, Any, Protocol, TypedDict, Union, Tuple
from datetime import datetime
import time
import asyncio
import websockets
import json
from config import APIConfig
from aiohttp import ClientError
from src.models import User, LiteUser, Market, Bet, Comment, PortfolioMetrics, Txn
from src.logger import logger, APIEvent, ErrorEvent
from copy import deepcopy

class WebSocketMessage(TypedDict):
    type: str
    topic: str
    data: Dict[str, Any]

class SubscriptionCallback(Protocol):
    async def __call__(self, message: WebSocketMessage) -> None:
        pass



class ManifoldClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or APIConfig.API_KEY
        if not self.api_key:
            raise ValueError("API key must be provided either as an argument or via the MANIFOLD_API_KEY environment variable")
        
        # HTTP configuration
        # api_root is the domain without the version prefix. base_url includes
        # the /v0 path for official endpoints.
        self.api_root = "https://api.manifold.markets"
        self.base_url = f"{self.api_root}/v0"
        self.headers = {
            'Authorization': f'Key {self.api_key}',
            'Content-Type': 'application/json'
        }
        self.timeout = 10  # seconds
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.cache_ttl = getattr(APIConfig, 'CACHE_TTL', 0)
        self.cache_ttl_overrides: Dict[str, int] = getattr(APIConfig, 'ENDPOINT_CACHE_TTLS', {})
        self._cache: Dict[str, Tuple[float, Any]] = {}

        # Delay creating the aiohttp session until ``init`` is called. This
        # avoids requiring a running event loop when constructing the client.
        self.session: Optional[aiohttp.ClientSession] = None

        # WebSocket configuration
        self.ws_url = "wss://api.manifold.markets/ws"
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Dict[str, List[SubscriptionCallback]] = {}
        self.connected = False
        self.txid = 0
        
        # Reconnection configuration
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # Initial delay in seconds
        self.max_reconnect_delay = 600  # Maximum delay between attempts
        self._is_reconnecting = False

        # Manual ping configuration
        self.ping_interval_seconds = 30
        self._ping_task: Optional[asyncio.Task] = None

    async def init(self) -> None:
        """Create the underlying :class:`aiohttp.ClientSession` if needed."""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def close(self) -> None:
        if self.session is not None and not self.session.closed:
            await self.session.close()

    def _cleanup_cache(self) -> None:
        """Remove expired items from the HTTP cache."""
        if self.cache_ttl <= 0 and not self.cache_ttl_overrides:
            return
        now = time.time()
        expired_keys = []
        for k, (ts, _) in self._cache.items():
            endpoint = k.split(':', 1)[0]
            ttl = self.cache_ttl_overrides.get(endpoint, self.cache_ttl)
            if ttl <= 0 or now - ts >= ttl:
                expired_keys.append(k)
        for k in expired_keys:
            del self._cache[k]

    def _get_endpoint_url(self, endpoint: str, undocumented: bool = False) -> str:
        """Get the full URL for an endpoint.

        If ``undocumented`` is True, the endpoint is assumed to not include the
        version prefix (``/v0``).
        """
        base = self.api_root if undocumented else self.base_url
        return f"{base}/{endpoint}"

    def _handle_error(self, response) -> None:
        """Handle API errors."""
        try:
            error_data = response.json()
            error_message = error_data.get('message', 'Unknown error')
        except ValueError:
            error_message = response.text
        
        raise Exception(f"API error ({response.status_code}): {error_message} | {response.text}")

    async def _make_request(
            self,
            endpoint: str,
            params: Optional[Dict] = None,
            is_get: bool = True,
            undocumented: bool = False,
    ) -> Dict:
        """Make a GET or POST request to the Manifold API with retry mechanism.

        Args:
            endpoint: The relative API endpoint path
            params: Query or JSON parameters depending on the request type
            is_get: Whether to use GET (True) or POST (False)
            undocumented: Whether this endpoint omits the ``/v0`` prefix
        """
        await self.init()
        url = self._get_endpoint_url(endpoint, undocumented)
        cache_key = None
        ttl = self.cache_ttl_overrides.get(endpoint, self.cache_ttl)
        if is_get and ttl > 0:
            self._cleanup_cache()
            key_data = json.dumps(params, sort_keys=True, default=str) if params else ""
            cache_key = f"{endpoint}:{key_data}"
            cached = self._cache.get(cache_key)
            if cached and time.time() - cached[0] < ttl:
                return deepcopy(cached[1])
            if cached:
                del self._cache[cache_key]
        for attempt in range(self.max_retries):
            try:
                if is_get:
                    async with self.session.get(url, params=params, timeout=self.timeout) as response:
                        if response.status >= 400:
                            text = await response.text()
                            raise Exception(f"API error ({response.status}): {text}")
                        data = await response.json()
                else:
                    async with self.session.post(url, json=params, timeout=self.timeout) as response:
                        if response.status >= 400:
                            text = await response.text()
                            raise Exception(f"API error ({response.status}): {text}")
                        data = await response.json()
                if is_get and cache_key is not None and ttl > 0:
                    self._cache[cache_key] = (time.time(), data)
                return data
            except ClientError as e:
                if attempt == self.max_retries - 1:
                    raise Exception(f"API request failed after {self.max_retries} attempts: {str(e)}")
                await asyncio.sleep(self.retry_delay)

    async def get_user(self, username: str) -> User:
        """Get user information by username."""
        data = await self._make_request(f'user/{username}')
        return User.from_dict(data)

    async def get_user_lite(self, username: str) -> LiteUser:
        """Get basic user display information by username."""
        data = await self._make_request(f'user/{username}/lite')
        return LiteUser.from_dict(data)

    async def get_user_by_id(self, user_id: str) -> User:
        """Get a user by their unique ID."""
        data = await self._make_request(f'user/by-id/{user_id}')
        return User.from_dict(data)

    async def get_user_by_id_lite(self, user_id: str) -> LiteUser:
        """Get basic user display information by ID."""
        data = await self._make_request(f'user/by-id/{user_id}/lite')
        return LiteUser.from_dict(data)

    async def get_me(self) -> User:
        """Get the authenticated user's information."""
        data = await self._make_request('me')
        return User.from_dict(data)

    async def get_users(self, limit: int = 100, before: Optional[int] = None) -> List[LiteUser]:
        """Get a list of users."""
        params = {'limit': limit}
        if before:
            params['before'] = before
        data = await self._make_request('users', params)
        return [LiteUser.from_dict(user) for user in data]

    async def get_market(self, market_id: str) -> Market:
        """Get a single market."""
        data = await self._make_request(f'market/{market_id}')
        return Market.from_dict(data)

    async def get_market_probability(
        self,
        market_id: str,
        answer_id: Optional[str] = None
    ) -> Union[float, Dict[str, float]]:
        """Get the current probability for a market or specific answer.
        
        Args:
            market_id: The ID of the market
            answer_id: Optional. For MULTIPLE_CHOICE markets, the specific answer ID to get probability for.
            
        Returns:
            float: For BINARY markets or when answer_id is provided
            Dict[str, float]: For MULTIPLE_CHOICE markets when answer_id is not provided, mapping answer IDs to probabilities
        """
        response = await self._make_request(f'market/{market_id}/prob')
        
        if 'prob' in response:  # Binary market
            return response['prob']
        elif 'answerProbs' in response:  # Multiple choice market
            if answer_id:
                if answer_id not in response['answerProbs']:
                    raise ValueError(f"Answer ID {answer_id} not found in market {market_id}")
                return response['answerProbs'][answer_id]
            return response['answerProbs']
        else:
            raise ValueError(f"Unexpected probability response format for market {market_id}")

    async def get_market_positions(self, market_id: str,
                           order: Optional[str] = 'profit',
                           top: Optional[int] = None,
                           bottom: Optional[int] = None,
                           user_id: Optional[str] = None,
                           answer_id: Optional[str] = None) -> List[Dict]:
        """Get positions in a market.
        
        Args:
            market_id: The ID of the market
            order: Optional. 'shares' or 'profit' (default). The field to order results by
            top: Optional. The number of top positions (ordered by order) to return
            bottom: Optional. The number of bottom positions (ordered by order) to return
            user_id: Optional. The user ID to query by. If provided, only the position for this user will be returned
            answer_id: Optional. The answer ID to query by. If provided, only the positions for this answer will be returned
            
        Returns:
            List of position dictionaries
        """
        params = {}
        if order:
            params['order'] = order
        if top:
            params['top'] = top
        if bottom:
            params['bottom'] = bottom
        if user_id:
            params['userId'] = user_id
        if answer_id:
            params['answerId'] = answer_id
        
        return await self._make_request(f'market/{market_id}/positions', params)

    async def get_markets(self,
                   limit: Optional[int] = 500,
                   before: Optional[str] = None,
                   sort: Optional[str] = 'created-time',
                   order: Optional[str] = 'desc',
                   user_id: Optional[str] = None,
                   group_id: Optional[str] = None) -> List[Market]:
        """List all markets, ordered by creation date descending by default.
        
        Args:
            limit: Optional. How many markets to return (max 1000, default 500)
            before: Optional. The ID of the market before which the list will start
            sort: Optional. One of 'created-time', 'updated-time', 'last-bet-time', 'last-comment-time'
            order: Optional. One of 'asc' or 'desc'
            user_id: Optional. Include only markets created by this user
            group_id: Optional. Include only markets tagged with this topic
        """
        params = {}
        if limit:
            params['limit'] = limit
        if before:
            params['before'] = before
        if sort:
            params['sort'] = sort
        if order:
            params['order'] = order
        if user_id:
            params['userId'] = user_id
        if group_id:
            params['groupId'] = group_id
            
        markets = await self._make_request('markets', params)
        return [Market.from_dict(market) for market in markets]

    async def get_bets(self,
                limit: int = 1000,
                before: Optional[str] = None,
                after: Optional[str] = None,
                contract_id: Optional[Union[str, List[str]]] = None,
                user_id: Optional[str] = None,
                username: Optional[str] = None,
                contract_slug: Optional[str] = None,
                before_time: Optional[int] = None,
                after_time: Optional[int] = None,
                kinds: Optional[List[str]] = None,
                order: Optional[str] = 'desc') -> List[Bet]:
        """Get a list of bets, ordered by creation date descending by default.
        
        Args:
            limit: Optional. How many bets to return (max 1000)
            before: Optional. Include only bets created before the bet with this ID
            after: Optional. Include only bets created after the bet with this ID
            contract_id: Optional. Include only bets on the market(s) with this ID/these IDs
            user_id: Optional. Include only bets by the user with this ID
            username: Optional. Include only bets by the user with this username
            contract_slug: Optional. Include only bets on the market with this slug
            before_time: Optional. Include only bets created before this timestamp
            after_time: Optional. Include only bets created after this timestamp
            kinds: Optional. Specifies subsets of bets to return (e.g. ['open-limit'])
            order: Optional. 'asc' or 'desc' (default)
        """
        params = {}
        if limit:
            params['limit'] = limit
        if before:
            params['before'] = before
        if after:
            params['after'] = after
        if contract_id:
            params['contractId'] = contract_id
        if user_id:
            params['userId'] = user_id
        if username:
            params['username'] = username
        if contract_slug:
            params['contractSlug'] = contract_slug
        if before_time:
            params['beforeTime'] = before_time
        if after_time:
            params['afterTime'] = after_time
        if kinds:
            params['kinds'] = kinds
        if order:
            params['order'] = order
            
        bets = await self._make_request('bets', params)
        return [Bet.from_dict(bet) for bet in bets]

    async def get_user_markets(self, username: str) -> List[Market]:
        """Get markets created by a specific user.
        
        This is more efficient than the previous implementation as it uses
        the markets endpoint directly with userId filter.
        """
        user = await self.get_user(username)
        return await self.get_markets(user_id=user.id)

    async def get_comments(self,
                    limit: int = 100,
                    before: Optional[str] = None,
                    contract_id: Optional[str] = None,
                    contract_slug: Optional[str] = None,
                    user_id: Optional[str] = None,
                    parent_id: Optional[str] = None,
                    is_deleted: Optional[bool] = None,
                    is_hidden: Optional[bool] = None,
                    is_spam: Optional[bool] = None,
                    is_moderated: Optional[bool] = None,
                    page: Optional[int] = None) -> List[Comment]:
        """Get a list of comments. Must specify a contract or user."""
        params = {'limit': limit}
        if before:
            params['before'] = before
        if contract_id:
            params['contractId'] = contract_id
        if contract_slug:
            params['contractSlug'] = contract_slug
        if user_id:
            params['userId'] = user_id
        if parent_id:
            params['parentId'] = parent_id
        if is_deleted is not None:
            params['isDeleted'] = is_deleted
        if is_hidden is not None:
            params['isHidden'] = is_hidden
        if is_spam is not None:
            params['isSpam'] = is_spam
        if is_moderated is not None:
            params['isModerated'] = is_moderated
        if page:
            params['page'] = page
        comments = await self._make_request('comments', params)
        return [Comment.from_dict(comment) for comment in comments]

    async def get_market_by_slug(self, slug: str) -> Market:
        """Get information about a single market by slug (the portion of the URL path after the username)."""
        data = await self._make_request(f'slug/{slug}')
        return Market.from_dict(data)
    
    ### POST

    # Forces limit orders for now
    async def place_bet(
        self,
        amount: int,
        contractId: str,
        outcome: str,
        limitProb: float,
        expiresMillisAfter: int,
        dryRun: bool = False,
        answerId: Optional[str] = None,
    ) -> Bet:
        params = {
            "amount": amount,
            "contractId": contractId,
            "outcome": outcome,
            "limitProb": limitProb,
            "expiresMillisAfter": expiresMillisAfter,
            "dryRun": dryRun,
        }

        if answerId:
            params['answerId'] = answerId

        bet = await self._make_request('bet', params, is_get=False)
        return Bet.from_dict(bet)

    async def connect(self, is_reconnect: bool = False) -> None:
        """Connect to the WebSocket server."""
        if not is_reconnect and self._is_reconnecting:
            logger.log(APIEvent("connect_skipped", "Connection attempt skipped, reconnect already in progress."))
            return

        try:
            # Cancel any existing ping task
            if self._ping_task:
                try:
                    self._ping_task.cancel()
                    await self._ping_task
                except asyncio.CancelledError:
                    pass
                self._ping_task = None

            if self.ws:
                try:
                    await self.ws.close()
                except Exception:
                    pass
            self.ws = None
            self.connected = False

            logger.log(APIEvent("connect_attempt", f"Attempting to connect to {self.ws_url} (is_reconnect={is_reconnect})"))
            # Removed ping_interval and ping_timeout as we're implementing manual ping
            self.ws = await websockets.connect(self.ws_url)
            self.connected = True
            logger.log(APIEvent("connect_successful", f"Successfully connected to {self.ws_url}"))
            
            # Start the manual ping loop
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            # Resubscribe to any existing subscriptions
            if self.subscriptions:
                topics = list(self.subscriptions.keys())
                await self._send_subscribe(topics)

        except Exception as e:
            self.connected = False
            log_message = f"WebSocket connection failed during {'reconnect' if is_reconnect else 'initial connect'}"
            logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context=log_message))
            raise

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        logger.log(APIEvent("disconnect_called", "Disconnect requested."))
        self._is_reconnecting = False
        self.connected = False
        
        # Cancel the ping task if it exists
        if self._ping_task:
            try:
                self._ping_task.cancel()
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None
        
        if self.ws:
            try:
                await self.ws.close()
                logger.log(APIEvent("websocket_closed", "WebSocket closed during disconnect."))
            except Exception as e:
                logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context="Error closing WebSocket during disconnect"))
        self.ws = None
        
        logger.log(APIEvent("disconnect_complete", f"Disconnected from {self.ws_url}"))

    async def _ping_loop(self) -> None:
        """Send periodic manual pings to keep connection alive."""
        logger.log(APIEvent("ping_loop_started", "Manual ping loop started."))
        
        while self.connected and self.ws:
            try:
                message = {
                    "type": "ping",
                    "txid": self.txid
                }
                self.txid += 1
                await self.ws.send(json.dumps(message))
                logger.log(APIEvent("manual_ping_sent", f"Sent manual ping with txid {self.txid-1}"))
                
                await asyncio.sleep(self.ping_interval_seconds)
                
            except websockets.exceptions.ConnectionClosed as e:
                logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context="Manual ping failed: ConnectionClosed"))
                self.connected = False
                break
            except Exception as e:
                logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context="Manual ping failed with unexpected error"))
                self.connected = False
                break

        logger.log(APIEvent("ping_loop_ended", "Manual ping loop ended."))

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the WebSocket server with exponential backoff."""
        if self._is_reconnecting:
            logger.log(APIEvent("reconnect_attempt_skipped", "Reconnect already in progress."))
            return

        self._is_reconnecting = True
        self.connected = False
        
        # Cancel any existing ping task
        if self._ping_task:
            try:
                self._ping_task.cancel()
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws = None

        logger.log(APIEvent("reconnect_initiated", "Attempting to reconnect to WebSocket."))
        
        current_attempt = 0
        while current_attempt < self.max_reconnect_attempts and not self.connected:
            current_attempt += 1
            delay = min(self.reconnect_delay * (2 ** (current_attempt - 1)), self.max_reconnect_delay)
            logger.log(APIEvent("reconnect_attempt", f"Reconnect attempt {current_attempt}/{self.max_reconnect_attempts}. Waiting for {delay}s."))
            await asyncio.sleep(delay)
            try:
                await self.connect(is_reconnect=True)
                if self.connected:
                    logger.log(APIEvent("reconnect_successful", "Successfully reconnected to WebSocket."))
                    self._is_reconnecting = False
                    return
            except Exception as e:
                logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context=f"Reconnect attempt {current_attempt} failed"))
        
        if not self.connected:
            logger.log(ErrorEvent(error_type=RuntimeError, message=f"Failed to reconnect after {self.max_reconnect_attempts} attempts.", source=__class__, context="Max reconnect attempts reached"))
        self._is_reconnecting = False

    async def listen(self) -> None:
        """Listen for incoming messages and route them to callbacks."""
        if not self.connected:
            logger.log(APIEvent("listen_attempt_reconnect", "Not connected at listen start. Attempting initial connect/reconnect."))
            await self._reconnect()
            if not self.connected:
                logger.log(ErrorEvent(error_type=RuntimeError, message="Cannot listen, WebSocket not connected after initial reconnect attempt.", source=__class__))
                return

        while True:
            if not self.connected or not self.ws:
                logger.log(APIEvent("listen_loop_disconnected", "WebSocket disconnected. Attempting to reconnect."))
                await self._reconnect()
                if not self.connected:
                    logger.log(ErrorEvent(error_type=RuntimeError, message="Failed to reconnect. Stopping listen.", source=__class__))
                    return

            try:
                message = await self.ws.recv()
                try:
                    data = json.loads(message)
                    
                    # Handle acknowledgments
                    if data["type"] == "ack":
                        # Log the acknowledgment
                        ack_txid = data.get("txid")
                        logger.log(APIEvent("manual_ping_ack_received", f"Received ack for txid {ack_txid if ack_txid is not None else 'unknown'}"))
                        continue
                        
                    # Handle broadcasts
                    if data["type"] == "broadcast":
                        topic = data["topic"]
                        if topic in self.subscriptions:
                            message_data = WebSocketMessage(
                                type=data["type"],
                                topic=topic,
                                data=data["data"]
                            )
                            for callback in self.subscriptions[topic]:
                                try:
                                    await callback(message_data)
                                except Exception as e:
                                    logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context=f"Callback error for topic {topic}: {e}"))

                except json.JSONDecodeError as e:
                    logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context=f"Failed to parse message: {message}"))
                except Exception as e:
                    logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context=f"Error parsing message: {message}"))

            except websockets.exceptions.ConnectionClosed as e:
                logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context=f"Websocket connection closed in listen. Code: {e.code}, Reason: {e.reason}"))
                self.connected = False
            except Exception as e:
                logger.log(ErrorEvent(error_type=type(e), message=str(e), source=__class__, context=f"Unexpected Websocket error in listen's recv"))
                self.connected = False

    async def subscribe(self, topics: Union[str, List[str]], callback: SubscriptionCallback) -> None:
        """Subscribe to topics and register callback."""
        if isinstance(topics, str):
            topics = [topics]
            
        for topic in topics:
            if topic not in self.subscriptions:
                self.subscriptions[topic] = []
            self.subscriptions[topic].append(callback)

        if self.connected:
            await self._send_subscribe(topics)
            logger.log(APIEvent("subscribe", f"Subscribed to topics: {str(topics)}"))

    async def _send_subscribe(self, topics: List[str]) -> None:
        """Send subscription message to server."""
        if not self.ws:
            raise Exception("Not connected to WebSocket server")
            
        message = {
            "type": "subscribe",
            "txid": self.txid,
            "topics": topics
        }
        self.txid += 1
        await self.ws.send(json.dumps(message))

    async def unsubscribe(self, topics: Union[str, List[str]]) -> None:
        """Unsubscribe from topics."""
        if isinstance(topics, str):
            topics = [topics]
            
        if not self.ws:
            raise Exception("Not connected to WebSocket server")

        message = {
            "type": "unsubscribe",
            "txid": self.txid,
            "topics": topics
        }
        self.txid += 1
        await self.ws.send(json.dumps(message))
        
        for topic in topics:
            self.subscriptions.pop(topic, None)

    async def get_user_portfolio(self, user_id: str) -> PortfolioMetrics:
        """Get a user's live portfolio metrics.
        
        Args:
            user_id: The ID of the user.
            
        Returns:
            PortfolioMetrics: The user's portfolio metrics.
        """
        result = await self._make_request('get-user-portfolio', {'userId': user_id})
        return PortfolioMetrics.from_dict(result)
    
    async def get_user_portfolio_history(self, user_id: str, period: str) -> List[PortfolioMetrics]:
        """Get a user's portfolio metrics.
        
        Args:
            user_id: The ID of the user.
            period: The time period for the portfolio history. Enum values: 'daily', 'weekly', 'monthly', 'allTime'.
            
        Returns:
            PortfolioMetrics: Array of PortfolioMetrics
        """
        result = await self._make_request('get-user-portfolio-history', {'userId': user_id, 'period': period})
        return [PortfolioMetrics.from_dict(p) for p in result]

    async def send_managram(self, to_ids: List[str], amount: int, message: str = "") -> Dict:
        """Send mana to other users via managram."""
        params = {
            'toIds': to_ids,
            'amount': amount,
            'message': message,
        }
        return await self._make_request('managram', params, is_get=False)

    async def request_loan(self) -> Dict:
        """Request the daily mana loan."""
        # This endpoint is not part of the documented API and omits the `/v0`
        # prefix.
        return await self._make_request('request-loan', undocumented=True)

    async def get_transactions(
        self,
        token: Optional[str] = None,
        offset: Optional[int] = None,
        limit: int = 100,
        before: Optional[int] = None,
        after: Optional[int] = None,
        to_id: Optional[str] = None,
        from_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Txn]:
        """Retrieve a list of transactions."""
        params: Dict[str, Any] = {'limit': limit}
        if token is not None:
            params['token'] = token
        if offset is not None:
            params['offset'] = offset
        if before is not None:
            params['before'] = before
        if after is not None:
            params['after'] = after
        if to_id is not None:
            params['toId'] = to_id
        if from_id is not None:
            params['fromId'] = from_id
        if category is not None:
            params['category'] = category

        result = await self._make_request('txns', params)
        return [Txn.from_dict(txn) for txn in result]

# Example usage remains the same
if __name__ == "__main__":
    client = ManifoldClient()
    
    # Get your own user info
    print("\nYour User Info:")
    user_info = client.get_user("Dagonet")
    print(f"Name: {user_info.name}")
    print(f"Balance: ${user_info.balance:.2f}")
    
    # Get your markets
    print("\nYour Markets:")
    markets = client.get_user_markets("Dagonet")
    for market in markets:
        print(f"\nMarket: {market.question}")
        print(f"URL: {market.url}")
        print(f"Created: {datetime.fromtimestamp(market.created_time/1000)}")
        if isinstance(market.pool, (int, float)):
            print(f"Pool: ${market.pool:.2f}")
        else:
            print("Pool: N/A")
        print(f"Probability: {market.probability*100:.1f}%")
