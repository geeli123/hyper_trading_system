"""
API package for Hyperliquid Trading System

This package contains all API-related modules including FastAPI server,
subscription management, and REST endpoints.
"""

from fastapi import APIRouter

from core.subscription_manager import SubscriptionManager, SubscriptionInfo, SubscriptionStatus
from . import accounts as accounts_router
from . import configs as configs_router
from . import logs as logs_router
from . import strategy_records as strategy_records_router
from . import subscriptions as subscriptions_router
from . import system as system_router

# Aggregate router to be mounted by external apps if desired
router = APIRouter()
router.include_router(system_router.router)
router.include_router(subscriptions_router.router)
router.include_router(configs_router.router)
router.include_router(accounts_router.router)
router.include_router(logs_router.router)
router.include_router(strategy_records_router.router)

__all__ = [
    'SubscriptionManager',
    'SubscriptionInfo',
    'SubscriptionStatus',
    'router'
]
