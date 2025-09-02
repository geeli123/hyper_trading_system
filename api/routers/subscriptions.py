"""
Subscription management router
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from ..api_server import (
    SubscriptionRequest, SubscriptionResponse, SubscriptionStats,
    get_subscription_manager, get_strategy
)
from ..subscription_manager import SubscriptionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

@router.get("/", response_model=List[SubscriptionResponse])
async def get_all_subscriptions(
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager)
):
    """Get all subscriptions"""
    try:
        subscriptions = subscription_manager.get_all_subscriptions()
        return [
            SubscriptionResponse(
                id=sub.id,
                type=sub.type,
                params=sub.params,
                status=sub.status.value,
                subscription_id=sub.subscription_id,
                error_message=sub.error_message
            )
            for sub in subscriptions
        ]
    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=List[SubscriptionResponse])
async def get_active_subscriptions(
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager)
):
    """Get only active subscriptions"""
    try:
        subscriptions = subscription_manager.get_active_subscriptions()
        return [
            SubscriptionResponse(
                id=sub.id,
                type=sub.type,
                params=sub.params,
                status=sub.status.value,
                subscription_id=sub.subscription_id,
                error_message=sub.error_message
            )
            for sub in subscriptions
        ]
    except Exception as e:
        logger.error(f"Error getting active subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: str,
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager)
):
    """Get specific subscription by ID"""
    try:
        subscription = subscription_manager.get_subscription(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return SubscriptionResponse(
            id=subscription.id,
            type=subscription.type,
            params=subscription.params,
            status=subscription.status.value,
            subscription_id=subscription.subscription_id,
            error_message=subscription.error_message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=SubscriptionResponse)
async def create_subscription(
    request: SubscriptionRequest,
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager)
):
    """Create a new subscription"""
    try:
        sub_id = subscription_manager.add_subscription(request.type, request.params)
        subscription = subscription_manager.get_subscription(sub_id)

        if not subscription:
            raise HTTPException(status_code=500, detail="Failed to create subscription")

        return SubscriptionResponse(
            id=subscription.id,
            type=subscription.type,
            params=subscription.params,
            status=subscription.status.value,
            subscription_id=subscription.subscription_id,
            error_message=subscription.error_message
        )
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager)
):
    """Delete a subscription"""
    try:
        success = subscription_manager.remove_subscription(subscription_id)
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found or failed to remove")

        return {"message": f"Subscription {subscription_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting subscription {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/")
async def clear_all_subscriptions(
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager)
):
    """Clear all subscriptions"""
    try:
        count = subscription_manager.clear_all_subscriptions()
        return {"message": f"Cleared {count} subscriptions"}
    except Exception as e:
        logger.error(f"Error clearing subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=SubscriptionStats)
async def get_subscription_stats(
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager)
):
    """Get subscription statistics"""
    try:
        stats = subscription_manager.get_subscription_stats()
        return SubscriptionStats(**stats)
    except Exception as e:
        logger.error(f"Error getting subscription stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates")
async def get_subscription_templates(
    strategy = Depends(get_strategy)
):
    """Get predefined subscription templates"""
    templates = {
        "candle_1m_eth": {
            "type": "candle",
            "params": {"type": "candle", "coin": "ETH", "interval": "1m"},
            "description": "ETH 1-minute candle data"
        },
        "candle_5m_eth": {
            "type": "candle",
            "params": {"type": "candle", "coin": "ETH", "interval": "5m"},
            "description": "ETH 5-minute candle data"
        },
        "candle_1h_eth": {
            "type": "candle",
            "params": {"type": "candle", "coin": "ETH", "interval": "1h"},
            "description": "ETH 1-hour candle data"
        },
        "candle_1m_btc": {
            "type": "candle",
            "params": {"type": "candle", "coin": "BTC", "interval": "1m"},
            "description": "BTC 1-minute candle data"
        },
        "user_fills": {
            "type": "userFills",
            "params": {"type": "userFills", "user": getattr(strategy, 'address', '')},
            "description": "User fill events"
        },
        "all_mids": {
            "type": "allMids",
            "params": {"type": "allMids"},
            "description": "All mid prices"
        },
        "trades_eth": {
            "type": "trades",
            "params": {"type": "trades", "coin": "ETH"},
            "description": "ETH trade events"
        }
    }
    return templates

@router.post("/templates/{template_name}", response_model=SubscriptionResponse)
async def create_subscription_from_template(
    template_name: str,
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager),
    strategy = Depends(get_strategy)
):
    """Create a subscription from a predefined template"""
    try:
        # Get templates
        templates = {
            "candle_1m_eth": {
                "type": "candle",
                "params": {"type": "candle", "coin": "ETH", "interval": "1m"},
                "description": "ETH 1-minute candle data"
            },
            "candle_5m_eth": {
                "type": "candle",
                "params": {"type": "candle", "coin": "ETH", "interval": "5m"},
                "description": "ETH 5-minute candle data"
            },
            "candle_1h_eth": {
                "type": "candle",
                "params": {"type": "candle", "coin": "ETH", "interval": "1h"},
                "description": "ETH 1-hour candle data"
            },
            "candle_1m_btc": {
                "type": "candle",
                "params": {"type": "candle", "coin": "BTC", "interval": "1m"},
                "description": "BTC 1-minute candle data"
            },
            "user_fills": {
                "type": "userFills",
                "params": {"type": "userFills", "user": getattr(strategy, 'address', '')},
                "description": "User fill events"
            },
            "all_mids": {
                "type": "allMids",
                "params": {"type": "allMids"},
                "description": "All mid prices"
            },
            "trades_eth": {
                "type": "trades",
                "params": {"type": "trades", "coin": "ETH"},
                "description": "ETH trade events"
            }
        }

        if template_name not in templates:
            raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

        template = templates[template_name]
        sub_id = subscription_manager.add_subscription(template["type"], template["params"])
        subscription = subscription_manager.get_subscription(sub_id)

        if not subscription:
            raise HTTPException(status_code=500, detail="Failed to create subscription from template")

        return SubscriptionResponse(
            id=subscription.id,
            type=subscription.type,
            params=subscription.params,
            status=subscription.status.value,
            subscription_id=subscription.subscription_id,
            error_message=subscription.error_message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription from template {template_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
