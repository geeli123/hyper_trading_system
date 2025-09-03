import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import accounts as accounts_router
from api import configs as configs_router
from api import logs as logs_router
from api import pages as pages_router
from api import strategy_records as strategy_records_router
from api import subscriptions as subscriptions_router
from api import system as system_router
from api.common import set_subscription_manager
from config.config_manager import ConfigManager
from core import MeanReversionBB
from core.subscription_manager import SubscriptionManager
from database.init_db import init_db
from database.session import Environment
from utils.exception import GlobalExceptionHandler, setup_exception_handlers

# Set log level to DEBUG
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def strategy_factory(exchange, info, address, symbol):
    return MeanReversionBB(exchange, info, address, symbol)


app = FastAPI(title="Hyperliquid Trading System API",
              description="API for managing trading system subscriptions and monitoring", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GlobalExceptionHandler)
setup_exception_handlers(app)

# Mount static files
app.mount("/templates", StaticFiles(directory="templates", html=True), name="templates")

subscription_manager = SubscriptionManager(strategy_factory=strategy_factory,
                                           environment=os.getenv("APP_ENV", Environment.dev))
set_subscription_manager(subscription_manager)

app.include_router(pages_router.router)
app.include_router(system_router.router)
app.include_router(subscriptions_router.router)
app.include_router(configs_router.router)
app.include_router(accounts_router.router)
app.include_router(logs_router.router)
app.include_router(strategy_records_router.router)

logger.info("Trading system initialized successfully (lazy contexts)!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # ensure default configs exist
    ConfigManager.init_default_configs()
    yield


app.router.lifespan_context = lifespan

# Start the API server (this will block and keep the server running)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
