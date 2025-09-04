import logging

from fastapi import APIRouter, Depends, HTTPException

from utils.response import ApiResponse
from .common import get_subscription_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/")
async def root():
    return ApiResponse.success({"message": "Hyperliquid Trading System API", "status": "running"})


@router.get("/status")
async def get_system_status(subscription_manager=Depends(get_subscription_manager)):
    try:
        ws_ready = subscription_manager.get_ws_ready_any()
        active_subscriptions = len(subscription_manager.get_active_subscriptions())
        stats = subscription_manager.get_subscription_stats()
        return ApiResponse.success({
            "ws_ready": ws_ready,
            "active_subscriptions": active_subscriptions,
            "subscription_stats": stats
        })
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
