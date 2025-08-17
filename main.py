import logging
from hyperliquid.info import Info  
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
import example_utils
from hyperliquid.utils import constants
import time   

# Set log level to DEBUG
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def callback(msg):  
    logger.debug("callback")
    logger.debug(f"Received: {msg}")  


address, info, exchange = example_utils.setup(base_url=constants.MAINNET_API_URL, skip_ws=False)

# Subscribe with the callback  
subscription = {"type": "allMids"}

while True:
    result = info.subscribe(subscription, callback)
    logger.debug(f"Subscribe result: {result}")
    logger.debug("subscribed")
    logger.debug(f"Active subscriptions: {info.ws_manager.active_subscriptions}")
    logger.debug(f"WS ready: {info.ws_manager.ws_ready}")
    time.sleep(1)

# user_state = info.user_state("0xB6001dDB4ecf684A226361812476f731CEA96d05")
# logger.debug(user_state)

# Place an order that should rest by setting the price very low
# order_result = exchange.order("ETH", True, 0.2, 1100, {"limit": {"tif": "Gtc"}})
# logger.debug(order_result)

# open_orders = info.open_orders(address)
# for open_order in open_orders:
#     logger.debug(f"cancelling order {open_order}")
#     exchange.cancel(open_order["coin"], open_order["oid"])
