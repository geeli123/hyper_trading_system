import logging
import pprint

import uvicorn

import example_utils
from api_server import create_api_server
from config import load_config
from mv_bb import MeanReversionBB
from subscription_manager import SubscriptionManager

# Set log level to DEBUG
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def callback(msg):
    logger.debug("callback")
    logger.debug(f"Received: {msg}")


# Set environment: 'mainnet' or 'testnet' (or None for default)
ENVIRONMENT = 'mainnet'
config = load_config(ENVIRONMENT)

# Print config in green color
GREEN = "\033[92m"
RESET = "\033[0m"
logger.info(f"{GREEN}Loaded config for environment '{ENVIRONMENT}':{RESET}")
for k, v in config.items():
    logger.info(f"{GREEN}  {k}: {v}{RESET}")

address, info, exchange = example_utils.setup(skip_ws=False, environment=ENVIRONMENT)

pprint.pprint(info.user_state(config.account_address))

strategy = MeanReversionBB(exchange, info, address, "ETH")

# Create subscription manager (no default subscriptions)
subscription_manager = SubscriptionManager(info, strategy.process_message)

logger.info("Trading system initialized successfully!")

# Create API server
api_app, host, port = create_api_server(subscription_manager, info, strategy)

# Start the API server (this will block and keep the server running)
if __name__ == "__main__":
    uvicorn.run(api_app, host=host, port=port, log_level="info")
