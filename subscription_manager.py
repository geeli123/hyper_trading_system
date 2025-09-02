"""
Subscription Manager for Hyperliquid Trading System

Manages WebSocket subscriptions and provides API for controlling them.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any

from hyperliquid.info import Info

logger = logging.getLogger(__name__)


class SubscriptionStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class SubscriptionInfo:
    """Information about a subscription"""
    id: str
    type: str
    params: Dict[str, Any]
    status: SubscriptionStatus
    subscription_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class SubscriptionManager:
    """Manages WebSocket subscriptions for the trading system"""

    def __init__(self, info: Info, strategy_callback):
        self.info = info
        self.strategy_callback = strategy_callback
        self.subscriptions: Dict[str, SubscriptionInfo] = {}
        self._subscription_counter = 0

    def _generate_subscription_id(self) -> str:
        """Generate a unique subscription ID"""
        self._subscription_counter += 1
        return f"sub_{self._subscription_counter}"

    def add_subscription(self, subscription_type: str, params: Dict[str, Any]) -> str:
        """Add a new subscription"""
        sub_id = self._generate_subscription_id()

        try:
            # Create subscription info
            subscription_info = SubscriptionInfo(
                id=sub_id,
                type=subscription_type,
                params=params,
                status=SubscriptionStatus.ACTIVE
            )

            # Subscribe to Hyperliquid
            subscription_id = self.info.subscribe(params, self.strategy_callback)
            subscription_info.subscription_id = subscription_id

            # Store subscription
            self.subscriptions[sub_id] = subscription_info

            logger.info(f"Added subscription {sub_id}: {subscription_type} with params {params}")
            return sub_id

        except Exception as e:
            logger.error(f"Failed to add subscription {sub_id}: {e}")
            subscription_info = SubscriptionInfo(
                id=sub_id,
                type=subscription_type,
                params=params,
                status=SubscriptionStatus.ERROR,
                error_message=str(e)
            )
            self.subscriptions[sub_id] = subscription_info
            return sub_id

    def remove_subscription(self, sub_id: str) -> bool:
        """Remove a subscription"""
        if sub_id not in self.subscriptions:
            logger.warning(f"Subscription {sub_id} not found")
            return False

        subscription = self.subscriptions[sub_id]

        try:
            if subscription.subscription_id is not None:
                # Unsubscribe from Hyperliquid
                self.info.unsubscribe(subscription.params, subscription.subscription_id)

            # Remove from our tracking
            del self.subscriptions[sub_id]

            logger.info(f"Removed subscription {sub_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove subscription {sub_id}: {e}")
            subscription.status = SubscriptionStatus.ERROR
            subscription.error_message = str(e)
            return False

    def get_subscription(self, sub_id: str) -> Optional[SubscriptionInfo]:
        """Get subscription information by ID"""
        return self.subscriptions.get(sub_id)

    def get_all_subscriptions(self) -> List[SubscriptionInfo]:
        """Get all subscriptions"""
        return list(self.subscriptions.values())

    def get_active_subscriptions(self) -> List[SubscriptionInfo]:
        """Get only active subscriptions"""
        return [sub for sub in self.subscriptions.values()
                if sub.status == SubscriptionStatus.ACTIVE]

    def get_subscriptions_by_type(self, subscription_type: str) -> List[SubscriptionInfo]:
        """Get subscriptions by type"""
        return [sub for sub in self.subscriptions.values()
                if sub.type == subscription_type]

    def update_subscription_status(self, sub_id: str, status: SubscriptionStatus,
                                   error_message: Optional[str] = None):
        """Update subscription status"""
        if sub_id in self.subscriptions:
            self.subscriptions[sub_id].status = status
            if error_message:
                self.subscriptions[sub_id].error_message = error_message

    def clear_all_subscriptions(self) -> int:
        """Clear all subscriptions"""
        count = 0
        sub_ids = list(self.subscriptions.keys())

        for sub_id in sub_ids:
            if self.remove_subscription(sub_id):
                count += 1

        logger.info(f"Cleared {count} subscriptions")
        return count

    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics"""
        total = len(self.subscriptions)
        active = len([s for s in self.subscriptions.values()
                      if s.status == SubscriptionStatus.ACTIVE])
        inactive = len([s for s in self.subscriptions.values()
                        if s.status == SubscriptionStatus.INACTIVE])
        error = len([s for s in self.subscriptions.values()
                     if s.status == SubscriptionStatus.ERROR])

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "error": error
        }
