from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from .base_model import BaseModel

@dataclass
class PortfolioMetrics(BaseModel):
    """Represents a user's portfolio metrics from Manifold."""
    
    investment_value: float
    cash_investment_value: float
    balance: float
    cash_balance: float
    spice_balance: float
    total_deposits: float
    total_cash_deposits: float
    loan_total: float
    timestamp: datetime
    user_id: Optional[str] = None
    profit: Optional[float] = None
    daily_profit: Optional[float] = None