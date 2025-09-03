import logging
from typing import Dict, Optional, Any

from fastapi import HTTPException
from pydantic import BaseModel

from core.subscription_manager import SubscriptionManager

logger = logging.getLogger(__name__)


# Pydantic models for API requests/responses
class SubscriptionRequest(BaseModel):
    type: str
    params: Dict[str, Any]


class SubscriptionResponse(BaseModel):
    id: str
    type: str
    params: Dict[str, Any]
    status: str
    subscription_id: Optional[int] = None
    error_message: Optional[str] = None


class SubscriptionStats(BaseModel):
    total: int
    active: int
    inactive: int
    error: int


class SystemStatus(BaseModel):
    ws_ready: bool
    active_subscriptions: int
    subscription_stats: SubscriptionStats


_subscription_manager: Optional[SubscriptionManager] = None


def set_subscription_manager(sm: SubscriptionManager) -> None:
    global _subscription_manager
    _subscription_manager = sm


def get_subscription_manager() -> SubscriptionManager:
    if _subscription_manager is None:
        raise HTTPException(status_code=500, detail="Subscription manager not initialized")
    return _subscription_manager
