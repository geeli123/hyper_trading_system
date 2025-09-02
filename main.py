import logging
import pprint

import example_utils
from config import load_config
from mv_bb import MeanReversionBB

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

# Subscribe with the callback
subscription1 = { "type": "candle", "coin": "ETH", "interval": "1m" }
subscription2 = { "type": "userFills", "user": address }

result1 = info.subscribe(subscription1, strategy.process_message)
result2 = info.subscribe(subscription2, strategy.process_message)

logger.debug(f"Subscribe result: {result1}")
logger.debug(f"Subscribe result: {result2}")
logger.debug("subscribed")
logger.debug(f"Active subscriptions: {info.ws_manager.active_subscriptions}")
logger.debug(f"WS ready: {info.ws_manager.ws_ready}")
