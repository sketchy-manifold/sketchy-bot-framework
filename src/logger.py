"""Logging system for the Manifold trading bot."""

import csv
import threading
from dataclasses import dataclass, asdict, field, fields
from datetime import datetime
from typing import Dict, Type, Optional
from pathlib import Path
from src.models import Bet, Market
from config import LogConfig

@dataclass
class LogEvent:
    """Base class for all log events."""
    timestamp: Optional[datetime] = field(default=None, init=False)

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class StratLogEvent(LogEvent):
    """Events that strategies can return"""
    strategy: Optional[str] = field(default=None, init=False)

@dataclass
class ErrorEvent(StratLogEvent):
    """Log event for error conditions."""
    error_type: str
    message: str
    source: str
    context: Optional[str] = None

@dataclass
class PlaceBetEvent(StratLogEvent):
    """Log event for placing a bet."""
    id: str
    user_id: str
    amount: float
    filled_amount: float
    outcome: str
    contract_id: str
    shares: Optional[float] = None
    limit_prob: Optional[float] = None
    expires_at: Optional[datetime] = None
    answer_id: Optional[str] = None
    ws_to_api_ms: Optional[int] = None
    extra_data: Optional[str] = None

    @classmethod
    def from_bet(cls, bet: Bet) -> "PlaceBetEvent":
        """Create a PlaceBetEvent from a :class:`Bet`."""
        return cls(
            id=bet.id,
            contract_id=bet.contract_id,
            user_id=bet.user_id,
            outcome=bet.outcome,
            amount=bet.amount,
            shares=bet.shares,
            limit_prob=bet.limit_prob,
            expires_at=bet.expires_at,
            answer_id=bet.answer_id,
            ws_to_api_ms=None,
            extra_data=None,
        )

@dataclass
class QualificationFailEvent(StratLogEvent):
    """Log event for assessing a bet."""
    id: str
    user_id: str
    amount: float
    shares: float
    outcome: str
    contract_id: str
    fail_reason: str
    url: str
    limit_prob: Optional[float] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[str] = None

    @classmethod
    def from_bet(
        cls,
        bet: Bet,
        market: Market,
        fail_reason: str,
        metadata: str,
    ) -> "QualificationFailEvent":
        """Create a QualificationFailEvent from a :class:`Bet`."""
        return cls(
            id=bet.id,
            contract_id=bet.contract_id,
            user_id=bet.user_id,
            outcome=bet.outcome,
            amount=bet.amount,
            shares=bet.shares,
            limit_prob=bet.limit_prob,
            expires_at=bet.expires_at,
            fail_reason=fail_reason,
            url=market.url,
            metadata=metadata,
        )

@dataclass
class ResponseBetDroppedEvent(StratLogEvent):
    """Log event for exiting strategy without proposing a bet."""
    id: str
    user_id: str
    amount: float
    shares: float
    outcome: str
    contract_id: str
    reason: str
    url: str
    limit_prob: Optional[float] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[str] = None

    @classmethod
    def from_bet(
        cls,
        bet: Bet,
        market: Market,
        reason: str,
        metadata: str,
    ) -> "ResponseBetDroppedEvent":
        """Create a ResponseBetDroppedEvent from a :class:`Bet`."""
        return cls(
            id=bet.id,
            reason=reason,
            contract_id=bet.contract_id,
            user_id=bet.user_id,
            outcome=bet.outcome,
            amount=bet.amount,
            shares=bet.shares,
            limit_prob=bet.limit_prob,
            expires_at=bet.expires_at,
            url=market.url,
            metadata=metadata,
        )

@dataclass
class HousekeepingEvent(StratLogEvent):
    """Log event describing housekeeping actions taken."""
    message: str
    actions: list[str]
    metadata: Optional[str] = None

@dataclass 
class APIEvent(LogEvent):
    """Interaction event with API"""
    type: str
    message: str


class Logger:
    """Thread-safe logger that writes events to domain-specific CSV files."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.log_dir = Path("logs")
            self.log_dir.mkdir(exist_ok=True)
            self._file_handles: Dict[str, Dict[str, tuple[Path, list[str]]]] = {}
            self._initialized = True

    def _rotate_if_needed(
        self,
        domain: str,
        event_name: str,
        csv_path: Path,
        headers: list[str],
    ) -> Path:
        """Rotate log file if it would exceed MAX_LOG_FILE_BYTES."""
        max_bytes = LogConfig.MAX_LOG_FILE_BYTES
        if csv_path.exists() and csv_path.stat().st_size >= max_bytes:
            domain_dir = csv_path.parent
            index = 2
            while True:
                new_path = domain_dir / f"{event_name}_{index}.csv"
                if not new_path.exists() or new_path.stat().st_size < max_bytes:
                    if not new_path.exists():
                        with open(new_path, "w", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow(headers)
                    csv_path = new_path
                    break
                index += 1
            self._file_handles[domain][event_name] = (csv_path, headers)
        return csv_path

    def _ensure_log_file(self, domain: str, event_type: Type[LogEvent]) -> tuple[Path, list[str]]:
        """Ensure the log file exists and return its path and headers."""
        if domain not in self._file_handles:
            self._file_handles[domain] = {}
            
        event_name = event_type.__name__.lower()
        if event_name not in self._file_handles[domain]:
            # Create domain directory if it doesn't exist
            domain_dir = self.log_dir / domain
            domain_dir.mkdir(exist_ok=True)
            
            # Get CSV path and headers
            csv_path = domain_dir / f"{event_name}.csv"
            headers = [f.name for f in fields(event_type)]
            
            # Create file with headers if it doesn't exist
            if not csv_path.exists():
                with open(csv_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
            
            self._file_handles[domain][event_name] = (csv_path, headers)
        else:
            csv_path, headers = self._file_handles[domain][event_name]

        # Rotate file if needed
        csv_path = self._rotate_if_needed(domain, event_name, csv_path, headers)
        self._file_handles[domain][event_name] = (csv_path, headers)

        return self._file_handles[domain][event_name]

    def log(self, event: LogEvent, domain=LogConfig.DEFAULT_LOG_DOMAIN) -> None:
        """Log an event to its domain-specific CSV file.

        Args:
            domain: The logging domain (e.g. "bets", "markets", "errors")
            event: The event to log
        """
        if not LogConfig.ENABLED:
            return
        csv_path, headers = self._ensure_log_file(domain, type(event))

        # Convert event to dict and ensure all fields are present
        event_dict = asdict(event)
        row = [str(event_dict.get(header, '')) for header in headers]
        event_name = type(event).__name__.lower()
        csv_path = self._rotate_if_needed(
            domain,
            event_name,
            csv_path,
            headers,
        )
        self._file_handles[domain][event_name] = (csv_path, headers)

        if LogConfig.VERBOSE:
            print(f"{type(event).__name__}:", str(row))
        
        # Write to CSV file with lock
        with self._lock:
            with open(csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)


# Global logger instance
logger = Logger()
