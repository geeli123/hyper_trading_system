"""
Subscription Manager for Hyperliquid Trading System

Manages WebSocket subscriptions and provides API for controlling them.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable
from typing import Dict, List, Optional, Any

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
    """Manages WebSocket subscriptions for the trading system.
    Lazily creates per-account contexts (info/exchange/strategy) when a subscription is added.
    """

    def __init__(self, strategy_factory: Callable, environment):
        self.strategy_factory = strategy_factory
        self.environment = environment
        self.subscriptions: Dict[str, SubscriptionInfo] = {}
        self._subscription_counter = 0
        self._contexts: Dict[str, Dict[str, Any]] = {}
        # Lazy import to avoid circular deps
        try:
            from database.session import SessionLocal  # type: ignore
            from database.models import StrategyRecord  # type: ignore
            self._SessionLocal = SessionLocal
            self._StrategyRecord = StrategyRecord
        except Exception:
            self._SessionLocal = None
            self._StrategyRecord = None

    def _generate_subscription_id(self) -> str:
        """Generate a unique subscription ID"""
        self._subscription_counter += 1
        return f"sub_{self._subscription_counter}"

    def add_strategy_subscriptions(self, strategy_params: Dict[str, Any]) -> Dict[str, str]:
        """Add subscriptions for a strategy (both candle and userFills)
        
        Returns:
            Dict containing subscription IDs: {"candle": "sub_1", "userFills": "sub_2"}
        """
        try:
            # Resolve dynamic account alias to concrete address for 'user' fields
            try:
                from database.session import SessionLocal  # type: ignore
                from database.models import Account  # type: ignore
                if strategy_params is not None:
                    account_alias = strategy_params.get("account_alias")
                    # If stream requires a user and not provided, map alias/address to 'user'
                    if account_alias and ("user" not in strategy_params):
                        user_secret_key = None
                        db = SessionLocal()
                        try:
                            acc = db.query(Account).filter_by(alias=account_alias).first()
                            if acc:
                                user_secret_key = acc.secret_key
                        finally:
                            db.close()
                        if user_secret_key:
                            strategy_params = {**strategy_params, "user_secret_key": user_secret_key}
                            strategy_params = {**strategy_params, "user": acc.account_address}
            except Exception as e:
                logger.warning(f"Dynamic account resolution skipped: {e}")

            # Ensure per-account context
            target_user = strategy_params.get("user")
            if not target_user:
                raise ValueError("Missing 'user' in params; provide account_alias or account_address to resolve")

            if target_user not in self._contexts:
                # Build context for this user
                from utils import exchange_utils  # local import
                # pull secret_key/api wallet from Account/Config inside setup
                address, info, exchange = exchange_utils.setup(
                    skip_ws=False,
                    environment=self.environment,
                    secret_key=strategy_params.get("user_secret_key"),
                    account_address=target_user
                )
                strategy = self.strategy_factory(exchange, info, address, strategy_params.get("coin"))
                self._contexts[target_user] = {
                    'info': info,
                    'exchange': exchange,
                    'strategy': strategy,
                }

            ctx = self._contexts[target_user]

            # Create both subscriptions for this strategy
            subscription_ids = {}
            
            # Create candle subscription
            candle_sub_id = self._generate_subscription_id()
            candle_params = {**strategy_params, "type": "candle"}
            candle_hyperliquid_id = ctx['info'].subscribe(candle_params, ctx['strategy'].process_message)
            
            candle_subscription = SubscriptionInfo(
                id=candle_sub_id,
                type="candle",
                params=candle_params,
                status=SubscriptionStatus.ACTIVE,
                subscription_id=candle_hyperliquid_id
            )
            self.subscriptions[candle_sub_id] = candle_subscription
            subscription_ids["candle"] = candle_sub_id
            logger.info(f"Added candle subscription {candle_sub_id} (HL ID: {candle_hyperliquid_id})")
            
            # Create userFills subscription
            userfills_sub_id = self._generate_subscription_id()
            userfills_params = {**strategy_params, "type": "userFills"}
            userfills_hyperliquid_id = ctx['info'].subscribe(userfills_params, ctx['strategy'].process_message)
            
            userfills_subscription = SubscriptionInfo(
                id=userfills_sub_id,
                type="userFills",
                params=userfills_params,
                status=SubscriptionStatus.ACTIVE,
                subscription_id=userfills_hyperliquid_id
            )
            self.subscriptions[userfills_sub_id] = userfills_subscription
            subscription_ids["userFills"] = userfills_sub_id
            logger.info(f"Added userFills subscription {userfills_sub_id} (HL ID: {userfills_hyperliquid_id})")

            return subscription_ids

        except Exception as e:
            logger.error(f"Failed to add strategy subscriptions: {e}")
            raise RuntimeError(e.args[0])

    def add_subscription(self, subscription_type: str, params: Dict[str, Any]) -> str:
        """Add a single subscription (legacy method for compatibility)"""
        # This method is kept for backward compatibility but should be deprecated
        # in favor of add_strategy_subscriptions for strategy-related subscriptions
        sub_id = self._generate_subscription_id()

        try:
            # Resolve user information
            target_user = params.get("user")
            if not target_user:
                raise ValueError("Missing 'user' in params; provide account_alias or account_address to resolve")

            if target_user not in self._contexts:
                from utils import exchange_utils
                address, info, exchange = exchange_utils.setup(
                    skip_ws=False,
                    environment=self.environment,
                    secret_key=params.get("user_secret_key"),
                    account_address=target_user
                )
                strategy = self.strategy_factory(exchange, info, address, params.get("coin"))
                self._contexts[target_user] = {
                    'info': info,
                    'exchange': exchange,
                    'strategy': strategy,
                }

            ctx = self._contexts[target_user]
            
            # Subscribe to Hyperliquid
            hyperliquid_subscription_id = ctx['info'].subscribe(params, ctx['strategy'].process_message)
            
            subscription_info = SubscriptionInfo(
                id=sub_id,
                type=subscription_type,
                params=params,
                status=SubscriptionStatus.ACTIVE,
                subscription_id=hyperliquid_subscription_id
            )

            self.subscriptions[sub_id] = subscription_info
            logger.info(f"Added single subscription {sub_id} (HL ID: {hyperliquid_subscription_id})")
            
            return sub_id

        except Exception as e:
            logger.error(f"Failed to add subscription {sub_id}: {e}")
            raise RuntimeError(e.args[0])

    def remove_strategy_subscriptions(self, subscription_ids: Dict[str, str]) -> bool:
        """Remove all subscriptions for a strategy
        
        Args:
            subscription_ids: Dict containing subscription IDs: {"candle": "sub_1", "userFills": "sub_2"}
            
        Returns:
            True if all subscriptions were removed successfully, False otherwise
        """
        success = True
        for sub_type, sub_id in subscription_ids.items():
            if not self.remove_subscription(sub_id):
                logger.error(f"Failed to remove {sub_type} subscription {sub_id}")
                success = False
            else:
                logger.info(f"Removed {sub_type} subscription {sub_id}")
        
        return success

    def remove_subscription(self, sub_id: str) -> bool:
        """Remove a single subscription"""
        if sub_id not in self.subscriptions:
            logger.warning(f"Subscription {sub_id} not found")
            return False

        subscription = self.subscriptions[sub_id]

        try:
            if subscription.subscription_id is not None:
                # Unsubscribe from the right context
                target_user = subscription.params.get("user")
                ctx = self._contexts.get(target_user) if target_user else None
                if ctx is not None:
                    ctx['info'].unsubscribe(subscription.params, subscription.subscription_id)

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

    def get_ws_ready_any(self) -> bool:
        try:
            return any(getattr(ctx['info'].ws_manager, 'ws_ready', False) for ctx in self._contexts.values())
        except Exception:
            return False
