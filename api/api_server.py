"""
FastAPI Server for Hyperliquid Trading System

Provides REST API endpoints for managing subscriptions and monitoring system status.
"""

import logging
from typing import Dict, Optional, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .subscription_manager import SubscriptionManager

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


# Global variables for dependency injection
subscription_manager: Optional[SubscriptionManager] = None
info = None
strategy = None


def get_subscription_manager() -> SubscriptionManager:
    """Dependency to get subscription manager"""
    if subscription_manager is None:
        raise HTTPException(status_code=500, detail="Subscription manager not initialized")
    return subscription_manager


def get_info():
    """Dependency to get info object"""
    if info is None:
        raise HTTPException(status_code=500, detail="Info object not initialized")
    return info


def get_strategy():
    """Dependency to get strategy object"""
    if strategy is None:
        raise HTTPException(status_code=500, detail="Strategy not initialized")
    return strategy


# Routes are now handled by separate router files

def create_api_server(sub_manager: SubscriptionManager, info_obj, strategy_obj,
                      host: str = "0.0.0.0", port: int = 8000):
    """Create and configure the API server"""
    # Set global variables for dependency injection
    global subscription_manager, info, strategy
    subscription_manager = sub_manager
    info = info_obj
    strategy = strategy_obj

    # Create FastAPI app
    app = FastAPI(
        title="Hyperliquid Trading System API",
        description="API for managing trading system subscriptions and monitoring",
        version="1.0.0"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    from .routers import system, subscriptions
    app.include_router(system.router)
    app.include_router(subscriptions.router)

    return app, host, port
