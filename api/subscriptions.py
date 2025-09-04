import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Response

from core.subscription_manager import SubscriptionManager
from database.session import Environment
from utils.response import ApiResponse
from .common import (
    SubscriptionRequest, get_subscription_manager
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/")
async def get_all_subscriptions(response: Response,
                                subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        # 添加环境信息到响应头
        app_env = os.getenv("APP_ENV", Environment.dev)
        response.headers["X-App-Env"] = app_env

        subscriptions = subscription_manager.get_all_subscriptions()
        data = [
            {
                "id": sub.id,
                "type": sub.type,
                "params": sub.params,
                "status": sub.status.value,
                "subscription_id": sub.subscription_id,
                "error_message": sub.error_message,
            }
            for sub in subscriptions
        ]
        return ApiResponse.success(data)
    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_subscriptions(subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        subscriptions = subscription_manager.get_active_subscriptions()
        data = [
            {
                "id": sub.id,
                "type": sub.type,
                "params": sub.params,
                "status": sub.status.value,
                "subscription_id": sub.subscription_id,
                "error_message": sub.error_message,
            }
            for sub in subscriptions
        ]
        return ApiResponse.success(data)
    except Exception as e:
        logger.error(f"Error getting active subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{subscription_id}")
async def get_subscription(subscription_id: str,
                           subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        subscription = subscription_manager.get_subscription(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return ApiResponse.success({
            "id": subscription.id,
            "type": subscription.type,
            "params": subscription.params,
            "status": subscription.status.value,
            "subscription_id": subscription.subscription_id,
            "error_message": subscription.error_message,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_subscription(request: SubscriptionRequest,
                              subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        sub_id = subscription_manager.add_subscription(request.type, request.params)
        subscription = subscription_manager.get_subscription(sub_id)
        if not subscription:
            raise HTTPException(status_code=500, detail="Failed to create subscription")
        return ApiResponse.success({
            "id": subscription.id,
            "type": subscription.type,
            "params": subscription.params,
            "status": subscription.status.value,
            "subscription_id": subscription.subscription_id,
            "error_message": subscription.error_message,
        }, "created")
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{subscription_id}")
async def delete_subscription(subscription_id: str,
                              subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        success = subscription_manager.remove_subscription(subscription_id)
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found or failed to remove")
        return ApiResponse.success({"message": f"Subscription {subscription_id} deleted successfully"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting subscription {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/")
async def clear_all_subscriptions(subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        count = subscription_manager.clear_all_subscriptions()
        return ApiResponse.success({"message": f"Cleared {count} subscriptions"})
    except Exception as e:
        logger.error(f"Error clearing subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_subscription_stats(subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        stats = subscription_manager.get_subscription_stats()
        return ApiResponse.success(stats)
    except Exception as e:
        logger.error(f"Error getting subscription stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{subscription_id}/retry")
async def retry_subscription(subscription_id: str,
                             subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    try:
        existing = subscription_manager.get_subscription(subscription_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Subscription not found")
        # Remove old subscription first
        subscription_manager.remove_subscription(subscription_id)
        # Recreate with same type and params
        new_id = subscription_manager.add_subscription(existing.type, existing.params)
        new_sub = subscription_manager.get_subscription(new_id)
        if not new_sub:
            raise HTTPException(status_code=500, detail="Failed to recreate subscription")
        return ApiResponse.success({
            "id": new_sub.id,
            "type": new_sub.type,
            "params": new_sub.params,
            "status": new_sub.status.value,
            "subscription_id": new_sub.subscription_id,
            "error_message": new_sub.error_message
        }, "retried")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying subscription {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
