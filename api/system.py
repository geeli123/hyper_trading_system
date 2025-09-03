import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from .common import SystemStatus, SubscriptionStats, get_subscription_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/", response_model=Dict[str, str])
async def root():
    return {"message": "Hyperliquid Trading System API", "status": "running"}


@router.get("/status", response_model=SystemStatus)
async def get_system_status(subscription_manager = Depends(get_subscription_manager)):
    try:
        ws_ready = subscription_manager.get_ws_ready_any()
        active_subscriptions = len(subscription_manager.get_active_subscriptions())
        stats = subscription_manager.get_subscription_stats()
        return SystemStatus(
            ws_ready=ws_ready,
            active_subscriptions=active_subscriptions,
            subscription_stats=SubscriptionStats(**stats)
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


