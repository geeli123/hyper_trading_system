"""
System status and monitoring router
"""

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Depends

from ..api_server import SystemStatus, SubscriptionStats, get_subscription_manager, get_info, get_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])

@router.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {"message": "Hyperliquid Trading System API", "status": "running"}

@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    subscription_manager = Depends(get_subscription_manager),
    info = Depends(get_info)
):
    """Get overall system status"""
    try:
        ws_ready = getattr(info.ws_manager, 'ws_ready', False)
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

@router.get("/strategy/state")
async def get_strategy_state(
    strategy = Depends(get_strategy)
):
    """Get current strategy state"""
    try:
        if hasattr(strategy, 'strategy_state'):
            return {
                "strategy_state": strategy.strategy_state.name,
                "symbol": getattr(strategy, 'symbol', 'Unknown'),
                "bollinger_bands": {
                    "upper": strategy.bollinger_bands.upper_band,
                    "middle": strategy.bollinger_bands.middle_band,
                    "lower": strategy.bollinger_bands.lower_band,
                    "is_ready": strategy.bollinger_bands.is_ready
                } if hasattr(strategy, 'bollinger_bands') else None
            }
        else:
            return {"strategy_state": "Unknown"}
    except Exception as e:
        logger.error(f"Error getting strategy state: {e}")
        raise HTTPException(status_code=500, detail=str(e))
