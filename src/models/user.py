from typing import Optional, List, Dict
from dataclasses import dataclass, field
from datetime import datetime
from .base_model import BaseModel

@dataclass
class User(BaseModel):
    """Represents a Manifold user."""
    
    id: str
    name: str
    username: str
    avatar_url: str
    created_time: datetime = None
    
    # Optional fields
    signup_bonus_paid: Optional[bool] = None
    id_verified: Optional[bool] = None
    last_bet_time: Optional[datetime] = None
    verified_phone: Optional[bool] = None
    creator_traders: Optional[Dict[str, int]] = None
    next_loan_cached: Optional[float] = None
    last_updated_time: Optional[datetime] = None
    has_seen_loan_modal: Optional[bool] = None
    is_advanced_trader: Optional[bool] = None
    is_banned_from_mana: Optional[bool] = None
    is_banned_from_posting: Optional[bool] = None
    referred_by_user_id: Optional[str] = None
    kyc_document_status: Optional[str] = None
    streak_forgiveness: Optional[int] = None
    temp_loan_debit_dec8: Optional[float] = None
    sweepstakes5k_limit: Optional[bool] = None
    follower_count_cached: Optional[int] = None
    sweepstakes_verified: Optional[bool] = None
    current_betting_streak: Optional[int] = None
    is_banned_from_sweepcash: Optional[bool] = None
    sweepstakes_verified_time: Optional[datetime] = None
    resolved_profit_adjustment: Optional[float] = None
    fraction_resolved_correctly: Optional[float] = None
    has_seen_contract_follow_modal: Optional[bool] = None
    balance: Optional[float] = None
    cash_balance: Optional[float] = None
    spice_balance: Optional[float] = None
    total_deposits: Optional[float] = None
    total_cash_deposits: Optional[float] = None
    url: Optional[str] = None
    is_bot: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_trustworthy: Optional[bool] = None
    should_show_welcome: Optional[bool] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    banner_url: Optional[str] = None
    discord_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    achievements: Optional[List[Dict]] = field(default_factory=list)
    opt_out_bet_warnings: Optional[bool] = None
    purchased_mana: Optional[int] = None
    referred_by_group_id: Optional[str] = None
    purchased_sweepcash: Optional[bool] = None
    referred_by_contract_id: Optional[str] = None
    free_questions_created: Optional[int] = None
    kyc_last_attempt_time: Optional[str] = None
    seen_streak_modal: Optional[bool] = None
    used_referral_code: Optional[bool] = None
    from_love: Optional[bool] = None
    user_deleted: Optional[bool] = None
    kyc_status: Optional[str] = None
    last_app_review_time: Optional[datetime] = None
