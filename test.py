import logging
import pprint

from hyperliquid.utils import constants

from utils import exchange_utils

# Set log level to DEBUG
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

address, info, exchange = exchange_utils.setup(base_url=constants.TESTNET_API_URL, skip_ws=False, secret_key=None, account_address=None)

pprint.pprint(info.user_state("0xB6001dDB4ecf684A226361812476f731CEA96d05"))

order_result = exchange.order("HYPE", False, 1, 135, {"limit": {"tif": "Gtc"}})
print(order_result)

open_orders = info.open_orders(address)
pprint.pprint(open_orders)
