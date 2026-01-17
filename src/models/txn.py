from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .base_model import BaseModel


@dataclass
class Txn(BaseModel):
    """Represents a generic transaction (e.g. managram)."""

    id: str
    data: Optional[Dict[str, Any]]
    to_id: str
    token: str
    amount: float
    from_id: str
    to_type: str
    category: str
    from_type: str
    created_time: datetime
    description: str
